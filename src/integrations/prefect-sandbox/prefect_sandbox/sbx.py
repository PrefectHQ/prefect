"""Docker Sandboxes (`sbx`) backend: local microVMs driven through the `sbx` CLI.

There is no Python SDK for Docker Sandboxes, so this backend shells out to the CLI
with `asyncio.create_subprocess_exec`. Every invocation is a fresh, short-lived child
process, which is what lets one `SbxSandbox` block instance serve concurrent flow runs
without holding per-sandbox state.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import shutil
import signal
import stat
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field

from prefect.settings import get_current_settings
from prefect_sandbox.base import (
    Sandbox,
    SandboxBackend,
    SandboxCreationError,
    SandboxError,
    SandboxResult,
    SandboxUnavailableError,
    _shielded_cleanup,
    new_sandbox_name,
    validate_exec_request,
)

__all__ = ["SbxSandbox"]

#: Reported when the outer wall clock expired, so the command's own status is unknown.
_UNKNOWN_EXIT_CODE = -1

#: Wall clock for the small bookkeeping subcommands (`rm`, `cp`, `policy deny`).
_CLI_TIMEOUT = 120.0

#: Cap on output retained from those bookkeeping subcommands: enough to surface an
#: error message, small enough that a chatty CLI cannot grow the worker.
_CLI_OUTPUT_BYTES = 16 * 1024

#: Larger bounded cap for structured inventory and policy responses.
_CLI_JSON_BYTES = 1024 * 1024

#: Pipe read size. Large enough to keep syscall overhead off a chatty command.
_READ_CHUNK = 64 * 1024

#: Prefix for host directories created and owned by this backend.
_WORKSPACE_PREFIX = "prefect-sandbox-ws-"

#: Metadata key carrying an HMAC over the sandbox name and host workspace.
_HANDLE_SIGNATURE_KEY = "handle_signature"

#: Persistent host-private signing key. A sandbox handle is meaningful only on the
#: host whose `sbx` daemon owns it, so every backend instance on that host shares this
#: key while no caller-supplied handle or guest-mounted workspace can read it.
_HANDLE_KEY_BYTES = 32
_HANDLE_KEY_DIR = "prefect-sandbox"
_HANDLE_KEY_FILE = "sbx-handle.key"


async def _adrain_capped(
    stream: asyncio.StreamReader | None, limit: int
) -> tuple[bytes, bool]:
    """Read `stream` to EOF, retaining at most `limit` bytes.

    Reading continues after the cap is reached and the excess is thrown away. Stopping
    early would fill the OS pipe buffer and block the child on its next write forever,
    turning a noisy command into a hang.

    Args:
        stream: Pipe to drain, or None if the child was not given one.
        limit: Maximum bytes to retain.

    Returns:
        The retained bytes and whether anything was discarded.
    """
    if stream is None:
        return b"", False
    kept = bytearray()
    truncated = False
    while True:
        chunk = await stream.read(_READ_CHUNK)
        if not chunk:
            return bytes(kept), truncated
        room = limit - len(kept)
        if room > 0:
            kept += chunk[:room]
        if len(chunk) > room:
            truncated = True


def _kill_process_tree(process: asyncio.subprocess.Process) -> None:
    """Kill `process` and, on POSIX, everything it spawned.

    The child is started as a session leader, so its pid doubles as a process-group id
    and one `killpg` reaches the CLI's own descendants. Without that, killing `sbx`
    can leave its daemon-facing child behind.
    """
    if os.name == "posix":
        with suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(process.pid, signal.SIGKILL)
    with suppress(ProcessLookupError):
        process.kill()


def _write_host_temp_file(content: str) -> str:
    """Write `content` to a new host temp file and return its path.

    The file outlives this call because `sbx cp` reads it from a separate process, so
    the caller owns deleting it — but only once it has been given the path. A write that
    dies partway, which for a large payload most likely means the disk filled up, has to
    clean up after itself here; leaving a partial file behind would make the very
    condition that caused the failure worse.
    """
    fd, path = tempfile.mkstemp(prefix="prefect-sandbox-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content.encode())
    except BaseException:
        _remove_host_temp_file(path)
        raise
    return path


def _remove_host_temp_file(path: str) -> None:
    """Delete a staged host file, suppressing only an already-absent path."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise SandboxError(
            f"Could not remove staged host file {path!r}: {exc}"
        ) from exc


