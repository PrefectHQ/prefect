"""One suite every sandbox provider must satisfy, run against both shipped backends.

`prefect_sandbox.base` claims to be vendor-neutral. The only way to keep that claim
honest is to state its rules once and run them against every implementation, so this
module contains no per-provider assertions at all: each test body talks to a
`ProviderFake`, and the two subclasses of it are the only code that knows whether it is
driving a REST API or a CLI.

A third-party provider onboards by copying this file, implementing one more
`ProviderFake`, and adding it to the `provider` fixture's parameters. Nothing here may
therefore assert anything the base contract does not promise — a rule that has real
teeth, because the two shipped backends already disagree about plenty of things the
contract deliberately leaves open (what a vanished sandbox looks like to `aexec`,
whether output printed before a timeout survives, what lands in `Sandbox.metadata`).

Two scoping notes on the fakes:

- The `sbx` fake is the executable `test_sbx` installs on PATH, imported rather than
  reimplemented so there is exactly one description of that CLI's behaviour in the
  suite. It is POSIX-only, and `test_sbx` skips at module level elsewhere, which skips
  this module with it.
- Invariant 7 is checked on the wire: what the backend *sends the provider* to describe
  the command. That is the right level for a portable check, because a backend may
  legitimately hand its own credentials to its own control plane — `sbx` inherits the
  worker environment so it can reach the host's Docker config, and Islo sends a session
  token in a header. Neither is something the guest sees; what the guest sees is the
  request described here.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import re
from abc import ABC, abstractmethod
from pathlib import Path

import httpx
import pytest
from prefect_sandbox.base import (
    SANDBOX_NAME_PREFIX,
    SandboxBackend,
    SandboxCreationError,
    SandboxExecutionError,
)
from prefect_sandbox.islo import IsloSandbox
from prefect_sandbox.sbx import SbxSandbox
from pydantic import SecretStr

# The fake `sbx` CLI is imported rather than reimplemented, so `test_sbx` stays the one
# description of that provider's behaviour. Importing the fixture is what registers it
# for this module; ruff cannot see a fixture being used, hence the suppression.
from test_sbx import FakeSbx, fake_sbx  # noqa: F401

#: Base URL the Islo fake answers on. Never resolved: every request is served in
#: process by an `httpx.MockTransport`.
_ISLO_BASE_URL = "https://api.islo.test"

#: Session token the fake hands back. Deliberately not a JWT, which exercises the
#: backend's fallback lifetime rather than requiring a clock to be manipulated.
_ISLO_SESSION_TOKEN = "conformance-session-token"

#: Worker environment a sandboxed command must never be handed. The values are
#: distinctive so a leak anywhere in a request is detectable by substring.
_WORKER_ENVIRONMENT = {
    "PREFECT_API_KEY": "pnu-conformance-canary",
    "PREFECT_API_URL": "https://api.prefect.cloud/conformance-canary",
    "AWS_SECRET_ACCESS_KEY": "conformance-aws-canary",
}

#: Requests `validate_exec_request` rejects, with the message the contract promises.
#: Every provider must reject these identically, which is what lets a caller validate
#: input once instead of per backend.
_INVALID_EXEC_REQUESTS = [
    pytest.param(
        {"command": [], "timeout": 5}, "command must not be empty.", id="empty"
    ),
    pytest.param(
        {"command": ["true"], "timeout": 0},
        "timeout must be a positive, finite number: 0",
        id="zero-timeout",
    ),
    pytest.param(
        {"command": ["true"], "timeout": -1},
        "timeout must be a positive, finite number: -1",
        id="negative-timeout",
    ),
    pytest.param(
        {"command": ["true"], "timeout": float("inf")},
        "timeout must be a positive, finite number: inf",
        id="infinite-timeout",
    ),
    pytest.param(
        {"command": ["true"], "timeout": float("nan")},
        "timeout must be a positive, finite number: nan",
        id="nan-timeout",
    ),
    pytest.param(
        {"command": ["true"], "timeout": 5, "env": {"BAD=NAME": "value"}},
        "Invalid environment variable name: 'BAD=NAME'",
        id="inexpressible-env-name",
    ),
    pytest.param(
        {"command": ["true"], "timeout": 5, "env": {"FOO": "ba\0r"}},
        "Environment variable 'FOO' contains a null byte.",
        id="null-byte-in-env-value",
    ),
]


@dataclasses.dataclass
class Script:
    """What a fake provider makes the next command do."""

    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    hang: bool = False


class ProviderFake(ABC):
    """A shipped backend wired to a fake of the provider behind it.

    The suite reaches a provider only through this interface, so no test body has to
    know which backend it is exercising. Everything a conformance assertion needs —
    scripting a command's outcome, making provisioning fail, observing what the
    provider was asked to do — is named once here and implemented once per provider.
    """

    #: Backend under test, built by `new_backend` when the fake is constructed.
    backend: SandboxBackend

    @abstractmethod
    def new_backend(self, **overrides: object) -> SandboxBackend:
        """Build another backend instance wired to this same fake provider."""

    @abstractmethod
    def script(self, *, exit_code: int = 0, stdout: str = "", stderr: str = "") -> None:
        """Make every subsequent command report this outcome."""

    @abstractmethod
    def script_hang(self) -> None:
        """Make every subsequent command never return."""

    @abstractmethod
    def fail_next_create(self) -> None:
        """Fail the next provisioning request after the provider took the name.

        The sandbox is left alive on purpose: invariant 4 is only interesting when
        there is something for the failure path to clean up.
        """

    @abstractmethod
    def forget(self, name: str) -> None:
        """Drop `name` from the provider, as if it had already been reaped."""

    @abstractmethod
    def destroy_attempts(self, name: str) -> int:
        """How many times teardown of `name` was requested."""

    @property
    @abstractmethod
    def live_sandboxes(self) -> set[str]:
        """Names the provider currently believes exist."""

    @property
    @abstractmethod
    def provisioned_names(self) -> list[str]:
        """Names the provider was asked to provision, in order."""

    @property
    @abstractmethod
    def exec_targets(self) -> list[str]:
        """The sandbox each command was addressed to, in order."""

    @property
    @abstractmethod
    def last_exec_request(self) -> str:
        """Everything the backend sent to describe the last command, as text.

        Flattened, because the two providers carry a command over different wires — an
        argv and a JSON body — and the invariant is a claim about what is in there
        rather than about its shape.
        """

    @property
    @abstractmethod
    def host_residue(self) -> set[str]:
        """State the backend created outside the provider and still owns."""

    @property
    @abstractmethod
    def interactions(self) -> int:
        """How many times the provider has been contacted at all."""


class SbxProviderFake(ProviderFake):
    """`SbxSandbox` driven through the fake `sbx` executable on PATH."""

    def __init__(self, fake: FakeSbx) -> None:
        self._fake = fake
        # Without a scripted outcome the fake CLI executes the argv it was handed, so
        # every conformance command would have to be a real host program.
        self.script()
        self.backend = self.new_backend()

    def new_backend(self, **overrides: object) -> SandboxBackend:
        """Build a backend that resolves `sbx` by name, exactly as a user's would."""
        return SbxSandbox(create_timeout=60.0, **overrides)  # type: ignore[arg-type]

    def script(self, *, exit_code: int = 0, stdout: str = "", stderr: str = "") -> None:
        """Make every subsequent `sbx exec` report this outcome."""
        self._fake.configure(
            "exec", exit=exit_code, stdout=stdout, stderr=stderr, mode=None
        )

    def script_hang(self) -> None:
        """Make every subsequent `sbx exec` never return."""
        self._fake.configure("exec", mode="hang")

    def fail_next_create(self) -> None:
        """Make `sbx create` fail while still leaving a microVM behind."""
        self._fake.configure("create", exit=1, stderr="Error: invalid memory value\n")

    def forget(self, name: str) -> None:
        """Delete the fake's record of `name`, so `sbx rm` reports it missing."""
        (self._fake.root / "sandboxes" / name).unlink()

    def destroy_attempts(self, name: str) -> int:
        """How many `sbx rm -f <name>` invocations there were."""
        removals = self._fake.calls_for("rm")
        return len([argv for argv in removals if argv and argv[-1] == name])

    @property
    def live_sandboxes(self) -> set[str]:
        """Names the fake CLI currently believes exist."""
        return self._fake.live_sandboxes

    @property
    def provisioned_names(self) -> list[str]:
        """The `--name` of every `sbx create`, in order."""
        return [
            argv[argv.index("--name") + 1] for argv in self._fake.calls_for("create")
        ]

    @property
    def exec_targets(self) -> list[str]:
        """The sandbox named by each `sbx exec`, in order."""
        return [self._exec_target(argv) for argv in self._fake.calls_for("exec")]

    @property
    def last_exec_request(self) -> str:
        """The last `sbx exec` argv, flattened."""
        return " ".join(self._fake.calls_for("exec")[-1])

    @property
    def host_residue(self) -> set[str]:
        """Workspace directories the backend created on the host and left behind."""
        return {
            argv[-1]
            for argv in self._fake.calls_for("create")
            if Path(argv[-1]).exists()
        }

    @property
    def interactions(self) -> int:
        """How many times the CLI was invoked at all."""
        return len(self._fake.calls)

    @staticmethod
    def _exec_target(argv: list[str]) -> str:
        """Pull the sandbox name out of an `sbx exec` argv."""
        rest = argv[1:]
        while rest and rest[0] in ("-e", "-w", "-u"):
            rest = rest[2:]
        return rest[0]


