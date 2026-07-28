"""`IsloSandbox` driven against a recording stand-in for the Islo REST API.

The backend's whole surface is HTTP, so the interesting failure modes are HTTP
failure modes: a credential that has to be exchanged before it is usable and can
expire mid-flight, a Server-Sent Event stream that can split anywhere, a status
that only becomes useful after polling, and a response that never arrives even
though the sandbox it asked for now exists.

`FakeIslo` below answers those requests. It is installed by swapping the
transport of the client `_new_client` builds, so the base URL, the
`Authorization` header and the per-call timeouts are the real ones — only the
socket is fake. Nothing here touches the network, and nothing sleeps for a real
poll interval.

Shapes verified against the published OpenAPI document: `POST /auth/token`
trades an `access_key` for a `session_token`, `POST /sandboxes` answers 201 with
a `status` of `starting`/`running`/`failed`/..., `POST
/sandboxes/{name}/exec/stream` answers `text/event-stream` with `stdout`,
`stderr`, `error` and `exit` events, `POST /sandboxes/{name}/files` takes a
`path` query parameter and a `file` part, `DELETE /sandboxes/{name}` answers 204,
and every error carries `{"code", "message"}`.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import json
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from prefect_sandbox import islo
from prefect_sandbox.base import (
    MAX_INLINE_FILE_BYTES,
    SANDBOX_NAME_PREFIX,
    Sandbox,
    SandboxCreationError,
    SandboxError,
    SandboxExecutionError,
    SandboxUnavailableError,
)
from prefect_sandbox.islo import IsloSandbox
from pydantic import SecretStr, ValidationError

#: The key configured on the block in most tests, and the one configured in the
#: environment, kept distinct so precedence is observable.
BLOCK_API_KEY = "islo-key-from-the-block"
ENVIRONMENT_API_KEY = "islo-key-from-the-environment"

#: One canned answer to one request, which is all a test needs to describe the
#: provider misbehaving.
Handler = Callable[[httpx.Request], httpx.Response]


def session_token(*, serial: int, ttl: float) -> str:
    """Build a session JWT that expires `ttl` seconds from now.

    Only the payload matters: the backend reads `exp` to decide when to ask for a
    new token and never verifies the signature.
    """
    claims = {"exp": time.time() + ttl, "jti": f"token-{serial}"}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=")
    return f"header.{payload.decode()}.signature"


def sse(*events: tuple[str, str]) -> bytes:
    """Encode `(event, data)` pairs the way the provider's stream does.

    A payload containing newlines becomes several `data:` lines in one event,
    which is what the SSE specification requires and what the provider emits for
    multi-line output.
    """
    blocks = []
    for name, data in events:
        lines = [f"event: {name}", *(f"data: {line}" for line in data.split("\n"))]
        blocks.append("\n".join(lines) + "\n\n")
    return "".join(blocks).encode()


async def in_chunks(payload: bytes, size: int = 1) -> AsyncIterator[bytes]:
    """Deliver `payload` in `size`-byte pieces, as a slow network would."""
    for start in range(0, len(payload), size):
        yield payload[start : start + size]


async def then_stalls(payload: bytes) -> AsyncIterator[bytes]:
    """Deliver `payload`, then hold the stream open indefinitely."""
    yield payload
    await asyncio.Event().wait()


async def then_drops(payload: bytes) -> AsyncIterator[bytes]:
    """Deliver `payload`, then lose the connection."""
    yield payload
    raise httpx.ReadError("connection reset by peer")


def reply(status_code: int, body: object = None) -> Handler:
    """A handler that always answers with `status_code` and `body`."""

    def handler(request: httpx.Request) -> httpx.Response:
        if body is None:
            return httpx.Response(status_code)
        return httpx.Response(status_code, json=body)

    return handler


def raises(error: Exception) -> Handler:
    """A handler that fails the way a lost connection does: no response at all."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    return handler


def route_of(request: httpx.Request) -> str:
    """Classify `request` by the endpoint it addresses.

    Derived from the request rather than from a registry of paths, so a call to
    an endpoint the backend was never meant to reach cannot be silently absorbed.
    """
    path = request.url.path
    if path == "/auth/token":
        return "auth"
    if path == "/sandboxes":
        return "create"
    if path.endswith("/exec/stream"):
        return "exec"
    if path.endswith("/files"):
        return "files"
    return "delete" if request.method == "DELETE" else "status"


@dataclasses.dataclass(frozen=True)
class RecordedRequest:
    """One request the fake API received."""

    route: str
    method: str
    url: httpx.URL
    headers: httpx.Headers
    content: bytes

    @property
    def path(self) -> str:
        """The request path, with any percent-escaping decoded."""
        return self.url.path

    @property
    def body(self) -> dict[str, Any]:
        """The JSON body, or `{}` when the request did not send one."""
        try:
            payload = json.loads(self.content)
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}

    @property
    def bearer(self) -> str:
        """The credential on the `Authorization` header, without its scheme."""
        return self.headers.get("Authorization", "").removeprefix("Bearer ")


