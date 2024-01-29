import asyncio
import signal
import sys
from functools import partial
from typing import Iterable, List, Optional

import anyio
import anyio.abc
import pendulum

from prefect import Task, get_client
from prefect._internal.concurrency.api import create_call, from_sync
from prefect.client.schemas.filters import TaskRunFilter
from prefect.client.schemas.objects import TaskRun
from prefect.logging.loggers import get_logger
from prefect.results import ResultFactory
from prefect.settings import PREFECT_RUNNER_POLL_FREQUENCY
from prefect.task_engine import submit_autonomous_task_to_engine
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.processutils import _register_signal
from prefect.utilities.services import critical_service_loop

logger = get_logger("task_server")


class TaskServer:
    """This class is responsible for serving tasks that may be executed autonomously
    (i.e., without a parent flow run).

    When `start()` is called, the task server will begin polling for pending task runs
    every `query_seconds` seconds. When a pending task run is found, the task server
    will submit the task run to the engine for execution, using `submit_autonomous_task_to_engine`
    to construct a minimal `EngineContext` for the task run.

    Args:
        - tasks (Iterable[Task]): A list of tasks to be served by the task server.
        - query_seconds (int, optional): The number of seconds to wait between polling
            for pending task runs. Defaults to the value of `PREFECT_RUNNER_POLL_FREQUENCY`.
        - tags (Iterable[str], optional): A list of tags to filter pending task runs by.
            Defaults to `["autonomous"]`.
    """

    def __init__(
        self,
        *tasks: Task,
        query_seconds: Optional[int] = None,
        tags: Optional[Iterable[str]] = None,
    ):
        self.tasks: list[Task] = tasks
        self.query_seconds: int = query_seconds or PREFECT_RUNNER_POLL_FREQUENCY.value()
        self.tags: Iterable[str] = tags or ["autonomous"]
        self.last_polled: Optional[pendulum.DateTime] = None
        self.started = False
        self.stopping = False

        self._client = get_client()
        self._logger = get_logger("task_server")

        self._runs_task_group: anyio.abc.TaskGroup = anyio.create_task_group()
        self._loops_task_group: anyio.abc.TaskGroup = anyio.create_task_group()

    def handle_sigterm(self, signum, frame):
        """
        Shuts down the task server when a SIGTERM is received.
        """
        self._logger.info("SIGTERM received, initiating graceful shutdown...")
        from_sync.call_in_loop_thread(create_call(self.stop))

        sys.exit(0)

    @sync_compatible
    async def start(self) -> None:
        """
        Starts a task server, which runs the tasks provided in the constructor.
        """
        _register_signal(signal.SIGTERM, self.handle_sigterm)

        async with self as task_server:
            async with self._loops_task_group as tg:
                tg.start_soon(
                    partial(
                        critical_service_loop,
                        workload=task_server._get_and_submit_task_runs,
                        interval=self.query_seconds,
                        jitter_range=0.3,
                    )
                )

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
        try:
            self._loops_task_group.cancel_scope.cancel()
        except Exception:
            self._logger.exception(
                "Exception encountered while shutting down", exc_info=True
            )

    async def run_once(self):
        """Runs one iteration of the task server's polling cycle (used for testing)"""
        async with self._runs_task_group:
            await self._get_and_submit_task_runs()

    async def _get_and_submit_task_runs(self):
        if self.stopping:
            return
        runs_response = await self._get_pending_task_runs()
        self._logger.debug(f"Found {len(runs_response)} task run(s)")
        self.last_polled = pendulum.now("UTC")
        await self._submit_pending_task_runs(task_run_response=runs_response)

    async def _get_pending_task_runs(self) -> List[TaskRun]:
        return await self._client.read_task_runs(
            task_run_filter=TaskRunFilter(
                state=dict(name=dict(any_=["Scheduled"])), tags=dict(all_=self.tags)
            ),
        )

    async def _submit_pending_task_runs(self, task_run_response):
        for task_run in task_run_response:
            self._logger.debug(
                f"Found task run: {task_run.name!r} in state: {task_run.state.name!r}"
            )

            task = next((t for t in self.tasks if t.name in task_run.task_key), None)

            if not task:
                self._logger.warning(
                    f"Task {task_run.name!r} not found in task server registry."
                )
                await self._client._client.delete(
                    f"/task_runs/{task_run.id}"
                )  # while testing, delete the task run

                continue

            self._logger.info(repr(task_run.state))

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
                    self._logger.info(
                        f"Failed to read parameters for task run {task_run.id}: {exc}"
                    )
                    await self._client._client.delete(
                        f"/task_runs/{task_run.id}"
                    )  # while testing, delete the task run
                    continue

            self._logger.debug(
                "Parameters: %r and state data: %r",
                parameters,
                task_run.state.state_details,
            )

            self._runs_task_group.start_soon(
                partial(
                    submit_autonomous_task_to_engine,
                    task=task,
                    task_run=task_run,
                    parameters=parameters,
                )
            )

    async def __aenter__(self):
        self._logger.debug("Starting task server...")
        self._client = get_client()
        await self._client.__aenter__()
        await self._runs_task_group.__aenter__()

        self.started = True
        return self

    async def __aexit__(self, *exc_info):
        self._logger.debug("Stopping task server...")
        self.started = False
        if self._runs_task_group:
            await self._runs_task_group.__aexit__(*exc_info)
        if self._client:
            await self._client.__aexit__(*exc_info)


def serve(
    *tasks: Task,
    query_seconds: Optional[int] = None,
    tags: Optional[Iterable[str]] = None,
    run_once: bool = False,
):
    async def run_server():
        task_server = TaskServer(*tasks, query_seconds=query_seconds, tags=tags)
        if run_once:
            await task_server.run_once()
        else:
            await task_server.start()

    asyncio.run(run_server())
