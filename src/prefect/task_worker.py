import asyncio
import inspect
import os
import signal
import socket
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import AsyncExitStack
from contextvars import copy_context
from typing import List, Optional

import anyio
import anyio.abc
from exceptiongroup import BaseExceptionGroup  # novermin
from websockets.exceptions import InvalidStatusCode

from prefect import Task
from prefect._internal.concurrency.api import create_call, from_sync
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import TaskRun
from prefect.client.subscriptions import Subscription
from prefect.exceptions import Abort, PrefectHTTPStatusError
from prefect.logging.loggers import get_logger
from prefect.results import ResultFactory
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_TASK_SCHEDULING_DELETE_FAILED_SUBMISSIONS,
)
from prefect.states import Pending
from prefect.task_engine import run_task_async, run_task_sync
from prefect.utilities.asyncutils import asyncnullcontext, sync_compatible
from prefect.utilities.engine import emit_task_run_state_change_event, propose_state
from prefect.utilities.processutils import _register_signal

logger = get_logger("task_worker")


class StopTaskWorker(Exception):
    """Raised when the task worker is stopped."""

    pass


def should_try_to_read_parameters(task: Task, task_run: TaskRun) -> bool:
    """Determines whether a task run should read parameters from the result factory."""
    new_enough_state_details = hasattr(
        task_run.state.state_details, "task_parameters_id"
    )
    task_accepts_parameters = bool(inspect.signature(task.fn).parameters)

    return new_enough_state_details and task_accepts_parameters


