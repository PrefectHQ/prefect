"""Tests for `SandboxOperation` / `SandboxProcess`.

Modelled on `prefect-shell`'s `tests/test_commands.py`: every behavioural assertion is
checked through both the one-shot (`run`) and the trigger/wait/fetch path, and log
assertions go through the two-layer caplog fixtures in `conftest.py`.

The backend under these tests is `FakeSandbox`, an in-memory `SandboxBackend` defined
below rather than a real microVM provider. That is deliberate: this module is about the
Prefect-facing surface — dispatch lanes, context managers, per-process ownership,
logging — and a fake is the only way to assert on *ordering* (create → write → exec →
destroy) and on which sandbox a teardown touched. Real backends have their own suites.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

import pytest
from prefect_sandbox.base import (
    Sandbox,
    SandboxBackend,
    SandboxCreationError,
    SandboxError,
    SandboxExecutionError,
    SandboxResult,
    new_sandbox_name,
)
from prefect_sandbox.operations import (
    DEFAULT_TIMEOUT_SECONDS,
    SandboxOperation,
    SandboxProcess,
)
from pydantic import PrivateAttr

from prefect import flow

#: Logger names a `SandboxOperation` and its processes use *outside* a run context.
#: Inside a flow or task run both objects log to the run logger instead, which is why
#: the log assertions below run outside one unless they say otherwise.
OPERATION_LOGGERS = {"prefect.SandboxOperation", "prefect.SandboxProcess"}


class FakeSandbox(SandboxBackend):
    """An in-memory backend that records what the operation layer asked it to do.

    Every call is appended to `events` as a `(kind, detail)` pair, so a test can assert
    on ordering as well as on arguments. `live` is the set of sandbox ids that have been
    created and not yet destroyed — the cheapest possible check for "did the operation
    leak a sandbox", and for "did closing one process destroy somebody else's".
    """

    backend_name: ClassVar[str] = "fake"

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
    truncated: bool = False
    sandbox_terminated: bool = False
    #: Seconds `aexec` pretends to work for, so a test can observe an in-flight process.
    exec_delay: float = 0.0

    _events: list[tuple[str, str]] = PrivateAttr(default_factory=list)
    _live: set[str] = PrivateAttr(default_factory=set)
    _execs: list[dict[str, Any]] = PrivateAttr(default_factory=list)
    _writes: list[tuple[str, str, str]] = PrivateAttr(default_factory=list)
    _close_calls: int = PrivateAttr(default=0)

    @property
    def events(self) -> list[tuple[str, str]]:
        """Every backend call in order, as `(kind, sandbox_id)` pairs."""
        return list(self._events)

    @property
    def event_kinds(self) -> list[str]:
        """Just the ordering: e.g. `["create", "write", "exec", "destroy"]`."""
        return [kind for kind, _ in self._events]

    @property
    def live(self) -> set[str]:
        """Ids of sandboxes created and not yet destroyed."""
        return set(self._live)

    @property
    def execs(self) -> list[dict[str, Any]]:
        """One record per `aexec`, with the argv and every keyword argument."""
        return list(self._execs)

    @property
    def writes(self) -> list[tuple[str, str, str]]:
        """One `(sandbox_id, path, content)` triple per `awrite_file`."""
        return list(self._writes)

    @property
    def close_calls(self) -> int:
        """How many times `aclose` was called on this backend."""
        return self._close_calls

    def result_for(self, command: Sequence[str]) -> SandboxResult:
        """The canned result. Overridden by subclasses that need per-command answers."""
        return SandboxResult(
            exit_code=self.exit_code,
            stdout=self.stdout,
            stderr=self.stderr,
            timed_out=self.timed_out,
            truncated=self.truncated,
            sandbox_terminated=self.sandbox_terminated,
        )

    async def acreate(self) -> Sandbox:
        """Hand out a fresh handle, with per-sandbox state living only on the handle."""
        sandbox = Sandbox(
            id=new_sandbox_name(),
            backend=self.backend_name,
            metadata={"fake": "yes"},
        )
        self._events.append(("create", sandbox.id))
        self._live.add(sandbox.id)
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
        """Record the call and return the canned result."""
        self._events.append(("exec", sandbox.id))
        self._execs.append(
            {
                "sandbox_id": sandbox.id,
                "command": list(command),
                "timeout": timeout,
                "env": None if env is None else dict(env),
                "working_dir": working_dir,
            }
        )
        if self.exec_delay:
            await asyncio.sleep(self.exec_delay)
        return self.result_for(command)

    async def adestroy(self, sandbox: Sandbox) -> None:
        """Forget the sandbox. Idempotent, as the contract requires."""
        self._events.append(("destroy", sandbox.id))
        self._live.discard(sandbox.id)

    async def awrite_file(self, sandbox: Sandbox, path: str, content: str) -> None:
        """Record the write natively, the way a backend with a file API would."""
        self._events.append(("write", sandbox.id))
        self._writes.append((sandbox.id, path, content))

    async def aclose(self) -> None:
        """Count backend-level closes, which the operation layer must never do."""
        self._close_calls += 1


class FailingCreateSandbox(FakeSandbox):
    """A backend whose provisioning always fails."""

    async def acreate(self) -> Sandbox:
        """Fail the way a real backend does — with a typed error, before any handle."""
        raise SandboxCreationError("no capacity")


class FailingWriteSandbox(FakeSandbox):
    """A backend that provisions fine but cannot accept files."""

    async def awrite_file(self, sandbox: Sandbox, path: str, content: str) -> None:
        """Fail after the sandbox exists, which is the interesting cleanup case."""
        raise SandboxError("disk full")


class FailingDestroySandbox(FakeSandbox):
    """A backend whose teardown raises, to prove `aclose` does not mask it silently."""

    async def adestroy(self, sandbox: Sandbox) -> None:
        """Raise, but still record the attempt."""
        self._events.append(("destroy", sandbox.id))
        raise RuntimeError("vendor API is down")


class FailOnceDestroySandbox(FakeSandbox):
    """A backend whose first teardown fails so retry behavior is observable."""

    _destroy_attempts: int = PrivateAttr(default=0)

    async def adestroy(self, sandbox: Sandbox) -> None:
        self._destroy_attempts += 1
        if self._destroy_attempts == 1:
            raise RuntimeError("temporary vendor outage")
        await super().adestroy(sandbox)


class SlowDestroySandbox(FakeSandbox):
    """A backend that pauses teardown so caller cancellation is deterministic."""

    _destroy_started: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)
    _allow_destroy: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)

    async def adestroy(self, sandbox: Sandbox) -> None:
        self._destroy_started.set()
        await self._allow_destroy.wait()
        await super().adestroy(sandbox)


class SlowFailOnceDestroySandbox(FailOnceDestroySandbox):
    """Pause the first teardown, then fail it so concurrent closers can join it."""

    _destroy_started: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)
    _allow_destroy: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)

    async def adestroy(self, sandbox: Sandbox) -> None:
        self._destroy_started.set()
        await self._allow_destroy.wait()
        await super().adestroy(sandbox)


class SlowCreateSandbox(FakeSandbox):
    """A backend whose create call waits so close/provision races are deterministic."""

    _create_started: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)
    _allow_create: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)

    async def acreate(self) -> Sandbox:
        self._create_started.set()
        await self._allow_create.wait()
        return await super().acreate()


class SlowWriteSandbox(FakeSandbox):
    """A backend that pauses after creation while a file upload is in flight."""

    _write_started: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)
    _allow_write: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)

    async def awrite_file(self, sandbox: Sandbox, path: str, content: str) -> None:
        self._write_started.set()
        await self._allow_write.wait()
        await super().awrite_file(sandbox, path, content)


class SlowWriteFailingDestroySandbox(SlowWriteSandbox, FailingDestroySandbox):
    """A backend that pauses mid-upload *and* cannot tear anything down."""


class UninterruptibleWriteSandbox(FakeSandbox):
    """A backend whose in-flight upload absorbs the cancellation sent to it.

    Backends that stream a file to a vendor API shield the transfer so a cancelled
    caller cannot leave a half-written file behind; the same shape appears whenever an
    upload is already committed to a blocking client call. The consequence for the
    operation layer is that a provisioning task can outlive the cancellation `aclose`
    sends it and go on to finish provisioning a sandbox nobody is tracking any more.
    """

    _write_started: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)

    async def awrite_file(self, sandbox: Sandbox, path: str, content: str) -> None:
        """Wait to be cancelled, swallow the cancellation, then complete the write."""
        self._write_started.set()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.Event().wait()
        await super().awrite_file(sandbox, path, content)


def stream_records(
    caplog: pytest.LogCaptureFixture, marker: str
) -> list[logging.LogRecord]:
    """Operation/process log records at INFO or above whose message contains `marker`."""
    return [
        record
        for record in caplog.records
        if record.levelno >= logging.INFO
        and record.name in OPERATION_LOGGERS
        and marker in record.message
    ]


class TestRunAndTrigger:
    """The two ways to execute an operation, checked through both lanes."""

    async def execute(self, operation: SandboxOperation, method: str) -> list[str]:
        """Run `operation` through either the one-shot or the trigger/wait/fetch path."""
        if method == "run":
            return await operation.arun()
        process = await operation.atrigger()
        try:
            await process.await_for_completion()
            return await process.afetch_result()
        finally:
            await process.aclose()

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_returns_stdout_lines(self, method: str) -> None:
        backend = FakeSandbox(stdout="testing\nthe output\ngood\n")
        operation = SandboxOperation(backend, ["echo hi"])

        assert await self.execute(operation, method) == [
            "testing",
            "the output",
            "good",
        ]

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_destroys_the_sandbox(self, method: str) -> None:
        backend = FakeSandbox(stdout="ok")
        operation = SandboxOperation(backend, ["echo ok"])

        await self.execute(operation, method)

        assert backend.live == set()
        assert backend.event_kinds == ["create", "exec", "destroy"]

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_commands_run_in_one_shell_joined_with_newlines(
        self, method: str
    ) -> None:
        backend = FakeSandbox()
        operation = SandboxOperation(backend, ["echo a", "echo b"], shell="bash")

        await self.execute(operation, method)

        # Not `os.linesep`: the guest is Linux whatever the worker runs on, and a
        # `\r\n`-joined script makes `sh` choke on the trailing carriage returns.
        assert backend.execs[0]["command"] == ["bash", "-c", "echo a\necho b"]

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_env_and_working_dir_reach_the_backend(self, method: str) -> None:
        backend = FakeSandbox()
        operation = SandboxOperation(
            backend,
            ["pwd"],
            env={"TOKEN": "abc"},
            working_dir="/work",
            timeout=42.0,
        )

        await self.execute(operation, method)

        call = backend.execs[0]
        assert call["env"] == {"TOKEN": "abc"}
        assert call["working_dir"] == "/work"
        assert call["timeout"] == 42.0

    async def test_empty_env_is_passed_as_none(self) -> None:
        backend = FakeSandbox()

        await SandboxOperation(backend, ["true"]).arun()

        # `{}` and `None` mean the same thing to a backend, and `None` lets one skip
        # building an `env` wrapper at all.
        assert backend.execs[0]["env"] is None

    async def test_default_timeout_is_bounded(self) -> None:
        backend = FakeSandbox()

        await SandboxOperation(backend, ["true"]).arun()

        assert backend.execs[0]["timeout"] == DEFAULT_TIMEOUT_SECONDS

    async def test_arun_never_registers_its_sandbox(self) -> None:
        backend = FakeSandbox()
        operation = SandboxOperation(backend, ["true"])

        await operation.arun()
        await operation.aclose()

        # One destroy, from `arun` itself: nothing was left for `aclose` to mop up.
        assert backend.event_kinds.count("destroy") == 1

    async def test_process_exposes_the_full_result(self) -> None:
        backend = FakeSandbox(stdout="out", stderr="err", exit_code=3, truncated=True)
        operation = SandboxOperation(backend, ["false"], raise_on_failure=False)

        process = await operation.atrigger()
        await process.await_for_completion()

        assert process.result is not None
        assert process.result.exit_code == 3
        assert process.result.stderr == "err"
        assert process.result.truncated is True
        assert process.return_code == 3
        # stderr is deliberately not folded into the fetched lines.
        assert await process.afetch_result() == ["out"]

    async def test_return_code_is_none_before_completion(self) -> None:
        backend = FakeSandbox(stdout="late", exec_delay=0.2)
        operation = SandboxOperation(backend, ["sleep 1"])

        process = await operation.atrigger()
        assert process.return_code is None
        assert process.result is None
        # Fetching early is allowed and returns what has been captured so far, which
        # for a backend that only reports at exit is nothing.
        assert await process.afetch_result() == []

        await process.await_for_completion()
        assert process.return_code == 0
        assert await process.afetch_result() == ["late"]

    async def test_fetch_result_returns_a_copy(self) -> None:
        backend = FakeSandbox(stdout="one\ntwo")
        operation = SandboxOperation(backend, ["true"])

        process = await operation.atrigger()
        await process.await_for_completion()
        first = await process.afetch_result()
        first.append("mutated")

        assert await process.afetch_result() == ["one", "two"]

    async def test_process_never_started_cannot_be_awaited(self) -> None:
        backend = FakeSandbox()
        sandbox = await backend.acreate()
        process = SandboxProcess(
            backend=backend,
            sandbox=sandbox,
            command=["true"],
            timeout=1.0,
        )

        with pytest.raises(RuntimeError, match="never started"):
            await process.await_for_completion()

        # Closing an unstarted process must still reclaim the sandbox.
        await process.aclose()
        assert backend.live == set()

    async def test_aclose_is_idempotent(self) -> None:
        backend = FakeSandbox()
        operation = SandboxOperation(backend, ["true"])

        process = await operation.atrigger()
        await process.await_for_completion()
        await process.aclose()
        await process.aclose()

        assert backend.event_kinds.count("destroy") == 1

    async def test_aclose_can_retry_a_failed_destroy(self) -> None:
        backend = FailOnceDestroySandbox()
        operation = SandboxOperation(backend, ["true"])
        process = await operation.atrigger()
        await process.await_for_completion()

        with pytest.raises(RuntimeError, match="temporary vendor outage"):
            await process.aclose()
        assert backend.live == {process.sandbox.id}

        await process.aclose()
        assert backend.live == set()

    async def test_aclose_cancels_an_in_flight_command(self) -> None:
        backend = FakeSandbox(exec_delay=30)
        operation = SandboxOperation(backend, ["sleep 30"])

        process = await operation.atrigger()
        await asyncio.sleep(0)  # let the execution task actually start
        await asyncio.wait_for(process.aclose(), timeout=5)

        assert backend.live == set()
        assert process.result is None

    async def test_backend_close_is_left_to_the_caller(self) -> None:
        backend = FakeSandbox()

        await SandboxOperation(backend, ["true"]).arun()

        # The operation does not own the backend: a shared block serving other
        # concurrent operations must not have its client closed underneath it.
        assert backend.close_calls == 0


class TestSyncLane:
    """The `@async_dispatch` twins, driven from genuinely synchronous callers."""

    def test_run_returns_a_list_not_a_coroutine(self) -> None:
        backend = FakeSandbox(stdout="sync out")

        result = SandboxOperation(backend, ["echo hi"]).run()

        assert not inspect.iscoroutine(result)
        assert result == ["sync out"]
        assert backend.live == set()

    def test_trigger_wait_fetch_close(self) -> None:
        backend = FakeSandbox(stdout="line1\nline2")
        operation = SandboxOperation(backend, ["echo hi"])

        process = operation.trigger()
        assert isinstance(process, SandboxProcess)

        assert process.wait_for_completion() is None
        result = process.fetch_result()
        assert not inspect.iscoroutine(result)
        assert result == ["line1", "line2"]

        assert process.close() is None
        assert backend.live == set()

    def test_operation_close_is_sync(self) -> None:
        backend = FakeSandbox()
        operation = SandboxOperation(backend, ["true"])

        process = operation.trigger()
        process.wait_for_completion()
        assert operation.close() is None

        assert backend.live == set()
        assert process._closed is True

    async def test_async_context_dispatches_to_the_async_twin(self) -> None:
        backend = FakeSandbox(stdout="hi")
        operation = SandboxOperation(backend, ["echo hi"])

        pending = operation.run()
        assert inspect.iscoroutine(pending)
        assert await pending == ["hi"]

    async def test_sync_can_be_forced_from_an_async_context(self) -> None:
        backend = FakeSandbox(stdout="hi")
        operation = SandboxOperation(backend, ["echo hi"])

        # `_sync=True` is the escape hatch every dispatched method honours, and is what
        # `__exit__` relies on: it must run to completion here, on the dedicated
        # run-sync loop thread, even though this caller has a loop of its own.
        result = operation.run(_sync=True)

        assert not inspect.iscoroutine(result)
        assert result == ["hi"]

    @pytest.mark.parametrize(
        "name",
        ["atrigger", "arun", "aclose", "trigger", "run", "close"],
    )
    def test_operation_exposes_both_twins(self, name: str) -> None:
        operation = SandboxOperation(FakeSandbox(), ["true"])
        assert callable(getattr(operation, name))

    @pytest.mark.parametrize(
        "name",
        [
            "await_for_completion",
            "afetch_result",
            "aclose",
            "wait_for_completion",
            "fetch_result",
            "close",
        ],
    )
    def test_process_exposes_both_twins(self, name: str) -> None:
        process = SandboxProcess(
            backend=FakeSandbox(),
            sandbox=Sandbox(id="x", backend="fake"),
            command=["true"],
            timeout=1.0,
        )
        assert callable(getattr(process, name))


class TestContextManagers:
    """Both context-manager lanes must destroy every sandbox they created."""

    async def test_async_context_manager(self) -> None:
        backend = FakeSandbox(stdout="testing")
        async with SandboxOperation(backend, ["echo testing"]) as operation:
            process = await operation.atrigger()
            await process.await_for_completion()
            assert await process.afetch_result() == ["testing"]
            assert backend.live == {process.sandbox.id}

        assert backend.live == set()

    def test_sync_context_manager(self) -> None:
        backend = FakeSandbox(stdout="testing")
        with SandboxOperation(backend, ["echo testing"]) as operation:
            process = operation.trigger()
            process.wait_for_completion()
            assert process.fetch_result() == ["testing"]

        assert backend.live == set()

    async def test_sync_context_manager_inside_an_async_context(self) -> None:
        """`__exit__` must force the sync branch or it leaks every sandbox.

        A bare `self.close()` inside a running event loop returns an un-awaited
        coroutine and the teardown silently never happens — the bug
        `ShellOperation.__exit__` has.
        """
        backend = FakeSandbox(stdout="hi")

        with SandboxOperation(backend, ["echo hi"]) as operation:
            process = await operation.atrigger()
            await process.await_for_completion()
            assert backend.live == {process.sandbox.id}

        assert backend.live == set()

    async def test_sync_context_inside_async_cancels_unfinished_execution(self) -> None:
        backend = FakeSandbox(exec_delay=30)

        with SandboxOperation(backend, ["sleep 30"]) as operation:
            process = await operation.atrigger()
            await asyncio.sleep(0)

        assert backend.live == set()
        assert process._task is not None
        with pytest.raises(asyncio.CancelledError):
            await process._task

    async def test_async_context_manager_destroys_on_exception(self) -> None:
        backend = FakeSandbox(exec_delay=30)

        with pytest.raises(ValueError, match="boom"):
            async with SandboxOperation(backend, ["sleep 30"]) as operation:
                await operation.atrigger()
                raise ValueError("boom")

        assert backend.live == set()

    def test_sync_context_manager_destroys_on_exception(self) -> None:
        backend = FakeSandbox()

        with pytest.raises(ValueError, match="boom"):
            with SandboxOperation(backend, ["true"]) as operation:
                operation.trigger()
                raise ValueError("boom")

        assert backend.live == set()

    async def test_process_is_its_own_async_context_manager(self) -> None:
        backend = FakeSandbox(stdout="hi")
        operation = SandboxOperation(backend, ["echo hi"])

        process = await operation.atrigger()
        async with process as entered:
            assert entered is process
            await entered.await_for_completion()

        assert backend.live == set()

    def test_process_is_its_own_sync_context_manager(self) -> None:
        backend = FakeSandbox(stdout="hi")
        operation = SandboxOperation(backend, ["echo hi"])

        process = operation.trigger()
        with process as entered:
            entered.wait_for_completion()

        assert backend.live == set()

    async def test_process_context_cleanup_does_not_mask_the_body_error(
        self, prefect_caplog: pytest.LogCaptureFixture
    ) -> None:
        """A failed teardown must never replace the error the body was already raising.

        The body's exception is the one the caller can act on; a teardown failure that
        overwrote it would leave them debugging the vendor API instead of their command.
        """
        backend = FailingDestroySandbox()
        operation = SandboxOperation(backend, ["true"])
        process = await operation.atrigger()

        with pytest.raises(ValueError, match="body failed"):
            async with process:
                raise ValueError("body failed")

        assert any(
            "while handling another error" in record.message
            for record in prefect_caplog.records
            if record.levelno >= logging.ERROR and record.name in OPERATION_LOGGERS
        )
        # Silently swallowed is not the same as unnoticed: the attempt was made.
        assert backend.event_kinds.count("destroy") == 1

    async def test_process_context_cleanup_failure_surfaces_when_the_body_succeeded(
        self,
    ) -> None:
        """With no error to preserve, a leaked sandbox must be the caller's problem."""
        backend = FailingDestroySandbox()
        operation = SandboxOperation(backend, ["true"])
        process = await operation.atrigger()

        with pytest.raises(RuntimeError, match="vendor API is down"):
            async with process:
                await process.await_for_completion()

    def test_sync_process_context_cleanup_does_not_mask_the_body_error(
        self, prefect_caplog: pytest.LogCaptureFixture
    ) -> None:
        backend = FailingDestroySandbox()
        operation = SandboxOperation(backend, ["true"])
        process = operation.trigger()

        with pytest.raises(ValueError, match="body failed"):
            with process:
                raise ValueError("body failed")

        assert any(
            "while handling another error" in record.message
            for record in prefect_caplog.records
            if record.levelno >= logging.ERROR and record.name in OPERATION_LOGGERS
        )
        assert backend.event_kinds.count("destroy") == 1

    def test_sync_process_context_cleanup_failure_surfaces_when_the_body_succeeded(
        self,
    ) -> None:
        backend = FailingDestroySandbox()
        operation = SandboxOperation(backend, ["true"])
        process = operation.trigger()

        with pytest.raises(RuntimeError, match="vendor API is down"):
            with process:
                process.wait_for_completion()

    async def test_aclose_skips_a_process_that_closed_itself(self) -> None:
        backend = FakeSandbox()
        operation = SandboxOperation(backend, ["true"])

        async with operation:
            process = await operation.atrigger()
            await process.await_for_completion()
            await process.aclose()

        assert backend.event_kinds.count("destroy") == 1

    async def test_aclose_logs_and_raises_a_teardown_failure(
        self, prefect_caplog: pytest.LogCaptureFixture
    ) -> None:
        prefect_caplog.set_level(logging.INFO)
        backend = FailingDestroySandbox()
        operation = SandboxOperation(backend, ["true"])

        process = await operation.atrigger()
        await process.await_for_completion()
        with pytest.raises(SandboxError, match="Failed to destroy 1 of 1"):
            await operation.aclose()

        errors = [
            record
            for record in prefect_caplog.records
            if record.levelno >= logging.ERROR and record.name in OPERATION_LOGGERS
        ]
        assert any("may still be running" in record.message for record in errors)

    async def test_operation_aclose_keeps_failed_processes_for_retry(self) -> None:
        backend = FailOnceDestroySandbox()
        operation = SandboxOperation(backend, ["true"])
        process = await operation.atrigger()
        await process.await_for_completion()

        with pytest.raises(SandboxError):
            await operation.aclose()
        await operation.aclose()

        assert backend.live == set()

    async def test_context_cleanup_does_not_mask_the_body_error(
        self, prefect_caplog: pytest.LogCaptureFixture
    ) -> None:
        backend = FailingDestroySandbox()
        operation = SandboxOperation(backend, ["true"])

        with pytest.raises(ValueError, match="body failed"):
            async with operation:
                await operation.atrigger()
                raise ValueError("body failed")

        assert any(
            "cleanup failed while handling another error" in record.message.lower()
            for record in prefect_caplog.records
        )

    async def test_context_cleanup_failure_surfaces_when_the_body_succeeded(
        self,
    ) -> None:
        """A clean body means nothing is competing with the cleanup error, so it wins.

        Suppressing it here would let a `async with` block exit successfully having
        leaked a microVM the caller is still being billed for.
        """
        backend = FailingDestroySandbox()
        operation = SandboxOperation(backend, ["true"])

        with pytest.raises(SandboxError, match="Failed to destroy 1 of 1"):
            async with operation:
                process = await operation.atrigger()
                await process.await_for_completion()

    def test_sync_context_cleanup_does_not_mask_the_body_error(
        self, prefect_caplog: pytest.LogCaptureFixture
    ) -> None:
        backend = FailingDestroySandbox()

        with pytest.raises(ValueError, match="body failed"):
            with SandboxOperation(backend, ["true"]) as operation:
                operation.trigger()
                raise ValueError("body failed")

        assert any(
            "cleanup failed while handling another error" in record.message.lower()
            for record in prefect_caplog.records
        )
        assert backend.event_kinds.count("destroy") == 1

    def test_sync_context_cleanup_failure_surfaces_when_the_body_succeeded(
        self,
    ) -> None:
        backend = FailingDestroySandbox()

        with pytest.raises(SandboxError, match="Failed to destroy 1 of 1"):
            with SandboxOperation(backend, ["true"]) as operation:
                process = operation.trigger()
                process.wait_for_completion()


