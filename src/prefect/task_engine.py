from contextlib import AsyncExitStack
from typing import (
    Any,
    Dict,
    Iterable,
    Optional,
    Type,
)

import anyio
from anyio import start_blocking_portal
from typing_extensions import Literal

from prefect._internal.concurrency.api import create_call, from_async, from_sync
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import TaskRun
from prefect.context import EngineContext
from prefect.engine import (
    begin_task_map,
    get_task_call_return_value,
)
from prefect.futures import PrefectFuture
from prefect.results import ResultFactory
from prefect.task_runners import BaseTaskRunner, SequentialTaskRunner
from prefect.tasks import Task
from prefect.utilities.asyncutils import sync_compatible

EngineReturnType = Literal["future", "state", "result"]


@sync_compatible
async def submit_autonomous_task_to_engine(
    task: Task,
    task_run: TaskRun,
    parameters: Optional[Dict] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
    mapped: bool = False,
    return_type: EngineReturnType = "future",
    task_runner: Optional[Type[BaseTaskRunner]] = None,
) -> Any:
    parameters = parameters or {}
    async with AsyncExitStack() as stack:
        with EngineContext(
            flow=None,
            flow_run=None,
            autonomous_task_run=task_run,
            task_runner=await stack.enter_async_context(
                (task_runner if task_runner else SequentialTaskRunner()).start()
            ),
            client=await stack.enter_async_context(get_client()),
            parameters=parameters,
            result_factory=await ResultFactory.from_task(task),
            background_tasks=await stack.enter_async_context(anyio.create_task_group()),
            sync_portal=(
                stack.enter_context(start_blocking_portal()) if task.isasync else None
            ),
        ) as flow_run_context:
            begin_run = create_call(
                begin_task_map if mapped else get_task_call_return_value,
                task=task,
                flow_run_context=flow_run_context,
                parameters=parameters,
                wait_for=wait_for,
                return_type=return_type,
                task_runner=task_runner,
            )
            if task.isasync:
                return await from_async.wait_for_call_in_loop_thread(begin_run)
            else:
                return from_sync.wait_for_call_in_loop_thread(begin_run)