class FakeIslo:
    """A recording, configurable stand-in for the Islo REST API.

    Healthy behaviour is the default: a key is exchanged for a session token, a
    created sandbox exists and is running, a command exits 0, and a deleted
    sandbox is gone. `replies` swaps in whatever a test needs instead, one route
    at a time, and the last queued handler repeats so a retry can be observed.
    """

    def __init__(self) -> None:
        self.requests: list[RecordedRequest] = []
        self.tokens: list[str] = []
        self.token_ttl = 3600.0
        self.opaque_tokens = False
        #: Names the fake currently believes exist.
        self.live: set[str] = set()
        self.provider_id = "sb_9f8e7d6c5b4a"
        self.create_status = "running"
        #: Statuses `GET /sandboxes/{name}` reports, in order; the last repeats.
        self.statuses: list[str] = ["running"]
        self.internet_enabled: bool | None = None
        self.events: object = sse(("exit", "0"))
        self._queued: dict[str, list[Handler]] = {}

    def replies(self, route: str, *handlers: Handler) -> None:
        """Answer the next requests to `route` with `handlers`, the last repeating."""
        self._queued[route] = list(handlers)

    def handler(self, request: httpx.Request) -> httpx.Response:
        """Record `request` and answer it."""
        route = route_of(request)
        self.requests.append(
            RecordedRequest(
                route=route,
                method=request.method,
                url=request.url,
                headers=request.headers,
                content=request.content,
            )
        )
        queued = self._queued.get(route)
        if queued:
            return (queued.pop(0) if len(queued) > 1 else queued[0])(request)
        return self.default(request)

    def default(self, request: httpx.Request) -> httpx.Response:
        """Answer `request` the way a healthy provider would."""
        return getattr(self, f"_{route_of(request)}")(request)

    def requests_for(self, route: str) -> list[RecordedRequest]:
        """Every recorded request to one route, in order."""
        return [recorded for recorded in self.requests if recorded.route == route]

    def name_in(self, route: str, index: int = 0) -> str:
        """The sandbox name addressed by the `index`th request to `route`."""
        return self.requests_for(route)[index].path.split("/")[2]

    def _sandbox(self, name: str, status: str) -> dict[str, Any]:
        """The provider's representation of one sandbox."""
        body: dict[str, Any] = {
            "id": self.provider_id,
            "name": name,
            "status": status,
            "image": "docker.io/library/islo-runner:latest",
            "created_at": "2026-01-01T00:00:00Z",
        }
        if self.internet_enabled is not None:
            body["internet_enabled"] = self.internet_enabled
        return body

    def _absent(self, name: str) -> httpx.Response:
        """The answer to a request naming a sandbox that does not exist."""
        return httpx.Response(
            404,
            json={"code": "SANDBOX_NOT_FOUND", "message": f"no sandbox named {name}"},
        )

    def _auth(self, request: httpx.Request) -> httpx.Response:
        """Trade an access key for a fresh session token."""
        serial = len(self.tokens)
        token = (
            f"opaque-token-{serial}"
            if self.opaque_tokens
            else session_token(serial=serial, ttl=self.token_ttl)
        )
        self.tokens.append(token)
        return httpx.Response(200, json={"session_token": token})

    def _create(self, request: httpx.Request) -> httpx.Response:
        """Provision a sandbox under the name the request asked for."""
        name = json.loads(request.content)["name"]
        self.live.add(name)
        return httpx.Response(201, json=self._sandbox(name, self.create_status))

    def _status(self, request: httpx.Request) -> httpx.Response:
        """Report the next status a booting sandbox reaches."""
        name = request.url.path.split("/")[2]
        if name not in self.live:
            return self._absent(name)
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        return httpx.Response(200, json=self._sandbox(name, status))

    def _exec(self, request: httpx.Request) -> httpx.Response:
        """Stream the configured events back as `text/event-stream`."""
        name = request.url.path.split("/")[2]
        if name not in self.live:
            return self._absent(name)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=self.events,  # type: ignore[arg-type]
        )

    def _files(self, request: httpx.Request) -> httpx.Response:
        """Accept one uploaded file."""
        name = request.url.path.split("/")[2]
        if name not in self.live:
            return self._absent(name)
        return httpx.Response(200, json={"status": "written"})

    def _delete(self, request: httpx.Request) -> httpx.Response:
        """Remove a sandbox, or report that it was already gone."""
        name = request.url.path.split("/")[2]
        if name not in self.live:
            return self._absent(name)
        self.live.discard(name)
        return httpx.Response(204)


@pytest.fixture(autouse=True)
def clean_islo_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a developer's own Islo configuration out of every test."""
    monkeypatch.delenv("ISLO_API_KEY", raising=False)
    monkeypatch.delenv("ISLO_API_URL", raising=False)


@pytest.fixture
def fake_islo(monkeypatch: pytest.MonkeyPatch) -> FakeIslo:
    """Answer every client the block builds from a fake API instead of a socket.

    Only the transport is replaced. The client itself is still the one
    `_new_client` returns, which keeps the resolved base URL, the `Authorization`
    header and the per-call timeouts inside what these tests exercise.
    """
    fake = FakeIslo()
    build_client = IsloSandbox._new_client

    def patched(
        self: IsloSandbox, *, token: str | None, timeout: float | httpx.Timeout
    ) -> httpx.AsyncClient:
        client = build_client(self, token=token, timeout=timeout)
        client._transport = httpx.MockTransport(fake.handler)
        return client

    monkeypatch.setattr(IsloSandbox, "_new_client", patched)
    return fake


@pytest.fixture
def backend(fake_islo: FakeIslo) -> IsloSandbox:
    """A backend with a key on the block, wired to the fake API."""
    return IsloSandbox(api_key=SecretStr(BLOCK_API_KEY))


@pytest.fixture
def sandbox(fake_islo: FakeIslo) -> Sandbox:
    """A handle to a sandbox the fake API already believes is running.

    Handles are self-contained, so an exec or teardown test does not have to
    provision one first — which also keeps `acreate`'s requests out of the
    recording.
    """
    name = f"{SANDBOX_NAME_PREFIX}0123456789ab"
    fake_islo.live.add(name)
    return Sandbox(id=name, backend="islo", metadata={"sandbox_id": "sb_existing"})


