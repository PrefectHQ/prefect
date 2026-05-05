from __future__ import annotations

import inspect
import logging
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import anyio
import anyio.abc
import pytest

from prefect.runner._flow_run_executor import FlowRunExecutor, ProcessStarter
from prefect.runner._process_manager import ProcessHandle
from prefect.utilities._infrastructure_exit_codes import get_infrastructure_exit_info

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_flow_run(*, cancelled: bool = False, cancelling: bool = False):
    """Return a MagicMock that looks like a FlowRun."""
    flow_run = MagicMock()
    flow_run.id = uuid4()
    flow_run.name = "test-flow-run"
    flow_run.state.is_cancelled.return_value = cancelled
    flow_run.state.is_cancelling.return_value = cancelling
    flow_run.state.is_crashed.return_value = False
    return flow_run


def _make_executor(
    *,
    flow_run=None,
    handle_returncode: int = 0,
    propose_submitting_result: bool = True,
    cancelled: bool = False,
    cancelling: bool = False,
    propose_submitting: bool = True,
):
    """Build a `FlowRunExecutor` with all-mock dependencies.

    Returns (executor, mocks_dict) so tests can assert on collaborators.

    The starter mock simulates the `ProcessStarter` contract: when
    `starter.start(flow_run, task_status=...)` is awaited it calls
    `task_status.started(handle)` then returns (mimicking "block until
    process exits, then return").
    """
    if flow_run is None:
        flow_run = _make_flow_run(cancelled=cancelled, cancelling=cancelling)

    mock_handle = MagicMock(spec=ProcessHandle)
    mock_handle.returncode = handle_returncode

    # Build a starter mock that honours the ProcessStarter contract:
    # call task_status.started(handle) then return.
    mock_starter = MagicMock()

    async def _fake_start(fr, task_status=anyio.TASK_STATUS_IGNORED):
        task_status.started(mock_handle)

    mock_starter.start = AsyncMock(side_effect=_fake_start)

    state_proposer = MagicMock()
    state_proposer.propose_submitting = AsyncMock(
        return_value=propose_submitting_result
    )
    state_proposer.propose_crashed = AsyncMock()
    state_proposer.propose_cancelled = AsyncMock()

    hook_runner = MagicMock()
    hook_runner.run_crashed_hooks = AsyncMock()

    process_manager = MagicMock()
    process_manager.add = AsyncMock()
    process_manager.remove = AsyncMock()
    process_manager.get = MagicMock(return_value=None)

    executor = FlowRunExecutor(
        flow_run=flow_run,
        starter=mock_starter,
        process_manager=process_manager,
        state_proposer=state_proposer,
        hook_runner=hook_runner,
        propose_submitting=propose_submitting,
    )

    mocks = dict(
        flow_run=flow_run,
        handle=mock_handle,
        starter=mock_starter,
        state_proposer=state_proposer,
        hook_runner=hook_runner,
        process_manager=process_manager,
    )
    return executor, mocks


class TestProcessStarterProtocol:
    def test_protocol_is_importable(self):
        """ProcessStarter can be imported from the module."""
        assert ProcessStarter is not None

    def test_protocol_defines_start_method(self):
        """ProcessStarter Protocol defines a start() method."""
        assert hasattr(ProcessStarter, "start")
        sig = inspect.signature(ProcessStarter.start)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "flow_run" in params
        assert "task_status" in params

    def test_async_mock_can_serve_as_starter(self):
        """An AsyncMock with start() attribute works as a stand-in."""
        mock_starter = MagicMock()
        mock_starter.start = AsyncMock()
        # Verifies the mock has the expected attribute
        assert hasattr(mock_starter, "start")

    async def test_conforming_class_can_be_called(self):
        """A conforming class can actually be awaited."""

        class FakeStarter:
            async def start(
                self,
                flow_run,
                task_status=anyio.TASK_STATUS_IGNORED,
            ) -> None:
                handle = ProcessHandle(MagicMock(pid=42, returncode=0))
                task_status.started(handle)

        starter = FakeStarter()
        mock_flow_run = MagicMock()
        mock_task_status = MagicMock()
        mock_task_status.started = MagicMock()

        await starter.start(mock_flow_run, task_status=mock_task_status)
        mock_task_status.started.assert_called_once()
        handle = mock_task_status.started.call_args[0][0]
        assert isinstance(handle, ProcessHandle)
        assert handle.pid == 42


# ---------------------------------------------------------------------------
# FlowRunExecutor.submit() tests
# ---------------------------------------------------------------------------


