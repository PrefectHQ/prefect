import asyncio
from typing import TYPE_CHECKING, Awaitable, TypeVar, Union

import prefect.logging.handlers
import prefect.results
import prefect.states
from prefect._internal.compatibility.experimental import experimental
from prefect._internal.concurrency.runtime import call_in_new_runtime
from prefect.logging.loggers import get_logger
from prefect.utilities.asyncutils import is_async_fn

if TYPE_CHECKING:
    import prefect
    import prefect.client.schemas


T = TypeVar("T")
logger = get_logger("prefect.engine")


@experimental("The new flow run engine", group="engine_v2", opt_in=True)
def enter_engine_with_runtime(
    call, flow, parent_flow_run_context
) -> Union["prefect.State", Awaitable["prefect.State"]]:
    # Determine if this is a parent or child flow run
    is_child_flow_run = parent_flow_run_context is not None

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
        result = await runtime.run_in_thread(call, __sync__=False)

    return result
