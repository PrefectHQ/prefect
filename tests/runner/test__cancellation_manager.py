from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from prefect.runner._cancellation_manager import _CancellationManager

from prefect.client.schemas.objects import StateType


def _make_flow_run(*, has_state: bool = True) -> MagicMock:
    flow_run = MagicMock()
    flow_run.id = uuid4()
    flow_run.name = f"test-run-{flow_run.id.hex[:8]}"
    if has_state:
        state = MagicMock()
        state.type = StateType.CANCELLING
        state.is_cancelling.return_value = True
        flow_run.state = state
    else:
        flow_run.state = None
    return flow_run


def _make_process_handle(*, pid: int = 12345) -> MagicMock:
    handle = MagicMock()
    handle.pid = pid
    return handle


def _make_manager(
    *,
    process_manager: MagicMock | None = None,
    hook_runner: MagicMock | None = None,
    state_proposer: MagicMock | None = None,
    event_emitter: MagicMock | None = None,
    client: MagicMock | None = None,
) -> _CancellationManager:
    if process_manager is None:
        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()
        process_manager.kill = AsyncMock()
        process_manager.flow_run_ids.return_value = set()

    if hook_runner is None:
        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock()

    if state_proposer is None:
        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock()

    if event_emitter is None:
        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

    if client is None:
        client = MagicMock()
        client.read_flow_run = AsyncMock()

    return _CancellationManager(
        process_manager=process_manager,
        hook_runner=hook_runner,
        state_proposer=state_proposer,
        event_emitter=event_emitter,
        client=client,
    )


class TestCancellationManagerCancel:
    async def test_cancel_executes_full_sequence(self):
        """All four steps called in order: kill, hooks, state, event."""
        flow_run = _make_flow_run()
        handle = _make_process_handle()

        process_manager = MagicMock()
        process_manager.get.return_value = handle
        process_manager.kill = AsyncMock()

        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock()

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock()

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        mgr = _make_manager(
            process_manager=process_manager,
            hook_runner=hook_runner,
            state_proposer=state_proposer,
            event_emitter=event_emitter,
        )

        await mgr.cancel(flow_run)

        process_manager.kill.assert_awaited_once_with(flow_run.id)
        hook_runner.run_cancellation_hooks.assert_awaited_once_with(
            flow_run, flow_run.state
        )
        state_proposer.propose_cancelled.assert_awaited_once()
        event_emitter.get_flow_and_deployment.assert_awaited_once_with(flow_run)
        event_emitter.emit_flow_run_cancelled.assert_awaited_once()

    async def test_cancel_skips_if_no_process(self):
        """When process_manager.get() returns None, method returns early."""
        flow_run = _make_flow_run()

        process_manager = MagicMock()
        process_manager.get.return_value = None
        process_manager.kill = AsyncMock()

        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock()

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock()

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock()
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        mgr = _make_manager(
            process_manager=process_manager,
            hook_runner=hook_runner,
            state_proposer=state_proposer,
            event_emitter=event_emitter,
        )

        await mgr.cancel(flow_run)

        process_manager.kill.assert_not_awaited()
        hook_runner.run_cancellation_hooks.assert_not_awaited()
        state_proposer.propose_cancelled.assert_not_awaited()
        event_emitter.emit_flow_run_cancelled.assert_not_awaited()

    async def test_cancel_skips_if_handle_has_no_pid(self):
        """When handle.pid is None, method returns early."""
        flow_run = _make_flow_run()

        handle = MagicMock()
        handle.pid = None

        process_manager = MagicMock()
        process_manager.get.return_value = handle
        process_manager.kill = AsyncMock()

        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock()

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock()

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock()
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        mgr = _make_manager(
            process_manager=process_manager,
            hook_runner=hook_runner,
            state_proposer=state_proposer,
            event_emitter=event_emitter,
        )

        await mgr.cancel(flow_run)

        process_manager.kill.assert_not_awaited()
        hook_runner.run_cancellation_hooks.assert_not_awaited()
        state_proposer.propose_cancelled.assert_not_awaited()
        event_emitter.emit_flow_run_cancelled.assert_not_awaited()

    async def test_cancel_continues_after_process_lookup_error(self):
        """kill raises ProcessLookupError; hooks, state, event still called."""
        flow_run = _make_flow_run()

        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()
        process_manager.kill = AsyncMock(side_effect=ProcessLookupError)

        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock()

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock()

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        mgr = _make_manager(
            process_manager=process_manager,
            hook_runner=hook_runner,
            state_proposer=state_proposer,
            event_emitter=event_emitter,
        )

        await mgr.cancel(flow_run)

        hook_runner.run_cancellation_hooks.assert_awaited_once()
        state_proposer.propose_cancelled.assert_awaited_once()
        event_emitter.emit_flow_run_cancelled.assert_awaited_once()

    async def test_cancel_aborts_on_unexpected_kill_error(self):
        """kill raises PermissionError; hooks, state, event NOT called."""
        flow_run = _make_flow_run()

        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()
        process_manager.kill = AsyncMock(side_effect=PermissionError("denied"))

        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock()

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock()

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock()
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        mgr = _make_manager(
            process_manager=process_manager,
            hook_runner=hook_runner,
            state_proposer=state_proposer,
            event_emitter=event_emitter,
        )

        await mgr.cancel(flow_run)

        hook_runner.run_cancellation_hooks.assert_not_awaited()
        state_proposer.propose_cancelled.assert_not_awaited()
        event_emitter.emit_flow_run_cancelled.assert_not_awaited()

    async def test_cancel_continues_after_hook_failure(self):
        """Hooks raise, but state and event still called."""
        flow_run = _make_flow_run()

        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()
        process_manager.kill = AsyncMock()

        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock(
            side_effect=RuntimeError("hook failed")
        )

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock()

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        mgr = _make_manager(
            process_manager=process_manager,
            hook_runner=hook_runner,
            state_proposer=state_proposer,
            event_emitter=event_emitter,
        )

        await mgr.cancel(flow_run)

        state_proposer.propose_cancelled.assert_awaited_once()
        event_emitter.emit_flow_run_cancelled.assert_awaited_once()

    async def test_cancel_omits_hooks_when_no_state(self):
        """flow_run.state is None; hook call skipped; state and event still called."""
        flow_run = _make_flow_run(has_state=False)

        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()
        process_manager.kill = AsyncMock()

        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock()

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock()

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        mgr = _make_manager(
            process_manager=process_manager,
            hook_runner=hook_runner,
            state_proposer=state_proposer,
            event_emitter=event_emitter,
        )

        await mgr.cancel(flow_run)

        hook_runner.run_cancellation_hooks.assert_not_awaited()
        state_proposer.propose_cancelled.assert_awaited_once()
        event_emitter.emit_flow_run_cancelled.assert_awaited_once()

    async def test_cancel_uses_custom_state_msg(self):
        """state_msg arg passed through to propose_cancelled."""
        flow_run = _make_flow_run()
        mgr = _make_manager()

        await mgr.cancel(flow_run, state_msg="Custom cancellation reason")

        propose_call = mgr._state_proposer.propose_cancelled.call_args
        assert (
            propose_call.kwargs["state_updates"]["message"]
            == "Custom cancellation reason"
        )


