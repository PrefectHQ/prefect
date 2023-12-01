from contextlib import AsyncExitStack
from typing import Awaitable, Dict, Iterable, Optional, Type, Union

from anyio import create_task_group, start_blocking_portal

from prefect import Task, get_client
from prefect._internal.concurrency.api import create_call, from_async, from_sync
from prefect.client.schemas.objects import Flow, FlowRun
from prefect.context import FlowRunContext
from prefect.engine import EngineReturnType, begin_task_map, get_task_call_return_value
from prefect.futures import PrefectFuture
from prefect.results import ResultFactory
from prefect.task_runners import BaseTaskRunner, ConcurrentTaskRunner
from prefect.utilities.asyncutils import sync_compatible


@sync_compatible
async def run_autonomous_task(
    task: Task,
    flow: Optional[Flow] = None,
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
    mapped: bool = False,
    return_type: EngineReturnType = "state",
    task_runner_cls: Type[BaseTaskRunner] = ConcurrentTaskRunner,
) -> Union[PrefectFuture, Awaitable[PrefectFuture]]:
    task_runner = task_runner_cls() if isinstance(task_runner_cls, type) else task_runner_cls
    async with AsyncExitStack() as stack:
        with FlowRunContext(
            flow=flow,
            flow_run=flow_run,
            task_runner=await stack.enter_async_context(
                task_runner.start()
            ),
            client=await stack.enter_async_context(get_client()),
            parameters=parameters or {},
            result_factory=await ResultFactory.from_task(task),
            background_tasks=await stack.enter_async_context(create_task_group()),
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
                # TODO: revisit awaiting `from_async.wait_for_call_in_loop_thread`
                # we await this call and run_autonomous_task is sync_compatible
                # so the user will await it if they are in an async context
                return await from_async.wait_for_call_in_loop_thread(begin_run)
            else:
                return from_sync.wait_for_call_in_loop_thread(begin_run)