class IsloProviderFake(ProviderFake):
    """`IsloSandbox` driven against an in-process stand-in for the Islo REST API.

    The backend builds a fresh client for every call, so replacing that one factory
    puts the whole REST surface — token exchange, provisioning, the SSE exec stream,
    deletion — behind an `httpx.MockTransport` without touching a socket.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._sandboxes: dict[str, str] = {}
        self._script = Script()
        self._fail_create = False
        self._requests: list[tuple[str, str, str]] = []
        # A real key or URL in the developer's environment must not change what these
        # tests exercise.
        monkeypatch.delenv("ISLO_API_KEY", raising=False)
        monkeypatch.delenv("ISLO_API_URL", raising=False)
        monkeypatch.setattr(IsloSandbox, "_new_client", self._client)
        self.backend = self.new_backend()

    def new_backend(self, **overrides: object) -> SandboxBackend:
        """Build a backend whose every client is routed to this fake."""
        return IsloSandbox(
            api_key=SecretStr("conformance-api-key"),
            api_url=_ISLO_BASE_URL,
            **overrides,  # type: ignore[arg-type]
        )

    def script(self, *, exit_code: int = 0, stdout: str = "", stderr: str = "") -> None:
        """Make every subsequent exec stream report this outcome."""
        self._script = Script(exit_code=exit_code, stdout=stdout, stderr=stderr)

    def script_hang(self) -> None:
        """Make every subsequent exec stream never produce a response."""
        self._script = Script(hang=True)

    def fail_next_create(self) -> None:
        """Reject the next `POST /sandboxes` after the sandbox already exists.

        Provisioning that fails only once the microVM is live is the case the cleanup
        path exists for; a request rejected before anything was allocated would prove
        nothing.
        """
        self._fail_create = True

    def forget(self, name: str) -> None:
        """Drop `name`, so the API reports `SANDBOX_NOT_FOUND` for it."""
        del self._sandboxes[name]

    def destroy_attempts(self, name: str) -> int:
        """How many `DELETE /sandboxes/{name}` requests there were."""
        return len(
            [
                path
                for method, path, _ in self._requests
                if method == "DELETE" and path == f"/sandboxes/{name}"
            ]
        )

    @property
    def live_sandboxes(self) -> set[str]:
        """Names the fake API currently believes exist."""
        return set(self._sandboxes)

    @property
    def provisioned_names(self) -> list[str]:
        """The name in every `POST /sandboxes` body, in order."""
        return [
            json.loads(body)["name"]
            for method, path, body in self._requests
            if method == "POST" and path == "/sandboxes"
        ]

    @property
    def exec_targets(self) -> list[str]:
        """The sandbox in the path of every exec stream request, in order."""
        return [
            path.split("/")[2]
            for _, path, _ in self._requests
            if path.endswith("/exec/stream")
        ]

    @property
    def last_exec_request(self) -> str:
        """The last exec stream request body."""
        return [
            body for _, path, body in self._requests if path.endswith("/exec/stream")
        ][-1]

    @property
    def host_residue(self) -> set[str]:
        """Nothing: a hosted provider leaves the worker's host untouched."""
        return set()

    @property
    def interactions(self) -> int:
        """How many API requests were made at all."""
        return len(self._requests)

    def _client(
        self, *, token: str | None, timeout: float | httpx.Timeout
    ) -> httpx.AsyncClient:
        """Stand in for `IsloSandbox._new_client`, routing every call to this fake."""
        return httpx.AsyncClient(
            base_url=_ISLO_BASE_URL,
            timeout=timeout,
            transport=httpx.MockTransport(self._handle),
            headers={"Authorization": f"Bearer {token}"} if token else {},
        )

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        """Answer one request the way the documented Islo API would."""
        path = request.url.path
        body = request.content.decode(errors="replace")
        self._requests.append((request.method, path, body))

        if path == "/auth/token":
            return httpx.Response(200, json={"session_token": _ISLO_SESSION_TOKEN})
        if request.method == "POST" and path == "/sandboxes":
            name = json.loads(body)["name"]
            self._sandboxes[name] = f"vm-{name}"
            if self._fail_create:
                self._fail_create = False
                return self._error(500, "INTERNAL_ERROR", "no capacity in this region")
            return httpx.Response(201, json=self._describe(name))

        name = path.split("/")[2]
        if name not in self._sandboxes:
            return self._error(404, "SANDBOX_NOT_FOUND", f"no sandbox named {name!r}")
        if request.method == "DELETE":
            del self._sandboxes[name]
            return httpx.Response(204)
        if request.method == "GET":
            return httpx.Response(200, json=self._describe(name))
        if path.endswith("/exec/stream"):
            if self._script.hang:
                # Released only by the caller's own deadline cancelling this request.
                await asyncio.Event().wait()
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=_server_sent_events(self._script),
            )
        return self._error(404, "VALIDATION_ERROR", f"unroutable path {path!r}")

    def _describe(self, name: str) -> dict[str, str]:
        """Body the API returns for one sandbox."""
        return {
            "id": self._sandboxes[name],
            "name": name,
            "status": "running",
            "image": "docker.io/library/islo-runner:latest",
            "created_at": "2026-01-01T00:00:00Z",
        }

    @staticmethod
    def _error(status: int, code: str, message: str) -> httpx.Response:
        """The API's structured error shape."""
        return httpx.Response(status, json={"code": code, "message": message})


