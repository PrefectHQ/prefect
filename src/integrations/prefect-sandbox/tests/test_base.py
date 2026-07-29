"""The vendor-neutral contract in `prefect_sandbox.base`, tested on its own.

Nothing here touches a real sandbox provider. The subject is the part of the
package every backend inherits or is judged against: the result type, the
helpers a backend is expected to use, and the two pieces of behaviour the ABC
implements for its subclasses (`awrite_file`'s portable fallback and
`asession`'s guaranteed teardown).

`RecordingBackend` below is the smallest thing that satisfies the ABC. It is
also a stand-in for a third-party backend, so a test that passes here is
evidence the contract is satisfiable without a vendor SDK.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import ClassVar

import prefect_sandbox.base as base_module
import pytest
from prefect_sandbox.base import (
    DEFAULT_MAX_OUTPUT_BYTES,
    MAX_INLINE_FILE_BYTES,
    SANDBOX_NAME_PREFIX,
    Sandbox,
    SandboxBackend,
    SandboxError,
    SandboxExecutionError,
    SandboxResult,
    new_sandbox_name,
    validate_env,
)
from pydantic import PrivateAttr, ValidationError


@dataclasses.dataclass(frozen=True)
class ExecCall:
    """One recorded `aexec` invocation."""

    sandbox: Sandbox
    command: list[str]
    timeout: float
    env: dict[str, str]
    working_dir: str | None


class RecordingBackend(SandboxBackend):
    """In-memory backend that records what the contract asks of it.

    Implements only the three abstract methods, so everything else under test
    is inherited behaviour rather than behaviour this class supplies.
    """

    backend_name: ClassVar[str] = "recording"

    _created: list[Sandbox] = PrivateAttr(default_factory=list)
    _destroyed: list[str] = PrivateAttr(default_factory=list)
    _execs: list[ExecCall] = PrivateAttr(default_factory=list)
    _next_result: SandboxResult | None = PrivateAttr(default=None)
    # Set to have `adestroy` block until released, which is how the teardown
    # tests get a deterministic window to interrupt cleanup in.
    _destroy_gate: asyncio.Event | None = PrivateAttr(default=None)
    _destroy_started: asyncio.Event | None = PrivateAttr(default=None)

    @property
    def created(self) -> list[Sandbox]:
        return self._created

    @property
    def destroyed(self) -> list[str]:
        return self._destroyed

    @property
    def execs(self) -> list[ExecCall]:
        return self._execs

    def returns(self, result: SandboxResult) -> None:
        """Make the next (and every subsequent) `aexec` return `result`."""
        self._next_result = result

    async def acreate(self) -> Sandbox:
        await asyncio.sleep(0)
        sandbox = Sandbox(
            id=new_sandbox_name(),
            backend=self.backend_name,
            metadata={"seq": str(len(self._created))},
        )
        self._created.append(sandbox)
        return sandbox

    async def aexec(
        self,
        sandbox: Sandbox,
        command: Sequence[str],
        *,
        timeout: float,
        env: Mapping[str, str] | None = None,
        working_dir: str | None = None,
    ) -> SandboxResult:
        await asyncio.sleep(0)
        self._execs.append(
            ExecCall(
                sandbox=sandbox,
                command=list(command),
                timeout=timeout,
                env=dict(env or {}),
                working_dir=working_dir,
            )
        )
        return self._next_result or SandboxResult(exit_code=0, stdout="", stderr="")

    async def adestroy(self, sandbox: Sandbox) -> None:
        if self._destroy_started is not None:
            self._destroy_started.set()
        if self._destroy_gate is not None:
            await self._destroy_gate.wait()
        await asyncio.sleep(0)
        self._destroyed.append(sandbox.id)


@pytest.fixture
def backend() -> RecordingBackend:
    return RecordingBackend()


class TestSandboxResult:
    """`ok` and `raise_for_status` are the whole success/failure protocol."""

    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            ({"exit_code": 0}, True),
            ({"exit_code": 1}, False),
            ({"exit_code": 137}, False),
            ({"exit_code": -1}, False),
            # A timeout is a failure even when the reported code is 0, because
            # the code is meaningless once the budget fired.
            ({"exit_code": 0, "timed_out": True}, False),
            # Truncation and a lost sandbox say nothing about success.
            ({"exit_code": 0, "truncated": True}, True),
            ({"exit_code": 0, "sandbox_terminated": True}, True),
        ],
    )
    def test_ok(self, kwargs: dict[str, object], expected: bool) -> None:
        result = SandboxResult(stdout="", stderr="", **kwargs)  # type: ignore[arg-type]
        assert result.ok is expected

    def test_defaults(self) -> None:
        result = SandboxResult(exit_code=0, stdout="out", stderr="err")
        assert (result.timed_out, result.truncated, result.sandbox_terminated) == (
            False,
            False,
            False,
        )

    def test_is_immutable(self) -> None:
        result = SandboxResult(exit_code=0, stdout="", stderr="")
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.exit_code = 1  # type: ignore[misc]

    def test_raise_for_status_is_silent_on_success(self) -> None:
        assert (
            SandboxResult(exit_code=0, stdout="", stderr="").raise_for_status() is None
        )

    def test_raise_for_status_reports_the_exit_code_and_stderr(self) -> None:
        result = SandboxResult(exit_code=3, stdout="ignored", stderr="boom")
        with pytest.raises(SandboxExecutionError) as excinfo:
            result.raise_for_status()
        message = str(excinfo.value)
        assert "exit code 3" in message
        assert "boom" in message
        # stderr wins over stdout, so a traceback is not buried under progress
        # output.
        assert "ignored" not in message

    def test_raise_for_status_falls_back_to_stdout(self) -> None:
        result = SandboxResult(exit_code=2, stdout="printed to stdout", stderr="")
        with pytest.raises(SandboxExecutionError, match="printed to stdout"):
            result.raise_for_status()

    def test_raise_for_status_keeps_the_tail_of_long_output(self) -> None:
        # The tail is what matters: the error is at the end of the output, not
        # the beginning.
        result = SandboxResult(
            exit_code=1, stdout="", stderr="HEAD" + "." * 500 + "-" * 2000 + "TAIL"
        )
        with pytest.raises(SandboxExecutionError) as excinfo:
            result.raise_for_status()
        message = str(excinfo.value)
        assert message.endswith("TAIL")
        assert "HEAD" not in message

    def test_raise_for_status_omits_the_output_clause_when_there_is_none(self) -> None:
        with pytest.raises(SandboxExecutionError) as excinfo:
            SandboxResult(exit_code=1, stdout="  ", stderr="").raise_for_status()
        assert "Output:" not in str(excinfo.value)

    def test_raise_for_status_reports_a_timeout_as_a_timeout(self) -> None:
        result = SandboxResult(exit_code=124, stdout="", stderr="", timed_out=True)
        with pytest.raises(SandboxExecutionError) as excinfo:
            result.raise_for_status()
        assert "timed out" in str(excinfo.value)
        assert "sandbox destroyed" not in str(excinfo.value)

    def test_raise_for_status_says_when_the_sandbox_is_gone(self) -> None:
        result = SandboxResult(
            exit_code=-1,
            stdout="",
            stderr="",
            timed_out=True,
            sandbox_terminated=True,
        )
        with pytest.raises(SandboxExecutionError, match="sandbox destroyed"):
            result.raise_for_status()


class TestNewSandboxName:
    def test_is_prefixed_so_orphans_are_identifiable(self) -> None:
        assert new_sandbox_name().startswith(SANDBOX_NAME_PREFIX)

    def test_is_unique(self) -> None:
        names = {new_sandbox_name() for _ in range(500)}
        assert len(names) == 500

    def test_suffix_is_twelve_hex_characters(self) -> None:
        suffix = new_sandbox_name().removeprefix(SANDBOX_NAME_PREFIX)
        assert re.fullmatch(r"[0-9a-f]{12}", suffix)

    def test_uses_only_characters_every_provider_accepts(self) -> None:
        # `sbx --name` allows letters, digits, hyphens, periods and plus signs
        # only; islo names appear in URLs. Nothing generated here may need
        # escaping or sanitising.
        assert re.fullmatch(r"[A-Za-z0-9.+-]+", new_sandbox_name())


class TestValidateEnv:
    @pytest.mark.parametrize("env", [None, {}, {"FOO": "bar"}, {"A_1": ""}])
    def test_accepts_expressible_environments(
        self, env: Mapping[str, str] | None
    ) -> None:
        assert validate_env(env) is None

    @pytest.mark.parametrize("key", ["", "FOO=BAR", "FOO\0BAR"])
    def test_rejects_keys_a_posix_env_cannot_express(self, key: str) -> None:
        with pytest.raises(ValueError, match="Invalid environment variable name"):
            validate_env({key: "value"})

    def test_names_the_offending_key(self) -> None:
        with pytest.raises(ValueError, match="FOO=BAR"):
            validate_env({"FOO=BAR": "value"})

    def test_rejects_a_null_byte_in_a_value(self) -> None:
        with pytest.raises(ValueError, match="null byte"):
            validate_env({"FOO": "ba\0r"})

    def test_reports_which_variable_holds_the_null_byte(self) -> None:
        with pytest.raises(ValueError, match="'SECOND'"):
            validate_env({"FIRST": "ok", "SECOND": "ba\0r"})


class TestSandbox:
    def test_str_identifies_the_backend_and_the_sandbox(self) -> None:
        assert str(Sandbox(id="abc", backend="sbx")) == "sbx:abc"

    def test_metadata_defaults_to_empty(self) -> None:
        assert Sandbox(id="abc", backend="sbx").metadata == {}

    def test_metadata_carries_everything_teardown_needs(self) -> None:
        # Invariant 1: per-sandbox state lives on the handle, not the backend,
        # which is what lets a different instance (or process) clean up.
        sandbox = Sandbox(id="abc", backend="sbx", metadata={"workspace": "/tmp/ws"})
        assert sandbox.metadata["workspace"] == "/tmp/ws"

    def test_is_immutable(self) -> None:
        sandbox = Sandbox(id="abc", backend="sbx")
        with pytest.raises(dataclasses.FrozenInstanceError):
            sandbox.id = "other"  # type: ignore[misc]

    def test_equality_is_by_value(self) -> None:
        assert Sandbox(id="a", backend="b", metadata={"k": "v"}) == Sandbox(
            id="a", backend="b", metadata={"k": "v"}
        )


class TestBackendShape:
    def test_the_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            SandboxBackend()  # type: ignore[abstract]

    def test_a_backend_advertises_the_run_in_sandbox_capability(self) -> None:
        assert SandboxBackend._block_schema_capabilities == ["run-in-sandbox"]
        assert RecordingBackend._block_schema_capabilities == ["run-in-sandbox"]

    def test_backend_name_is_a_class_var_not_a_configurable_field(self) -> None:
        # A backend's identity is not user-editable; if it were a field it
        # would show up in the block schema and in saved block documents.
        assert "backend_name" not in RecordingBackend.model_fields
        assert RecordingBackend.backend_name == "recording"

    def test_max_output_bytes_defaults_to_the_shared_budget(self) -> None:
        assert RecordingBackend().max_output_bytes == DEFAULT_MAX_OUTPUT_BYTES

    @pytest.mark.parametrize("value", [0, -1])
    def test_max_output_bytes_must_be_positive(self, value: int) -> None:
        with pytest.raises(ValidationError):
            RecordingBackend(max_output_bytes=value)

    async def test_aclose_defaults_to_a_no_op(self, backend: RecordingBackend) -> None:
        assert await backend.aclose() is None

    def test_construction_performs_no_work(self) -> None:
        """Invariant 2: Block instances are built at import time."""
        instance = RecordingBackend()
        assert instance.created == []
        assert instance.execs == []


class TestPortableWriteFile:
    """`awrite_file`'s fallback, which must work with nothing but `aexec`."""

    async def test_runs_a_single_shell_command(self, backend: RecordingBackend) -> None:
        sandbox = await backend.acreate()
        await backend.awrite_file(sandbox, "/work/main.py", "print(1)\n")

        (call,) = backend.execs
        assert call.sandbox == sandbox
        assert call.command[:2] == ["sh", "-c"]
        assert call.timeout == 60
        assert call.env == {}

    async def test_smuggles_the_payload_as_base64(
        self, backend: RecordingBackend
    ) -> None:
        sandbox = await backend.acreate()
        content = "quotes ' \" and $(subshell) and\nnewlines\n"
        await backend.awrite_file(sandbox, "/work/main.py", content)

        command = backend.execs[0].command
        script = command[2]
        assert "".join(command[4:]) == base64.b64encode(content.encode()).decode()
        assert "base64 -d" in script
        # The payload must never appear verbatim; that is the entire point of
        # encoding it.
        assert "$(subshell)" not in script

    async def test_creates_the_parent_directory(
        self, backend: RecordingBackend
    ) -> None:
        sandbox = await backend.acreate()
        await backend.awrite_file(sandbox, "/deeply/nested/main.py", "x")
        script = backend.execs[0].command[2]
        assert script.startswith("mkdir -p /deeply/nested && ")

    async def test_quotes_a_hostile_parent_directory(
        self, backend: RecordingBackend
    ) -> None:
        sandbox = await backend.acreate()
        await backend.awrite_file(sandbox, "/wo rk/$(id)/main.py", "x")
        script = backend.execs[0].command[2]
        assert "mkdir -p '/wo rk/$(id)'" in script
        assert "> '/wo rk/$(id)/main.py'" in script

    async def test_skips_mkdir_for_a_bare_filename(
        self, backend: RecordingBackend
    ) -> None:
        sandbox = await backend.acreate()
        await backend.awrite_file(sandbox, "main.py", "x")
        assert "mkdir" not in backend.execs[0].command[2]

    @pytest.mark.skipif(
        shutil.which("sh") is None or shutil.which("base64") is None,
        reason="needs a POSIX shell and base64 to run the generated script",
    )
    @pytest.mark.parametrize(
        "content",
        [
            "plain\n",
            "no trailing newline",
            "quotes ' \" backtick ` dollar $HOME $(id)",
            "unicode: héllo → 🌍\n",
            "",
        ],
    )
    async def test_the_generated_script_really_round_trips(
        self, backend: RecordingBackend, tmp_path: Path, content: str
    ) -> None:
        """Run the emitted script for real, not just inspect it.

        The fallback's whole risk is quoting, so the only convincing check is
        executing the script it produces and comparing bytes.
        """
        sandbox = await backend.acreate()
        target = tmp_path / "sub" / "dir" / "out.txt"
        await backend.awrite_file(sandbox, str(target), content)

        command = backend.execs[0].command
        completed = subprocess.run(command, capture_output=True, timeout=30)
        assert completed.returncode == 0, completed.stderr
        assert target.read_text(encoding="utf-8") == content

    async def test_rejects_a_payload_over_the_inline_ceiling(
        self, backend: RecordingBackend
    ) -> None:
        sandbox = await backend.acreate()
        with pytest.raises(SandboxError) as excinfo:
            await backend.awrite_file(
                sandbox, "/big", "x" * (MAX_INLINE_FILE_BYTES + 1)
            )
        message = str(excinfo.value)
        assert str(MAX_INLINE_FILE_BYTES) in message
        assert "RecordingBackend" in message
        # Nothing was attempted: the limit is checked before any exec.
        assert backend.execs == []

    async def test_accepts_a_payload_exactly_at_the_ceiling(
        self, backend: RecordingBackend
    ) -> None:
        sandbox = await backend.acreate()
        await backend.awrite_file(sandbox, "/big", "x" * MAX_INLINE_FILE_BYTES)
        (call,) = backend.execs
        assert len(call.command[4:]) > 1
        assert (
            max(map(len, call.command[4:])) <= base_module._INLINE_FILE_ARGUMENT_BYTES
        )

    @pytest.mark.skipif(
        shutil.which("sh") is None or shutil.which("base64") is None,
        reason="needs a POSIX shell and base64 to run the generated script",
    )
    async def test_the_ceiling_round_trips_without_one_oversized_argument(
        self, backend: RecordingBackend, tmp_path: Path
    ) -> None:
        content = "x" * MAX_INLINE_FILE_BYTES
        target = tmp_path / "at-ceiling"
        sandbox = await backend.acreate()
        await backend.awrite_file(sandbox, str(target), content)

        (call,) = backend.execs
        completed = subprocess.run(call.command, capture_output=True, timeout=30)

        assert completed.returncode == 0, completed.stderr
        assert target.read_text() == content

    async def test_the_ceiling_is_measured_in_encoded_bytes(
        self, backend: RecordingBackend
    ) -> None:
        # Two bytes per character, so half as many characters exhausts it.
        content = "é" * (MAX_INLINE_FILE_BYTES // 2 + 1)
        assert len(content) < MAX_INLINE_FILE_BYTES
        sandbox = await backend.acreate()
        with pytest.raises(SandboxError):
            await backend.awrite_file(sandbox, "/big", content)

    async def test_a_failed_write_raises(self, backend: RecordingBackend) -> None:
        backend.returns(
            SandboxResult(exit_code=1, stdout="", stderr="Read-only file system")
        )
        sandbox = await backend.acreate()
        with pytest.raises(SandboxError) as excinfo:
            await backend.awrite_file(sandbox, "/work/main.py", "x")
        message = str(excinfo.value)
        assert "/work/main.py" in message
        assert "exit 1" in message
        assert "Read-only file system" in message

    async def test_a_timed_out_write_raises(self, backend: RecordingBackend) -> None:
        backend.returns(
            SandboxResult(exit_code=124, stdout="", stderr="", timed_out=True)
        )
        sandbox = await backend.acreate()
        with pytest.raises(SandboxError):
            await backend.awrite_file(sandbox, "/work/main.py", "x")


class TestSession:
    """`asession` exists to make teardown unconditional."""

    async def test_provisions_and_destroys(self, backend: RecordingBackend) -> None:
        async with backend.asession() as sandbox:
            assert sandbox in backend.created
            assert backend.destroyed == []
        assert backend.destroyed == [sandbox.id]

    async def test_destroys_when_the_body_raises(
        self, backend: RecordingBackend
    ) -> None:
        with pytest.raises(RuntimeError, match="boom"):
            async with backend.asession() as sandbox:
                raise RuntimeError("boom")
        assert backend.destroyed == [sandbox.id]

    async def test_destroys_when_the_body_is_cancelled(
        self, backend: RecordingBackend
    ) -> None:
        entered = asyncio.Event()

        async def work() -> None:
            async with backend.asession():
                entered.set()
                await asyncio.sleep(3600)

        task = asyncio.ensure_future(work())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(backend.destroyed) == 1

    async def test_destroys_when_cancelled_during_teardown(
        self, backend: RecordingBackend
    ) -> None:
        """A second cancellation must wait until teardown has finished."""
        backend._destroy_started = asyncio.Event()
        backend._destroy_gate = asyncio.Event()
        entered = asyncio.Event()

        async def work() -> None:
            async with backend.asession():
                entered.set()
                await asyncio.sleep(3600)

        task = asyncio.ensure_future(work())
        await entered.wait()
        task.cancel()
        await backend._destroy_started.wait()
        task.cancel()
        backend._destroy_gate.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(backend.destroyed) == 1

    async def test_concurrent_sessions_are_isolated(
        self, backend: RecordingBackend
    ) -> None:
        """Invariant 1, at the level of the shared base implementation.

        Two coroutines using ONE backend instance must get two sandboxes, and
        the end of one session must not tear down the other's.
        """
        first_ready = asyncio.Event()
        second_ready = asyncio.Event()
        seen: dict[str, Sandbox] = {}

        async def first() -> None:
            async with backend.asession() as sandbox:
                seen["first"] = sandbox
                first_ready.set()
                await second_ready.wait()

        async def second() -> None:
            async with backend.asession() as sandbox:
                seen["second"] = sandbox
                await first_ready.wait()
            second_ready.set()

        await asyncio.gather(first(), second())

        assert seen["first"].id != seen["second"].id
        assert sorted(backend.destroyed) == sorted(
            [seen["first"].id, seen["second"].id]
        )
        # Each sandbox destroyed exactly once, by its own session.
        assert len(backend.destroyed) == 2