class TestRaiseOnFailure:
    """A nonzero exit is data unless the caller asked for an exception."""

    async def execute(self, operation: SandboxOperation, method: str) -> list[str]:
        """Run through either lane, letting `aclose` reclaim the sandbox either way."""
        if method == "run":
            return await operation.arun()
        process = await operation.atrigger()
        try:
            await process.await_for_completion()
            return await process.afetch_result()
        finally:
            await process.aclose()

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_nonzero_exit_raises_by_default(self, method: str) -> None:
        backend = FakeSandbox(exit_code=2, stderr="ls: no such file")
        operation = SandboxOperation(backend, ["ls /nope"])

        with pytest.raises(SandboxExecutionError, match="exit code 2"):
            await self.execute(operation, method)

        # And the sandbox is still gone: the failure path cleans up.
        assert backend.live == set()

    @pytest.mark.parametrize("method", ["run", "trigger"])
    async def test_nonzero_exit_is_data_when_asked(self, method: str) -> None:
        backend = FakeSandbox(exit_code=2, stdout="partial")
        operation = SandboxOperation(backend, ["ls /nope"], raise_on_failure=False)

        assert await self.execute(operation, method) == ["partial"]

    async def test_exit_code_is_readable_off_the_process(self) -> None:
        backend = FakeSandbox(exit_code=42, stdout="out")
        operation = SandboxOperation(backend, ["exit 42"], raise_on_failure=False)

        process = await operation.atrigger()
        await process.await_for_completion()

        assert process.return_code == 42
        assert process.result is not None and process.result.ok is False

    async def test_timeout_raises_with_a_timeout_message(self) -> None:
        backend = FakeSandbox(exit_code=124, timed_out=True, sandbox_terminated=True)
        operation = SandboxOperation(backend, ["sleep 999"], timeout=1)

        with pytest.raises(SandboxExecutionError, match="timed out"):
            await operation.arun()

    async def test_timeout_is_logged_with_the_termination_notice(
        self, prefect_caplog: pytest.LogCaptureFixture
    ) -> None:
        prefect_caplog.set_level(logging.INFO)
        backend = FakeSandbox(exit_code=124, timed_out=True, sandbox_terminated=True)
        operation = SandboxOperation(
            backend, ["sleep 999"], timeout=1, raise_on_failure=False
        )

        await operation.arun()

        warnings = [
            record
            for record in prefect_caplog.records
            if record.levelno >= logging.WARNING and record.name in OPERATION_LOGGERS
        ]
        assert any("timed out after 1" in record.message for record in warnings)
        assert any("was destroyed to stop it" in record.message for record in warnings)


