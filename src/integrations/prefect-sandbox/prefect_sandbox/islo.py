"""Islo backend: hosted microVM sandboxes driven through the Islo REST API.

There is no Python SDK for Islo, and its CLI is a signed-in developer tool that keeps
credentials in the OS keyring — neither of which suits a worker. This backend therefore
talks to the documented REST API (https://docs.islo.dev/openapi.json) with an API key,
so a Prefect deployment needs nothing installed and nothing logged in: a key in a Block
or in `ISLO_API_KEY` is the whole configuration.

The key is exchanged for a short-lived session token, which is the only credential that
ever travels on a request. Neither the key nor the token is passed to a sandboxed
command.
"""

from __future__ import annotations

import asyncio
import base64
import codecs
import json
import math
import os
import time
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, Literal
from urllib.parse import quote

import httpx
from pydantic import Field, PrivateAttr, SecretStr

from prefect_sandbox.base import (
    Sandbox,
    SandboxBackend,
    SandboxCreationError,
    SandboxError,
    SandboxExecutionError,
    SandboxResult,
    SandboxUnavailableError,
    _shielded_cleanup,
    new_sandbox_name,
    validate_exec_request,
)

__all__ = ["IsloSandbox"]

#: Control plane. Regional compute endpoints (`https://<region>.compute.islo.dev`) speak
#: the same API and can be set on the block.
_DEFAULT_API_URL = "https://api.islo.dev"

#: Environment fallbacks, matching the names the Islo CLI itself reads.
_API_KEY_ENV_VAR = "ISLO_API_KEY"
_API_URL_ENV_VAR = "ISLO_API_URL"

#: Reported when the wall clock expired, so the command's own status is unknown.
_UNKNOWN_EXIT_CODE = -1

#: Per-request budget for the small control-plane calls: create, poll, delete.
_CONTROL_TIMEOUT = 60.0

#: A file upload streams a whole payload, so it gets its own, larger budget.
_UPLOAD_TIMEOUT = 300.0

#: Gap between sandbox-status polls while a microVM boots.
_POLL_INTERVAL = 2.0

#: Refresh a session token this long before its own expiry, so a request already in
#: flight cannot land after the token dies.
_TOKEN_SKEW = 60.0

#: Session-token lifetime assumed when the token carries no readable expiry.
_FALLBACK_TOKEN_TTL = 600.0

#: Exit code recorded when the provider's exit event is not an integer. Matches the
#: Islo CLI, which reports an unparsable exit as a generic failure rather than success.
_UNPARSABLE_EXIT_CODE = 1

#: Status a sandbox reaches once it can accept commands.
_READY_STATUS = "running"

#: Statuses a booting sandbox never recovers from, so creation fails immediately
#: instead of polling until `create_timeout`.
_FATAL_STATUSES = frozenset(
    {"failed", "error", "deleted", "stopped", "stopping", "paused", "terminated"}
)

#: Cap on provider error text echoed into an exception message.
_ERROR_DETAIL_CHARS = 2000


