from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

from prefect._internal.concurrency.api import create_call, from_async
from prefect.logging import get_logger
from prefect.logging.loggers import flow_run_logger
from prefect.utilities._engine import get_hook_name
from prefect.utilities.asyncutils import is_async_fn

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.flows import Flow
    from prefect.states import State


async def _run_hooks(
    hooks: list[Any],
    flow_run: FlowRun,
    flow: Flow[..., Any],
    state: State,
) -> None:
    """Execute hooks sequentially. Log ERROR on failure and continue to remaining hooks."""
    logger = flow_run_logger(flow_run, flow)
    for hook in hooks:
        hook_name = get_hook_name(hook)
        try:
            logger.info(
                "Running hook %r in response to entering state %r",
                hook_name,
                state.name,
            )
            if is_async_fn(hook):
                await hook(flow=flow, flow_run=flow_run, state=state)
            else:
                await from_async.call_in_new_thread(
                    create_call(hook, flow=flow, flow_run=flow_run, state=state)
                )
        except Exception:
            logger.error(
                "An error was encountered while running hook %r",
                hook_name,
                exc_info=True,
            )
        else:
            logger.info("Hook %r finished running successfully", hook_name)


class _HookRunner:
    """Executes on_cancellation and on_crashed hooks via an injected flow resolver.

    Stateless service — no `__aenter__`/`__aexit__`. Dependencies injected
    via keyword-only constructor arguments.
    """

    def __init__(
        self,
        *,
        resolve_flow: Callable[[FlowRun], Awaitable[Flow[Any, Any]]],
    ) -> None:
        self._resolve_flow = resolve_flow
        self._logger = get_logger("runner.hook_runner")

    async def run_cancellation_hooks(self, flow_run: FlowRun, state: State) -> None:
        """Run on_cancellation hooks. No-op if state is not cancelling.
        Swallows flow resolution errors with a WARNING log."""
        if not state.is_cancelling():
            return
        try:
            flow = await self._resolve_flow(flow_run)
            hooks = flow.on_cancellation_hooks or []
            await _run_hooks(hooks, flow_run, flow, state)
        except Exception:
            self._logger.warning(
                "Runner failed to retrieve flow to execute on_cancellation hooks"
                " for flow run %r.",
                flow_run.id,
                exc_info=True,
            )

    async def run_crashed_hooks(self, flow_run: FlowRun, state: State) -> None:
        """Run on_crashed hooks. No-op if state is not crashed.
        Swallows flow resolution errors with a WARNING log."""
        if not state.is_crashed():
            return
        try:
            flow = await self._resolve_flow(flow_run)
            hooks = flow.on_crashed_hooks or []
            await _run_hooks(hooks, flow_run, flow, state)
        except Exception:
            self._logger.warning(
                "Runner failed to retrieve flow to execute on_crashed hooks"
                " for flow run %r.",
                flow_run.id,
                exc_info=True,
            )