class TestStreamOutput:
    """`stream_output` relays the sandbox's captured output to the run logger."""

    async def test_output_is_logged_line_by_line(
        self, prefect_caplog: pytest.LogCaptureFixture
    ) -> None:
        prefect_caplog.set_level(logging.INFO)
        backend = FakeSandbox(stdout="testing\nthe output", stderr="warned\ntwice")

        assert await SandboxOperation(backend, ["echo hi", "echo bye"]).arun() == [
            "testing",
            "the output",
        ]

        out = stream_records(prefect_caplog, "stream output:")
        err = stream_records(prefect_caplog, "stderr:")
        assert [record.message.splitlines()[-1] for record in out] == [
            "testing",
            "the output",
        ]
        assert [record.message.splitlines()[-1] for record in err] == [
            "warned",
            "twice",
        ]
        assert stream_records(prefect_caplog, "triggered with 2 commands running")
        assert stream_records(prefect_caplog, "completed with exit code 0")

    async def test_stream_output_false_logs_no_output(
        self, prefect_caplog: pytest.LogCaptureFixture
    ) -> None:
        prefect_caplog.set_level(logging.INFO)
        backend = FakeSandbox(stdout="secret", stderr="also secret")

        assert await SandboxOperation(
            backend, ["echo hi"], stream_output=False
        ).arun() == ["secret"]

        assert stream_records(prefect_caplog, "stream output:") == []
        assert stream_records(prefect_caplog, "stderr:") == []
        # The lifecycle records survive: only the sandbox's own output is suppressed.
        assert stream_records(prefect_caplog, "triggered with 1 commands running")
        assert stream_records(prefect_caplog, "completed with exit code 0")

    async def test_truncation_is_reported(
        self, prefect_caplog: pytest.LogCaptureFixture
    ) -> None:
        prefect_caplog.set_level(logging.INFO)
        backend = FakeSandbox(stdout="a", truncated=True, max_output_bytes=1024)

        await SandboxOperation(backend, ["yes"]).arun()

        warnings = [
            record
            for record in prefect_caplog.records
            if record.levelno >= logging.WARNING and record.name in OPERATION_LOGGERS
        ]
        assert any(
            "truncated at the backend's 1024-byte" in w.message for w in warnings
        )

    async def test_config_is_snapshotted_at_trigger_time(
        self, prefect_caplog: pytest.LogCaptureFixture
    ) -> None:
        """Flipping the operation's config must not change an already-running process.

        `ShellProcess` keeps a live back-reference to its operation, so mutating the
        operation mid-run silently retunes work that is already in flight.
        """
        prefect_caplog.set_level(logging.INFO)
        backend = FakeSandbox(stdout="still logged", exec_delay=0.05)
        operation = SandboxOperation(backend, ["echo hi"])

        process = await operation.atrigger()
        operation.stream_output = False
        await process.await_for_completion()
        await process.aclose()

        assert stream_records(prefect_caplog, "still logged")

    async def test_output_reaches_the_run_logger_inside_a_flow(
        self, prefect_task_runs_caplog: pytest.LogCaptureFixture
    ) -> None:
        prefect_task_runs_caplog.set_level(logging.INFO)
        backend = FakeSandbox(stdout="from inside a flow")

        @flow
        async def sandbox_flow() -> list[str]:
            return await SandboxOperation(backend, ["echo hi"]).arun()

        assert await sandbox_flow() == ["from inside a flow"]
        assert "from inside a flow" in prefect_task_runs_caplog.text