def _server_sent_events(script: Script) -> bytes:
    """Encode a scripted outcome as the SSE body the exec endpoint returns."""
    events: list[tuple[str, str]] = []
    if script.stdout:
        events.append(("stdout", script.stdout))
    if script.stderr:
        events.append(("stderr", script.stderr))
    events.append(("exit", str(script.exit_code)))
    return "".join(
        "event: {}\n{}\n".format(
            name, "".join(f"data: {line}\n" for line in data.split("\n"))
        )
        for name, data in events
    ).encode()


@pytest.fixture
def sbx_provider(request: pytest.FixtureRequest) -> SbxProviderFake:
    """`SbxSandbox` wired to the fake CLI `test_sbx` installs on PATH.

    The fake is requested by name because a parameter called `fake_sbx` would shadow
    the import that makes it available here.
    """
    fake: FakeSbx = request.getfixturevalue("fake_sbx")
    return SbxProviderFake(fake)


@pytest.fixture
def islo_provider(monkeypatch: pytest.MonkeyPatch) -> IsloProviderFake:
    """`IsloSandbox` wired to an in-process fake of the Islo REST API."""
    return IsloProviderFake(monkeypatch)


@pytest.fixture(params=["islo", "sbx"])
def provider(request: pytest.FixtureRequest) -> ProviderFake:
    """Run the test that requests this once per shipped backend."""
    fake: ProviderFake = request.getfixturevalue(f"{request.param}_provider")
    return fake


