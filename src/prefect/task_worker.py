from __future__ import annotations

import asyncio
import inspect
import os
import signal
import socket
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import AsyncExitStack
from contextvars import copy_context
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

import anyio
import anyio.abc
import uvicorn
from exceptiongroup import BaseExceptionGroup  # novermin
from fastapi import FastAPI
from typing_extensions import ParamSpec, Self, TypeVar
from websockets.exceptions import InvalidStatus

import prefect.types._datetime
from prefect import Task
from prefect._internal.compatibility.blocks import call_explicitly_async_block_method
from prefect._internal.concurrency.api import create_call, from_sync
from prefect.cache_policies import DEFAULT, NO_CACHE
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import TaskRun
from prefect.client.subscriptions import Subscription
from prefect.logging.loggers import get_logger
from prefect.results import (
    ResultRecord,
    ResultRecordMetadata,
    ResultStore,
    get_or_create_default_task_scheduling_storage,
)
from prefect.settings import get_current_settings
from prefect.states import Pending
from prefect.task_engine import run_task_async, run_task_sync
from prefect.types import DateTime
from prefect.utilities.annotations import NotSet
from prefect.utilities.asyncutils import asyncnullcontext, sync_compatible
from prefect.utilities.engine import emit_task_run_state_change_event
from prefect.utilities.processutils import (
    _register_signal,  # pyright: ignore[reportPrivateUsage]
)
from prefect.utilities.services import start_client_metrics_server
from prefect.utilities.timeout import timeout_async
from prefect.utilities.urls import url_for

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger("task_worker")

P = ParamSpec("P")
R = TypeVar("R", infer_variance=True)


class StopTaskWorker(Exception):
    """Raised when the task worker is stopped."""

    pass