class _CappedText:
    """Byte-bounded accumulator for one output stream.

    Bounded in *bytes* rather than characters so the cap means the same thing here as
    in the backends that drain OS pipes, and so `max_output_bytes` is a real memory
    ceiling regardless of what the guest prints.
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._kept = bytearray()
        self.truncated = False

    def append(self, text: str) -> None:
        """Retain as much of `text` as the cap allows, discarding the rest."""
        raw = text.encode()
        if not raw:
            return
        room = max(self._limit - len(self._kept), 0)
        if room:
            self._kept += raw[:room]
        if len(raw) > room:
            self.truncated = True

    def text(self) -> str:
        """Decode what was retained, tolerating a cut mid-character."""
        return self._kept.decode(errors="replace")


def _split_sse_events(buffer: str) -> tuple[list[tuple[str, str]], str]:
    """Pull complete Server-Sent Events out of `buffer`.

    Args:
        buffer: Accumulated stream text, newline-normalized.

    Returns:
        The `(event, data)` pairs that were complete, and the unconsumed remainder.
        Multiple `data:` lines in one event are joined with newlines per the SSE
        specification, which is how the provider encodes multi-line output.
    """
    events: list[tuple[str, str]] = []
    while True:
        boundary = buffer.find("\n\n")
        if boundary < 0:
            return events, buffer
        block, buffer = buffer[:boundary], buffer[boundary + 2 :]
        name: str | None = None
        data: list[str] = []
        for line in block.split("\n"):
            field, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]
            if field == "event":
                name = value.strip()
            elif field == "data":
                data.append(value)
        if name is not None:
            events.append((name, "\n".join(data)))


def _token_expiry(token: str) -> float:
    """Best-effort expiry timestamp for a session JWT.

    The payload is read without verifying the signature — this is not an authorization
    decision, only a hint about when to ask for a new token. Anything unreadable falls
    back to a short lifetime, so a changed token format costs an extra exchange rather
    than a failed request.
    """
    fallback = time.time() + _FALLBACK_TOKEN_TTL
    parts = token.split(".")
    if len(parts) != 3:
        return fallback
    payload = parts[1]
    try:
        claims = json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        )
        return float(claims["exp"]) - _TOKEN_SKEW
    except (ValueError, TypeError, KeyError):
        return fallback


def _json_object(response: httpx.Response) -> dict[str, Any]:
    """Decode a JSON object body, returning `{}` for anything else."""
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _error_detail(response: httpx.Response) -> str:
    """Summarize a failed response for an exception message.

    Prefers the provider's structured `{code, message}` body, which names the actual
    problem — insufficient credits, a suspended tenant, an invalid image — and falls
    back to raw text so an unexpected error shape is still legible.
    """
    body = _json_object(response)
    code, message = body.get("code"), body.get("message")
    if isinstance(message, str) and message:
        detail = f"{code}: {message}" if isinstance(code, str) and code else message
    else:
        detail = (response.text or "").strip() or "<no body>"
    return f"HTTP {response.status_code} {detail[:_ERROR_DETAIL_CHARS]}"


def _is_absent(response: httpx.Response) -> bool:
    """True when a response says the sandbox does not exist."""
    return (
        response.status_code == 404
        or _json_object(response).get("code") == "SANDBOX_NOT_FOUND"
    )


class IsloSandbox(SandboxBackend):
    """Run commands in a hosted Islo microVM sandbox.

    Each sandbox is a microVM with its own kernel, provisioned on Islo's infrastructure
    rather than on the worker's host, so nothing needs to be installed next to Prefect
    and the worker never runs the untrusted code itself. `acreate` maps to
    `POST /sandboxes`, `aexec` to `POST /sandboxes/{name}/exec/stream`, `awrite_file`
    to `POST /sandboxes/{name}/files`, and `adestroy` to `DELETE /sandboxes/{name}`.
    Sandboxes are addressed by their generated name, which is also `Sandbox.id`.

    Authentication is an API key (`islo api-key create <name> --show`), read from
    `api_key` or from `ISLO_API_KEY`. The key never leaves the worker: it is exchanged
    for a short-lived session token, and only that token is sent on subsequent calls.
    Neither reaches a sandboxed command.

    Prefect injects none of its context into the sandbox — no `PREFECT_API_KEY`, no
    `PREFECT_API_URL`, no worker environment, no flow-run parameters. A command sees
    only what the image provides plus the `env` passed to that specific `aexec` call.

    Outbound network access is decided at creation: `egress="deny"` requests a sandbox
    with the internet switched off, and `gateway_profile` selects a named Islo gateway
    profile when some egress is required. Unlike a policy overlay applied after the
    fact, this is part of the provisioning request, so there is no window in which the
    sandbox exists with the wrong egress; creation fails if the provider reports
    internet access after it was denied.

    There is no backend-level connection pool, so `aclose` stays the base no-op: each
    call opens its own HTTP client, which is what keeps one saved block usable from
    both Prefect's sync and async interfaces.

    Attributes:
        image: Container image used as the sandbox template.
        vcpus: Virtual CPUs to allocate.
        memory_mb: Memory to allocate, in MiB.
        disk_gb: Disk to allocate, in GiB.
        workdir: Default working directory for commands.
        user: Guest user to run commands as.
        api_key: Islo API key. Falls back to `ISLO_API_KEY`.
        api_url: API base URL. Falls back to `ISLO_API_URL`, then the public endpoint.
        create_timeout: Seconds allowed for provisioning.
        egress: Whether to provision the sandbox with the internet switched off.
        gateway_profile: Named Islo gateway profile governing allowed egress.
        delete_after: Provider-side reaper for sandboxes teardown never reached.
        max_output_bytes: Per-stream cap on captured output.

    Examples:
        Load a configured block:
        ```python
        from prefect_sandbox import IsloSandbox

        islo_sandbox = IsloSandbox.load("BLOCK_NAME")
        ```

        Run untrusted code in a throwaway microVM with no network access:
        ```python
        from prefect import flow
        from prefect_sandbox import IsloSandbox

        @flow
        async def run_generated_code(source: str) -> str:
            backend = IsloSandbox(egress="deny")
            async with backend.asession() as sandbox:
                await backend.awrite_file(sandbox, "/tmp/main.py", source)
                result = await backend.aexec(
                    sandbox, ["python3", "/tmp/main.py"], timeout=60
                )
            return result.stdout
        ```
    """

    _block_type_name = "Islo Sandbox"
    _logo_url = "https://avatars.githubusercontent.com/islo-labs"
    _documentation_url = "https://docs.prefect.io/integrations/prefect-sandbox"

    backend_name: ClassVar[str] = "islo"

    image: str = Field(
        default="docker.io/library/islo-runner:latest",
        min_length=1,
        title="Template Image",
        description="Container image used as the sandbox template.",
    )
    vcpus: int = Field(
        default=2,
        gt=0,
        title="vCPUs",
        description="Virtual CPUs to allocate to the sandbox.",
    )
    memory_mb: int = Field(
        default=2048,
        gt=0,
        title="Memory (MiB)",
        description="Memory to allocate to the sandbox, in MiB.",
    )
    disk_gb: int = Field(
        default=10,
        gt=0,
        title="Disk (GiB)",
        description="Disk to allocate to the sandbox, in GiB.",
    )
    workdir: str | None = Field(
        default=None,
        title="Working Directory",
        description=(
            "Default working directory for commands. The `working_dir` argument to "
            "`aexec` overrides it for a single command."
        ),
    )
    user: str | None = Field(
        default=None,
        description=(
            "Guest user to run commands as. Leave unset to use the image's default "
            "user."
        ),
    )
    api_key: SecretStr | None = Field(
        default=None,
        title="API Key",
        description=(
            "Islo API key, created with `islo api-key create <name> --show`. Leave "
            "unset to read the `ISLO_API_KEY` environment variable instead."
        ),
    )
    api_url: str | None = Field(
        default=None,
        title="API URL",
        description=(
            "Base URL of the Islo API. Leave unset to read the `ISLO_API_URL` "
            f"environment variable, then fall back to `{_DEFAULT_API_URL}`. Set a "
            "regional compute endpoint, such as `https://ca.compute.islo.dev`, to "
            "pin sandboxes to one region."
        ),
    )
    create_timeout: float = Field(
        default=600.0,
        gt=0,
        description=(
            "Seconds allowed for provisioning. A cold image pull plus the first "
            "microVM boot can take minutes."
        ),
    )
    egress: Literal["inherit", "deny"] = Field(
        default="inherit",
        title="Network Egress",
        description=(
            "Set to `deny` to provision the sandbox with outbound internet access "
            "switched off, and fail creation if the provider reports otherwise. "
            "`inherit` accepts the tenant default."
        ),
    )
    gateway_profile: str | None = Field(
        default=None,
        title="Gateway Profile",
        description=(
            "Name of an Islo gateway profile governing which destinations the sandbox "
            'may reach. Use this instead of `egress="deny"` when a command needs a '
            "specific allowlist rather than no network at all."
        ),
    )
    delete_after: int | None = Field(
        default=3600,
        gt=0,
        title="Delete After (seconds)",
        description=(
            "Provider-side lifetime after which Islo deletes the sandbox even if "
            "Prefect never gets to. This is the backstop for a worker that is killed "
            "outright — set it above the longest command a sandbox will serve, or to "
            "null to rely solely on Prefect-side teardown."
        ),
    )

    #: Cached session token and the moment it should be replaced. Deliberately not
    #: guarded by a lock: two concurrent flow runs racing to refresh perform one extra
    #: exchange and both end up with a valid token, whereas an `asyncio.Lock` created
    #: on a Block would bind this instance to whichever event loop touched it first.
    _session_token: str | None = PrivateAttr(default=None)
    _session_token_expires_at: float = PrivateAttr(default=0.0)

    def _resolved_api_url(self) -> str:
        """Return the API base URL, honouring the block, then the environment."""
        url = self.api_url or os.environ.get(_API_URL_ENV_VAR) or _DEFAULT_API_URL
        return url.rstrip("/")

    def _resolved_api_key(self) -> str:
        """Return the API key.

        Raises:
            SandboxUnavailableError: If no key is configured anywhere, which is the
                "this backend is not usable here" case rather than a command failure.
        """
        secret = self.api_key.get_secret_value() if self.api_key else ""
        key = (secret or os.environ.get(_API_KEY_ENV_VAR, "")).strip()
        if not key:
            raise SandboxUnavailableError(
                "No Islo API key is configured. Set the block's api_key or the "
                f"{_API_KEY_ENV_VAR} environment variable; create one with "
                "'islo api-key create prefect --show'."
            )
        return key

    def _new_client(
        self, *, token: str | None, timeout: float | httpx.Timeout
    ) -> httpx.AsyncClient:
        """Build a client for one call.

        A fresh client per call is deliberate. A saved Block outlives any single event
        loop — Prefect's sync interface runs coroutines on a loop of its own — and an
        `httpx.AsyncClient` binds its connection pool to the loop that created it, so a
        cached client would fail the second time a block was used from the other
        interface. The handshake is paid a handful of times per sandbox, not per byte.
        """
        return httpx.AsyncClient(
            base_url=self._resolved_api_url(),
            timeout=timeout,
            headers={"Authorization": f"Bearer {token}"} if token else {},
        )

    async def _atoken(self, *, force_refresh: bool = False) -> str:
        """Return a session token, exchanging the API key when necessary.

        The raw API key is not accepted as a bearer credential; it has to be traded for
        a session token first, which is also what keeps the long-lived secret off every
        subsequent request.

        Raises:
            SandboxUnavailableError: If no key is configured, the key was rejected, or
                the API could not be reached at all.
        """
        cached = self._session_token
        if (
            not force_refresh
            and cached
            and time.time() < self._session_token_expires_at
        ):
            return cached

        api_key = self._resolved_api_key()
        async with self._new_client(token=None, timeout=_CONTROL_TIMEOUT) as client:
            try:
                response = await client.post(
                    "/auth/token", json={"access_key": api_key}
                )
            except httpx.HTTPError as exc:
                raise SandboxUnavailableError(
                    f"Could not reach the Islo API at {self._resolved_api_url()}: {exc}"
                ) from exc

        if response.status_code in (401, 403):
            raise SandboxUnavailableError(
                f"Islo rejected the API key: {_error_detail(response)}. Create a new "
                "key with 'islo api-key create prefect --show'."
            )
        if response.status_code >= 400:
            raise SandboxUnavailableError(
                f"Islo token exchange failed: {_error_detail(response)}"
            )

        token = _json_object(response).get("session_token")
        if not isinstance(token, str) or not token:
            raise SandboxUnavailableError(
                "Islo token exchange returned no session token."
            )
        self._session_token = token
        self._session_token_expires_at = _token_expiry(token)
        return token

    async def _arequest(
        self,
        method: str,
        path: str,
        *,
        timeout: float = _CONTROL_TIMEOUT,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make one authenticated API call, retrying once with a fresh token on 401.

        A non-2xx response is returned rather than raised: what a given status means
        depends on the caller — a 404 is a failure for `aexec` and a success for
        `adestroy`.

        Raises:
            SandboxError: If the request could not be completed at all.
            SandboxUnavailableError: If no usable credential could be obtained.
        """
        for attempt in (0, 1):
            token = await self._atoken(force_refresh=attempt == 1)
            async with self._new_client(token=token, timeout=timeout) as client:
                try:
                    response = await client.request(method, path, **kwargs)
                except httpx.HTTPError as exc:
                    raise SandboxError(
                        f"Islo API request {method} {path} failed: {exc}"
                    ) from exc
            # A 401 on the first attempt means the cached token expired mid-flight;
            # a 401 on the second is a genuinely rejected credential, and the caller
            # decides what that means for the operation it was performing.
            if response.status_code != 401 or attempt == 1:
                return response
        raise SandboxError(  # pragma: no cover - the loop always returns
            f"Islo API request {method} {path} exhausted its attempts."
        )

    async def _adelete(self, name: str) -> None:
        """Delete one sandbox by name.

        Idempotent by design: an already-absent sandbox is a success, and anything else
        is raised, because untrusted code may still be running inside it.

        Raises:
            SandboxError: If deletion was neither confirmed nor already true.
        """
        response = await self._arequest("DELETE", f"/sandboxes/{quote(name, safe='')}")
        if response.status_code in (200, 202, 204) or _is_absent(response):
            return
        raise SandboxError(
            f"Failed to delete Islo sandbox {name!r}; it may still be running: "
            f"{_error_detail(response)}"
        )

    async def _aawait_ready(self, name: str, status: str) -> None:
        """Poll `name` until it can accept commands.

        Args:
            name: Generated sandbox name.
            status: Status reported by the creation response, so a sandbox that is
                already running costs no extra request.

        Raises:
            SandboxCreationError: If the sandbox failed, vanished, or was still not
                ready within `create_timeout`.
        """
        deadline = time.monotonic() + self.create_timeout
        while True:
            normalized = status.strip().lower()
            if normalized == _READY_STATUS:
                return
            if normalized in _FATAL_STATUSES:
                raise SandboxCreationError(
                    f"Islo sandbox {name!r} reported status {status!r} while starting."
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SandboxCreationError(
                    f"Islo sandbox {name!r} was still {status or 'unknown'!r} after "
                    f"{self.create_timeout:g}s. A cold image pull can exceed the "
                    "default; raise create_timeout."
                )
            await asyncio.sleep(min(_POLL_INTERVAL, remaining))
            response = await self._arequest("GET", f"/sandboxes/{quote(name, safe='')}")
            if response.status_code >= 400:
                raise SandboxCreationError(
                    f"Could not read the status of Islo sandbox {name!r}: "
                    f"{_error_detail(response)}"
                )
            body = _json_object(response)
            self._verify_egress(name, body)
            status = str(body.get("status", ""))

    def _verify_egress(self, name: str, body: Mapping[str, Any]) -> None:
        """Fail creation if the provider reports egress the caller asked to block.

        Only an explicit contradiction counts. The creation request is the authority on
        egress — it is not an overlay applied afterwards — so silence in the response is
        not evidence of a problem, and guessing at it would fail creation for sandboxes
        that are configured correctly.

        Raises:
            SandboxCreationError: If the sandbox reports internet access after
                `egress="deny"` was requested.
        """
        if self.egress == "deny" and body.get("internet_enabled") is True:
            raise SandboxCreationError(
                f"Islo sandbox {name!r} reports internet access enabled after egress "
                "was denied. Check whether tenant policy overrides per-sandbox egress."
            )

    async def acreate(self) -> Sandbox:
        """Provision one microVM and wait until it can accept commands.

        The generated name is chosen before the request is sent, so every failure path —
        including a response that never arrives — can still delete by name. Nothing
        about the sandbox is stored on the block; the provider's own id travels in
        `Sandbox.metadata` purely so an operator can find the sandbox in the Islo
        console.

        Returns:
            A handle whose `id` is the sandbox's Islo name.

        Raises:
            SandboxUnavailableError: If no API key is configured or Islo is unreachable.
            SandboxCreationError: If provisioning failed or timed out.
        """
        name = new_sandbox_name()
        payload: dict[str, Any] = {
            "name": name,
            "image": self.image,
            "vcpus": self.vcpus,
            "memory_mb": self.memory_mb,
            "disk_gb": self.disk_gb,
            "request_id": name,
        }
        if self.workdir:
            payload["workdir"] = self.workdir
        if self.egress == "deny":
            payload["internet_enabled"] = False
        if self.gateway_profile:
            payload["gateway_profile"] = self.gateway_profile
        if self.delete_after is not None:
            payload["lifecycle"] = {"delete_after": self.delete_after}

        # Resolve a credential *before* the guarded block. A missing or rejected key is
        # the one failure that provably cannot have provisioned anything, so failing
        # fast here is what lets every failure below be cleaned up unconditionally —
        # including a later token refresh dying mid-poll, which would otherwise look
        # like "no credential, so no sandbox" long after a microVM had been created.
        await self._atoken()

        body: dict[str, Any] = {}
        try:
            response = await self._arequest(
                "POST", "/sandboxes", json=payload, timeout=_CONTROL_TIMEOUT
            )
            if response.status_code not in (200, 201):
                raise SandboxCreationError(
                    f"Islo refused to create sandbox {name!r}: "
                    f"{_error_detail(response)}"
                )
            body.update(_json_object(response))
            self._verify_egress(name, body)
            await self._aawait_ready(name, str(body.get("status", "")))
        except BaseException as create_error:
            # Nothing may survive a failed create. A rejected request, a lost response,
            # a sandbox that never boots and a cancellation can all leave a live microVM
            # behind, and only the name is needed to remove it. Shielded, because a
            # cancellation arriving here would otherwise abort at the first await and
            # abandon the sandbox.
            try:
                await _shielded_cleanup(self._adelete(name))
            except asyncio.CancelledError:
                raise
            except BaseException as cleanup_error:
                raise SandboxCreationError(
                    f"Sandbox creation failed and cleanup of {name!r} could not be "
                    f"confirmed; it may still be running. Original failure: "
                    f"{create_error}"
                ) from cleanup_error
            raise

        metadata = {"api_url": self._resolved_api_url()}
        sandbox_id = body.get("id")
        if isinstance(sandbox_id, str) and sandbox_id:
            metadata["sandbox_id"] = sandbox_id
        return Sandbox(id=name, backend=self.backend_name, metadata=metadata)

    async def aexec(
        self,
        sandbox: Sandbox,
        command: Sequence[str],
        *,
        timeout: float,
        env: Mapping[str, str] | None = None,
        working_dir: str | None = None,
    ) -> SandboxResult:
        """Run `command` inside `sandbox` and return its outcome.

        The command is sent as an argv list, so no shell is involved and the caller
        never has to quote anything. Output arrives as Server-Sent Events and is capped
        as it streams. The provider treats its own `timeout_secs` as a hint, so the
        wall clock is enforced here; when it expires the sandbox is destroyed, because
        closing the stream would not stop the guest process.

        Args:
            sandbox: Handle returned by `acreate`.
            command: Argv to execute.
            timeout: Seconds the command may run.
            env: Environment variables for this command only.
            working_dir: Directory inside the sandbox to run in, overriding `workdir`.

        Returns:
            A `SandboxResult`; a nonzero exit code is data, not an error.

        Raises:
            ValueError: If `command` is empty, `timeout` is not a positive finite
                number, or `env` cannot be expressed as POSIX environment variables.
            SandboxExecutionError: If the execution stream itself failed.
        """
        validate_exec_request(command, timeout, env)

        payload: dict[str, Any] = {
            "command": list(command),
            # Sent for the provider's own bookkeeping. It is documented as a hint, so
            # nothing here relies on it firing.
            "timeout_secs": max(1, math.ceil(timeout)),
        }
        if env:
            payload["env"] = dict(env)
        directory = working_dir or self.workdir
        if directory:
            payload["workdir"] = directory
        if self.user:
            payload["user"] = self.user

        stdout = _CappedText(self.max_output_bytes)
        stderr = _CappedText(self.max_output_bytes)
        try:
            exit_code = await asyncio.wait_for(
                self._astream_exec(sandbox.id, payload, stdout, stderr), timeout
            )
        except asyncio.TimeoutError:
            # Abandoning the stream does not prove the guest process stopped. Taking the
            # sandbox is the only honest way to enforce the requested wall clock.
            await _shielded_cleanup(self.adestroy(sandbox))
            notice = (
                f"Command did not return within {timeout:g}s; the sandbox was "
                "destroyed."
            )
            captured = stderr.text()
            return SandboxResult(
                exit_code=_UNKNOWN_EXIT_CODE,
                # Whatever the command managed to print before the deadline is the most
                # useful thing a caller can have here, so it survives the timeout.
                stdout=stdout.text(),
                stderr=f"{captured}\n{notice}" if captured else notice,
                timed_out=True,
                truncated=stdout.truncated or stderr.truncated,
                sandbox_terminated=True,
            )
        return SandboxResult(
            exit_code=exit_code,
            stdout=stdout.text(),
            stderr=stderr.text(),
            truncated=stdout.truncated or stderr.truncated,
        )

    async def _astream_exec(
        self,
        name: str,
        payload: Mapping[str, Any],
        stdout: _CappedText,
        stderr: _CappedText,
    ) -> int:
        """Stream one command's output into `stdout`/`stderr` and return its exit code.

        Retries once on a 401, which can only be seen before any event is delivered, so
        the buffers cannot be written twice.

        Raises:
            SandboxExecutionError: If the stream could not be opened, broke before the
                command reported an exit, or the sandbox is gone.
        """
        path = f"/sandboxes/{quote(name, safe='')}/exec/stream"
        for attempt in (0, 1):
            token = await self._atoken(force_refresh=attempt == 1)
            # No read timeout: a command may legitimately print nothing for a long
            # time, and the caller's wall clock is the only deadline that applies.
            client = self._new_client(
                token=token, timeout=httpx.Timeout(_CONTROL_TIMEOUT, read=None)
            )
            async with client:
                try:
                    async with client.stream("POST", path, json=payload) as response:
                        if response.status_code == 401 and attempt == 0:
                            await response.aread()
                            continue
                        if response.status_code >= 400:
                            await response.aread()
                            raise SandboxExecutionError(
                                f"Islo refused to run the command in {name!r}: "
                                f"{_error_detail(response)}"
                            )
                        return await self._aconsume_events(
                            name, response, stdout, stderr
                        )
                except httpx.HTTPError as exc:
                    raise SandboxExecutionError(
                        f"Islo execution stream for {name!r} failed: {exc}. The "
                        "command may still be running in the sandbox."
                    ) from exc
        raise SandboxExecutionError(
            f"Islo rejected the session token twice while running a command in "
            f"{name!r}."
        )

    async def _aconsume_events(
        self,
        name: str,
        response: httpx.Response,
        stdout: _CappedText,
        stderr: _CappedText,
    ) -> int:
        """Decode the SSE body of `response` and return the command's exit code.

        Returns as soon as the exit event arrives rather than draining to EOF: the exit
        code is the last thing worth reading, and nothing in the API promises the server
        closes the body promptly afterwards. Waiting for EOF would let a keep-alive or a
        buffering proxy turn a command that already succeeded into a timeout — and, since
        a timeout destroys the sandbox, into a destroyed one.

        Raises:
            SandboxExecutionError: If the stream ended without an exit event.
        """
        # Incremental decoding, because a UTF-8 character can straddle two chunks and
        # decoding each chunk on its own would corrupt it.
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        buffer = ""
        # A CR held back from the end of a chunk. Normalizing per chunk would leave a
        # `\r\n` split across two chunks un-normalized, and a boundary landing inside an
        # event-terminating `\r\n\r\n` would then merge two events into one — losing the
        # exit event on a stream that was perfectly well formed on the wire.
        carried_cr = ""
        exit_code: int | None = None
        try:
            async for chunk in response.aiter_bytes():
                text = carried_cr + decoder.decode(chunk)
                carried_cr = ""
                if text.endswith("\r"):
                    text, carried_cr = text[:-1], "\r"
                buffer += text.replace("\r\n", "\n")
                events, buffer = _split_sse_events(buffer)
                for event, data in events:
                    if event == "stdout":
                        stdout.append(data)
                    elif event == "stderr":
                        stderr.append(data)
                    elif event == "error":
                        stderr.append(f"{data}\n")
                    elif event == "exit":
                        try:
                            exit_code = int(data.strip())
                        except ValueError:
                            exit_code = _UNPARSABLE_EXIT_CODE
                if exit_code is not None:
                    break
        except httpx.HTTPError:
            # A connection torn down after the exit event is a completed command, not a
            # failure; the provider closes the stream at the same moment.
            if exit_code is None:
                raise
        if exit_code is None:
            raise SandboxExecutionError(
                f"Islo execution stream for {name!r} ended without an exit event. The "
                "command may still be running in the sandbox."
            )
        return exit_code

    async def adestroy(self, sandbox: Sandbox) -> None:
        """Delete `sandbox`. Idempotent.

        Raises:
            SandboxError: If deletion could not be confirmed, since untrusted code may
                still be running.
        """
        await self._adelete(sandbox.id)

    async def awrite_file(self, sandbox: Sandbox, path: str, content: str) -> None:
        """Write `content` to `path` inside `sandbox` using Islo's file API.

        Overrides the base implementation, which smuggles the payload through the
        command line and is therefore capped at a few hundred kilobytes. This uploads
        the bytes directly, so size is bounded only by the sandbox's disk.

        Args:
            sandbox: Handle returned by `acreate`.
            path: Absolute destination path inside the sandbox.
            content: Text to write.

        Raises:
            SandboxError: If the destination directory could not be created or the
                upload failed.
        """
        directory = path.rsplit("/", 1)[0] if "/" in path else ""
        if directory:
            # The upload endpoint writes one file; it does not create missing parents.
            result = await self.aexec(sandbox, ["mkdir", "-p", directory], timeout=60)
            if not result.ok:
                raise SandboxError(
                    f"Could not create {directory!r} in {sandbox}: "
                    f"exit {result.exit_code} {result.stderr.strip()[:500]}"
                )

        filename = path.rsplit("/", 1)[-1] or "file"
        response = await self._arequest(
            "POST",
            f"/sandboxes/{quote(sandbox.id, safe='')}/files",
            params={"path": path},
            files={"file": (filename, content.encode(), "application/octet-stream")},
            timeout=_UPLOAD_TIMEOUT,
        )
        if response.status_code not in (200, 201, 204):
            raise SandboxError(
                f"Failed to write {path!r} into {sandbox}: {_error_detail(response)}"
            )