class TaskWorker:
    """This class is responsible for serving tasks that may be executed in the background
    by a task runner via the traditional engine machinery.

    When `start()` is called, the task worker will open a websocket connection to a
    server-side queue of scheduled task runs. When a scheduled task run is found, the
    scheduled task run is submitted to the engine for execution with a minimal `EngineContext`
    so that the task run can be governed by orchestration rules.

    Args:
        - tasks: A list of tasks to serve. These tasks will be submitted to the engine
            when a scheduled task run is found.
        - limit: The maximum number of tasks that can be run concurrently. Defaults to 10.
            Pass `None` to remove the limit.
    """

    def __init__(
        self,
        *tasks: Task,
        limit: Optional[int] = 10,
    ):
        self.tasks: List[Task] = list(tasks)

        self.started: bool = False
        self.stopping: bool = False

        self._client = get_client()
        self._exit_stack = AsyncExitStack()

        if not asyncio.get_event_loop().is_running():
            raise RuntimeError(
                "TaskWorker must be initialized within an async context."
            )

        self._runs_task_group: anyio.abc.TaskGroup = anyio.create_task_group()
        self._executor = ThreadPoolExecutor()
        self._limiter = anyio.CapacityLimiter(limit) if limit else None

    @property
    def _client_id(self) -> str:
        return f"{socket.gethostname()}-{os.getpid()}"

    def handle_sigterm(self, signum, frame):
        """
        Shuts down the task worker when a SIGTERM is received.
        """
        logger.info("SIGTERM received, initiating graceful shutdown...")
        from_sync.call_in_loop_thread(create_call(self.stop))

        sys.exit(0)

    @sync_compatible
    async def start(self) -> None:
        """
        Starts a task worker, which runs the tasks provided in the constructor.
        """
        _register_signal(signal.SIGTERM, self.handle_sigterm)

        async with asyncnullcontext() if self.started else self:
            logger.info("Starting task worker...")
            try:
                await self._subscribe_to_task_scheduling()
            except InvalidStatusCode as exc:
                if exc.status_code == 403:
                    logger.error(
                        "Could not establish a connection to the `/task_runs/subscriptions/scheduled`"
                        f" endpoint found at:\n\n {PREFECT_API_URL.value()}"
                        "\n\nPlease double-check the values of your"
                        " `PREFECT_API_URL` and `PREFECT_API_KEY` environment variables."
                    )
                else:
                    raise

    @sync_compatible
    async def stop(self):
        """Stops the task worker's polling cycle."""
        if not self.started:
            raise RuntimeError(
                "Task worker has not yet started. Please start the task worker by"
                " calling .start()"
            )

        self.started = False
        self.stopping = True

        raise StopTaskWorker

    async def _subscribe_to_task_scheduling(self):
        logger.info(
            f"Subscribing to tasks: {' | '.join(t.task_key.split('.')[-1] for t in self.tasks)}"
        )
        async for task_run in Subscription(
            model=TaskRun,
            path="/task_runs/subscriptions/scheduled",
            keys=[task.task_key for task in self.tasks],
            client_id=self._client_id,
        ):
            if self._limiter:
                await self._limiter.acquire_on_behalf_of(task_run.id)
            logger.info(f"Received task run: {task_run.id} - {task_run.name}")
            self._runs_task_group.start_soon(self._submit_scheduled_task_run, task_run)

    async def _submit_scheduled_task_run(self, task_run: TaskRun):
        logger.debug(
            f"Found task run: {task_run.name!r} in state: {task_run.state.name!r}"
        )

        task = next((t for t in self.tasks if t.task_key == task_run.task_key), None)

        if not task:
            if PREFECT_TASK_SCHEDULING_DELETE_FAILED_SUBMISSIONS:
                logger.warning(
                    f"Task {task_run.name!r} not found in task worker registry."
                )
                await self._client._client.delete(f"/task_runs/{task_run.id}")  # type: ignore

            return

        # The ID of the parameters for this run are stored in the Scheduled state's
        # state_details. If there is no parameters_id, then the task was created
        # without parameters.
        parameters = {}
        wait_for = []
        run_context = None
        if should_try_to_read_parameters(task, task_run):
            parameters_id = task_run.state.state_details.task_parameters_id
            task.persist_result = True
            factory = await ResultFactory.from_autonomous_task(task)
            try:
                run_data = await factory.read_parameters(parameters_id)
                parameters = run_data.get("parameters", {})
                wait_for = run_data.get("wait_for", [])
                run_context = run_data.get("context", None)
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

        try:
            new_state = Pending()
            new_state.state_details.deferred = True
            state = await propose_state(
                client=get_client(),  # TODO prove that we cannot use self._client here
                state=new_state,
                task_run_id=task_run.id,
            )
        except Abort as exc:
            logger.exception(
                f"Failed to submit task run {task_run.id!r} to engine", exc_info=exc
            )
            return
        except PrefectHTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning(
                    f"Task run {task_run.id!r} not found. It may have been deleted."
                )
                return
            raise

        if not state.is_pending():
            logger.warning(
                f"Cancelling submission of task run {task_run.id!r} -"
                f" server returned a non-pending state {state.type.value!r}."
            )
            return

        emit_task_run_state_change_event(
            task_run=task_run,
            initial_state=task_run.state,
            validated_state=state,
        )

        if task.isasync:
            await run_task_async(
                task=task,
                task_run_id=task_run.id,
                task_run=task_run,
                parameters=parameters,
                wait_for=wait_for,
                return_type="state",
                context=run_context,
            )
        else:
            context = copy_context()
            future = self._executor.submit(
                context.run,
                run_task_sync,
                task=task,
                task_run_id=task_run.id,
                task_run=task_run,
                parameters=parameters,
                wait_for=wait_for,
                return_type="state",
                context=run_context,
            )
            await asyncio.wrap_future(future)
        if self._limiter:
            self._limiter.release_on_behalf_of(task_run.id)

    async def execute_task_run(self, task_run: TaskRun):
        """Execute a task run in the task worker."""
        async with self if not self.started else asyncnullcontext():
            if self._limiter:
                await self._limiter.acquire_on_behalf_of(task_run.id)
            await self._submit_scheduled_task_run(task_run)

    async def __aenter__(self):
        logger.debug("Starting task worker...")

        if self._client._closed:
            self._client = get_client()

        await self._exit_stack.enter_async_context(self._client)
        await self._exit_stack.enter_async_context(self._runs_task_group)
        self._exit_stack.enter_context(self._executor)

        self.started = True
        return self

    async def __aexit__(self, *exc_info):
        logger.debug("Stopping task worker...")
        self.started = False
        await self._exit_stack.__aexit__(*exc_info)


@sync_compatible
async def serve(*tasks: Task, limit: Optional[int] = 10):
    """Serve the provided tasks so that their runs may be submitted to and executed.
    in the engine. Tasks do not need to be within a flow run context to be submitted.
    You must `.submit` the same task object that you pass to `serve`.

    Args:
        - tasks: A list of tasks to serve. When a scheduled task run is found for a
            given task, the task run will be submitted to the engine for execution.
        - limit: The maximum number of tasks that can be run concurrently. Defaults to 10.
            Pass `None` to remove the limit.

    Example:
        ```python
        from prefect import task
        from prefect.task_worker import serve

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
    task_worker = TaskWorker(*tasks, limit=limit)

    try:
        await task_worker.start()

    except BaseExceptionGroup as exc:  # novermin
        exceptions = exc.exceptions
        n_exceptions = len(exceptions)
        logger.error(
            f"Task worker stopped with {n_exceptions} exception{'s' if n_exceptions != 1 else ''}:"
            f"\n" + "\n".join(str(e) for e in exceptions)
        )

    except StopTaskWorker:
        logger.info("Task worker stopped.")

    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Task worker interrupted, stopping...")