def should_try_to_read_parameters(task: Task[P, R], task_run: TaskRun) -> bool:
    """Determines whether a task run should read parameters from the result store."""
    if TYPE_CHECKING:
        assert task_run.state is not None
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
        *tasks: Task[P, R],
        limit: int | None = 10,
    ):
        self.tasks: list["Task[..., Any]"] = []
        for t in tasks:
            if not TYPE_CHECKING:
                if not isinstance(t, Task):
                    continue

            if t.cache_policy in [None, NO_CACHE, NotSet]:
                self.tasks.append(
                    t.with_options(persist_result=True, cache_policy=DEFAULT)
                )
            else:
                self.tasks.append(t.with_options(persist_result=True))

        self.task_keys: set[str] = set(t.task_key for t in tasks if isinstance(t, Task))  # pyright: ignore[reportUnnecessaryIsInstance]

        self._started_at: Optional[DateTime] = None
        self.stopping: bool = False

        self._client = get_client()
        self._exit_stack = AsyncExitStack()

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            raise RuntimeError(
                "TaskWorker must be initialized within an async context."
            )

        self._runs_task_group: Optional[anyio.abc.TaskGroup] = None
        self._executor = ThreadPoolExecutor(max_workers=limit if limit else None)
        self._limiter = anyio.CapacityLimiter(limit) if limit else None

        self.in_flight_task_runs: dict[str, dict[UUID, DateTime]] = {
            task_key: {} for task_key in self.task_keys
        }
        self.finished_task_runs: dict[str, int] = {
            task_key: 0 for task_key in self.task_keys
        }

    @property
    def client_id(self) -> str:
        return f"{socket.gethostname()}-{os.getpid()}"

    @property
    def started_at(self) -> Optional[DateTime]:
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

    def handle_sigterm(self, signum: int, frame: object) -> None:
        """
        Shuts down the task worker when a SIGTERM is received.
        """
        logger.info("SIGTERM received, initiating graceful shutdown...")
        from_sync.call_in_loop_thread(create_call(self.stop))

        sys.exit(0)

    @sync_compatible
    async def start(self, timeout: Optional[float] = None) -> None:
        """
        Starts a task worker, which runs the tasks provided in the constructor.

        Args:
            timeout: If provided, the task worker will exit after the given number of
                seconds. Defaults to None, meaning the task worker will run indefinitely.
        """
        _register_signal(signal.SIGTERM, self.handle_sigterm)

        start_client_metrics_server()

        async with asyncnullcontext() if self.started else self:
            logger.info("Starting task worker...")
            try:
                with timeout_async(timeout):
                    await self._subscribe_to_task_scheduling()
            except InvalidStatus as exc:
                if exc.response.status_code == 403:
                    logger.error(
                        "403: Could not establish a connection to the `/task_runs/subscriptions/scheduled`"
                        f" endpoint found at:\n\n {get_current_settings().api.url}"
                        "\n\nPlease double-check the values of"
                        " `PREFECT_API_AUTH_STRING` and `PREFECT_SERVER_API_AUTH_STRING` if running a Prefect server "
                        "or `PREFECT_API_URL` and `PREFECT_API_KEY` environment variables if using Prefect Cloud."
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
        base_url = get_current_settings().api.url
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
                assert self._runs_task_group is not None, (
                    "Task group was not initialized"
                )
                self._runs_task_group.start_soon(
                    self._safe_submit_scheduled_task_run, task_run
                )

    async def _safe_submit_scheduled_task_run(self, task_run: TaskRun):
        self.in_flight_task_runs[task_run.task_key][task_run.id] = (
            prefect.types._datetime.now("UTC")
        )
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
        if TYPE_CHECKING:
            assert task_run.state is not None
        logger.debug(
            f"Found task run: {task_run.name!r} in state: {task_run.state.name!r}"
        )

        task = next((t for t in self.tasks if t.task_key == task_run.task_key), None)

        if not task:
            if get_current_settings().tasks.scheduling.delete_failed_submissions:
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
            if parameters_id is None:
                logger.warning(
                    f"Task run {task_run.id!r} has no parameters ID. Skipping parameter retrieval."
                )
                return

            task.persist_result = True
            store = await ResultStore(
                result_storage=await get_or_create_default_task_scheduling_storage()
            ).update_for_task(task)
            try:
                run_data: dict[str, Any] = await read_parameters(store, parameters_id)
                parameters = run_data.get("parameters", {})
                wait_for = run_data.get("wait_for", [])
                run_context = run_data.get("context", None)
            except Exception as exc:
                logger.exception(
                    f"Failed to read parameters for task run {task_run.id!r}",
                    exc_info=exc,
                )
                if get_current_settings().tasks.scheduling.delete_failed_submissions:
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

    async def execute_task_run(self, task_run: TaskRun) -> None:
        """Execute a task run in the task worker."""
        async with self if not self.started else asyncnullcontext():
            token_acquired = await self._acquire_token(task_run.id)
            if token_acquired:
                await self._safe_submit_scheduled_task_run(task_run)

    async def __aenter__(self) -> Self:
        logger.debug("Starting task worker...")

        if self._client._closed:  # pyright: ignore[reportPrivateUsage]
            self._client = get_client()
        self._runs_task_group = anyio.create_task_group()

        await self._exit_stack.__aenter__()
        await self._exit_stack.enter_async_context(self._client)
        await self._exit_stack.enter_async_context(self._runs_task_group)
        self._exit_stack.enter_context(self._executor)

        self._started_at = prefect.types._datetime.now("UTC")
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        logger.debug("Stopping task worker...")
        self._started_at = None
        await self._exit_stack.__aexit__(*exc_info)


def create_status_server(task_worker: TaskWorker) -> FastAPI:
    status_app = FastAPI()

    @status_app.get("/status")
    def status():  # pyright: ignore[reportUnusedFunction]
        if TYPE_CHECKING:
            assert task_worker.started_at is not None
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
    *tasks: Task[P, R],
    limit: Optional[int] = 10,
    status_server_port: Optional[int] = None,
    timeout: Optional[float] = None,
):
    """Serve the provided tasks so that their runs may be submitted to
    and executed in the engine. Tasks do not need to be within a flow run context to be
    submitted. You must `.submit` the same task object that you pass to `serve`.

    Args:
        - tasks: A list of tasks to serve. When a scheduled task run is found for a
            given task, the task run will be submitted to the engine for execution.
        - limit: The maximum number of tasks that can be run concurrently. Defaults to 10.
            Pass `None` to remove the limit.
        - status_server_port: An optional port on which to start an HTTP server
            exposing status information about the task worker. If not provided, no
            status server will run.
        - timeout: If provided, the task worker will exit after the given number of
            seconds. Defaults to None, meaning the task worker will run indefinitely.

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
        await task_worker.start(timeout=timeout)

    except TimeoutError:
        if timeout is not None:
            logger.info(f"Task worker timed out after {timeout} seconds. Exiting...")
        else:
            raise

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


async def store_parameters(
    result_store: ResultStore, identifier: UUID, parameters: dict[str, Any]
) -> None:
    """Store parameters for a task run in the result store.

    Args:
        result_store: The result store to store the parameters in.
        identifier: The identifier of the task run.
        parameters: The parameters to store.
    """
    if result_store.result_storage is None:
        raise ValueError(
            "Result store is not configured - must have a result storage block to store parameters"
        )
    record = ResultRecord(
        result=parameters,
        metadata=ResultRecordMetadata(
            serializer=result_store.serializer, storage_key=str(identifier)
        ),
    )

    await call_explicitly_async_block_method(
        result_store.result_storage,
        "write_path",
        (f"parameters/{identifier}",),
        {"content": record.serialize()},
    )


async def read_parameters(
    result_store: ResultStore, identifier: UUID
) -> dict[str, Any]:
    """Read parameters for a task run from the result store.

    Args:
        result_store: The result store to read the parameters from.
        identifier: The identifier of the task run.

    Returns:
        The parameters for the task run.
    """
    if result_store.result_storage is None:
        raise ValueError(
            "Result store is not configured - must have a result storage block to read parameters"
        )
    record: ResultRecord[Any] = ResultRecord[Any].deserialize(
        await call_explicitly_async_block_method(
            result_store.result_storage,
            "read_path",
            (f"parameters/{identifier}",),
            {},
        )
    )
    return record.result