class TestLogger:
    """The logger property has to work outside a run context, not just inside one."""

    def test_named_for_the_class_outside_a_run_context(self) -> None:
        operation = SandboxOperation(FakeSandbox(), ["true"])

        assert operation.logger.name == "prefect.SandboxOperation"

    async def test_process_named_for_the_class_outside_a_run_context(self) -> None:
        operation = SandboxOperation(FakeSandbox(), ["true"])

        process = await operation.atrigger()
        try:
            assert process.logger.name == "prefect.SandboxProcess"
        finally:
            await process.aclose()

    async def test_run_logger_inside_a_flow(self) -> None:
        backend = FakeSandbox()

        @flow
        async def sandbox_flow() -> str:
            operation = SandboxOperation(backend, ["true"])
            logger = operation.logger
            # Inside a run, `.logger` is the run logger adapter, not `prefect.<Class>`.
            return getattr(logger, "logger", logger).name

        assert await sandbox_flow() == "prefect.flow_runs"


class TestConcurrency:
    """Two concurrent triggers on ONE operation must stay completely independent.

    This is the hazard the design exists to avoid: `ShellOperation` pushes every
    triggered process onto a single shared `AsyncExitStack`, so closing one unwinds
    the other's cleanup too.
    """

    async def test_concurrent_triggers_get_distinct_sandboxes(self) -> None:
        backend = FakeSandbox(stdout="hi", exec_delay=0.05)
        operation = SandboxOperation(backend, ["echo hi"])

        first, second = await asyncio.gather(operation.atrigger(), operation.atrigger())

        assert first.sandbox.id != second.sandbox.id
        assert backend.live == {first.sandbox.id, second.sandbox.id}

        await asyncio.gather(
            first.await_for_completion(), second.await_for_completion()
        )
        assert await first.afetch_result() == ["hi"]
        assert await second.afetch_result() == ["hi"]

        await operation.aclose()
        assert backend.live == set()

    async def test_closing_one_process_leaves_the_other_alone(self) -> None:
        backend = FakeSandbox(stdout="hi", exec_delay=0.3)
        operation = SandboxOperation(backend, ["sleep 1"])

        first, second = await asyncio.gather(operation.atrigger(), operation.atrigger())

        await first.aclose()

        assert backend.live == {second.sandbox.id}
        assert [
            sandbox_id for kind, sandbox_id in backend.events if kind == "destroy"
        ] == [first.sandbox.id]
        # The survivor's command is untouched and still completes normally.
        await second.await_for_completion()
        assert await second.afetch_result() == ["hi"]

        await operation.aclose()
        assert backend.live == set()
        destroyed = [
            sandbox_id for kind, sandbox_id in backend.events if kind == "destroy"
        ]
        # Exactly one destroy each: `aclose` on the operation skipped the process that
        # had already closed itself rather than double-destroying it.
        assert destroyed == [first.sandbox.id, second.sandbox.id]

    async def test_concurrent_arun_calls_are_independent(self) -> None:
        backend = FakeSandbox(stdout="hi", exec_delay=0.05)
        operation = SandboxOperation(backend, ["echo hi"])

        results = await asyncio.gather(
            operation.arun(), operation.arun(), operation.arun()
        )

        assert results == [["hi"], ["hi"], ["hi"]]
        assert backend.live == set()
        assert backend.event_kinds.count("create") == 3
        assert len({call["sandbox_id"] for call in backend.execs}) == 3

    async def test_concurrent_process_closers_share_one_destroy(self) -> None:
        backend = SlowDestroySandbox()
        operation = SandboxOperation(backend, ["true"])
        process = await operation.atrigger()
        await process.await_for_completion()

        first_close = asyncio.create_task(process.aclose())
        await backend._destroy_started.wait()
        second_close = asyncio.create_task(process.aclose())
        await asyncio.sleep(0)

        assert not second_close.done()
        backend._allow_destroy.set()
        await asyncio.gather(first_close, second_close)

        assert backend.live == set()
        assert backend.event_kinds.count("destroy") == 1

    async def test_operation_joins_an_in_flight_process_close_failure(self) -> None:
        """The operation must retain a process whose shared destroy attempt failed."""
        backend = SlowFailOnceDestroySandbox()
        operation = SandboxOperation(backend, ["true"])
        process = await operation.atrigger()
        await process.await_for_completion()

        process_close = asyncio.create_task(process.aclose())
        await backend._destroy_started.wait()
        operation_close = asyncio.create_task(operation.aclose())
        await asyncio.sleep(0)
        backend._allow_destroy.set()

        with pytest.raises(RuntimeError, match="temporary vendor outage"):
            await process_close
        with pytest.raises(SandboxError, match="Failed to destroy 1 of 1"):
            await operation_close

        assert backend.live == {process.sandbox.id}
        assert operation._processes == [process]

        await operation.aclose()
        assert backend.live == set()
        assert operation._processes == []

    async def test_concurrent_operation_closers_share_one_destroy(self) -> None:
        backend = SlowDestroySandbox()
        operation = SandboxOperation(backend, ["true"])
        process = await operation.atrigger()
        await process.await_for_completion()

        first_close = asyncio.create_task(operation.aclose())
        await backend._destroy_started.wait()
        second_close = asyncio.create_task(operation.aclose())
        await asyncio.sleep(0)

        assert not second_close.done()
        backend._allow_destroy.set()
        await asyncio.gather(first_close, second_close)

        assert backend.live == set()
        assert backend.event_kinds.count("destroy") == 1

    async def test_concurrent_operation_closers_share_a_failure(self) -> None:
        backend = SlowFailOnceDestroySandbox()
        operation = SandboxOperation(backend, ["true"])
        process = await operation.atrigger()
        await process.await_for_completion()

        first_close = asyncio.create_task(operation.aclose())
        await backend._destroy_started.wait()
        second_close = asyncio.create_task(operation.aclose())
        await asyncio.sleep(0)
        backend._allow_destroy.set()

        with pytest.raises(SandboxError, match="Failed to destroy 1 of 1"):
            await first_close
        with pytest.raises(SandboxError, match="Failed to destroy 1 of 1"):
            await second_close

        assert backend.live == {process.sandbox.id}
        assert operation._processes == [process]

        await operation.aclose()
        assert backend.live == set()
        assert operation._processes == []

    async def test_cancelling_aclose_still_visits_every_captured_process(
        self,
    ) -> None:
        """Cancellation is re-delivered only after the whole close generation ends."""
        backend = SlowDestroySandbox()
        operation = SandboxOperation(backend, ["true"])
        processes = await asyncio.gather(
            operation.atrigger(),
            operation.atrigger(),
            operation.atrigger(),
        )

        close_task = asyncio.create_task(operation.aclose())
        await backend._destroy_started.wait()
        close_task.cancel()
        await asyncio.sleep(0)
        assert not close_task.done()

        backend._allow_destroy.set()
        with pytest.raises(asyncio.CancelledError):
            await close_task

        destroyed = {
            sandbox_id for kind, sandbox_id in backend.events if kind == "destroy"
        }
        assert destroyed == {process.sandbox.id for process in processes}
        assert backend.live == set()
        assert operation._processes == []