class TestFlowRunExecutorSubmit:
    """Tests for the happy-path and branching logic inside submit()."""

    async def test_submit_full_lifecycle(self):
        """Happy path: propose_submitting True -> start process ->
        exit_code 0 -> no crash state proposed."""
        executor, m = _make_executor(handle_returncode=0)

        task_status = MagicMock()
        task_status.started = MagicMock()

        await executor.submit(task_status=task_status)

        # Pending proposed
        m["state_proposer"].propose_submitting.assert_awaited_once_with(m["flow_run"])
        # Process started via starter.start (called directly, not via task group)
        m["starter"].start.assert_awaited_once()
        # Handle added to process_manager (inside _start_process)
        m["process_manager"].add.assert_awaited_once_with(m["flow_run"].id, m["handle"])
        # Handle removed from process_manager
        m["process_manager"].remove.assert_awaited_once_with(m["flow_run"].id)
        # No crash proposed (exit code 0)
        m["state_proposer"].propose_crashed.assert_not_awaited()
        m["hook_runner"].run_crashed_hooks.assert_not_awaited()

    async def test_submit_aborts_if_pending_rejected(self):
        """propose_submitting returns False -> no process started."""
        executor, m = _make_executor(propose_submitting_result=False)

        await executor.submit()

        m["state_proposer"].propose_submitting.assert_awaited_once()
        # No process started
        m["starter"].start.assert_not_awaited()

    async def test_submit_marks_cancelling_run_as_cancelled(self):
        """Cancelling run is marked as cancelled before propose_submitting is even called."""
        executor, m = _make_executor(cancelling=True)

        await executor.submit()

        m["state_proposer"].propose_cancelled.assert_awaited_once()
        # propose_submitting should not be reached — early return
        m["state_proposer"].propose_submitting.assert_not_awaited()
        m["starter"].start.assert_not_awaited()

    async def test_submit_marks_cancelling_run_as_cancelled_even_without_propose_submitting(
        self,
    ):
        """Cancelling precheck fires even when propose_submitting=False."""
        executor, m = _make_executor(cancelling=True, propose_submitting=False)

        await executor.submit()

        m["state_proposer"].propose_cancelled.assert_awaited_once()
        m["state_proposer"].propose_submitting.assert_not_awaited()
        m["starter"].start.assert_not_awaited()

    async def test_submit_skips_already_cancelled_run(self):
        """flow_run.state.is_cancelled() True -> log skip -> no process started."""
        executor, m = _make_executor(cancelled=True)

        await executor.submit()

        m["state_proposer"].propose_submitting.assert_awaited_once()
        # No process started
        m["starter"].start.assert_not_awaited()

    async def test_submit_proposes_crashed_on_nonzero_exit(self):
        """mock handle.returncode = 1 -> propose_crashed called."""
        executor, m = _make_executor(handle_returncode=1)

        await executor.submit()

        m["state_proposer"].propose_crashed.assert_awaited_once()
        # Verify the message mentions the exit code
        call_args = m["state_proposer"].propose_crashed.call_args
        assert m["flow_run"] == call_args[0][0]
        assert "1" in call_args[1]["message"]

    async def test_submit_proposes_crashed_when_cancelled_after_start(self):
        """Cancellation after the process has started should mark the run as crashed."""
        executor, m = _make_executor()
        cancelled_error = anyio.get_cancelled_exc_class()()
        executor._start_process = AsyncMock(side_effect=cancelled_error)
        m["process_manager"].get = MagicMock(return_value=m["handle"])

        with pytest.raises(anyio.get_cancelled_exc_class()):
            await executor.submit()

        m["process_manager"].remove.assert_awaited_once_with(m["flow_run"].id)
        m["state_proposer"].propose_crashed.assert_awaited_once_with(
            m["flow_run"],
            message="Flow run process exited due to worker shutdown.",
        )
        m["hook_runner"].run_crashed_hooks.assert_not_awaited()

    async def test_submit_crashed_message_includes_registry_explanation(self):
        """The crashed state message should include the explanation from
        the centralized exit code registry."""
        executor, m = _make_executor(handle_returncode=-9)

        await executor.submit()

        call_args = m["state_proposer"].propose_crashed.call_args
        msg = call_args[1]["message"]
        info = get_infrastructure_exit_info(-9)
        assert str(-9) in msg
        assert info.explanation in msg

    async def test_submit_logs_resolution_separately(
        self, caplog: "pytest.LogCaptureFixture"
    ):
        """Resolution hint should be logged as a separate INFO message."""
        executor, m = _make_executor(handle_returncode=137)

        with caplog.at_level(logging.INFO, logger="prefect.runner.flow_run_executor"):
            await executor.submit()

        info = get_infrastructure_exit_info(137)
        # The resolution should appear as a separate log record
        resolution_records = [r for r in caplog.records if r.message == info.resolution]
        assert len(resolution_records) == 1
        assert resolution_records[0].levelno == logging.INFO

    async def test_submit_passes_proposed_state_to_crashed_hooks(self):
        """run_crashed_hooks receives the state returned by propose_crashed,
        not self._flow_run.state."""
        mock_crashed_state = MagicMock()
        executor, m = _make_executor(handle_returncode=1)
        m["state_proposer"].propose_crashed = AsyncMock(return_value=mock_crashed_state)

        await executor.submit()

        m["hook_runner"].run_crashed_hooks.assert_awaited_once_with(
            m["flow_run"], mock_crashed_state
        )

    async def test_submit_calls_crashed_hooks_after_state_proposal(self):
        """run_crashed_hooks called after propose_crashed."""
        call_order: list[str] = []

        executor, m = _make_executor(handle_returncode=1)

        original_propose_crashed = m["state_proposer"].propose_crashed

        async def tracking_propose_crashed(*args, **kwargs):
            call_order.append("propose_crashed")
            return await original_propose_crashed(*args, **kwargs)

        m["state_proposer"].propose_crashed = AsyncMock(
            side_effect=tracking_propose_crashed
        )

        original_run_crashed_hooks = m["hook_runner"].run_crashed_hooks

        async def tracking_run_crashed_hooks(*args, **kwargs):
            call_order.append("run_crashed_hooks")
            return await original_run_crashed_hooks(*args, **kwargs)

        m["hook_runner"].run_crashed_hooks = AsyncMock(
            side_effect=tracking_run_crashed_hooks
        )

        await executor.submit()

        assert call_order.index("propose_crashed") < call_order.index(
            "run_crashed_hooks"
        )

    async def test_submit_signals_task_status_with_handle(self):
        """Outer task_status.started(handle) called with ProcessHandle."""
        executor, m = _make_executor()

        task_status = MagicMock()
        task_status.started = MagicMock()

        await executor.submit(task_status=task_status)

        task_status.started.assert_called_once_with(m["handle"])

    async def test_submit_blocks_until_process_exits(self):
        """Verify that exit-code handling happens AFTER the
        starter returns (i.e., after process exits), not immediately after
        task_status.started() is called."""
        call_order: list[str] = []

        executor, m = _make_executor(handle_returncode=1)

        # Replace the starter with one that records timing
        async def _tracking_start(fr, task_status=anyio.TASK_STATUS_IGNORED):
            call_order.append("starter_signals_started")
            task_status.started(m["handle"])
            # Simulate process running for a while before exiting
            call_order.append("starter_process_exits")

        m["starter"].start = AsyncMock(side_effect=_tracking_start)

        original_propose_crashed = m["state_proposer"].propose_crashed

        async def tracking_propose_crashed(*args, **kwargs):
            call_order.append("propose_crashed")
            return await original_propose_crashed(*args, **kwargs)

        m["state_proposer"].propose_crashed = AsyncMock(
            side_effect=tracking_propose_crashed
        )

        await executor.submit()

        # Exit-code handling must happen AFTER the process exits
        assert call_order.index("starter_signals_started") < call_order.index(
            "starter_process_exits"
        )
        assert call_order.index("starter_process_exits") < call_order.index(
            "propose_crashed"
        )

    async def test_submit_adds_handle_to_process_manager_before_cleanup(self):
        """Handle is registered with process_manager after starter signals
        started, allowing cancellation to find it during the run."""
        executor, m = _make_executor()

        await executor.submit()

        m["process_manager"].add.assert_awaited_once_with(m["flow_run"].id, m["handle"])
        # Also removed during cleanup
        m["process_manager"].remove.assert_awaited_once_with(m["flow_run"].id)

    async def test_submit_skips_propose_submitting_when_disabled(self):
        """When propose_submitting=False, propose_submitting() is never called
        and the process starts directly."""
        executor, m = _make_executor(handle_returncode=0, propose_submitting=False)

        task_status = MagicMock()
        task_status.started = MagicMock()

        await executor.submit(task_status=task_status)

        # propose_submitting should NOT have been called
        m["state_proposer"].propose_submitting.assert_not_awaited()
        # But the process should still have started
        m["starter"].start.assert_awaited_once()
        # And the handle forwarded
        task_status.started.assert_called_once_with(m["handle"])

    async def test_submit_default_proposes_submitting(self):
        """Default executor (propose_submitting=True) calls propose_submitting()."""
        executor, m = _make_executor(handle_returncode=0)

        await executor.submit()

        m["state_proposer"].propose_submitting.assert_awaited_once_with(m["flow_run"])

    async def test_handle_registered_while_process_alive(self):
        """INT-02: process_manager.add() is called DURING process execution,
        not after process exits.  The inner task group pattern ensures the
        handle is registered between task_status.started() and process exit."""
        call_order: list[str] = []

        executor, m = _make_executor(handle_returncode=0)

        # A starter that records when started() fires and when it "exits"
        # with an asyncio.Event gate in between to prove ordering.
        process_running = anyio.Event()
        process_may_exit = anyio.Event()

        async def _gated_start(fr, task_status=anyio.TASK_STATUS_IGNORED):
            task_status.started(m["handle"])
            call_order.append("started_signalled")
            process_running.set()
            await process_may_exit.wait()
            call_order.append("process_exited")

        m["starter"].start = AsyncMock(side_effect=_gated_start)

        original_add = m["process_manager"].add

        async def _tracking_add(*args, **kwargs):
            call_order.append("pm_add")
            return await original_add(*args, **kwargs)

        m["process_manager"].add = AsyncMock(side_effect=_tracking_add)

        async with anyio.create_task_group() as tg:

            async def _run_submit():
                await executor.submit()

            tg.start_soon(_run_submit)
            # Wait until the process has signalled started
            await process_running.wait()
            # At this point pm_add should have been called (before process exits)
            assert "pm_add" in call_order, (
                "process_manager.add() must be called while process is alive"
            )
            assert "process_exited" not in call_order, (
                "process should not have exited yet"
            )
            # Let the process exit
            process_may_exit.set()

        assert call_order == [
            "started_signalled",
            "pm_add",
            "process_exited",
        ]


