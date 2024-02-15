import asyncio
import signal
import sys
from contextlib import AsyncExitStack
from functools import partial
from typing import Optional, Type

import anyio
import anyio.abc

from prefect import Task, get_client
from prefect._internal.concurrency.api import create_call, from_sync
from prefect.client.schemas.objects import TaskRun
from prefect.client.subscriptions import Subscription
from prefect.engine import propose_state
from prefect.logging.loggers import get_logger
from prefect.results import ResultFactory
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING,
    PREFECT_TASK_SCHEDULING_DELETE_FAILED_SUBMISSIONS,
)
from prefect.states import Pending
from prefect.task_engine import submit_autonomous_task_to_engine
from prefect.task_runners import BaseTaskRunner, ConcurrentTaskRunner
from prefect.utilities.asyncutils import asyncnullcontext, sync_compatible
from prefect.utilities.processutils import _register_signal

logger = get_logger("task_server")


class StopTaskServer(Exception):
    """Raised when the task server is stopped."""

    pass


class TaskServer:
    """This class is responsible for serving tasks that may be executed autonomously by a
    task runner in the engine.

    When `start()` is called, the task server will open a websocket connection to a
    server-side queue of scheduled task runs. When a scheduled task run is found, the
    scheduled task run is submitted to the engine for execution with a minimal `EngineContext`
    so that the task run can be governed by orchestration rules.

    Args:
        - tasks: A list of tasks to serve. These tasks will be submitted to the engine
            when a scheduled task run is found.
        - task_runner: The task runner to use for executing the tasks. Defaults to
            `ConcurrentTaskRunner`.
    """

    def __init__(
        self,
        *tasks: Task,
        task_runner: Optional[Type[BaseTaskRunner]] = None,
    ):
        self.tasks: list[Task] = tasks
        self.task_runner: Type[BaseTaskRunner] = task_runner or ConcurrentTaskRunner()
        self.started: bool = False
        self.stopping: bool = False

        self._client = get_client()
        self._exit_stack = AsyncExitStack()

        if not asyncio.get_event_loop().is_running():
            raise RuntimeError(
                "TaskServer must be initialized within an async context."
            )

        self._runs_task_group: anyio.abc.TaskGroup = anyio.create_task_group()

    def handle_sigterm(self, signum, frame):
        """
        Shuts down the task server when a SIGTERM is received.
        """
        logger.info("SIGTERM received, initiating graceful shutdown...")
        from_sync.call_in_loop_thread(create_call(self.stop))

        sys.exit(0)

    @sync_compatible
    async def start(self) -> None:
        """
        Starts a task server, which runs the tasks provided in the constructor.
        """
        _register_signal(signal.SIGTERM, self.handle_sigterm)

        async with asyncnullcontext() if self.started else self:
            await self._subscribe_to_task_scheduling()

    @sync_compatible
    async def stop(self):
        """Stops the task server's polling cycle."""
        if not self.started:
            raise RuntimeError(
                "Task server has not yet started. Please start the task server by"
                " calling .start()"
            )

        self.started = False
        self.stopping = True

        raise StopTaskServer

    async def _subscribe_to_task_scheduling(self):
        async for task_run in Subscription(
            TaskRun,
            "/task_runs/subscriptions/scheduled",
            [task.task_key for task in self.tasks],
        ):
            logger.info(f"Received task run: {task_run.id} - {task_run.name}")
            await self._submit_scheduled_task_run(task_run)

    async def _submit_scheduled_task_run(self, task_run: TaskRun):
        logger.debug(
            f"Found task run: {task_run.name!r} in state: {task_run.state.name!r}"
        )

        task = next((t for t in self.tasks if t.name in task_run.task_key), None)

        if not task:
            if PREFECT_TASK_SCHEDULING_DELETE_FAILED_SUBMISSIONS.value():
                logger.warning(
                    f"Task {task_run.name!r} not found in task server registry."
                )
                await self._client._client.delete(f"/task_runs/{task_run.id}")

            return

        # The ID of the parameters for this run are stored in the Scheduled state's
        # state_details. If there is no parameters_id, then the task was created
        # without parameters.
        parameters = {}
        if hasattr(task_run.state.state_details, "task_parameters_id"):
            parameters_id = task_run.state.state_details.task_parameters_id
            task.persist_result = True
            factory = await ResultFactory.from_task(task)
            try:
                parameters = await factory.read_parameters(parameters_id)
            except Exception as exc:
                logger.exception(
                    f"Failed to read parameters for task run {task_run.id!r}",
                    exc_info=exc,
                )
                if PREFECT_TASK_SCHEDULING_DELETE_FAILED_SUBMISSIONS.value():
                    logger.info(
                        f"Deleting task run {task_run.id!r} because it failed to submit"
                    )
                    await self._client._client.delete(f"/task_runs/{task_run.id}")
                return

        logger.debug(
            f"Submitting run {task_run.name!r} of task {task.name!r} to engine"
        )

        state = await propose_state(
            client=get_client(),  # TODO prove that we cannot use self._client here
            state=Pending(),
            task_run_id=task_run.id,
        )

        if not state.is_pending():
            logger.warning(
                f"Aborted task run {task_run.id!r} -"
                f" server returned a non-pending state {state.type.value!r}."
                " Task run may have already begun execution."
            )

        self._runs_task_group.start_soon(
            partial(
                submit_autonomous_task_to_engine,
                task=task,
                task_run=task_run,
                parameters=parameters,
                task_runner=self.task_runner,
                client=self._client,
            )
        )

    async def __aenter__(self):
        logger.debug("Starting task server...")

        self._client = await self._exit_stack.enter_async_context(get_client())
        await self._exit_stack.enter_async_context(self._runs_task_group)
        await self._exit_stack.enter_async_context(self.task_runner.start())

        self.started = True
        return self

    async def __aexit__(self, *exc_info):
        logger.debug("Stopping task server...")
        self.started = False

        await self._exit_stack.__aexit__(*exc_info)


@sync_compatible
async def serve(*tasks: Task, task_runner: Optional[Type[BaseTaskRunner]] = None):
    """Serve the provided tasks so that their runs may be submitted to and executed.
    in the engine. Tasks do not need to be within a flow run context to be submitted.
    You must `.submit` the same task object that you pass to `serve`.

    Args:
        - tasks: A list of tasks to serve. When a scheduled task run is found for a
            given task, the task run will be submitted to the engine for execution.
        - task_runner: The task runner to use for executing the tasks. Defaults to
            `ConcurrentTaskRunner`.

    Example:
        ```python
        from prefect import task
        from prefect.task_server import serve

        @task(log_prints=True)
        def say(message: str):
            print(message)

        @task(log_prints=True)
        def yell(message: str):
            print(message.upper())

        # starts a long-lived process that listens for scheduled runs of these tasks
        if __name__ == "__main__":
            serve(say, yell)
        ```
    """
    if not PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING.value():
        raise RuntimeError(
            "To enable task scheduling, set PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING"
            " to True."
        )

    task_server = TaskServer(*tasks, task_runner=task_runner)
    try:
        await task_server.start()

    except StopTaskServer:
        logger.info("Task server stopped.")

    except asyncio.CancelledError:
        logger.info("Task server interrupted, stopping...")
