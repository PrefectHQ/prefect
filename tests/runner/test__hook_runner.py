from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from prefect import flows as flows_mod
from prefect.flows import load_flow_from_flow_run
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

    async def test_run_hooks_sync_hook_runs_in_thread(self):
        captured: dict[str, object] = {}

        def my_sync_hook(flow, flow_run, state):
            captured["flow"] = flow
            captured["flow_run"] = flow_run
            captured["state"] = state

        flow_run = _make_flow_run()
        flow = _make_flow()
        state = _make_state(name="Crashed")

        await _run_hooks([my_sync_hook], flow_run, flow, state)

        assert captured["flow"] is flow
        assert captured["flow_run"] is flow_run
        assert captured["state"] is state

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

        with caplog.at_level(logging.WARNING, logger="prefect.flow_runs"):
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

        with caplog.at_level(logging.WARNING, logger="prefect.flow_runs"):
            await runner.run_crashed_hooks(flow_run, state)

        assert "on_crashed hooks" in caplog.text


class TestCancellationHooksWithClientInjector:
    """Regression tests for https://github.com/PrefectHQ/prefect/issues/12714.

    The CLI `prefect flow-run execute` code path passes
    `load_flow_from_flow_run` (decorated with `@client_injector`) as the
    `resolve_flow` callback.  A previous bug passed the client explicitly as a
    positional argument::

        resolve_flow=lambda fr: load_flow_from_flow_run(ctx.client, fr)

    Because `@client_injector` already prepends a client, the explicit client
    ended up in the `flow_run` parameter, causing
    `AttributeError: 'PrefectClient' object has no attribute 'deployment_id'`.

    The fix uses a keyword argument instead::

        resolve_flow=lambda fr: load_flow_from_flow_run(flow_run=fr)
    """

    async def test_cancellation_hooks_fire_with_client_injected_resolver(self):
        """End-to-end: the fixed CLI lambda correctly passes the flow_run
        to `load_flow_from_flow_run`, the `@client_injector` decorator
        injects the client, and the cancellation hook fires."""
        cancel_hook = AsyncMock()
        cancel_hook.__name__ = "on_cancel"
        flow = _make_flow(on_cancellation_hooks=[cancel_hook])

        flow_run = _make_flow_run()
        flow_run.deployment_id = uuid4()
        state = _make_state(name="Cancelling", is_cancelling=True)

        # Replace the entire decorated load_flow_from_flow_run with a mock
        # so we don't hit real deployment lookup, but still exercise the
        # lambda wiring that caused the original bug.
        mock_load = AsyncMock(return_value=flow)

        with patch.object(flows_mod, "load_flow_from_flow_run", mock_load):
            # Reproduce the fixed CLI pattern: keyword-only flow_run
            async def resolve_flow(fr):
                return await flows_mod.load_flow_from_flow_run(flow_run=fr)

            runner = HookRunner(resolve_flow=resolve_flow)
            await runner.run_cancellation_hooks(flow_run, state)

        mock_load.assert_awaited_once_with(flow_run=flow_run)
        cancel_hook.assert_awaited_once_with(flow=flow, flow_run=flow_run, state=state)

    async def test_explicit_client_positional_arg_causes_misrouted_flow_run(
        self, caplog
    ):
        """Demonstrate the original bug: passing the client as a positional arg
        to `load_flow_from_flow_run` causes it to land in `flow_run`,
        triggering an AttributeError on `deployment_id`.

        HookRunner swallows the exception and logs a warning, so we verify
        that the warning is produced (meaning the hook could NOT run).
        """
        flow_run = _make_flow_run()
        state = _make_state(name="Cancelling", is_cancelling=True)

        fake_client = MagicMock()  # stands in for ctx.client

        with patch(
            "prefect.client.utilities.get_or_create_client",
            return_value=(MagicMock(), True),
        ):
            # Reproduce the OLD (broken) pattern — double client
            async def resolve_flow(fr):
                return await load_flow_from_flow_run(fake_client, fr)

            runner = HookRunner(resolve_flow=resolve_flow)

            # The injected client becomes the first arg (client param),
            # fake_client lands in flow_run, real flow_run lands in
            # ignore_storage.  Accessing deployment_id on fake_client
            # inside load_flow_from_flow_run triggers an error which
            # HookRunner catches and logs as a warning.
            with caplog.at_level(logging.WARNING, logger="prefect.flow_runs"):
                await runner.run_cancellation_hooks(flow_run, state)

        assert "on_cancellation hooks" in caplog.text