async def _astage_host_temp_file(content: str) -> str:
    """Finish staging before delivering cancellation, deleting any staged file."""
    staging = asyncio.create_task(asyncio.to_thread(_write_host_temp_file, content))
    cancelled = False
    while not staging.done():
        try:
            await asyncio.shield(staging)
        except asyncio.CancelledError:
            cancelled = True
    host_path = staging.result()
    if cancelled:
        await _shielded_cleanup(asyncio.to_thread(_remove_host_temp_file, host_path))
        raise asyncio.CancelledError
    return host_path


def _validated_workspace_path(workspace: str) -> Path:
    """Return an owned workspace path or reject unsafe recursive deletion."""
    candidate = Path(workspace)
    temp_root = Path(tempfile.gettempdir()).resolve()
    resolved = candidate.resolve(strict=False)
    if (
        not candidate.is_absolute()
        or resolved.parent != temp_root
        or not resolved.name.startswith(_WORKSPACE_PREFIX)
    ):
        raise SandboxError(
            f"Refusing to remove unowned sandbox workspace {workspace!r}."
        )
    return resolved


def _handle_key_path() -> Path:
    """Return the host-private key path without touching the filesystem."""
    return Path(get_current_settings().home) / _HANDLE_KEY_DIR / _HANDLE_KEY_FILE


