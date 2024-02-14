import threading
from contextlib import AsyncExitStack
from typing import (
    Any,
    Dict,
    Iterable,
    Optional,
    Type,
)

import anyio
import greenback
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
from prefect.task_runners import BaseTaskRunner
from prefect.tasks import Task
from prefect.utilities.asyncutils import sync_compatible

EngineReturnType = Literal["future", "state", "result"]


@sync_compatible
async def submit_autonomous_task_to_engine(
    task: Task,
    task_run: TaskRun,
    task_runner: Type[BaseTaskRunner],
    parameters: Optional[Dict] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
    mapped: bool = False,
    return_type: EngineReturnType = "future",
    client=None,
) -> Any:
    async with AsyncExitStack() as stack:
        if not task_runner._started:
            task_runner_ctx = await stack.enter_async_context(task_runner.start())
        else:
            task_runner_ctx = task_runner
        parameters = parameters or {}
        with EngineContext(
            flow=None,
            flow_run=None,
            autonomous_task_run=task_run,
            task_runner=task_runner_ctx,
            client=client or await stack.enter_async_context(get_client()),
            parameters=parameters,
            result_factory=await ResultFactory.from_task(task),
            background_tasks=await stack.enter_async_context(anyio.create_task_group()),
        ) as flow_run_context:
            begin_run = create_call(
                begin_task_map if mapped else get_task_call_return_value,
                task=task,
                flow_run_context=flow_run_context,
                parameters=parameters,
                wait_for=wait_for,
                return_type=return_type,
                task_runner=task_runner,
                user_thread=threading.current_thread(),
            )
            if task.isasync:
                return await from_async.wait_for_call_in_loop_thread(begin_run)
            else:
                await greenback.ensure_portal()
                return from_sync.wait_for_call_in_loop_thread(begin_run)