class TestCancellationManagerCancelAll:
    async def test_cancel_all_iterates_snapshot(self):
        """Mocked process_manager.flow_run_ids() returns {uuid1, uuid2}; cancel called for each."""
        uuid1, uuid2 = uuid4(), uuid4()
        flow_run_1 = _make_flow_run()
        flow_run_1.id = uuid1
        flow_run_2 = _make_flow_run()
        flow_run_2.id = uuid2

        process_manager = MagicMock()
        process_manager.flow_run_ids.return_value = {uuid1, uuid2}
        process_manager.get.return_value = _make_process_handle()
        process_manager.kill = AsyncMock()

        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock()

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock()

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        client = MagicMock()

        def read_flow_run_side_effect(fid):
            if fid == uuid1:
                return flow_run_1
            return flow_run_2

        client.read_flow_run = AsyncMock(side_effect=read_flow_run_side_effect)

        mgr = _make_manager(
            process_manager=process_manager,
            hook_runner=hook_runner,
            state_proposer=state_proposer,
            event_emitter=event_emitter,
            client=client,
        )

        await mgr.cancel_all()

        assert client.read_flow_run.await_count == 2
        assert process_manager.kill.await_count == 2

    async def test_cancel_all_continues_after_single_failure(self):
        """One cancel raises; the other still runs."""
        uuid1, uuid2 = uuid4(), uuid4()
        flow_run_1 = _make_flow_run()
        flow_run_1.id = uuid1
        flow_run_2 = _make_flow_run()
        flow_run_2.id = uuid2

        process_manager = MagicMock()
        process_manager.flow_run_ids.return_value = {uuid1, uuid2}
        process_manager.get.return_value = _make_process_handle()
        process_manager.kill = AsyncMock()

        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock()

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock()

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        client = MagicMock()
        # First read fails, second succeeds
        client.read_flow_run = AsyncMock(
            side_effect=[RuntimeError("API down"), flow_run_2]
        )

        mgr = _make_manager(
            process_manager=process_manager,
            hook_runner=hook_runner,
            state_proposer=state_proposer,
            event_emitter=event_emitter,
            client=client,
        )

        await mgr.cancel_all()

        # Both should be attempted
        assert client.read_flow_run.await_count == 2
        # At least one cancel sequence completes (kill called at least once)
        assert process_manager.kill.await_count >= 1


class TestCancellationManagerCancelById:
    async def test_cancel_by_id_fetches_then_cancels(self):
        """client.read_flow_run called; cancel called with returned flow_run."""
        flow_run = _make_flow_run()
        flow_run_id = flow_run.id

        client = MagicMock()
        client.read_flow_run = AsyncMock(return_value=flow_run)

        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()
        process_manager.kill = AsyncMock()

        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock()

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock()

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        mgr = _make_manager(
            process_manager=process_manager,
            hook_runner=hook_runner,
            state_proposer=state_proposer,
            event_emitter=event_emitter,
            client=client,
        )

        await mgr.cancel_by_id(flow_run_id)

        client.read_flow_run.assert_awaited_once_with(flow_run_id)
        process_manager.kill.assert_awaited_once_with(flow_run.id)
        state_proposer.propose_cancelled.assert_awaited_once()
        event_emitter.emit_flow_run_cancelled.assert_awaited_once()