class TestBackendIdentity:
    """A backend names itself, and that name reaches every handle it hands out."""

    def test_the_backend_name_is_a_non_empty_string(
        self, provider: ProviderFake
    ) -> None:
        assert isinstance(type(provider.backend).backend_name, str)
        assert type(provider.backend).backend_name

    def test_the_backend_name_is_not_a_configurable_field(
        self, provider: ProviderFake
    ) -> None:
        # As a field it would enter the block schema and saved block documents, and a
        # saved block could then claim to be a different provider.
        assert "backend_name" not in type(provider.backend).model_fields

    async def test_the_backend_name_lands_on_the_handle(
        self, provider: ProviderFake
    ) -> None:
        sandbox = await provider.backend.acreate()
        assert sandbox.backend == type(provider.backend).backend_name

    async def test_a_generated_name_is_identifiable_as_prefects(
        self, provider: ProviderFake
    ) -> None:
        """The prefix is how an operator finds orphans in a vendor console."""
        sandbox = await provider.backend.acreate()
        assert sandbox.id.startswith(SANDBOX_NAME_PREFIX)
        assert provider.provisioned_names == [sandbox.id]


class TestConstruction:
    """Invariant 2: Block instances are built at import time, so construction is free."""

    def test_construction_contacts_no_provider(self, provider: ProviderFake) -> None:
        before = provider.interactions
        provider.new_backend()
        assert provider.interactions == before


