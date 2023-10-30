import inspect
from contextlib import AsyncExitStack
from typing import Type

from anyio import create_task_group, start_blocking_portal
from pydantic import BaseModel

from prefect import Task, get_client
from prefect.context import FlowRunContext
from prefect.engine import enter_task_run_engine
from prefect.results import ResultFactory
from prefect.task_runners import BaseTaskRunner
from prefect.utilities.pydantic import PartialModel


class TaskManager(BaseModel):
    task_runner: Type[BaseTaskRunner]

    async def run(self, task: Task, parameters: dict = None, *args, **kwargs):
        async with AsyncExitStack() as stack:
            partial_context = PartialModel(
                FlowRunContext,
                flow=None,
                flow_run=None,
                task_runner=await stack.enter_async_context(self.task_runner().start()),
                client=await stack.enter_async_context(get_client()),
                parameters=parameters,
            )
            with partial_context.finalize(
                result_factory=await ResultFactory.from_task(task),
                background_tasks=await stack.enter_async_context(create_task_group()),
                sync_portal=(
                    stack.enter_context(start_blocking_portal())
                    if task.isasync
                    else None
                ),
            ) as flow_run_context:
                result = enter_task_run_engine(
                    task=task,
                    parameters=parameters,
                    task_runner=flow_run_context.task_runner,
                    *args,
                    **kwargs
                )
                if inspect.isawaitable(result):
                    result = await result
                return result


##
if __name__ == "__main__":
    import asyncio

    from prefect import task
    from prefect.task_runners import SequentialTaskRunner

    @task
    def add(x, y):
        return x + y

    result = asyncio.run(
        TaskManager(task_runner=SequentialTaskRunner).run(
            task=add,
            parameters=dict(x=1, y=2),
            wait_for=None,
            return_type="result",
            mapped=False,
        )
    )

    print(result)
