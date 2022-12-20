import asyncio
from functools import partial
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Dict,
    Iterable,
    Optional,
    TypeVar,
    Union,
)

import prefect.logging.handlers
import prefect.results
import prefect.states
from prefect._internal.compatibility.experimental import experimental
from prefect._internal.concurrency.runtime import call_in_new_runtime
from prefect.context import FlowRunContext
from prefect.logging.loggers import get_logger
from prefect.utilities.asyncutils import is_async_fn

if TYPE_CHECKING:
    import prefect
    import prefect.client.schemas


T = TypeVar("T")
logger = get_logger("prefect.engine")


@experimental("The new flow run engine", group="engine_v2", opt_in=True)
def enter_engine_from_flow_call(
    flow: "prefect.Flow",
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable["prefect.PrefectFuture"]],
    return_type: str,
) -> Union["prefect.State", Awaitable["prefect.State"]]:
    """
    Synchronous entrypoint for the flow run engine.

    - Create a new runtime if a root flow run or load the existing runtime if a child
    - Call the flow run engine
    """
    # Determine if this is a parent or child flow run
    parent_flow_run_context = FlowRunContext.get()
    is_child_flow_run = parent_flow_run_context is not None

    from prefect.engine import create_and_begin_subflow_run, create_then_begin_flow_run

    call = partial(
        (
            create_then_begin_flow_run
            if not is_child_flow_run
            else create_and_begin_subflow_run
        ),
        flow=flow,
        parameters=parameters,
        wait_for=wait_for,
        return_type=return_type,
    )

    if not is_child_flow_run:
        return call_in_new_runtime(call, sync=not flow.isasync)
    else:
        return parent_flow_run_context.runtime.run_in_loop(
            call, runtime=parent_flow_run_context.runtime
        )


async def execute_flow(runtime, flow, call):
    if runtime.is_async == is_async_fn(flow.fn):
        future = runtime.submit_from_thread(call)
        result = await asyncio.wrap_future(future)
    else:
        result = await runtime.run_in_thread(call)

    return result