class TestExecOutcome:
    """Invariant 8: a command's exit status is data, not an exception."""

    async def test_a_nonzero_exit_is_returned_rather_than_raised(
        self, provider: ProviderFake
    ) -> None:
        provider.script(exit_code=3, stdout="out", stderr="err")
        sandbox = await provider.backend.acreate()

        result = await provider.backend.aexec(sandbox, ["whatever"], timeout=5)

        assert (result.exit_code, result.stdout, result.stderr) == (3, "out", "err")
        assert not result.timed_out
        assert not result.sandbox_terminated
        # A command that merely failed does not cost its sandbox.
        assert provider.live_sandboxes == {sandbox.id}

    async def test_ok_and_raise_for_status_agree_with_a_nonzero_exit(
        self, provider: ProviderFake
    ) -> None:
        provider.script(exit_code=3, stderr="err")
        sandbox = await provider.backend.acreate()

        result = await provider.backend.aexec(sandbox, ["whatever"], timeout=5)

        assert result.ok is False
        with pytest.raises(SandboxExecutionError, match="exit code 3"):
            result.raise_for_status()

    async def test_ok_and_raise_for_status_agree_with_a_zero_exit(
        self, provider: ProviderFake
    ) -> None:
        provider.script(exit_code=0, stdout="done")
        sandbox = await provider.backend.acreate()

        result = await provider.backend.aexec(sandbox, ["whatever"], timeout=5)

        assert result.ok is True
        assert result.raise_for_status() is None
        assert not result.truncated

    async def test_the_streams_stay_separate(self, provider: ProviderFake) -> None:
        provider.script(stdout="out", stderr="err")
        sandbox = await provider.backend.acreate()

        result = await provider.backend.aexec(sandbox, ["whatever"], timeout=5)

        assert (result.stdout, result.stderr) == ("out", "err")


class TestOutputCap:
    """Invariant 5: output is capped as it streams, and flagged when the cap bites."""

    async def test_output_over_the_cap_is_flagged_and_bounded(
        self, provider: ProviderFake
    ) -> None:
        flood = "x" * 4096
        provider.script(exit_code=0, stdout=flood)
        backend = provider.new_backend(max_output_bytes=64)
        sandbox = await backend.acreate()

        result = await backend.aexec(sandbox, ["whatever"], timeout=30)

        assert result.truncated
        assert len(result.stdout.encode()) <= 64
        assert flood.startswith(result.stdout)
        # The cap bounds what is kept; it does not turn a finished command into a
        # failure, and it does not lose the exit status.
        assert result.exit_code == 0

    async def test_stderr_is_capped_as_well(self, provider: ProviderFake) -> None:
        flood = "y" * 4096
        provider.script(exit_code=0, stderr=flood)
        backend = provider.new_backend(max_output_bytes=64)
        sandbox = await backend.acreate()

        result = await backend.aexec(sandbox, ["whatever"], timeout=30)

        assert result.truncated
        assert len(result.stderr.encode()) <= 64
        assert flood.startswith(result.stderr)

    async def test_output_exactly_at_the_cap_is_not_flagged(
        self, provider: ProviderFake
    ) -> None:
        provider.script(exit_code=0, stdout="x" * 64)
        backend = provider.new_backend(max_output_bytes=64)
        sandbox = await backend.acreate()

        result = await backend.aexec(sandbox, ["whatever"], timeout=30)

        assert result.stdout == "x" * 64
        assert not result.truncated


