import asyncio
import inspect
import os
import signal
import socket
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import AsyncExitStack
from contextvars import copy_context
from typing import Optional
from uuid import UUID

import anyio
import anyio.abc
import pendulum
import uvicorn
from exceptiongroup import BaseExceptionGroup  # novermin
from fastapi import FastAPI
from websockets.exceptions import InvalidStatusCode

from prefect import Task
from prefect._internal.concurrency.api import create_call, from_sync
from prefect.cache_policies import DEFAULT, NONE
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import TaskRun
from prefect.client.subscriptions import Subscription
from prefect.logging.loggers import get_logger
from prefect.results import ResultStore, get_or_create_default_task_scheduling_storage
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_TASK_SCHEDULING_DELETE_FAILED_SUBMISSIONS,
)
from prefect.states import Pending
from prefect.task_engine import run_task_async, run_task_sync
from prefect.utilities.annotations import NotSet
from prefect.utilities.asyncutils import asyncnullcontext, sync_compatible
from prefect.utilities.engine import emit_task_run_state_change_event
from prefect.utilities.processutils import _register_signal
from prefect.utilities.services import start_client_metrics_server
from prefect.utilities.urls import url_for

logger = get_logger("task_worker")


class StopTaskWorker(Exception):
    """Raised when the task worker is stopped."""

    pass