class TestFilesAndProvisioning:
    """`files` are written before the commands, and a failed provision leaks nothing."""

    async def test_files_are_written_before_the_commands(self) -> None:
        backend = FakeSandbox()
        operation = SandboxOperation(
            backend,
            ["python /app/main.py"],
            files={"/app/main.py": "print('hi')\n"},
        )

        await operation.arun()

        assert backend.event_kinds == ["create", "write", "exec", "destroy"]
        sandbox_id, path, content = backend.writes[0]
        assert (path, content) == ("/app/main.py", "print('hi')\n")
        assert sandbox_id == backend.execs[0]["sandbox_id"]

    async def test_a_failed_create_leaves_nothing_tracked(self) -> None:
        backend = FailingCreateSandbox()
        operation = SandboxOperation(backend, ["true"])

        with pytest.raises(SandboxCreationError, match="no capacity"):
            await operation.atrigger()

        assert backend.events == []
        await operation.aclose()
        assert backend.events == []

    async def test_a_failed_file_write_destroys_the_sandbox(self) -> None:
        backend = FailingWriteSandbox()
        operation = SandboxOperation(backend, ["true"], files={"/app/x": "y"})

        with pytest.raises(SandboxError, match="disk full"):
            await operation.arun()

        # Created, then destroyed, and never executed: no half-provisioned microVM.
        assert backend.event_kinds == ["create", "destroy"]
        assert backend.live == set()

    async def test_a_failed_trigger_is_not_registered_for_later_close(self) -> None:
        backend = FailingWriteSandbox()
        operation = SandboxOperation(backend, ["true"], files={"/app/x": "y"})

        with pytest.raises(SandboxError):
            await operation.atrigger()

        await operation.aclose()
        assert backend.event_kinds.count("destroy") == 1

    async def test_close_cancels_in_flight_create(self) -> None:
        backend = SlowCreateSandbox()
        operation = SandboxOperation(backend, ["true"])
        trigger = asyncio.create_task(operation.atrigger())
        await backend._create_started.wait()

        await operation.aclose()

        with pytest.raises(asyncio.CancelledError):
            await trigger
        assert backend.live == set()

    async def test_a_sync_close_destroys_a_sandbox_provisioned_on_another_loop(
        self, prefect_task_runs_caplog: pytest.LogCaptureFixture
    ) -> None:
        """The cross-loop twin of the same-loop test below, and the harder case.

        `with` inside async code closes through `close(_sync=True)`, which runs
        `aclose()` on Prefect's own loop while this thread stays blocked. The
        provisioning task therefore lives on a loop the closer cannot join — joining
        would deadlock, since this thread owns it — so cancellation is only scheduled.
        Without destroying the already-created sandbox from the closing loop, the
        microVM is simply abandoned.
        """
        backend = SlowWriteSandbox()
        operation = SandboxOperation(backend, ["true"], files={"/app/x": "y"})
        trigger = asyncio.create_task(operation.atrigger())
        await backend._write_started.wait()
        assert len(backend.live) == 1

        # Exactly what `__exit__` does. Called from inside a running loop on purpose:
        # `run_coro_as_sync` puts `aclose()` on Prefect's own loop and blocks *this*
        # thread, so the provisioning task cannot advance and a merely scheduled
        # cancellation cannot be consumed while the close is in progress.
        operation.close(_sync=True)

        assert backend.live == set(), "a sandbox was abandoned on the other loop"
        assert any(
            "another event loop" in record.message
            for record in prefect_task_runs_caplog.records
        ), "the operator-facing log must not claim zero sandboxes were closed"

        backend._allow_write.set()
        with contextlib.suppress(asyncio.CancelledError, SandboxError):
            await trigger

    async def test_provisioning_is_refused_while_the_operation_closes(self) -> None:
        """A trigger that starts after closure began must not create a sandbox at all."""
        backend = FakeSandbox()
        operation = SandboxOperation(backend, ["true"])
        operation._active_closers += 1

        with pytest.raises(SandboxError, match="while the operation closes"):
            await operation.atrigger()

        assert backend.live == set()
        assert backend.event_kinds.count("create") == 0

    async def test_close_destroys_a_sandbox_with_an_in_flight_file_write(self) -> None:
        backend = SlowWriteSandbox()
        operation = SandboxOperation(backend, ["true"], files={"/app/x": "y"})
        trigger = asyncio.create_task(operation.atrigger())
        await backend._write_started.wait()
        assert len(backend.live) == 1

        await operation.aclose()

        with pytest.raises(asyncio.CancelledError):
            await trigger
        assert backend.live == set()

    async def test_a_sandbox_provisioned_after_closure_began_is_destroyed(self) -> None:
        """Provisioning that outlives its cancellation must not hand back a live sandbox.

        `aclose` cancels in-flight provisioning, but cancellation is a request, not a
        guarantee: a backend whose upload is shielded finishes anyway and the
        provisioner reaches the end of its work after the operation stopped tracking
        anything. Returning that `SandboxProcess` would hand the caller a sandbox no
        `aclose` will ever reclaim, so the provisioner destroys it and says so.
        """
        backend = UninterruptibleWriteSandbox()
        operation = SandboxOperation(backend, ["true"], files={"/app/x": "y"})
        trigger = asyncio.create_task(operation.atrigger())
        await backend._write_started.wait()

        await operation.aclose()

        with pytest.raises(SandboxError, match="raced operation closure"):
            await trigger
        assert backend.live == set()
        # And it is not left behind as something a second `aclose` would retry.
        assert operation._processes == []

    async def test_a_failed_cross_loop_destroy_is_reported(
        self, prefect_caplog: pytest.LogCaptureFixture
    ) -> None:
        """The orphan-destroying arm of `aclose` must report failures like any other.

        A sandbox provisioned on another event loop is destroyed by the closer itself
        because nobody else can — the provisioner's own cleanup runs on a loop this
        closer must not join. If that destroy fails and is not counted, the close
        reports success over a microVM that is still running.
        """
        backend = SlowWriteFailingDestroySandbox()
        operation = SandboxOperation(backend, ["true"], files={"/app/x": "y"})
        trigger = asyncio.create_task(operation.atrigger())
        await backend._write_started.wait()
        assert len(backend.live) == 1

        # As `__exit__` does: `aclose` runs on Prefect's loop, so the provisioning task
        # belongs to a loop it can only schedule a cancellation on.
        with pytest.raises(SandboxError, match="Failed to destroy 1 of 1"):
            operation.close(_sync=True)

        assert any(
            "may still be running" in record.message
            for record in prefect_caplog.records
            if record.levelno >= logging.ERROR and record.name in OPERATION_LOGGERS
        )

        # Let the abandoned provisioner finish unwinding; its own teardown fails too.
        backend._allow_write.set()
        with contextlib.suppress(asyncio.CancelledError, RuntimeError):
            await trigger

    async def test_close_with_nothing_open_is_harmless(self) -> None:
        backend = FakeSandbox()

        await SandboxOperation(backend, ["true"]).aclose()

        assert backend.events == []