class TestTimeout:
    """Invariant 6: `timed_out` is set only when the deadline actually fired."""

    async def test_a_command_that_never_returns_times_out(
        self, provider: ProviderFake
    ) -> None:
        provider.script_hang()
        sandbox = await provider.backend.acreate()

        result = await provider.backend.aexec(sandbox, ["whatever"], timeout=0.5)

        assert result.timed_out
        assert not result.ok
        with pytest.raises(SandboxExecutionError, match="timed out"):
            result.raise_for_status()

    async def test_a_timeout_that_cost_the_sandbox_says_so(
        self, provider: ProviderFake
    ) -> None:
        """Abandoning the call does not stop the guest, so the sandbox has to go —
        and the caller has to be told the handle is dead."""
        provider.script_hang()
        sandbox = await provider.backend.acreate()

        result = await provider.backend.aexec(sandbox, ["whatever"], timeout=0.5)

        assert result.sandbox_terminated
        assert provider.destroy_attempts(sandbox.id) >= 1
        assert provider.live_sandboxes == set()

    async def test_an_exit_code_that_looks_like_a_timeout_is_not_one(
        self, provider: ProviderFake
    ) -> None:
        # 124 is what `timeout(1)` reports, so inferring a timeout from the code would
        # mislabel a command that chose it.
        provider.script(exit_code=124)
        sandbox = await provider.backend.acreate()

        result = await provider.backend.aexec(sandbox, ["whatever"], timeout=30)

        assert result.exit_code == 124
        assert not result.timed_out
        assert not result.sandbox_terminated
        assert provider.live_sandboxes == {sandbox.id}


class TestExecRequestValidation:
    """`validate_exec_request` is shared, so every provider rejects the same inputs."""

    @pytest.mark.parametrize(("kwargs", "message"), _INVALID_EXEC_REQUESTS)
    async def test_the_same_request_is_rejected_with_the_same_message(
        self, provider: ProviderFake, kwargs: dict[str, object], message: str
    ) -> None:
        sandbox = await provider.backend.acreate()

        with pytest.raises(ValueError, match=re.escape(message)):
            await provider.backend.aexec(sandbox, **kwargs)  # type: ignore[arg-type]

        # Validation is refusal, not a failed attempt: nothing may reach the provider.
        assert provider.exec_targets == []


class TestDestroy:
    """Invariant 3: teardown is idempotent."""

    async def test_destroy_removes_the_sandbox(self, provider: ProviderFake) -> None:
        sandbox = await provider.backend.acreate()

        await provider.backend.adestroy(sandbox)

        assert provider.live_sandboxes == set()
        assert provider.host_residue == set()

    async def test_destroy_can_be_called_twice(self, provider: ProviderFake) -> None:
        sandbox = await provider.backend.acreate()

        await provider.backend.adestroy(sandbox)
        await provider.backend.adestroy(sandbox)

        assert provider.destroy_attempts(sandbox.id) == 2
        assert provider.live_sandboxes == set()

    async def test_destroying_a_sandbox_the_provider_already_reaped_succeeds(
        self, provider: ProviderFake
    ) -> None:
        """A provider-side reaper, or an operator, can remove a sandbox first."""
        sandbox = await provider.backend.acreate()
        provider.forget(sandbox.id)

        await provider.backend.adestroy(sandbox)

        assert provider.destroy_attempts(sandbox.id) == 1


class TestCreateFailure:
    """Invariant 4: a failed `acreate` leaves nothing behind."""

    async def test_a_failed_create_tears_down_the_name_it_claimed(
        self, provider: ProviderFake
    ) -> None:
        provider.fail_next_create()

        with pytest.raises(SandboxCreationError):
            await provider.backend.acreate()

        (name,) = provider.provisioned_names
        assert provider.destroy_attempts(name) >= 1
        assert provider.live_sandboxes == set()
        assert provider.host_residue == set()