# ---------------------------------------------------------------------------
# FlowRunExecutorContext._handle_cancellation_observer_failure tests
# ---------------------------------------------------------------------------


class TestCancellationObserverFailure:
    def test_cancellation_observer_failure_logs_warning_when_crash_disabled(
        self, caplog: pytest.LogCaptureFixture
    ):
        """Default setting: logs a warning and does not kill processes."""
        from prefect.runner._flow_run_executor import FlowRunExecutorContext

        ctx = FlowRunExecutorContext()
        ctx._logger = logging.getLogger("test.executor_context")
        ctx._cancellation_task_group = MagicMock()
        ctx.process_manager = MagicMock()

        flow_run_ids = {uuid4(), uuid4()}

        with caplog.at_level(logging.WARNING, logger="test.executor_context"):
            ctx._handle_cancellation_observer_failure(flow_run_ids)

        assert "Cancellation observer failed" in caplog.text
        assert "PREFECT_RUNNER_CRASH_ON_CANCELLATION_FAILURE" in caplog.text
        ctx._cancellation_task_group.start_soon.assert_not_called()

    def test_cancellation_observer_failure_kills_processes_when_crash_enabled(
        self, caplog: pytest.LogCaptureFixture
    ):
        """When crash_on_cancellation_failure is enabled, kills all in-flight runs."""
        from prefect.runner._flow_run_executor import FlowRunExecutorContext
        from prefect.settings import (
            PREFECT_RUNNER_CRASH_ON_CANCELLATION_FAILURE,
            temporary_settings,
        )

        ctx = FlowRunExecutorContext()
        ctx._logger = logging.getLogger("test.executor_context")
        ctx._cancellation_task_group = MagicMock()
        ctx.process_manager = MagicMock()

        frid1, frid2 = uuid4(), uuid4()
        flow_run_ids = {frid1, frid2}

        with temporary_settings({PREFECT_RUNNER_CRASH_ON_CANCELLATION_FAILURE: True}):
            with caplog.at_level(logging.ERROR, logger="test.executor_context"):
                ctx._handle_cancellation_observer_failure(flow_run_ids)

        assert "killing 2 in-flight flow run(s)" in caplog.text
        assert ctx._cancellation_task_group.start_soon.call_count == 2

        killed_ids = {
            call.args[1]
            for call in ctx._cancellation_task_group.start_soon.call_args_list
        }
        assert killed_ids == flow_run_ids