class TestValidation:
    """Bad configuration is rejected up front, naming the offending value."""

    def test_commands_must_not_be_empty(self) -> None:
        with pytest.raises(ValueError, match="at least one command"):
            SandboxOperation(FakeSandbox(), [])

    @pytest.mark.parametrize(
        "timeout", [0, -1, -0.5, float("inf"), float("-inf"), float("nan")]
    )
    def test_timeout_must_be_positive(self, timeout: float) -> None:
        with pytest.raises(ValueError, match="positive, finite"):
            SandboxOperation(FakeSandbox(), ["true"], timeout=timeout)

    @pytest.mark.parametrize("name", ["", "A=B", "A\0B"])
    def test_env_names_are_validated(self, name: str) -> None:
        with pytest.raises(ValueError, match="Invalid environment variable name"):
            SandboxOperation(FakeSandbox(), ["true"], env={name: "value"})

    def test_null_bytes_in_env_values_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="null byte"):
            SandboxOperation(FakeSandbox(), ["true"], env={"A": "b\0c"})

    def test_commands_and_env_are_copied(self) -> None:
        commands = ["echo hi"]
        env = {"A": "b"}
        operation = SandboxOperation(FakeSandbox(), commands, env=env)

        commands.append("rm -rf /")
        env["A"] = "tampered"

        assert operation.commands == ["echo hi"]
        assert operation.env == {"A": "b"}