class TestSession:
    """`asession` exists to make teardown unconditional."""

    async def test_the_sandbox_is_destroyed_on_the_way_out(
        self, provider: ProviderFake
    ) -> None:
        async with provider.backend.asession() as sandbox:
            assert provider.live_sandboxes == {sandbox.id}
        assert provider.live_sandboxes == set()

    async def test_the_sandbox_is_destroyed_when_the_body_raises(
        self, provider: ProviderFake
    ) -> None:
        with pytest.raises(RuntimeError, match="boom"):
            async with provider.backend.asession() as sandbox:
                raise RuntimeError("boom")

        assert provider.destroy_attempts(sandbox.id) >= 1
        assert provider.live_sandboxes == set()

    async def test_the_sandbox_is_destroyed_when_the_body_is_cancelled(
        self, provider: ProviderFake
    ) -> None:
        """A cancelled flow run is the common case, not an exotic one."""
        entered = asyncio.Event()

        async def work() -> None:
            async with provider.backend.asession():
                entered.set()
                await asyncio.sleep(3600)

        task = asyncio.ensure_future(work())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert provider.live_sandboxes == set()
        assert provider.host_residue == set()


class TestHandleIsolation:
    """Invariant 1: per-sandbox state lives on the handle, never on the backend."""

    async def test_one_backend_serves_two_concurrent_sandboxes(
        self, provider: ProviderFake
    ) -> None:
        backend = provider.backend
        first, second = await asyncio.gather(backend.acreate(), backend.acreate())
        assert first.id != second.id
        assert provider.live_sandboxes == {first.id, second.id}

        await backend.aexec(first, ["whatever"], timeout=5)
        await backend.aexec(second, ["whatever"], timeout=5)
        assert provider.exec_targets == [first.id, second.id]

        await backend.adestroy(first)

        # Ending one run neither removes nor breaks the other's sandbox.
        assert provider.live_sandboxes == {second.id}
        result = await backend.aexec(second, ["whatever"], timeout=5)
        assert result.ok
        assert provider.exec_targets[-1] == second.id

    async def test_another_instance_can_destroy_a_sandbox_it_did_not_create(
        self, provider: ProviderFake
    ) -> None:
        """The handle carries everything teardown needs, so a worker restart — or a
        second block instance — can still clean up."""
        sandbox = await provider.backend.acreate()

        await provider.new_backend().adestroy(sandbox)

        assert provider.live_sandboxes == set()

    async def test_two_concurrent_sessions_destroy_only_their_own_sandbox(
        self, provider: ProviderFake
    ) -> None:
        first_ready = asyncio.Event()
        second_ready = asyncio.Event()
        seen: dict[str, str] = {}

        async def first() -> None:
            async with provider.backend.asession() as sandbox:
                seen["first"] = sandbox.id
                first_ready.set()
                await second_ready.wait()

        async def second() -> None:
            async with provider.backend.asession() as sandbox:
                seen["second"] = sandbox.id
                await first_ready.wait()
            second_ready.set()

        await asyncio.gather(first(), second())

        assert seen["first"] != seen["second"]
        assert provider.destroy_attempts(seen["first"]) == 1
        assert provider.destroy_attempts(seen["second"]) == 1
        assert provider.live_sandboxes == set()


class TestAmbientCredentials:
    """Invariant 7: only what the caller passed in `env` reaches a command."""

    async def test_no_worker_environment_variable_is_forwarded(
        self, provider: ProviderFake, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name, value in _WORKER_ENVIRONMENT.items():
            monkeypatch.setenv(name, value)
        sandbox = await provider.backend.acreate()

        await provider.backend.aexec(
            sandbox, ["env"], timeout=5, env={"CALLER": "conformance-caller-value"}
        )

        request = provider.last_exec_request
        assert "CALLER" in request
        assert "conformance-caller-value" in request
        for name, value in _WORKER_ENVIRONMENT.items():
            assert name not in request
            assert value not in request

    async def test_a_command_with_no_env_carries_nothing(
        self, provider: ProviderFake, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name, value in _WORKER_ENVIRONMENT.items():
            monkeypatch.setenv(name, value)
        sandbox = await provider.backend.acreate()

        await provider.backend.aexec(sandbox, ["env"], timeout=5)

        request = provider.last_exec_request
        for name, value in _WORKER_ENVIRONMENT.items():
            assert name not in request
            assert value not in request
