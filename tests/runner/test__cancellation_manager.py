from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from prefect.client.schemas.objects import StateType
from prefect.runner._cancellation_manager import CancellationManager


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
    control_channel: MagicMock | None = None,
) -> CancellationManager:
    if process_manager is None:
        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()
        process_manager.wait_for_exit = AsyncMock(return_value=False)
        process_manager.kill = AsyncMock()
        process_manager.flow_run_ids.return_value = set()

    if hook_runner is None:
        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock()

    if state_proposer is None:
        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock()
        state_proposer.propose_crashed = AsyncMock(return_value=MagicMock())

    if event_emitter is None:
        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

    if client is None:
        client = MagicMock()
        client.read_flow_run = AsyncMock()

    return CancellationManager(
        process_manager=process_manager,
        hook_runner=hook_runner,
        state_proposer=state_proposer,
        event_emitter=event_emitter,
        client=client,
        control_channel=control_channel,
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

        process_manager.kill.assert_awaited_once_with(flow_run.id, grace_seconds=30.0)
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

    async def test_cancel_skips_finalization_when_acked_process_is_already_completed(
        self,
    ):
        flow_run = _make_flow_run()

        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()
        process_manager.kill = AsyncMock(side_effect=ProcessLookupError)

        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock()

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock(return_value=True)

        final_state = MagicMock()
        final_state.is_cancelled.return_value = False
        final_state.is_final.return_value = True
        final_state.type.value = "COMPLETED"

        client = MagicMock()
        client.read_flow_run = AsyncMock(return_value=MagicMock(state=final_state))

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        control_channel = MagicMock()
        control_channel.signal = AsyncMock(return_value=True)

        mgr = _make_manager(
            process_manager=process_manager,
            hook_runner=hook_runner,
            state_proposer=state_proposer,
            event_emitter=event_emitter,
            client=client,
            control_channel=control_channel,
        )

        await mgr.cancel(flow_run)

        client.read_flow_run.assert_awaited_once_with(flow_run.id)
        hook_runner.run_cancellation_hooks.assert_not_awaited()
        state_proposer.propose_cancelled.assert_not_awaited()
        event_emitter.emit_flow_run_cancelled.assert_not_awaited()

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
        assert propose_call.args[1]["message"] == "Custom cancellation reason"

    async def test_cancel_falls_back_to_crashed_when_cancelled_state_cannot_be_verified(
        self,
    ):
        flow_run = _make_flow_run()

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock(
            side_effect=RuntimeError("api down")
        )
        state_proposer.propose_crashed = AsyncMock(return_value=MagicMock())

        non_terminal = MagicMock()
        non_terminal.is_cancelled.return_value = False
        non_terminal.is_final.return_value = False
        current_run = MagicMock(state=non_terminal)

        client = MagicMock()
        client.read_flow_run = AsyncMock(return_value=current_run)

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        mgr = _make_manager(
            state_proposer=state_proposer,
            client=client,
            event_emitter=event_emitter,
        )

        await mgr.cancel(flow_run)

        state_proposer.propose_crashed.assert_awaited_once()
        event_emitter.emit_flow_run_cancelled.assert_not_awaited()

    async def test_cancel_emits_cancelled_event_when_re_read_confirms_cancelled(
        self,
    ):
        flow_run = _make_flow_run()

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock(
            side_effect=RuntimeError("api down")
        )
        state_proposer.propose_crashed = AsyncMock()

        cancelled_state = MagicMock()
        cancelled_state.is_cancelled.return_value = True
        cancelled_state.is_final.return_value = True
        current_run = MagicMock(state=cancelled_state)

        client = MagicMock()
        client.read_flow_run = AsyncMock(return_value=current_run)

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        mgr = _make_manager(
            state_proposer=state_proposer,
            client=client,
            event_emitter=event_emitter,
        )

        await mgr.cancel(flow_run)

        state_proposer.propose_crashed.assert_not_awaited()
        event_emitter.emit_flow_run_cancelled.assert_awaited_once()

    async def test_cancel_treats_successful_cancel_write_as_durable_without_reread(
        self,
    ):
        flow_run = _make_flow_run()

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock(return_value=True)
        state_proposer.propose_crashed = AsyncMock()

        client = MagicMock()
        client.read_flow_run = AsyncMock(side_effect=RuntimeError("api down"))

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        mgr = _make_manager(
            state_proposer=state_proposer,
            client=client,
            event_emitter=event_emitter,
        )

        await mgr.cancel(flow_run)

        client.read_flow_run.assert_not_awaited()
        state_proposer.propose_crashed.assert_not_awaited()
        event_emitter.emit_flow_run_cancelled.assert_awaited_once()

    async def test_cancel_falls_back_to_crashed_when_propose_cancelled_noops(
        self,
    ):
        flow_run = _make_flow_run(has_state=False)

        state_proposer = MagicMock()
        state_proposer.propose_cancelled = AsyncMock(return_value=False)
        state_proposer.propose_crashed = AsyncMock(return_value=MagicMock())

        current_run = MagicMock(state=None)

        client = MagicMock()
        client.read_flow_run = AsyncMock(return_value=current_run)

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock(return_value=(None, None))
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        mgr = _make_manager(
            state_proposer=state_proposer,
            client=client,
            event_emitter=event_emitter,
        )

        await mgr.cancel(flow_run)

        state_proposer.propose_cancelled.assert_awaited_once()
        state_proposer.propose_crashed.assert_awaited_once()
        event_emitter.emit_flow_run_cancelled.assert_not_awaited()

    async def test_cancel_waits_for_acked_process_before_fallback_kill_on_windows(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Acked cancellation should get a graceful-exit window before kill."""
        flow_run = _make_flow_run()
        call_order: list[str] = []
        monkeypatch.setattr("prefect.runner._cancellation_manager.os.name", "nt")

        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()

        async def _wait(_id, *, grace_seconds):
            call_order.append("wait")
            return False

        async def _kill(_id, *, grace_seconds):
            call_order.append("kill")

        process_manager.wait_for_exit = AsyncMock(side_effect=_wait)
        process_manager.kill = AsyncMock(side_effect=_kill)

        control_channel = MagicMock()

        async def _signal(_id, _intent):
            call_order.append("signal")
            return True

        control_channel.signal = AsyncMock(side_effect=_signal)

        mgr = _make_manager(
            process_manager=process_manager,
            control_channel=control_channel,
        )

        monotonic_values = iter([100.0, 112.5])
        monkeypatch.setattr(
            "prefect.runner._cancellation_manager.time.monotonic",
            lambda: next(monotonic_values, 112.5),
        )

        await mgr.cancel(flow_run)

        control_channel.signal.assert_awaited_once_with(flow_run.id, "cancel")
        process_manager.wait_for_exit.assert_awaited_once_with(
            flow_run.id, grace_seconds=30.0
        )
        process_manager.kill.assert_awaited_once_with(flow_run.id, grace_seconds=17.5)
        assert call_order == ["signal", "wait", "kill"]

    async def test_cancel_skips_kill_if_acked_process_exits_during_grace_period_on_windows(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("prefect.runner._cancellation_manager.os.name", "nt")
        flow_run = _make_flow_run()

        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()
        process_manager.wait_for_exit = AsyncMock(return_value=True)
        process_manager.kill = AsyncMock()

        control_channel = MagicMock()
        control_channel.signal = AsyncMock(return_value=True)

        mgr = _make_manager(
            process_manager=process_manager,
            control_channel=control_channel,
        )

        await mgr.cancel(flow_run)

        process_manager.wait_for_exit.assert_awaited_once_with(
            flow_run.id, grace_seconds=30.0
        )
        process_manager.kill.assert_not_awaited()

    async def test_cancel_skips_finalization_if_acked_process_already_finalized_on_windows(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("prefect.runner._cancellation_manager.os.name", "nt")
        monkeypatch.setattr(
            "prefect.runner._cancellation_manager.should_skip_cancel_after_acked_process_exit",
            AsyncMock(return_value=True),
        )
        flow_run = _make_flow_run()

        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()
        process_manager.wait_for_exit = AsyncMock(return_value=True)
        process_manager.kill = AsyncMock()

        hook_runner = MagicMock()
        hook_runner.run_cancellation_hooks = AsyncMock()

        event_emitter = MagicMock()
        event_emitter.get_flow_and_deployment = AsyncMock()
        event_emitter.emit_flow_run_cancelled = AsyncMock()

        mgr = _make_manager(
            process_manager=process_manager,
            hook_runner=hook_runner,
            event_emitter=event_emitter,
            control_channel=MagicMock(signal=AsyncMock(return_value=True)),
        )
        mgr._finalize_cancelled_state = AsyncMock(return_value=True)

        await mgr.cancel(flow_run)

        process_manager.kill.assert_not_awaited()
        hook_runner.run_cancellation_hooks.assert_not_awaited()
        mgr._finalize_cancelled_state.assert_not_awaited()
        event_emitter.emit_flow_run_cancelled.assert_not_awaited()

    async def test_cancel_kills_immediately_after_ack_on_posix(self):
        flow_run = _make_flow_run()

        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()
        process_manager.wait_for_exit = AsyncMock()
        process_manager.kill = AsyncMock()

        control_channel = MagicMock()
        control_channel.signal = AsyncMock(return_value=True)

        mgr = _make_manager(
            process_manager=process_manager,
            control_channel=control_channel,
        )

        await mgr.cancel(flow_run)

        process_manager.wait_for_exit.assert_not_awaited()
        process_manager.kill.assert_awaited_once_with(flow_run.id, grace_seconds=30.0)

    async def test_cancel_falls_through_when_channel_returns_false(self):
        """If the channel reports the child did not ack, kill still proceeds."""
        flow_run = _make_flow_run()

        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()
        process_manager.wait_for_exit = AsyncMock()
        process_manager.kill = AsyncMock()

        control_channel = MagicMock()
        control_channel.signal = AsyncMock(return_value=False)

        mgr = _make_manager(
            process_manager=process_manager,
            control_channel=control_channel,
        )

        await mgr.cancel(flow_run)

        control_channel.signal.assert_awaited_once_with(flow_run.id, "cancel")
        process_manager.wait_for_exit.assert_not_awaited()
        process_manager.kill.assert_awaited_once_with(flow_run.id, grace_seconds=30.0)

    async def test_cancel_falls_through_when_channel_raises(self):
        """If the channel raises, kill still proceeds — channel is best-effort."""
        flow_run = _make_flow_run()

        process_manager = MagicMock()
        process_manager.get.return_value = _make_process_handle()
        process_manager.wait_for_exit = AsyncMock()
        process_manager.kill = AsyncMock()

        control_channel = MagicMock()
        control_channel.signal = AsyncMock(side_effect=RuntimeError("channel oops"))

        mgr = _make_manager(
            process_manager=process_manager,
            control_channel=control_channel,
        )

        await mgr.cancel(flow_run)

        process_manager.wait_for_exit.assert_not_awaited()
        process_manager.kill.assert_awaited_once_with(flow_run.id, grace_seconds=30.0)


class TestCancellationManagerCancelAll:
    async def test_cancel_all_iterates_snapshot(self):
        """Mocked process_manager.flow_run_ids() returns {uuid1, uuid2}; cancel called for each."""
        uuid1, uuid2 = uuid4(), uuid4()
        flow_run_1 = _make_flow_run()
        flow_run_1.id = uuid1
        flow_run_1.state.is_cancelled.return_value = True
        flow_run_1.state.is_final.return_value = True
        flow_run_2 = _make_flow_run()
        flow_run_2.id = uuid2
        flow_run_2.state.is_cancelled.return_value = True
        flow_run_2.state.is_final.return_value = True

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
        flow_run_2.state.is_cancelled.return_value = True
        flow_run_2.state.is_final.return_value = True

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
        flow_run.state.is_cancelled.return_value = True
        flow_run.state.is_final.return_value = True

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

        assert client.read_flow_run.await_count == 1
        client.read_flow_run.assert_any_await(flow_run_id)
        process_manager.kill.assert_awaited_once_with(flow_run.id, grace_seconds=30.0)
        state_proposer.propose_cancelled.assert_awaited_once()
        event_emitter.emit_flow_run_cancelled.assert_awaited_once()
