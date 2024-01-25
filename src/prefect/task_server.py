import signal
import sys
from functools import partial
from typing import Optional

import anyio
import anyio.abc
import pendulum

from prefect import Task, get_client
from prefect._internal.concurrency.api import create_call, from_sync
from prefect.client.schemas.filters import TaskRunFilter
from prefect.client.schemas.objects import TaskRun
from prefect.logging.loggers import get_logger
from prefect.settings import PREFECT_RUNNER_POLL_FREQUENCY
from prefect.task_engine import submit_autonomous_task_to_engine
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.processutils import _register_signal
from prefect.utilities.services import critical_service_loop


class TaskServer:
    def __init__(
        self,
        *tasks: Task,
        query_seconds: Optional[int] = None,
    ):
        self.tasks: list[Task] = tasks
        self.query_seconds: int = query_seconds or PREFECT_RUNNER_POLL_FREQUENCY.value()
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

    async def _get_and_submit_task_runs(self):
        if self.stopping:
            return
        runs_response = await self._get_scheduled_task_runs()
        self._logger.debug(f"Found {len(runs_response)} task runs")
        self.last_polled = pendulum.now("UTC")
        await self._submit_scheduled_task_runs(task_run_response=runs_response)

    async def _get_scheduled_task_runs(self) -> list[TaskRun]:
        return await self._client.read_task_runs(
            task_run_filter=TaskRunFilter(
                state=dict(name=dict(any_=["Pending"])), tags=dict(all_=["autonomous"])
            ),
        )

    async def _submit_scheduled_task_runs(self, task_run_response):
        for task_run in task_run_response:
            self._logger.debug(
                f"Found task run: {task_run.name!r} in state: {task_run.state.name!r}"
            )

            task = next((t for t in self.tasks if t.name in task_run.dynamic_key), None)

            if not task:
                self._logger.warning(
                    f"Task {task_run.name!r} not found in task server registry."
                )
                await self._client._client.delete(
                    f"/task_runs/{task_run.id}"
                )  # while testing, delete the task run

                continue

            self._runs_task_group.start_soon(
                partial(submit_autonomous_task_to_engine, task)
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
