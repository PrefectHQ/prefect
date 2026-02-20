from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from prefect.runner._hook_runner import HookRunner, _run_hooks


def _make_flow_run():
    flow_run = MagicMock()
    flow_run.id = uuid4()
    flow_run.name = "test-flow-run"
    return flow_run


def _make_state(name="Running", is_cancelling=False, is_crashed=False):
    state = MagicMock()
    state.name = name
    state.is_cancelling.return_value = is_cancelling
    state.is_crashed.return_value = is_crashed
    return state


def _make_flow(on_cancellation_hooks=None, on_crashed_hooks=None):
    flow = MagicMock()
    flow.name = "test-flow"
    flow.on_cancellation_hooks = on_cancellation_hooks
    flow.on_crashed_hooks = on_crashed_hooks
    return flow


class TestRunHooks:
    async def test_run_hooks_empty_list_is_noop(self, caplog):
        flow_run = _make_flow_run()
        flow = _make_flow()
        state = _make_state()

        with caplog.at_level(logging.INFO, logger="prefect.flow_runs"):
            await _run_hooks([], flow_run, flow, state)

        assert caplog.text == ""

    async def test_run_hooks_async_hook_is_awaited(self):
        flow_run = _make_flow_run()
        flow = _make_flow()
        state = _make_state(name="Cancelling")
        async_hook = AsyncMock()
        async_hook.__name__ = "my_async_hook"

        await _run_hooks([async_hook], flow_run, flow, state)

        async_hook.assert_awaited_once_with(flow=flow, flow_run=flow_run, state=state)

    @patch("prefect.runner._hook_runner.from_async")
    async def test_run_hooks_sync_hook_runs_in_thread(self, mock_from_async):
        flow_run = _make_flow_run()
        flow = _make_flow()
        state = _make_state(name="Crashed")
        sync_hook = MagicMock()
        sync_hook.__name__ = "my_sync_hook"

        await _run_hooks([sync_hook], flow_run, flow, state)

        mock_from_async.call_in_new_thread.assert_called_once()

    async def test_run_hooks_logs_hook_name_on_start(self, caplog):
        flow_run = _make_flow_run()
        flow = _make_flow()
        state = _make_state(name="Cancelling")
        async_hook = AsyncMock()
        async_hook.__name__ = "on_cancel_hook"

        with caplog.at_level(logging.INFO, logger="prefect.flow_runs"):
            await _run_hooks([async_hook], flow_run, flow, state)

        assert "on_cancel_hook" in caplog.text
        assert "Cancelling" in caplog.text

    async def test_run_hooks_hook_failure_logs_error_and_continues(self, caplog):
        flow_run = _make_flow_run()
        flow = _make_flow()
        state = _make_state(name="Crashed")

        failing_hook = AsyncMock(side_effect=RuntimeError("boom"))
        failing_hook.__name__ = "bad_hook"
        second_hook = AsyncMock()
        second_hook.__name__ = "good_hook"

        with caplog.at_level(logging.ERROR, logger="prefect.flow_runs"):
            await _run_hooks([failing_hook, second_hook], flow_run, flow, state)

        assert "bad_hook" in caplog.text
        second_hook.assert_awaited_once_with(flow=flow, flow_run=flow_run, state=state)

    async def test_run_hooks_successful_hook_logs_finished(self, caplog):
        flow_run = _make_flow_run()
        flow = _make_flow()
        state = _make_state(name="Cancelling")
        async_hook = AsyncMock()
        async_hook.__name__ = "my_hook"

        with caplog.at_level(logging.INFO, logger="prefect.flow_runs"):
            await _run_hooks([async_hook], flow_run, flow, state)

        assert "finished running successfully" in caplog.text


class TestHookRunnerRunCancellationHooks:
    async def test_run_cancellation_hooks_noop_when_not_cancelling(self):
        resolve_flow = AsyncMock()
        runner = HookRunner(resolve_flow=resolve_flow)
        flow_run = _make_flow_run()
        state = _make_state(is_cancelling=False)

        await runner.run_cancellation_hooks(flow_run, state)

        resolve_flow.assert_not_awaited()

    async def test_run_cancellation_hooks_resolves_and_runs(self):
        async_hook = AsyncMock()
        async_hook.__name__ = "cancel_hook"
        flow = _make_flow(on_cancellation_hooks=[async_hook])
        resolve_flow = AsyncMock(return_value=flow)
        runner = HookRunner(resolve_flow=resolve_flow)
        flow_run = _make_flow_run()
        state = _make_state(name="Cancelling", is_cancelling=True)

        await runner.run_cancellation_hooks(flow_run, state)

        resolve_flow.assert_awaited_once_with(flow_run)
        async_hook.assert_awaited_once_with(flow=flow, flow_run=flow_run, state=state)

    async def test_run_cancellation_hooks_resolution_failure_logs_warning(self, caplog):
        resolve_flow = AsyncMock(side_effect=ValueError("cannot resolve"))
        runner = HookRunner(resolve_flow=resolve_flow)
        flow_run = _make_flow_run()
        state = _make_state(is_cancelling=True)

        with caplog.at_level(logging.WARNING, logger="prefect.runner.hook_runner"):
            await runner.run_cancellation_hooks(flow_run, state)

        assert "on_cancellation hooks" in caplog.text

    async def test_run_cancellation_hooks_empty_hooks(self):
        flow = _make_flow(on_cancellation_hooks=[])
        resolve_flow = AsyncMock(return_value=flow)
        runner = HookRunner(resolve_flow=resolve_flow)
        flow_run = _make_flow_run()
        state = _make_state(is_cancelling=True)

        await runner.run_cancellation_hooks(flow_run, state)

        resolve_flow.assert_awaited_once_with(flow_run)


class TestHookRunnerRunCrashedHooks:
    async def test_run_crashed_hooks_noop_when_not_crashed(self):
        resolve_flow = AsyncMock()
        runner = HookRunner(resolve_flow=resolve_flow)
        flow_run = _make_flow_run()
        state = _make_state(is_crashed=False)

        await runner.run_crashed_hooks(flow_run, state)

        resolve_flow.assert_not_awaited()

    async def test_run_crashed_hooks_resolves_and_runs(self):
        async_hook = AsyncMock()
        async_hook.__name__ = "crashed_hook"
        flow = _make_flow(on_crashed_hooks=[async_hook])
        resolve_flow = AsyncMock(return_value=flow)
        runner = HookRunner(resolve_flow=resolve_flow)
        flow_run = _make_flow_run()
        state = _make_state(name="Crashed", is_crashed=True)

        await runner.run_crashed_hooks(flow_run, state)

        resolve_flow.assert_awaited_once_with(flow_run)
        async_hook.assert_awaited_once_with(flow=flow, flow_run=flow_run, state=state)

    async def test_run_crashed_hooks_resolution_failure_logs_warning(self, caplog):
        resolve_flow = AsyncMock(side_effect=ValueError("cannot resolve"))
        runner = HookRunner(resolve_flow=resolve_flow)
        flow_run = _make_flow_run()
        state = _make_state(is_crashed=True)

        with caplog.at_level(logging.WARNING, logger="prefect.runner.hook_runner"):
            await runner.run_crashed_hooks(flow_run, state)

        assert "on_crashed hooks" in caplog.text