@pytest.fixture
def poll_delays(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Collapse the gap between status polls, recording what was asked for.

    A booting microVM is polled every couple of seconds; waiting for that would
    measure `asyncio.sleep` and nothing else.
    """
    slept: list[float] = []

    async def instant(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(islo.asyncio, "sleep", instant)
    return slept


class TestCredentials:
    async def test_the_key_on_the_block_is_exchanged(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        await backend.acreate()
        (exchange,) = fake_islo.requests_for("auth")
        assert exchange.body == {"access_key": BLOCK_API_KEY}

    async def test_the_environment_supplies_the_key_when_the_block_has_none(
        self, fake_islo: FakeIslo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ISLO_API_KEY", ENVIRONMENT_API_KEY)
        await IsloSandbox().acreate()
        assert fake_islo.requests_for("auth")[0].body["access_key"] == (
            ENVIRONMENT_API_KEY
        )

    async def test_a_key_on_the_block_wins_over_the_environment(
        self, backend: IsloSandbox, fake_islo: FakeIslo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ISLO_API_KEY", ENVIRONMENT_API_KEY)
        await backend.acreate()
        assert fake_islo.requests_for("auth")[0].body["access_key"] == BLOCK_API_KEY

    async def test_surrounding_whitespace_is_not_part_of_the_key(
        self, fake_islo: FakeIslo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A key pasted into an environment file routinely arrives with a newline."""
        monkeypatch.setenv("ISLO_API_KEY", f"  {ENVIRONMENT_API_KEY}\n")
        await IsloSandbox().acreate()
        assert fake_islo.requests_for("auth")[0].body["access_key"] == (
            ENVIRONMENT_API_KEY
        )

    async def test_no_key_anywhere_is_reported_as_unavailable(
        self, fake_islo: FakeIslo
    ) -> None:
        with pytest.raises(SandboxUnavailableError) as excinfo:
            await IsloSandbox().acreate()
        message = str(excinfo.value)
        assert "ISLO_API_KEY" in message
        assert "api_key" in message

    async def test_a_missing_key_attempts_nothing_at_all(
        self, fake_islo: FakeIslo
    ) -> None:
        """No credential means no sandbox, so there is nothing to clean up."""
        with pytest.raises(SandboxUnavailableError):
            await IsloSandbox().acreate()
        assert fake_islo.requests == []

    async def test_an_empty_key_is_treated_as_no_key(self, fake_islo: FakeIslo) -> None:
        with pytest.raises(SandboxUnavailableError):
            await IsloSandbox(api_key=SecretStr("   ")).acreate()

    async def test_the_api_key_never_travels_as_a_bearer_credential(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """The raw key is not accepted as a bearer token, and must not be sent as one."""
        await backend.acreate()
        await backend.aexec(sandbox, ["true"], timeout=5)

        for recorded in fake_islo.requests:
            assert BLOCK_API_KEY not in recorded.headers.get("Authorization", "")
            if recorded.route != "auth":
                assert recorded.bearer == fake_islo.tokens[0]

    async def test_the_key_is_only_ever_sent_to_the_token_endpoint(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        await backend.acreate()
        await backend.aexec(sandbox, ["true"], timeout=5)

        for recorded in fake_islo.requests:
            if recorded.route == "auth":
                continue
            assert BLOCK_API_KEY not in recorded.content.decode()
            assert BLOCK_API_KEY not in str(recorded.headers)

    async def test_a_rejected_key_is_reported_as_unavailable(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        fake_islo.replies(
            "auth",
            reply(401, {"code": "AUTH_REQUIRED", "message": "unknown access key"}),
        )
        with pytest.raises(SandboxUnavailableError) as excinfo:
            await backend.acreate()
        message = str(excinfo.value)
        assert "unknown access key" in message
        assert "islo api-key create" in message
        assert fake_islo.requests_for("create") == []

    async def test_a_forbidden_key_is_reported_as_unavailable(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        fake_islo.replies(
            "auth",
            reply(403, {"code": "TENANT_SUSPENDED", "message": "tenant is suspended"}),
        )
        with pytest.raises(SandboxUnavailableError, match="tenant is suspended"):
            await backend.acreate()

    async def test_a_broken_token_endpoint_is_reported_as_unavailable(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        fake_islo.replies(
            "auth", reply(500, {"code": "INTERNAL_ERROR", "message": "try again"})
        )
        with pytest.raises(SandboxUnavailableError, match="token exchange failed"):
            await backend.acreate()

    async def test_an_exchange_without_a_token_is_reported_as_unavailable(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        fake_islo.replies("auth", reply(200, {"expires_in": 900}))
        with pytest.raises(SandboxUnavailableError, match="no session token"):
            await backend.acreate()

    async def test_an_unreachable_api_is_reported_as_unavailable(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        fake_islo.replies("auth", raises(httpx.ConnectError("name resolution failed")))
        with pytest.raises(SandboxUnavailableError) as excinfo:
            await backend.acreate()
        message = str(excinfo.value)
        # The endpoint that could not be reached is the first thing an operator needs.
        # Taken from the module rather than repeated as a literal, so the assertion
        # cannot drift from the default it is describing.
        assert islo._DEFAULT_API_URL in message
        assert "name resolution failed" in message


class TestApiUrl:
    async def test_defaults_to_the_public_control_plane(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        await backend.acreate()
        assert str(fake_islo.requests_for("create")[0].url) == (
            "https://api.islo.dev/sandboxes"
        )

    async def test_the_environment_selects_a_regional_endpoint(
        self, fake_islo: FakeIslo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ISLO_API_URL", "https://ca.compute.islo.dev")
        await IsloSandbox(api_key=SecretStr(BLOCK_API_KEY)).acreate()
        assert fake_islo.requests[0].url.host == "ca.compute.islo.dev"

    async def test_the_block_wins_over_the_environment(
        self, fake_islo: FakeIslo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ISLO_API_URL", "https://ignored.compute.islo.dev")
        await IsloSandbox(
            api_key=SecretStr(BLOCK_API_KEY), api_url="https://eu.compute.islo.dev"
        ).acreate()
        assert fake_islo.requests[0].url.host == "eu.compute.islo.dev"

    async def test_a_trailing_slash_does_not_double_up(
        self, fake_islo: FakeIslo
    ) -> None:
        await IsloSandbox(
            api_key=SecretStr(BLOCK_API_KEY), api_url="https://eu.compute.islo.dev/"
        ).acreate()
        assert str(fake_islo.requests_for("create")[0].url) == (
            "https://eu.compute.islo.dev/sandboxes"
        )

    async def test_the_resolved_url_travels_on_the_handle(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        handle = await backend.acreate()
        assert handle.metadata["api_url"] == "https://api.islo.dev"


class TestBlockShape:
    def test_construction_resolves_nothing(self, fake_islo: FakeIslo) -> None:
        """Invariant 2: blocks are built at import time, with no key in sight."""
        instance = IsloSandbox()
        assert instance.backend_name == "islo"
        assert fake_islo.requests == []

    def test_the_api_key_stays_out_of_reprs_and_dumps(self) -> None:
        instance = IsloSandbox(api_key=SecretStr(BLOCK_API_KEY))
        assert BLOCK_API_KEY not in repr(instance)
        assert BLOCK_API_KEY not in str(instance)
        assert BLOCK_API_KEY not in str(instance.model_dump())
        assert BLOCK_API_KEY not in instance.model_dump_json()
        # Still recoverable by the backend itself, which is the whole point.
        assert instance.api_key is not None
        assert instance.api_key.get_secret_value() == BLOCK_API_KEY

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"image": ""},
            {"vcpus": 0},
            {"memory_mb": 0},
            {"disk_gb": -1},
            {"create_timeout": 0},
            {"delete_after": 0},
            {"max_output_bytes": 0},
            {"egress": "allow-all"},
        ],
    )
    def test_invalid_configuration_is_rejected(self, kwargs: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            IsloSandbox(**kwargs)  # type: ignore[arg-type]

    async def test_aclose_stays_a_no_op(self, backend: IsloSandbox) -> None:
        """There is no backend-level pool to close: a client is built per call."""
        assert await backend.aclose() is None


class TestSessionToken:
    async def test_the_key_is_exchanged_once_and_the_token_reused(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        handle = await backend.acreate()
        await backend.aexec(handle, ["true"], timeout=5)
        await backend.adestroy(handle)

        assert len(fake_islo.requests_for("auth")) == 1
        assert {
            recorded.bearer
            for recorded in fake_islo.requests
            if recorded.route != "auth"
        } == {fake_islo.tokens[0]}

    async def test_an_expired_token_is_exchanged_again(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        fake_islo.token_ttl = 0.0
        handle = await backend.acreate()
        await backend.adestroy(handle)

        assert len(fake_islo.requests_for("auth")) > 1
        assert fake_islo.requests_for("delete")[0].bearer == fake_islo.tokens[-1]

    async def test_a_token_with_an_unreadable_payload_still_works_and_is_reused(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        """A changed token format costs one extra exchange, not a failed request."""
        fake_islo.opaque_tokens = True
        handle = await backend.acreate()
        await backend.adestroy(handle)

        assert len(fake_islo.requests_for("auth")) == 1
        assert fake_islo.requests_for("delete")[0].bearer == "opaque-token-0"

    async def test_a_rejected_request_is_retried_once_with_a_fresh_token(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        """A token can expire between the last poll and the next request."""
        fake_islo.replies(
            "create",
            reply(401, {"code": "AUTH_REQUIRED", "message": "token expired"}),
            fake_islo.default,
        )

        handle = await backend.acreate()

        assert len(fake_islo.requests_for("auth")) == 2
        first, second = fake_islo.requests_for("create")
        assert first.bearer != second.bearer
        assert handle.id in fake_islo.live

    async def test_a_second_rejection_is_surfaced_rather_than_looped(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        fake_islo.replies(
            "delete", reply(401, {"code": "AUTH_REQUIRED", "message": "still no"})
        )
        with pytest.raises(SandboxError, match="still no"):
            await backend.adestroy(Sandbox(id="prefect-sandbox-abc", backend="islo"))
        assert len(fake_islo.requests_for("delete")) == 2


class TestCreateRequest:
    async def test_posts_the_configured_shape_and_the_generated_name(
        self, fake_islo: FakeIslo
    ) -> None:
        backend = IsloSandbox(
            api_key=SecretStr(BLOCK_API_KEY),
            image="alpine:3.20",
            vcpus=4,
            memory_mb=8192,
            disk_gb=25,
            delete_after=None,
        )
        handle = await backend.acreate()

        (created,) = fake_islo.requests_for("create")
        assert created.method == "POST"
        assert created.path == "/sandboxes"
        assert created.body["name"] == handle.id
        assert created.body["image"] == "alpine:3.20"
        assert created.body["vcpus"] == 4
        assert created.body["memory_mb"] == 8192
        assert created.body["disk_gb"] == 25

    async def test_the_generated_name_is_the_handle_id(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        handle = await backend.acreate()
        assert handle.id.startswith(SANDBOX_NAME_PREFIX)
        assert handle.backend == "islo"
        assert fake_islo.live == {handle.id}

    async def test_the_provider_id_and_api_url_travel_on_the_handle(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        """Invariant 1: everything teardown or an operator needs is on the handle."""
        handle = await backend.acreate()
        assert handle.metadata == {
            "api_url": "https://api.islo.dev",
            "sandbox_id": fake_islo.provider_id,
        }

    async def test_a_provider_without_an_id_still_yields_a_usable_handle(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        fake_islo.replies(
            "create", reply(201, {"name": "ignored", "status": "running"})
        )
        handle = await backend.acreate()
        assert "sandbox_id" not in handle.metadata
        assert handle.id.startswith(SANDBOX_NAME_PREFIX)

    async def test_the_workdir_is_sent_only_when_configured(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        await backend.acreate()
        assert "workdir" not in fake_islo.requests_for("create")[0].body

        await IsloSandbox(api_key=SecretStr(BLOCK_API_KEY), workdir="/work").acreate()
        assert fake_islo.requests_for("create")[1].body["workdir"] == "/work"

    async def test_the_gateway_profile_is_sent_only_when_configured(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        await backend.acreate()
        assert "gateway_profile" not in fake_islo.requests_for("create")[0].body

        await IsloSandbox(
            api_key=SecretStr(BLOCK_API_KEY), gateway_profile="pypi-only"
        ).acreate()
        assert (
            fake_islo.requests_for("create")[1].body["gateway_profile"] == "pypi-only"
        )

    async def test_delete_after_is_sent_as_the_provider_side_lifecycle(
        self, fake_islo: FakeIslo
    ) -> None:
        await IsloSandbox(api_key=SecretStr(BLOCK_API_KEY), delete_after=900).acreate()
        assert fake_islo.requests_for("create")[0].body["lifecycle"] == {
            "delete_after": 900
        }

    async def test_no_lifecycle_is_sent_when_the_reaper_is_switched_off(
        self, fake_islo: FakeIslo
    ) -> None:
        await IsloSandbox(api_key=SecretStr(BLOCK_API_KEY), delete_after=None).acreate()
        assert "lifecycle" not in fake_islo.requests_for("create")[0].body

    async def test_concurrent_creates_on_one_block_are_isolated(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        """Invariant 1: one shared block instance, no shared per-sandbox state."""
        first, second = await asyncio.gather(backend.acreate(), backend.acreate())
        assert first.id != second.id
        assert fake_islo.live == {first.id, second.id}


class TestCreateReadiness:
    async def test_a_booting_sandbox_is_polled_until_it_can_accept_commands(
        self, backend: IsloSandbox, fake_islo: FakeIslo, poll_delays: list[float]
    ) -> None:
        fake_islo.create_status = "starting"
        fake_islo.statuses = ["starting", "running"]

        handle = await backend.acreate()

        assert len(fake_islo.requests_for("status")) == 2
        assert len(poll_delays) == 2
        assert handle.id in fake_islo.live

    async def test_a_sandbox_that_is_already_running_costs_no_extra_request(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        await backend.acreate()
        assert fake_islo.requests_for("status") == []

    async def test_a_failed_status_fails_creation_without_polling(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        fake_islo.create_status = "failed"

        with pytest.raises(SandboxCreationError, match="failed"):
            await backend.acreate()

        assert fake_islo.requests_for("status") == []
        assert fake_islo.live == set()

    @pytest.mark.parametrize("status", ["deleted", "stopped", "stopping", "paused"])
    async def test_no_status_a_booting_sandbox_never_recovers_from_is_awaited(
        self, backend: IsloSandbox, fake_islo: FakeIslo, status: str
    ) -> None:
        fake_islo.create_status = status
        with pytest.raises(SandboxCreationError, match=status):
            await backend.acreate()
        assert fake_islo.requests_for("status") == []

    async def test_a_sandbox_that_never_boots_fails_and_is_deleted(
        self, fake_islo: FakeIslo
    ) -> None:
        fake_islo.create_status = "starting"
        fake_islo.statuses = ["starting"]
        backend = IsloSandbox(api_key=SecretStr(BLOCK_API_KEY), create_timeout=0.001)

        with pytest.raises(SandboxCreationError) as excinfo:
            await backend.acreate()

        assert "create_timeout" in str(excinfo.value)
        assert fake_islo.requests_for("delete")
        assert fake_islo.live == set()

    async def test_an_unreadable_status_fails_creation(
        self, backend: IsloSandbox, fake_islo: FakeIslo, poll_delays: list[float]
    ) -> None:
        fake_islo.create_status = "starting"
        fake_islo.replies(
            "status",
            reply(500, {"code": "INTERNAL_ERROR", "message": "status unavailable"}),
        )

        with pytest.raises(SandboxCreationError, match="status unavailable"):
            await backend.acreate()

        assert fake_islo.live == set()

    async def test_a_sandbox_that_vanishes_while_booting_fails_creation(
        self, backend: IsloSandbox, fake_islo: FakeIslo, poll_delays: list[float]
    ) -> None:
        fake_islo.create_status = "starting"
        fake_islo.replies("status", reply(404, {"code": "SANDBOX_NOT_FOUND"}))

        with pytest.raises(SandboxCreationError, match="SANDBOX_NOT_FOUND"):
            await backend.acreate()


class TestCreateFailureCleanup:
    """Invariant 4: a failed create never leaves a microVM behind."""

    @pytest.mark.parametrize(
        ("status_code", "body", "expected"),
        [
            (
                400,
                {"code": "VALIDATION_ERROR", "message": "vcpus exceeds plan limit"},
                "vcpus exceeds plan limit",
            ),
            (
                409,
                {"code": "SANDBOX_ALREADY_EXISTS", "message": "name is taken"},
                "SANDBOX_ALREADY_EXISTS",
            ),
            (
                402,
                {"code": "BILLING_NOT_ALLOWED", "message": "insufficient credits"},
                "insufficient credits",
            ),
        ],
    )
    async def test_a_rejected_create_reports_the_providers_reason(
        self,
        backend: IsloSandbox,
        fake_islo: FakeIslo,
        status_code: int,
        body: dict[str, str],
        expected: str,
    ) -> None:
        fake_islo.replies("create", reply(status_code, body))

        with pytest.raises(SandboxCreationError) as excinfo:
            await backend.acreate()

        message = str(excinfo.value)
        assert expected in message
        assert str(status_code) in message

    @pytest.mark.parametrize(
        "failure",
        [
            reply(400, {"code": "VALIDATION_ERROR", "message": "bad image"}),
            reply(500, {"code": "INTERNAL_ERROR", "message": "scheduler down"}),
            raises(httpx.ReadTimeout("no response")),
        ],
    )
    async def test_every_failed_create_deletes_the_name_it_generated(
        self, backend: IsloSandbox, fake_islo: FakeIslo, failure: Handler
    ) -> None:
        """A lost response is not evidence that nothing was provisioned, so the
        name is deleted even when no status code ever came back."""
        fake_islo.replies("create", failure)

        with pytest.raises(SandboxError):
            await backend.acreate()

        assert (
            fake_islo.name_in("delete")
            == fake_islo.requests_for("create")[0].body["name"]
        )
        assert fake_islo.live == set()

    async def test_a_cancelled_create_still_deletes_the_sandbox(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        """A cancelled flow run must not abandon a live microVM.

        The cleanup is shielded for exactly this: without it the first await in
        the handler would re-raise and orphan the sandbox.
        """
        fake_islo.create_status = "starting"
        fake_islo.statuses = ["starting"]

        task = asyncio.ensure_future(backend.acreate())
        while not fake_islo.requests_for("create"):
            await asyncio.sleep(0)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert fake_islo.requests_for("delete")
        assert fake_islo.live == set()

    async def test_a_credential_failing_mid_boot_still_deletes_the_sandbox(
        self, backend: IsloSandbox, fake_islo: FakeIslo, poll_delays: list[float]
    ) -> None:
        """A token refresh dying while the microVM boots is not proof it never existed.

        Session tokens are short-lived, so a slow cold boot re-exchanges the key
        mid-poll. If that exchange fails — a transient 503, a key rotated under a
        running flow — the sandbox is already provisioned and must still be deleted,
        even though the error says the backend has no usable credential.
        """
        fake_islo.token_ttl = -1.0  # already expired, so every call re-exchanges
        fake_islo.create_status = "starting"
        fake_islo.statuses = ["starting"]
        spent: list[bool] = []

        def dies_once_the_sandbox_exists(request: httpx.Request) -> httpx.Response:
            """Fail the first exchange that happens after something was provisioned."""
            if fake_islo.live and not spent:
                spent.append(True)
                return httpx.Response(
                    503, json={"code": "RESOURCE_UNAVAILABLE", "message": "try again"}
                )
            return fake_islo.default(request)

        fake_islo.replies("auth", dies_once_the_sandbox_exists)

        with pytest.raises(SandboxUnavailableError):
            await backend.acreate()

        assert (
            fake_islo.name_in("delete")
            == fake_islo.requests_for("create")[0].body["name"]
        )
        assert fake_islo.live == set()

    async def test_a_missing_credential_deletes_nothing(
        self, fake_islo: FakeIslo
    ) -> None:
        """The one failure that proves nothing was provisioned.

        The credential is resolved before anything is created, so there is no name
        to delete and a cleanup call would only fail the same way.
        """
        with pytest.raises(SandboxUnavailableError):
            await IsloSandbox().acreate()

        assert fake_islo.requests == []

    async def test_a_failed_cleanup_reports_a_possibly_live_sandbox(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        fake_islo.replies(
            "create", reply(400, {"code": "VALIDATION_ERROR", "message": "bad image"})
        )
        fake_islo.replies(
            "delete", reply(500, {"code": "INTERNAL_ERROR", "message": "cannot delete"})
        )

        with pytest.raises(SandboxCreationError) as excinfo:
            await backend.acreate()

        message = str(excinfo.value)
        assert "may still be running" in message
        # The original failure is what an operator needs; the cleanup failure is
        # context.
        assert "bad image" in message


class TestEgress:
    async def test_inherit_leaves_the_decision_to_the_tenant_default(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        await backend.acreate()
        assert "internet_enabled" not in fake_islo.requests_for("create")[0].body

    async def test_deny_switches_the_internet_off_at_provisioning_time(
        self, fake_islo: FakeIslo
    ) -> None:
        """Part of the creation request, so there is no window in which the
        sandbox exists with the wrong egress."""
        await IsloSandbox(api_key=SecretStr(BLOCK_API_KEY), egress="deny").acreate()
        assert fake_islo.requests_for("create")[0].body["internet_enabled"] is False

    async def test_reported_internet_access_after_a_denial_fails_creation(
        self, fake_islo: FakeIslo
    ) -> None:
        fake_islo.internet_enabled = True

        with pytest.raises(SandboxCreationError) as excinfo:
            await IsloSandbox(api_key=SecretStr(BLOCK_API_KEY), egress="deny").acreate()

        assert "internet access" in str(excinfo.value)
        assert fake_islo.live == set()

    async def test_internet_access_appearing_during_boot_fails_creation(
        self, fake_islo: FakeIslo, poll_delays: list[float]
    ) -> None:
        fake_islo.create_status = "starting"
        fake_islo.statuses = ["starting", "running"]
        fake_islo.replies(
            "status",
            reply(200, {"status": "starting", "internet_enabled": True}),
        )

        with pytest.raises(SandboxCreationError, match="internet access"):
            await IsloSandbox(api_key=SecretStr(BLOCK_API_KEY), egress="deny").acreate()

        assert fake_islo.live == set()

    async def test_reported_internet_access_is_fine_when_it_was_not_denied(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        fake_islo.internet_enabled = True
        handle = await backend.acreate()
        assert handle.id in fake_islo.live


class TestExecRequest:
    async def test_sends_the_command_as_an_argv_list(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        await backend.aexec(sandbox, ["echo", "hello world"], timeout=5)

        (executed,) = fake_islo.requests_for("exec")
        assert executed.method == "POST"
        assert executed.path == f"/sandboxes/{sandbox.id}/exec/stream"
        assert executed.body["command"] == ["echo", "hello world"]
        # No shell trampoline: nothing the caller passes is ever re-parsed.
        assert "sh" not in executed.body["command"]
        assert "-c" not in executed.body["command"]

    async def test_sends_the_environment_for_that_command_only(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        await backend.aexec(
            sandbox, ["env"], timeout=5, env={"FIRST": "1", "SECOND": "two words"}
        )
        assert fake_islo.requests_for("exec")[0].body["env"] == {
            "FIRST": "1",
            "SECOND": "two words",
        }

    async def test_sends_no_environment_when_the_caller_passed_none(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        await backend.aexec(sandbox, ["env"], timeout=5)
        assert "env" not in fake_islo.requests_for("exec")[0].body

    async def test_the_working_directory_overrides_the_block_default(
        self, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        backend = IsloSandbox(api_key=SecretStr(BLOCK_API_KEY), workdir="/default")

        await backend.aexec(sandbox, ["pwd"], timeout=5)
        assert fake_islo.requests_for("exec")[0].body["workdir"] == "/default"

        await backend.aexec(sandbox, ["pwd"], timeout=5, working_dir="/elsewhere")
        assert fake_islo.requests_for("exec")[1].body["workdir"] == "/elsewhere"

    async def test_no_working_directory_is_sent_when_neither_is_configured(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        await backend.aexec(sandbox, ["pwd"], timeout=5)
        assert "workdir" not in fake_islo.requests_for("exec")[0].body

    async def test_the_guest_user_is_sent_only_when_configured(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        await backend.aexec(sandbox, ["id"], timeout=5)
        assert "user" not in fake_islo.requests_for("exec")[0].body

        await IsloSandbox(api_key=SecretStr(BLOCK_API_KEY), user="nobody").aexec(
            sandbox, ["id"], timeout=5
        )
        assert fake_islo.requests_for("exec")[1].body["user"] == "nobody"

    async def test_the_providers_own_budget_is_sent_as_whole_seconds(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """The API documents `timeout_secs` as a hint, so it is bookkeeping only:
        the caller's wall clock is enforced locally regardless."""
        await backend.aexec(sandbox, ["true"], timeout=29.2)
        assert fake_islo.requests_for("exec")[0].body["timeout_secs"] == 30

        await backend.aexec(sandbox, ["true"], timeout=0.1)
        assert fake_islo.requests_for("exec")[1].body["timeout_secs"] == 1

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"command": [], "timeout": 5}, "must not be empty"),
            ({"command": ["true"], "timeout": 0}, "positive"),
            ({"command": ["true"], "timeout": -1}, "positive"),
            ({"command": ["true"], "timeout": float("inf")}, "positive"),
            ({"command": ["true"], "timeout": float("nan")}, "positive"),
            (
                {"command": ["true"], "timeout": 5, "env": {"BAD=NAME": "value"}},
                "Invalid environment variable name",
            ),
            (
                {"command": ["true"], "timeout": 5, "env": {"BAD\0NAME": "value"}},
                "Invalid environment variable name",
            ),
            (
                {"command": ["true"], "timeout": 5, "env": {"OK": "va\0lue"}},
                "null byte",
            ),
        ],
    )
    async def test_an_impossible_request_is_rejected_before_any_call(
        self,
        backend: IsloSandbox,
        fake_islo: FakeIslo,
        sandbox: Sandbox,
        kwargs: dict[str, object],
        match: str,
    ) -> None:
        with pytest.raises(ValueError, match=match):
            await backend.aexec(sandbox, **kwargs)  # type: ignore[arg-type]
        assert fake_islo.requests == []

    async def test_no_worker_environment_reaches_the_command(
        self,
        backend: IsloSandbox,
        fake_islo: FakeIslo,
        sandbox: Sandbox,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Invariant 7: only what the caller passed in `env` is forwarded."""
        monkeypatch.setenv("PREFECT_API_KEY", "pnu_supersecret")
        monkeypatch.setenv("PREFECT_API_URL", "https://api.prefect.cloud/x")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "canary-aws-secret")

        await backend.aexec(sandbox, ["env"], timeout=5, env={"SAFE": "yes"})

        (executed,) = fake_islo.requests_for("exec")
        assert executed.body["env"] == {"SAFE": "yes"}
        payload = executed.content.decode()
        for secret in ("pnu_supersecret", "api.prefect.cloud", "canary-aws-secret"):
            assert secret not in payload
        assert "PREFECT_API_KEY" not in payload


class TestExecResults:
    async def test_maps_the_streams_and_the_exit_code_onto_the_result(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        fake_islo.events = sse(("stdout", "out"), ("stderr", "err"), ("exit", "0"))
        result = await backend.aexec(sandbox, ["true"], timeout=5)

        assert (result.stdout, result.stderr) == ("out", "err")
        assert result.exit_code == 0
        assert result.ok
        assert not result.truncated
        assert not result.timed_out
        assert not result.sandbox_terminated

    async def test_a_nonzero_exit_is_data_not_an_exception(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """Invariant 8."""
        fake_islo.events = sse(("stderr", "boom"), ("exit", "3"))
        result = await backend.aexec(sandbox, ["false"], timeout=5)

        assert result.exit_code == 3
        assert not result.ok
        assert not result.timed_out
        assert sandbox.id in fake_islo.live
        # Only asking for a raise produces one.
        with pytest.raises(SandboxError):
            result.raise_for_status()

    async def test_an_error_event_is_reported_on_stderr(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """The provider reports its own trouble in-band; attributing it to the
        command's stderr keeps it in front of whoever reads the result."""
        fake_islo.events = sse(("error", "guest agent restarted"), ("exit", "1"))
        result = await backend.aexec(sandbox, ["true"], timeout=5)

        assert "guest agent restarted" in result.stderr
        assert result.stdout == ""
        assert result.exit_code == 1

    async def test_an_unparsable_exit_event_is_reported_as_a_failure(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """Guessing success from an exit code nobody can read would be worse."""
        fake_islo.events = sse(("exit", "killed"))
        result = await backend.aexec(sandbox, ["true"], timeout=5)
        assert result.exit_code == 1
        assert not result.ok

    async def test_an_unknown_event_is_ignored(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """New event types must not break an older worker."""
        fake_islo.events = sse(
            ("heartbeat", "still here"), ("stdout", "ok"), ("exit", "0")
        )
        result = await backend.aexec(sandbox, ["true"], timeout=5)
        assert (result.stdout, result.exit_code) == ("ok", 0)


class TestExecStreamDecoding:
    async def test_multi_line_output_is_reassembled(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        fake_islo.events = sse(("stdout", "first\nsecond\nthird"), ("exit", "0"))
        result = await backend.aexec(sandbox, ["true"], timeout=5)
        assert result.stdout == "first\nsecond\nthird"

    async def test_consecutive_events_are_concatenated_in_order(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        fake_islo.events = sse(
            ("stdout", "one"), ("stdout", "two"), ("stdout", "three"), ("exit", "0")
        )
        result = await backend.aexec(sandbox, ["true"], timeout=5)
        assert result.stdout == "onetwothree"

    async def test_events_split_across_chunks_decode_correctly(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """One byte per chunk splits every event boundary and every multi-byte
        character, which is what a real network is free to do."""
        fake_islo.events = in_chunks(
            sse(("stdout", "héllo 🌍"), ("stderr", "warnûng"), ("exit", "0"))
        )
        result = await backend.aexec(sandbox, ["true"], timeout=5)

        assert result.stdout == "héllo 🌍"
        assert result.stderr == "warnûng"
        assert result.exit_code == 0

    async def test_carriage_returns_from_the_wire_are_not_kept(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """SSE line endings are CRLF on the wire; only the payload is the
        command's output."""
        fake_islo.events = (
            b"event: stdout\r\ndata: hi\r\n\r\nevent: exit\r\ndata: 0\r\n\r\n"
        )
        result = await backend.aexec(sandbox, ["true"], timeout=5)
        assert (result.stdout, result.exit_code) == ("hi", 0)

    @pytest.mark.parametrize("split_at", range(1, 40))
    async def test_crlf_framing_survives_any_chunk_boundary(
        self,
        backend: IsloSandbox,
        fake_islo: FakeIslo,
        sandbox: Sandbox,
        split_at: int,
    ) -> None:
        """A CRLF stream must decode identically wherever the network splits it.

        The dangerous boundary falls between the CR and the LF of an event
        terminator: normalizing each chunk on its own leaves that `\\r\\n`
        un-normalized, which merges two events into one and loses the exit event
        for a command that in fact succeeded.
        """
        wire = b"event: stdout\r\ndata: hi\r\n\r\nevent: exit\r\ndata: 0\r\n\r\n"

        async def split() -> AsyncIterator[bytes]:
            yield wire[:split_at]
            yield wire[split_at:]

        fake_islo.events = split()
        result = await backend.aexec(sandbox, ["true"], timeout=5)
        assert (result.stdout, result.exit_code) == ("hi", 0)

    async def test_a_stream_held_open_after_the_exit_event_does_not_time_out(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """The exit event ends the command, not the closing of the connection.

        Nothing in the API promises the body closes promptly afterwards, and a
        keep-alive or a buffering proxy holding it open must not turn a command
        that exited 0 into a timeout — which would also destroy the sandbox.
        """
        fake_islo.events = then_stalls(sse(("stdout", "ok"), ("exit", "0")))
        result = await backend.aexec(sandbox, ["true"], timeout=5)

        assert (result.exit_code, result.stdout) == (0, "ok")
        assert not result.timed_out
        assert not result.sandbox_terminated
        assert fake_islo.live == {sandbox.id}


class TestExecOutputCap:
    """Invariant 5: capped while streaming, never buffered then trimmed."""

    async def test_stdout_beyond_the_cap_is_dropped_and_flagged(
        self, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        backend = IsloSandbox(api_key=SecretStr(BLOCK_API_KEY), max_output_bytes=64)
        # Two orders of magnitude past the cap, delivered as many events: what is
        # retained is what bounds the worker's memory.
        fake_islo.events = sse(
            *[("stdout", "x" * 1024) for _ in range(64)], ("exit", "0")
        )

        result = await backend.aexec(sandbox, ["true"], timeout=5)

        assert len(result.stdout.encode()) == 64
        assert result.truncated
        assert result.exit_code == 0

    async def test_each_stream_is_capped_independently(
        self, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        backend = IsloSandbox(api_key=SecretStr(BLOCK_API_KEY), max_output_bytes=16)
        fake_islo.events = sse(
            ("stdout", "o" * 100), ("stderr", "e" * 100), ("exit", "0")
        )

        result = await backend.aexec(sandbox, ["true"], timeout=5)

        assert result.stdout == "o" * 16
        assert result.stderr == "e" * 16
        assert result.truncated

    async def test_output_exactly_at_the_cap_is_not_flagged(
        self, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        backend = IsloSandbox(api_key=SecretStr(BLOCK_API_KEY), max_output_bytes=8)
        fake_islo.events = sse(("stdout", "12345678"), ("exit", "0"))

        result = await backend.aexec(sandbox, ["true"], timeout=5)

        assert result.stdout == "12345678"
        assert not result.truncated

    async def test_the_cap_counts_bytes_not_characters(
        self, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """A guest that prints emoji must not be able to keep four times the cap."""
        backend = IsloSandbox(api_key=SecretStr(BLOCK_API_KEY), max_output_bytes=8)
        fake_islo.events = sse(("stdout", "🌍" * 4), ("exit", "0"))

        result = await backend.aexec(sandbox, ["true"], timeout=5)

        assert len(result.stdout.encode()) <= 8
        assert result.truncated
        # A character cut in half is replaced, not raised.
        assert result.stdout.startswith("🌍🌍")


class TestExecFailures:
    async def test_a_refused_stream_reports_the_providers_reason(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        fake_islo.replies(
            "exec",
            reply(
                429,
                {
                    "code": "RATE_LIMITED",
                    "message": "too many concurrent executions",
                },
            ),
        )

        with pytest.raises(SandboxExecutionError) as excinfo:
            await backend.aexec(sandbox, ["true"], timeout=5)

        message = str(excinfo.value)
        assert "RATE_LIMITED" in message
        assert "too many concurrent executions" in message
        assert "429" in message

    async def test_a_vanished_sandbox_is_an_execution_failure(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        with pytest.raises(SandboxExecutionError, match="SANDBOX_NOT_FOUND"):
            await backend.aexec(
                Sandbox(id="prefect-sandbox-gone", backend="islo"),
                ["true"],
                timeout=5,
            )

    async def test_a_stream_that_ends_without_an_exit_event_is_a_failure(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """Silence is not success: the command's fate is unknown."""
        fake_islo.events = sse(("stdout", "half the story"))

        with pytest.raises(SandboxExecutionError) as excinfo:
            await backend.aexec(sandbox, ["true"], timeout=5)

        message = str(excinfo.value)
        assert "without an exit event" in message
        assert "may still be running" in message

    async def test_a_connection_lost_before_the_exit_event_is_a_failure(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        fake_islo.events = then_drops(sse(("stdout", "partial")))

        with pytest.raises(SandboxExecutionError) as excinfo:
            await backend.aexec(sandbox, ["true"], timeout=5)

        assert "may still be running" in str(excinfo.value)

    async def test_a_connection_lost_after_the_exit_event_is_a_completed_command(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """The provider closes the stream at the moment the command exits, so a
        torn-down connection there is the normal ending, not a failure."""
        fake_islo.events = then_drops(sse(("stdout", "done"), ("exit", "7")))

        result = await backend.aexec(sandbox, ["true"], timeout=5)

        assert result.exit_code == 7
        assert result.stdout == "done"
        assert not result.timed_out

    async def test_a_rejected_token_on_the_stream_is_retried_once(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        fake_islo.replies(
            "exec",
            reply(401, {"code": "AUTH_REQUIRED", "message": "token expired"}),
            fake_islo.default,
        )
        fake_islo.events = sse(("stdout", "second attempt"), ("exit", "0"))

        result = await backend.aexec(sandbox, ["true"], timeout=5)

        assert result.stdout == "second attempt"
        first, second = fake_islo.requests_for("exec")
        assert first.bearer != second.bearer

    async def test_a_token_rejected_twice_on_the_stream_is_surfaced(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        fake_islo.replies(
            "exec", reply(401, {"code": "AUTH_REQUIRED", "message": "still no"})
        )

        with pytest.raises(SandboxExecutionError, match="still no"):
            await backend.aexec(sandbox, ["true"], timeout=5)

        assert len(fake_islo.requests_for("exec")) == 2


class TestExecTimeout:
    """Invariant 6: `timed_out` only when the budget actually fired."""

    async def test_an_overrun_destroys_the_sandbox_and_keeps_what_was_printed(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """Abandoning the stream would not stop the guest process, so enforcing
        the wall clock costs the sandbox."""
        fake_islo.events = then_stalls(sse(("stdout", "printed before the deadline")))

        result = await backend.aexec(sandbox, ["sleep", "3600"], timeout=0.05)

        assert result.timed_out
        assert result.sandbox_terminated
        assert result.exit_code == -1
        assert result.stdout == "printed before the deadline"
        assert "destroyed" in result.stderr
        assert fake_islo.requests_for("delete")
        assert fake_islo.live == set()

    async def test_an_overrun_does_not_claim_termination_when_deletion_fails(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        fake_islo.events = then_stalls(b"")
        fake_islo.replies(
            "delete", reply(500, {"code": "INTERNAL_ERROR", "message": "cannot delete"})
        )

        with pytest.raises(SandboxError, match="may still be running"):
            await backend.aexec(sandbox, ["sleep", "3600"], timeout=0.05)

        assert sandbox.id in fake_islo.live

    async def test_a_command_that_exits_124_is_not_mislabeled_as_timed_out(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """124 is what the guest's own `timeout` utility reports; only the
        backend's wall clock firing makes a result a timeout."""
        fake_islo.events = sse(("exit", "124"))

        result = await backend.aexec(sandbox, ["true"], timeout=5)

        assert result.exit_code == 124
        assert not result.timed_out
        assert not result.sandbox_terminated
        assert sandbox.id in fake_islo.live


class TestDestroy:
    async def test_deletes_the_sandbox_by_name(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        await backend.adestroy(sandbox)

        (deleted,) = fake_islo.requests_for("delete")
        assert deleted.method == "DELETE"
        assert deleted.path == f"/sandboxes/{sandbox.id}"
        assert fake_islo.live == set()

    async def test_a_name_needing_escaping_stays_inside_its_path_segment(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        """The name is interpolated into a URL, so it is escaped rather than
        trusted to be URL-safe."""
        await backend.adestroy(Sandbox(id="../other-tenant", backend="islo"))
        assert fake_islo.requests_for("delete")[0].url.raw_path == (
            b"/sandboxes/..%2Fother-tenant"
        )

    async def test_is_idempotent_when_the_sandbox_is_already_gone(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """Invariant 3."""
        await backend.adestroy(sandbox)
        await backend.adestroy(sandbox)
        assert len(fake_islo.requests_for("delete")) == 2

    async def test_a_not_found_body_also_counts_as_already_gone(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """Some deployments answer a missing sandbox with the structured code
        rather than a 404, and both mean the same thing."""
        fake_islo.replies(
            "delete",
            reply(400, {"code": "SANDBOX_NOT_FOUND", "message": "already deleted"}),
        )
        await backend.adestroy(sandbox)

    async def test_destroying_a_handle_that_was_never_created_succeeds(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        await backend.adestroy(Sandbox(id="prefect-sandbox-never", backend="islo"))
        assert fake_islo.requests_for("delete")

    async def test_any_other_failure_is_loud_because_code_may_still_run(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        fake_islo.replies(
            "delete",
            reply(500, {"code": "INTERNAL_ERROR", "message": "hypervisor unreachable"}),
        )

        with pytest.raises(SandboxError) as excinfo:
            await backend.adestroy(sandbox)

        message = str(excinfo.value)
        assert "may still be running" in message
        assert "hypervisor unreachable" in message
        assert sandbox.id in fake_islo.live

    async def test_destroying_one_sandbox_leaves_the_other_alone(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        """Invariant 1: one shared backend, two flow runs, no crosstalk."""
        first, second = await asyncio.gather(backend.acreate(), backend.acreate())

        await backend.adestroy(first)

        assert fake_islo.live == {second.id}


class TestWriteFile:
    async def test_uploads_the_content_to_the_files_endpoint(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        await backend.awrite_file(sandbox, "/work/dir/main.py", "print('hi')\n")

        (uploaded,) = fake_islo.requests_for("files")
        assert uploaded.method == "POST"
        assert uploaded.path == f"/sandboxes/{sandbox.id}/files"
        assert uploaded.url.params["path"] == "/work/dir/main.py"
        assert b'name="file"' in uploaded.content
        assert b'filename="main.py"' in uploaded.content
        assert b"print('hi')\n" in uploaded.content

    async def test_creates_the_parent_directory_first(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """The upload endpoint writes one file; it does not create parents."""
        await backend.awrite_file(sandbox, "/work/dir/main.py", "x")

        (prepared,) = fake_islo.requests_for("exec")
        assert prepared.body["command"] == ["mkdir", "-p", "/work/dir"]
        assert fake_islo.requests.index(prepared) < fake_islo.requests.index(
            fake_islo.requests_for("files")[0]
        )

    async def test_no_directory_is_created_for_a_bare_filename(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        await backend.awrite_file(sandbox, "main.py", "x")
        assert fake_islo.requests_for("exec") == []
        assert fake_islo.requests_for("files")[0].url.params["path"] == "main.py"

    async def test_is_not_bound_by_the_inline_fallback_ceiling(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        """The base fallback smuggles the payload through the command line and is
        capped; a native upload is bounded only by the sandbox's disk."""
        content = "y" * (MAX_INLINE_FILE_BYTES * 4)

        await backend.awrite_file(sandbox, "/work/big.txt", content)

        assert content.encode() in fake_islo.requests_for("files")[0].content

    async def test_content_is_uploaded_verbatim(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        content = "quotes ' \" $(id)\nunicode héllo 🌍\n"
        await backend.awrite_file(sandbox, "/work/tricky.txt", content)
        assert content.encode() in fake_islo.requests_for("files")[0].content

    async def test_a_failed_upload_names_the_path(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        fake_islo.replies(
            "files",
            reply(507, {"code": "RESOURCE_UNAVAILABLE", "message": "no space left"}),
        )

        with pytest.raises(SandboxError) as excinfo:
            await backend.awrite_file(sandbox, "/work/main.py", "x")

        message = str(excinfo.value)
        assert "/work/main.py" in message
        assert "no space left" in message

    async def test_a_failed_directory_creation_stops_before_uploading(
        self, backend: IsloSandbox, fake_islo: FakeIslo, sandbox: Sandbox
    ) -> None:
        fake_islo.events = sse(("stderr", "Read-only file system"), ("exit", "1"))

        with pytest.raises(SandboxError, match="/work/dir"):
            await backend.awrite_file(sandbox, "/work/dir/main.py", "x")

        assert fake_islo.requests_for("files") == []


class TestSession:
    async def test_provisions_and_destroys(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        async with backend.asession() as handle:
            assert fake_islo.live == {handle.id}
        assert fake_islo.live == set()

    async def test_destroys_the_sandbox_when_the_body_raises(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        with pytest.raises(RuntimeError, match="boom"):
            async with backend.asession():
                raise RuntimeError("boom")
        assert fake_islo.live == set()

    async def test_concurrent_sessions_get_their_own_sandbox(
        self, backend: IsloSandbox, fake_islo: FakeIslo
    ) -> None:
        async def run(marker: str) -> str:
            async with backend.asession() as handle:
                await backend.aexec(handle, ["echo", marker], timeout=5)
                return handle.id

        first, second = await asyncio.gather(run("first"), run("second"))

        assert first != second
        assert fake_islo.live == set()