def _read_handle_key(path: Path) -> bytes:
    """Read and validate one host-private signing key without following a symlink."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise SandboxUnavailableError(
                f"Sandbox handle key {str(path)!r} is not a regular file."
            )
        if os.name == "posix" and info.st_mode & 0o077:
            raise SandboxUnavailableError(
                f"Sandbox handle key {str(path)!r} must not be accessible by "
                "group or other users."
            )
        with os.fdopen(fd, "rb", closefd=False) as handle:
            key = handle.read(_HANDLE_KEY_BYTES + 1)
    finally:
        os.close(fd)
    if len(key) != _HANDLE_KEY_BYTES:
        raise SandboxUnavailableError(
            f"Sandbox handle key {str(path)!r} has an invalid length."
        )
    return key


@lru_cache(maxsize=128)
def _sync_handle_key_directory(directory: Path) -> None:
    """Make the handle-key directory durable once in this host process."""
    if os.name != "posix":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        fd = os.open(directory, flags)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise SandboxUnavailableError(
            f"Could not sync sandbox handle key directory {str(directory)!r}: {exc}"
        ) from exc


def _load_or_create_handle_key() -> bytes:
    """Load the host signing key, publishing a complete 0600 file atomically."""
    path = _handle_key_path()
    key_directory_existed = path.parent.is_dir()
    try:
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    except OSError as exc:
        raise SandboxUnavailableError(
            f"Could not prepare sandbox handle key directory {str(path.parent)!r}: "
            f"{exc}"
        ) from exc
    if not key_directory_existed:
        _sync_handle_key_directory.cache_clear()
        _sync_handle_key_directory(path.parent.parent)

    while True:
        try:
            key = _read_handle_key(path)
            _sync_handle_key_directory(path.parent)
            return key
        except FileNotFoundError:
            key = secrets.token_bytes(_HANDLE_KEY_BYTES)
            staging_path = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            try:
                fd = os.open(staging_path, flags, 0o600)
            except OSError as exc:
                raise SandboxUnavailableError(
                    f"Could not stage sandbox handle key {str(path)!r}: {exc}"
                ) from exc
            try:
                try:
                    try:
                        with os.fdopen(fd, "wb", closefd=False) as handle:
                            handle.write(key)
                            handle.flush()
                            os.fsync(fd)
                    except OSError as exc:
                        raise SandboxUnavailableError(
                            f"Could not write sandbox handle key {str(path)!r}: {exc}"
                        ) from exc
                finally:
                    os.close(fd)
                try:
                    # A hard link publishes the already-complete inode without
                    # replacing a key another process may have won the race to
                    # install.
                    os.link(staging_path, path)
                except FileExistsError:
                    _sync_handle_key_directory.cache_clear()
                    _sync_handle_key_directory(path.parent)
                    continue
                except OSError as exc:
                    raise SandboxUnavailableError(
                        f"Could not install sandbox handle key {str(path)!r}: {exc}"
                    ) from exc
                _sync_handle_key_directory.cache_clear()
                _sync_handle_key_directory(path.parent)
                return key
            finally:
                try:
                    staging_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    raise SandboxUnavailableError(
                        "Could not remove staged sandbox handle key "
                        f"{str(staging_path)!r}: {exc}"
                    ) from exc
        except OSError as exc:
            raise SandboxUnavailableError(
                f"Could not read sandbox handle key {str(path)!r}: {exc}"
            ) from exc


def _handle_signature(name: str, workspace: str, key: bytes) -> str:
    """Bind one sandbox name and workspace to the host-private key."""
    message = f"{name}\0{workspace}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _authenticated_workspace(sandbox: Sandbox) -> str:
    """Authenticate `sandbox.id` and its workspace before targeting either."""
    workspace = sandbox.metadata.get("workspace")
    signature = sandbox.metadata.get(_HANDLE_SIGNATURE_KEY)
    if (
        not isinstance(workspace, str)
        or not isinstance(signature, str)
        or not signature
    ):
        raise SandboxError(
            "Docker Sandbox handle metadata is not authenticated; recreate the "
            "handle with SbxSandbox.acreate()."
        )
    canonical_workspace = str(_validated_workspace_path(workspace))
    expected = _handle_signature(
        sandbox.id, canonical_workspace, _load_or_create_handle_key()
    )
    if not hmac.compare_digest(signature, expected):
        raise SandboxError(
            "Docker Sandbox handle metadata failed authentication; refusing to "
            "execute, copy, or delete through it."
        )
    return canonical_workspace


def _strip_autostart_notice(stderr: str, name: str) -> str:
    """Remove `sbx exec`'s sandbox auto-start notice from captured stderr.

    `sbx exec` silently starts a stopped sandbox and announces it on **stderr**, so
    without this every command run against an idle sandbox would report a line of CLI
    chatter as if the sandboxed program had written it.
    """
    notice = f"Sandbox {name} started successfully"
    if notice not in stderr:
        return stderr
    return "".join(
        line for line in stderr.splitlines(keepends=True) if line.strip() != notice
    )


class SbxSandbox(SandboxBackend):
    """Run commands in a Docker Sandboxes (`sbx`) microVM on the local host.

    Each sandbox is a microVM with its own kernel, so code you did not author is
    isolated far more strongly than by a shared-kernel container. `acreate` maps to
    `sbx create`, `aexec` to `sbx exec`, and `adestroy` to `sbx rm -f`; sandboxes are
    addressed by their generated `--name`, which is also `Sandbox.id`.

    Prefect injects none of its context into the sandbox — no `PREFECT_API_KEY`, no
    `PREFECT_API_URL`, no worker environment, no flow-run parameters. The only
    environment a command sees is what the template image bakes in, whatever the `sbx`
    runtime itself adds (proxy variables and `SBX_CRED_*`/`*_API_KEY` placeholders it
    manages on the sandbox's behalf, governed by `sbx secret` on the host), and the
    `env` passed to that specific `aexec` call.

    Requirements, all host-level and none of them configured by Prefect:

    - The `sbx` binary on PATH and a signed-in host (`sbx login`). Docker Desktop
      is not required. Follow Docker's platform prerequisites; Ubuntu hosts need KVM.
    - A one-time `sbx policy init <allow-all|balanced|deny-all>` on the host.
    Outbound network egress is governed by the host `sbx policy`, which is a
    deployment-level control: run `sbx policy init deny-all` for a no-egress default.
    Setting `egress="deny"` additionally layers a per-sandbox deny-all rule over
    whatever the host allows, since deny rules beat allow rules in `sbx`. The backend
    verifies that an active deny-all rule applies and fails creation if organization
    governance made the local rule inactive.

    Attributes:
        image: Container image used as the sandbox template.
        memory: Memory limit for the sandbox.
        cpus: Number of CPUs to allocate.
        sbx_path: Path to the `sbx` binary.
        create_timeout: Seconds allowed for provisioning.
        egress: Whether to layer a per-sandbox deny-all network rule.
        max_output_bytes: Per-stream cap on captured output.

    Examples:
        Load a configured block:
        ```python
        from prefect_sandbox import SbxSandbox

        sbx_sandbox = SbxSandbox.load("BLOCK_NAME")
        ```

        Run untrusted code in a throwaway microVM with no network access:
        ```python
        from prefect import flow
        from prefect_sandbox import SbxSandbox

        @flow
        async def run_generated_code(source: str) -> str:
            backend = SbxSandbox(image="python:3.12-slim", egress="deny")
            async with backend.asession() as sandbox:
                await backend.awrite_file(
                    sandbox, "/tmp/prefect-sandbox/main.py", source
                )
                result = await backend.aexec(
                    sandbox,
                    ["python", "/tmp/prefect-sandbox/main.py"],
                    timeout=60,
                )
            return result.stdout
        ```
    """

    _block_type_name = "Sbx Sandbox"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/14a315b79990200db7341e42553e23650b34bb96-250x250.png"
    _documentation_url = "https://docs.prefect.io/integrations/prefect-sandbox"

    backend_name: ClassVar[str] = "sbx"

    image: str = Field(
        default="python:3.12-slim",
        min_length=1,
        title="Template Image",
        description="Container image used as the sandbox template (`sbx --template`).",
    )
    memory: str = Field(
        default="2g",
        min_length=1,
        description=(
            "Memory limit for the sandbox in binary units, such as `2g`. `sbx` "
            "enforces a 1 GiB minimum and validates the value server-side, after the "
            "template image has been pulled."
        ),
    )
    cpus: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Number of CPUs to allocate. Leave unset to accept the `sbx` default of "
            "all host CPUs."
        ),
    )
    sbx_path: str = Field(
        default="sbx",
        min_length=1,
        title="sbx Path",
        description="Path to the `sbx` binary, resolved on PATH when not absolute.",
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
            "Set to `deny` to add a per-sandbox rule blocking all outbound network "
            "access and verify it is active. Creation fails if organization governance "
            "makes the local rule inactive. `inherit` uses the active host or "
            "organization policy unchanged."
        ),
    )

    def _check_binary(self) -> None:
        """Fail early, and legibly, when Docker Sandboxes is not installed.

        Raises:
            SandboxUnavailableError: If the binary is not on PATH.
        """
        if shutil.which(self.sbx_path) is None:
            raise SandboxUnavailableError(
                f"The {self.sbx_path!r} binary was not found on PATH. Install Docker "
                "Sandboxes (https://docs.docker.com/ai/sandboxes/), run 'sbx login', "
                "and initialize a host policy."
            )

    async def _acli(
        self, args: Sequence[str], *, timeout: float, max_bytes: int
    ) -> tuple[int, str, str, bool]:
        """Run one `sbx` invocation, capping retained output while it streams.

        Args:
            args: Arguments following the binary itself.
            timeout: Wall-clock budget for the whole invocation.
            max_bytes: Bytes to retain from each of stdout and stderr.

        Returns:
            Exit code, stdout, stderr, and whether either stream was truncated.

        Raises:
            asyncio.TimeoutError: If the invocation outlived `timeout`.
            SandboxUnavailableError: If the binary could not be executed.
        """
        # The CLI inherits the worker environment on purpose: it needs the host's own
        # Docker config and credentials from it. None of that reaches the sandbox —
        # `sbx exec` forwards nothing but the `-e` values, so a sandboxed command sees
        # only the template image's environment plus this call's `env`.
        try:
            if os.name == "posix":
                # Its own session, so a wedged CLI and its descendants can be killed
                # as a group, and a signal aimed at the worker's process group does
                # not also hit a teardown that is still in flight.
                process = await asyncio.create_subprocess_exec(
                    self.sbx_path,
                    *args,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    start_new_session=True,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    self.sbx_path,
                    *args,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
        except OSError as exc:
            raise SandboxUnavailableError(
                f"Could not execute {self.sbx_path!r}: {exc}. Install Docker Sandboxes "
                "(https://docs.docker.com/ai/sandboxes/), run 'sbx login', and "
                "initialize a host policy."
            ) from exc
        readers = (
            asyncio.ensure_future(_adrain_capped(process.stdout, max_bytes)),
            asyncio.ensure_future(_adrain_capped(process.stderr, max_bytes)),
        )
        gathered = asyncio.gather(*readers, process.wait())
        try:
            (
                (stdout, out_truncated),
                (stderr, err_truncated),
                code,
            ) = await asyncio.wait_for(gathered, timeout)
        except BaseException:
            # Covers the timeout and flow-run cancellation alike: the CLI must not
            # outlive this call, and a killed child still has to be reaped or asyncio
            # complains about an abandoned transport.
            gathered.cancel()
            _kill_process_tree(process)
            with suppress(BaseException):
                await process.wait()
            await asyncio.gather(*readers, return_exceptions=True)
            raise
        return (
            code,
            stdout.decode(errors="replace"),
            stderr.decode(errors="replace"),
            out_truncated or err_truncated,
        )

    async def _aremove_sandbox(self, name: str) -> None:
        """Remove a sandbox, accepting only a confirmed already-absent result."""
        try:
            code, _, rm_stderr, _ = await self._acli(
                ["rm", "-f", name],
                timeout=_CLI_TIMEOUT,
                max_bytes=_CLI_OUTPUT_BYTES,
            )
        except asyncio.TimeoutError as exc:
            raise SandboxError(
                f"Timed out removing sandbox {name!r}; it may still be running."
            ) from exc
        if code == 0:
            return

        try:
            ls_code, stdout, ls_stderr, ls_truncated = await self._acli(
                ["ls", "--json"],
                timeout=_CLI_TIMEOUT,
                max_bytes=_CLI_JSON_BYTES,
            )
            payload = json.loads(stdout) if ls_code == 0 and not ls_truncated else {}
            sandboxes = (
                payload.get("sandboxes", [])
                if isinstance(payload, dict) and not ls_truncated
                else None
            )
        except (asyncio.TimeoutError, json.JSONDecodeError) as exc:
            raise SandboxError(
                f"Could not confirm removal of sandbox {name!r}; it may still be "
                f"running. 'sbx rm' exited {code}: "
                f"{rm_stderr.strip()[:1000] or '<no output>'}"
            ) from exc
        if not isinstance(sandboxes, list):
            raise SandboxError(
                f"Could not confirm removal of sandbox {name!r}: 'sbx ls --json' "
                "returned an invalid response."
            )
        still_exists = any(
            isinstance(item, dict)
            and (item.get("name") == name or item.get("id") == name)
            for item in sandboxes
        )
        if ls_code != 0 or still_exists:
            detail = (
                ls_stderr.strip()[:1000] if ls_code != 0 else rm_stderr.strip()[:1000]
            )
            raise SandboxError(
                f"Failed to remove sandbox {name!r}; it may still be running "
                f"('sbx rm' exit {code}): {detail or '<no output>'}"
            )

    async def _aremove_workspace(self, workspace: str) -> None:
        """Remove a host workspace only when it matches this backend's ownership."""
        path = _validated_workspace_path(workspace)
        try:
            await asyncio.to_thread(shutil.rmtree, path)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise SandboxError(
                f"Failed to remove sandbox workspace {str(path)!r}: {exc}"
            ) from exc

    async def _adiscard(self, name: str, workspace: str) -> None:
        """Remove a sandbox and its host workspace, confirming both.

        Used on the failure paths of `acreate`, where either may or may not exist.
        """
        await self._aremove_sandbox(name)
        await self._aremove_workspace(workspace)

    async def _adeny_egress(self, name: str) -> None:
        """Block all outbound network access for one sandbox.

        `sbx create` has no `--network`/`--policy` flag; the only per-sandbox control is
        a policy overlay applied after the sandbox exists, and deny rules beat allow
        rules, so a single `**` deny defeats the host allowlist. The rule takes effect
        immediately on a running sandbox, and `sbx rm` removes it along with the
        sandbox, so there is nothing extra to clean up.

        A failure here is fatal by design: continuing would hand the caller a sandbox
        with exactly the egress they asked to have blocked.

        Raises:
            SandboxCreationError: If the rule could not be applied.
        """
        try:
            code, _, stderr, _ = await self._acli(
                ["policy", "deny", "network", "--sandbox", name, "**"],
                timeout=_CLI_TIMEOUT,
                max_bytes=_CLI_OUTPUT_BYTES,
            )
        except asyncio.TimeoutError as exc:
            raise SandboxCreationError(
                f"Timed out applying the deny-all egress rule to sandbox {name!r}."
            ) from exc
        if code != 0:
            raise SandboxCreationError(
                f"Could not apply the deny-all egress rule to sandbox {name!r} "
                f"(exit {code}): {stderr.strip()[:2000] or '<no output>'}. The host "
                "policy store may not be initialized; run 'sbx policy init' once."
            )
        try:
            code, stdout, stderr, truncated = await self._acli(
                ["policy", "ls", name, "--json"],
                timeout=_CLI_TIMEOUT,
                max_bytes=_CLI_JSON_BYTES,
            )
            payload = json.loads(stdout) if code == 0 and not truncated else {}
            rules = (
                payload.get("rules", [])
                if isinstance(payload, dict) and not truncated
                else []
            )
        except (asyncio.TimeoutError, json.JSONDecodeError, AttributeError) as exc:
            raise SandboxCreationError(
                f"Could not verify the deny-all egress rule for sandbox {name!r}."
            ) from exc
        active_deny_all = isinstance(rules, list) and any(
            isinstance(rule, dict)
            and rule.get("resource_type") == "network"
            and rule.get("decision") == "deny"
            and rule.get("status") == "active"
            and isinstance(rule.get("resources"), list)
            and "**" in rule["resources"]
            for rule in rules
        )
        if not active_deny_all:
            detail = stderr.strip()[:1000] if code != 0 else "no active deny-all rule"
            raise SandboxCreationError(
                f"Could not verify blocked egress for sandbox {name!r}: {detail}. "
                "Organization governance may have made the local rule inactive."
            )

    async def acreate(self) -> Sandbox:
        """Provision one microVM.

        The sandbox is created against a throwaway empty host directory. `sbx create`
        requires at least one workspace path and mounts it read-write at the *same*
        absolute path inside the microVM, so pointing it at a temp dir is what keeps
        the rest of the host filesystem out of reach. The path is recorded in
        `Sandbox.metadata` rather than on the block, so concurrent flow runs sharing
        one block cannot clean up each other's workspace.

        Returns:
            A handle whose `id` is the sandbox's `sbx` name.

        Raises:
            SandboxUnavailableError: If the `sbx` binary is not installed.
            SandboxCreationError: If provisioning failed or timed out.
        """
        self._check_binary()
        handle_key = await asyncio.to_thread(_load_or_create_handle_key)
        name = new_sandbox_name()
        workspace = str(
            _validated_workspace_path(
                await asyncio.to_thread(tempfile.mkdtemp, prefix=_WORKSPACE_PREFIX)
            )
        )
        handle_signature = _handle_signature(name, workspace, handle_key)
        # `shell` is a required agent subcommand, not a hint, and the workspace path
        # must follow it -- `sbx create` rejects both omissions.
        args = ["create", "-q", "--name", name, "--memory", self.memory]
        if self.cpus is not None:
            args += ["--cpus", str(self.cpus)]
        args += ["--template", self.image, "shell", workspace]
        # Whether `sbx create` has been launched. Once it has, a microVM may exist no
        # matter how the rest of this fails, and cleanup has to confirm the name is
        # gone. Tracked explicitly rather than inferred from the exception type: `_acli`
        # reports an `OSError` from `create_subprocess_exec` as
        # `SandboxUnavailableError`, and it does that for the *policy* subprocess too —
        # which runs after the sandbox already exists. Keying cleanup on the type would
        # read that as "nothing was created" and leak a live sandbox, quite possibly
        # without the deny-all rule the caller asked for.
        launched = False
        try:
            try:
                launched = True
                code, _, stderr, _ = await self._acli(
                    args, timeout=self.create_timeout, max_bytes=_CLI_OUTPUT_BYTES
                )
            except SandboxUnavailableError:
                # Raised only when the binary could not be executed at all, so no
                # microVM can exist and only the workspace is ours to remove.
                launched = False
                raise
            except asyncio.TimeoutError as exc:
                raise SandboxCreationError(
                    f"'sbx create' did not finish within {self.create_timeout}s. A "
                    "cold image pull can exceed the default; raise create_timeout or "
                    f"pre-pull {self.image!r}."
                ) from exc
            if code != 0:
                raise SandboxCreationError(
                    f"'sbx create' failed with exit code {code}: "
                    f"{stderr.strip()[:2000] or '<no output>'}"
                )
            if self.egress == "deny":
                await self._adeny_egress(name)
        except BaseException as create_error:
            # Nothing may survive a failed create: a nonzero exit, a timeout, a
            # rejected policy rule and a cancellation can all leave a live microVM
            # behind, and the workspace tempdir is ours either way. Shielded because a
            # cancellation landing mid-create would otherwise abort at the first await
            # in this handler and abandon the microVM.
            cleanup = (
                self._adiscard(name, workspace)
                if launched
                else self._aremove_workspace(workspace)
            )
            try:
                await _shielded_cleanup(cleanup)
            except asyncio.CancelledError:
                raise
            except BaseException as cleanup_error:
                raise SandboxCreationError(
                    f"Sandbox creation failed and cleanup of {name!r} could not be "
                    f"confirmed; it may still be running. Original failure: "
                    f"{create_error}"
                ) from cleanup_error
            raise
        return Sandbox(
            id=name,
            backend=self.backend_name,
            metadata={
                "workspace": workspace,
                _HANDLE_SIGNATURE_KEY: handle_signature,
            },
        )

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

        `env` and `working_dir` use `sbx exec`'s own `-e`/`-w` flags, so no shell is
        involved anywhere and the caller never has to quote anything. The timeout is
        enforced around the `sbx exec` process itself. When it expires, the backend
        destroys the sandbox to guarantee the guest command cannot keep running.

        Args:
            sandbox: Handle returned by `acreate`.
            command: Argv to execute.
            timeout: Seconds the command may run.
            env: Environment variables for this command only.
            working_dir: Directory inside the sandbox to run in.

        Returns:
            A `SandboxResult`; a nonzero exit code is data, not an error.

        Raises:
            ValueError: If `command` is empty, `timeout` is not a positive finite
                number, or `env` cannot be expressed as POSIX environment variables.
        """
        validate_exec_request(command, timeout, env)
        await asyncio.to_thread(_authenticated_workspace, sandbox)

        args = ["exec"]
        for key, value in (env or {}).items():
            args += ["-e", f"{key}={value}"]
        if working_dir:
            args += ["-w", working_dir]
        args.append(sandbox.id)
        args += command

        try:
            code, stdout, stderr, truncated = await self._acli(
                args,
                timeout=timeout,
                max_bytes=self.max_output_bytes,
            )
        except asyncio.TimeoutError:
            # Killing the local CLI does not prove the guest process stopped. Taking
            # the sandbox is the only honest way to enforce the requested wall clock.
            await _shielded_cleanup(self.adestroy(sandbox))
            return SandboxResult(
                exit_code=_UNKNOWN_EXIT_CODE,
                stdout="",
                stderr=(
                    f"'sbx exec' did not return within {timeout:g}s; "
                    "the sandbox was destroyed."
                ),
                timed_out=True,
                sandbox_terminated=True,
            )
        # A vanished sandbox also exits 1 here, indistinguishable from a command that
        # exited 1, and the CLI's wording for it differs between subcommands and
        # versions. Reporting it as a plain failure with the CLI's message intact beats
        # pattern-matching error text and mislabelling a real command failure.
        return SandboxResult(
            exit_code=code,
            stdout=stdout,
            stderr=_strip_autostart_notice(stderr, sandbox.id),
            truncated=truncated,
        )

    async def adestroy(self, sandbox: Sandbox) -> None:
        """Remove `sandbox` and the host workspace that was mounted into it.

        Idempotent: when `sbx rm -f` returns nonzero, `sbx ls --json` must confirm the
        sandbox is already absent. Other failures are raised because untrusted code may
        still be running. `-f` is not optional — only it can remove a sandbox in use.
        """
        workspace = await asyncio.to_thread(_authenticated_workspace, sandbox)
        await self._aremove_sandbox(sandbox.id)
        await self._aremove_workspace(workspace)

    async def awrite_file(self, sandbox: Sandbox, path: str, content: str) -> None:
        """Write `content` to `path` inside `sandbox` using `sbx cp`.

        Overrides the base implementation, which smuggles the payload through the
        command line and is therefore capped at a few hundred kilobytes. `sbx cp`
        streams from a host file instead, so size is bounded only by the sandbox's
        disk.

        Args:
            sandbox: Handle returned by `acreate`.
            path: Absolute destination path inside the sandbox.
            content: Text to write.

        Raises:
            SandboxError: If the destination directory could not be created or the
                copy failed.
        """
        await asyncio.to_thread(_authenticated_workspace, sandbox)
        directory = path.rsplit("/", 1)[0] if "/" in path else ""
        if directory:
            # `sbx cp` does not create missing parents; it fails inside its own tar
            # extraction with a 500 from the daemon.
            result = await self.aexec(sandbox, ["mkdir", "-p", directory], timeout=60)
            if not result.ok:
                raise SandboxError(
                    f"Could not create {directory!r} in {sandbox}: "
                    f"exit {result.exit_code} {result.stderr.strip()[:500]}"
                )

        host_path = await _astage_host_temp_file(content)
        try:
            try:
                code, _, stderr, _ = await self._acli(
                    ["cp", host_path, f"{sandbox.id}:{path}"],
                    timeout=_CLI_TIMEOUT,
                    max_bytes=_CLI_OUTPUT_BYTES,
                )
            except asyncio.TimeoutError as exc:
                raise SandboxError(
                    f"Timed out copying {path!r} into {sandbox}."
                ) from exc
            if code != 0:
                raise SandboxError(
                    f"Failed to write {path!r} into {sandbox}: exit {code} "
                    f"{stderr.strip()[:500]}"
                )
        finally:
            await _shielded_cleanup(
                asyncio.to_thread(_remove_host_temp_file, host_path)
            )
