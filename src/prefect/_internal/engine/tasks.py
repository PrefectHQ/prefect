import asyncio
from typing import TYPE_CHECKING, Awaitable, TypeVar, Union

import prefect.logging.handlers
import prefect.results
import prefect.states
from prefect._internal.compatibility.experimental import experimental
from prefect.logging.loggers import get_logger
from prefect.utilities.asyncutils import is_async_fn

if TYPE_CHECKING:
    import prefect
    import prefect.client.schemas


T = TypeVar("T")
logger = get_logger("prefect.engine")


@experimental("The new task run engine", group="engine_v2", opt_in=True)
def enter_engine_with_runtime(
    call, task, parent_flow_run_context
) -> Union["prefect.State", Awaitable["prefect.State"]]:
    return parent_flow_run_context.runtime.run_in_loop(
        call,
        __sync__=(
            False
            if is_async_fn(task.fn) and is_async_fn(parent_flow_run_context.flow.fn)
            else True
        ),
    )


async def execute_task(runtime, task, call):
    if runtime.is_async == is_async_fn(task.fn):
        future = runtime.submit_from_thread(call)
        result = await asyncio.wrap_future(future)
    else:
        result = await runtime.run_in_thread(call)

    return result
