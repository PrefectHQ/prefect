from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import anyio
import anyio.abc

from prefect.runner._flow_run_executor import FlowRunExecutor, ProcessStarter
from prefect.runner._process_manager import ProcessHandle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_flow_run(*, cancelled: bool = False):
    """Return a MagicMock that looks like a FlowRun."""
    flow_run = MagicMock()
    flow_run.id = uuid4()
    flow_run.name = "test-flow-run"
    flow_run.state.is_cancelled.return_value = cancelled
    flow_run.state.is_crashed.return_value = False
    return flow_run


def _make_executor(
    *,
    flow_run=None,
    handle_returncode: int = 0,
    propose_pending_result: bool = True,
    cancelled: bool = False,
):
    """Build a `FlowRunExecutor` with all-mock dependencies.

    Returns (executor, mocks_dict) so tests can assert on collaborators.
    """
    if flow_run is None:
        flow_run = _make_flow_run(cancelled=cancelled)

    mock_handle = MagicMock(spec=ProcessHandle)
    mock_handle.returncode = handle_returncode

    mock_starter = MagicMock()
    mock_starter.start = AsyncMock()

    limit_slot_token = uuid4()
    limit_manager = MagicMock()
    limit_manager.acquire.return_value = limit_slot_token
    limit_manager.release = MagicMock()

    state_proposer = MagicMock()
    state_proposer.propose_pending = AsyncMock(return_value=propose_pending_result)
    state_proposer.propose_crashed = AsyncMock()

    hook_runner = MagicMock()
    hook_runner.run_crashed_hooks = AsyncMock()

    cancellation_manager = MagicMock()
    cancellation_manager.cancel = AsyncMock()

    process_manager = MagicMock()
    process_manager.add = AsyncMock()
    process_manager.remove = AsyncMock()
    process_manager.get = MagicMock(return_value=None)

    runs_task_group = MagicMock()
    runs_task_group.start = AsyncMock(return_value=mock_handle)

    client = MagicMock()

    executor = FlowRunExecutor(
        flow_run=flow_run,
        starter=mock_starter,
        process_manager=process_manager,
        limit_manager=limit_manager,
        state_proposer=state_proposer,
        hook_runner=hook_runner,
        cancellation_manager=cancellation_manager,
        runs_task_group=runs_task_group,
        client=client,
    )

    mocks = dict(
        flow_run=flow_run,
        handle=mock_handle,
        starter=mock_starter,
        limit_manager=limit_manager,
        limit_slot_token=limit_slot_token,
        state_proposer=state_proposer,
        hook_runner=hook_runner,
        cancellation_manager=cancellation_manager,
        process_manager=process_manager,
        runs_task_group=runs_task_group,
        client=client,
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
        """Happy path: acquire slot -> propose_pending True -> start process ->
        release slot -> exit_code 0 -> no crash state proposed."""
        executor, m = _make_executor(handle_returncode=0)

        task_status = MagicMock()
        task_status.started = MagicMock()

        await executor.submit(task_status=task_status)

        # Slot acquired
        m["limit_manager"].acquire.assert_called_once()
        # Pending proposed
        m["state_proposer"].propose_pending.assert_awaited_once_with(m["flow_run"])
        # Process started via runs_task_group.start
        m["runs_task_group"].start.assert_awaited_once_with(
            m["starter"].start, m["flow_run"]
        )
        # Handle added to process_manager
        m["process_manager"].add.assert_awaited_once_with(m["flow_run"].id, m["handle"])
        # Slot released
        m["limit_manager"].release.assert_called_once_with(m["limit_slot_token"])
        # Handle removed from process_manager
        m["process_manager"].remove.assert_awaited_once_with(m["flow_run"].id)
        # No crash proposed (exit code 0)
        m["state_proposer"].propose_crashed.assert_not_awaited()
        m["hook_runner"].run_crashed_hooks.assert_not_awaited()

    async def test_submit_aborts_if_pending_rejected(self):
        """propose_pending returns False -> release slot -> no process started."""
        executor, m = _make_executor(propose_pending_result=False)

        await executor.submit()

        m["state_proposer"].propose_pending.assert_awaited_once()
        # Slot acquired then released
        m["limit_manager"].acquire.assert_called_once()
        m["limit_manager"].release.assert_called_once_with(m["limit_slot_token"])
        # No process started
        m["runs_task_group"].start.assert_not_awaited()

    async def test_submit_skips_already_cancelled_run(self):
        """flow_run.state.is_cancelled() True -> log skip -> release slot ->
        no process started."""
        executor, m = _make_executor(cancelled=True)

        await executor.submit()

        m["state_proposer"].propose_pending.assert_awaited_once()
        # Slot released (via finally)
        m["limit_manager"].release.assert_called_once_with(m["limit_slot_token"])
        # No process started
        m["runs_task_group"].start.assert_not_awaited()

    async def test_submit_releases_slot_before_state_proposal(self):
        """Verify release called BEFORE propose_crashed (use call_order tracking)."""
        call_order: list[str] = []

        executor, m = _make_executor(handle_returncode=1)

        original_release = m["limit_manager"].release

        def tracking_release(token):
            call_order.append("release")
            return original_release(token)

        m["limit_manager"].release = MagicMock(side_effect=tracking_release)

        original_propose_crashed = m["state_proposer"].propose_crashed

        async def tracking_propose_crashed(*args, **kwargs):
            call_order.append("propose_crashed")
            return await original_propose_crashed(*args, **kwargs)

        m["state_proposer"].propose_crashed = AsyncMock(
            side_effect=tracking_propose_crashed
        )

        await executor.submit()

        assert "release" in call_order
        assert "propose_crashed" in call_order
        assert call_order.index("release") < call_order.index("propose_crashed")

    async def test_submit_proposes_crashed_on_nonzero_exit(self):
        """mock handle.returncode = 1 -> propose_crashed called."""
        executor, m = _make_executor(handle_returncode=1)

        await executor.submit()

        m["state_proposer"].propose_crashed.assert_awaited_once()
        # Verify the message mentions the exit code
        call_args = m["state_proposer"].propose_crashed.call_args
        assert m["flow_run"] == call_args[0][0]
        assert "1" in call_args[1]["message"]

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

    async def test_submit_acquires_and_releases_slot_token(self):
        """Same UUID token passed to release() that was returned by acquire()."""
        executor, m = _make_executor()

        await executor.submit()

        acquired_token = m["limit_manager"].acquire.return_value
        m["limit_manager"].release.assert_called_once_with(acquired_token)
        assert acquired_token == m["limit_slot_token"]

    async def test_submit_signals_task_status_with_handle(self):
        """Outer task_status.started(handle) called with ProcessHandle."""
        executor, m = _make_executor()

        task_status = MagicMock()
        task_status.started = MagicMock()

        await executor.submit(task_status=task_status)

        task_status.started.assert_called_once_with(m["handle"])


class TestFlowRunExecutorSlotExhausted:
    """Tests for when no concurrency slots are available."""

    async def test_submit_returns_early_if_no_slots(self):
        """acquire raises WouldBlock -> method returns immediately, no other calls."""
        executor, m = _make_executor()
        m["limit_manager"].acquire.side_effect = anyio.WouldBlock

        await executor.submit()

        m["limit_manager"].acquire.assert_called_once()
        # Nothing else should happen
        m["state_proposer"].propose_pending.assert_not_awaited()
        m["runs_task_group"].start.assert_not_awaited()
        m["limit_manager"].release.assert_not_called()
        m["process_manager"].add.assert_not_awaited()
        m["process_manager"].remove.assert_not_awaited()