def should_try_to_read_parameters(task: Task, task_run: TaskRun) -> bool:
    """Determines whether a task run should read parameters from the result store."""
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
        self.tasks = []
        for t in tasks:
            if isinstance(t, Task):
                if t.cache_policy in [None, NONE, NotSet]:
                    self.tasks.append(
                        t.with_options(persist_result=True, cache_policy=DEFAULT)
                    )
                else:
                    self.tasks.append(t.with_options(persist_result=True))

        self.task_keys = set(t.task_key for t in tasks if isinstance(t, Task))

        self._started_at: Optional[pendulum.DateTime] = None
        self.stopping: bool = False

        self._client = get_client()
        self._exit_stack = AsyncExitStack()

        if not asyncio.get_event_loop().is_running():
            raise RuntimeError(
                "TaskWorker must be initialized within an async context."
            )

        self._runs_task_group: anyio.abc.TaskGroup = anyio.create_task_group()
        self._executor = ThreadPoolExecutor(max_workers=limit if limit else None)
        self._limiter = anyio.CapacityLimiter(limit) if limit else None

        self.in_flight_task_runs: dict[str, dict[UUID, pendulum.DateTime]] = {
            task_key: {} for task_key in self.task_keys
        }
        self.finished_task_runs: dict[str, int] = {
            task_key: 0 for task_key in self.task_keys
        }

    @property
    def client_id(self) -> str:
        return f"{socket.gethostname()}-{os.getpid()}"

    @property
    def started_at(self) -> Optional[pendulum.DateTime]:
        return self._started_at

    @property
    def started(self) -> bool:
        return self._started_at is not None

    @property
    def limit(self) -> Optional[int]:
        return int(self._limiter.total_tokens) if self._limiter else None

    @property
    def current_tasks(self) -> Optional[int]:
        return (
            int(self._limiter.borrowed_tokens)
            if self._limiter
            else sum(len(runs) for runs in self.in_flight_task_runs.values())
        )

    @property
    def available_tasks(self) -> Optional[int]:
        return int(self._limiter.available_tokens) if self._limiter else None

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

        start_client_metrics_server()

        async with asyncnullcontext() if self.started else self:
            logger.info("Starting task worker...")
            try:
                await self._subscribe_to_task_scheduling()
            except InvalidStatusCode as exc:
                if exc.status_code == 403:
                    logger.error(
                        "403: Could not establish a connection to the `/task_runs/subscriptions/scheduled`"
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

        self._started_at = None
        self.stopping = True

        raise StopTaskWorker

    async def _acquire_token(self, task_run_id: UUID) -> bool:
        try:
            if self._limiter:
                await self._limiter.acquire_on_behalf_of(task_run_id)
        except RuntimeError:
            logger.debug(f"Token already acquired for task run: {task_run_id!r}")
            return False

        return True

    def _release_token(self, task_run_id: UUID) -> bool:
        try:
            if self._limiter:
                self._limiter.release_on_behalf_of(task_run_id)
        except RuntimeError:
            logger.debug(f"No token to release for task run: {task_run_id!r}")
            return False

        return True

    async def _subscribe_to_task_scheduling(self):
        base_url = PREFECT_API_URL.value()
        if base_url is None:
            raise ValueError(
                "`PREFECT_API_URL` must be set to use the task worker. "
                "Task workers are not compatible with the ephemeral API."
            )
        task_keys_repr = " | ".join(
            task_key.split(".")[-1].split("-")[0] for task_key in sorted(self.task_keys)
        )
        logger.info(f"Subscribing to runs of task(s): {task_keys_repr}")
        async for task_run in Subscription(
            model=TaskRun,
            path="/task_runs/subscriptions/scheduled",
            keys=self.task_keys,
            client_id=self.client_id,
            base_url=base_url,
        ):
            logger.info(f"Received task run: {task_run.id} - {task_run.name}")

            token_acquired = await self._acquire_token(task_run.id)
            if token_acquired:
                self._runs_task_group.start_soon(
                    self._safe_submit_scheduled_task_run, task_run
                )

    async def _safe_submit_scheduled_task_run(self, task_run: TaskRun):
        self.in_flight_task_runs[task_run.task_key][task_run.id] = pendulum.now()
        try:
            await self._submit_scheduled_task_run(task_run)
        except BaseException as exc:
            logger.exception(
                f"Failed to submit task run {task_run.id!r}",
                exc_info=exc,
            )
        finally:
            self.in_flight_task_runs[task_run.task_key].pop(task_run.id, None)
            self.finished_task_runs[task_run.task_key] += 1
            self._release_token(task_run.id)

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
            store = await ResultStore(
                result_storage=await get_or_create_default_task_scheduling_storage()
            ).update_for_task(task)
            try:
                run_data = await store.read_parameters(parameters_id)
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

        initial_state = task_run.state
        new_state = Pending()
        new_state.state_details.deferred = True
        new_state.state_details.task_run_id = task_run.id
        new_state.state_details.flow_run_id = task_run.flow_run_id
        state = new_state
        task_run.state = state

        emit_task_run_state_change_event(
            task_run=task_run,
            initial_state=initial_state,
            validated_state=state,
        )

        if task_run_url := url_for(task_run):
            logger.info(
                f"Submitting task run {task_run.name!r} to engine. View in the UI: {task_run_url}"
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

    async def execute_task_run(self, task_run: TaskRun):
        """Execute a task run in the task worker."""
        async with self if not self.started else asyncnullcontext():
            token_acquired = await self._acquire_token(task_run.id)
            if token_acquired:
                await self._safe_submit_scheduled_task_run(task_run)

    async def __aenter__(self):
        logger.debug("Starting task worker...")

        if self._client._closed:
            self._client = get_client()

        await self._exit_stack.enter_async_context(self._client)
        await self._exit_stack.enter_async_context(self._runs_task_group)
        self._exit_stack.enter_context(self._executor)

        self._started_at = pendulum.now()
        return self

    async def __aexit__(self, *exc_info):
        logger.debug("Stopping task worker...")
        self._started_at = None
        await self._exit_stack.__aexit__(*exc_info)


def create_status_server(task_worker: TaskWorker) -> FastAPI:
    status_app = FastAPI()

    @status_app.get("/status")
    def status():
        return {
            "client_id": task_worker.client_id,
            "started_at": task_worker.started_at.isoformat(),
            "stopping": task_worker.stopping,
            "limit": task_worker.limit,
            "current": task_worker.current_tasks,
            "available": task_worker.available_tasks,
            "tasks": sorted(task_worker.task_keys),
            "finished": task_worker.finished_task_runs,
            "in_flight": {
                key: {str(run): start.isoformat() for run, start in tasks.items()}
                for key, tasks in task_worker.in_flight_task_runs.items()
            },
        }

    return status_app


@sync_compatible
async def serve(
    *tasks: Task, limit: Optional[int] = 10, status_server_port: Optional[int] = None
):
    """Serve the provided tasks so that their runs may be submitted to and executed.
    in the engine. Tasks do not need to be within a flow run context to be submitted.
    You must `.submit` the same task object that you pass to `serve`.

    Args:
        - tasks: A list of tasks to serve. When a scheduled task run is found for a
            given task, the task run will be submitted to the engine for execution.
        - limit: The maximum number of tasks that can be run concurrently. Defaults to 10.
            Pass `None` to remove the limit.
        - status_server_port: An optional port on which to start an HTTP server
            exposing status information about the task worker. If not provided, no
            status server will run.

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

    status_server_task = None
    if status_server_port is not None:
        server = uvicorn.Server(
            uvicorn.Config(
                app=create_status_server(task_worker),
                host="127.0.0.1",
                port=status_server_port,
                access_log=False,
                log_level="warning",
            )
        )
        loop = asyncio.get_event_loop()
        status_server_task = loop.create_task(server.serve())

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

    finally:
        if status_server_task:
            status_server_task.cancel()
            try:
                await status_server_task
            except asyncio.CancelledError:
                pass
