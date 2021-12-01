"""
The agent is responsible for checking for flow runs that are ready to run and starting
their execution.
"""
from functools import partial
from typing import Awaitable, Callable, List, Optional
from uuid import UUID

import anyio
import anyio.to_process
import pendulum
from anyio.abc import TaskGroup

from prefect import settings
from prefect.client import OrionClient
from prefect.flow_runners import FlowRunner, SubprocessFlowRunner
from prefect.orion.schemas.core import FlowRun
from prefect.orion.schemas.filters import FlowRunFilter
from prefect.orion.schemas.sorting import FlowRunSort
from prefect.orion.schemas.states import StateType
from prefect.utilities.logging import get_logger


class OrionAgent:
    def __init__(
        self,
        prefetch_seconds: int = settings.agent.prefetch_seconds,
    ) -> None:
        self.prefetch_seconds = prefetch_seconds
        self.submitting_flow_run_ids = set()
        self.started = False
        self.logger = get_logger("agent")
        self.task_group: Optional[TaskGroup] = None
        self.client: Optional[OrionClient] = None

    def flow_run_query_filter(self) -> FlowRunFilter:
        return FlowRunFilter(
            id=dict(not_any_=self.submitting_flow_run_ids),
            state=dict(type=dict(any_=[StateType.SCHEDULED])),
            next_scheduled_start_time=dict(
                before_=pendulum.now("utc").add(seconds=self.prefetch_seconds)
            ),
            deployment_id=dict(is_null_=False),
        )

    async def get_and_submit_flow_runs(self) -> List[FlowRun]:
        if not self.started:
            raise RuntimeError("Agent is not started. Use `async with OrionAgent()...`")

        submittable_runs = await self.client.read_flow_runs(
            sort=FlowRunSort.NEXT_SCHEDULED_START_TIME_ASC,
            flow_run_filter=self.flow_run_query_filter(),
        )

        for flow_run in submittable_runs:
            self.logger.info(f"Submitting flow run '{flow_run.id}'")
            self.submitting_flow_run_ids.add(flow_run.id)
            self.task_group.start_soon(
                self.lookup_submission_method(flow_run),
                flow_run,
                self.task_group,
                partial(self.submitted_callback, flow_run.id),
            )
        return submittable_runs

    def lookup_submission_method(
        self, flow_run: FlowRun
    ) -> Callable[[FlowRun, TaskGroup, Callable[[bool], None]], Awaitable[None]]:
        """
        Returns a submission method based on the flow runner configuration
        """
        if flow_run.flow_runner is not None:
            return FlowRunner.from_settings(flow_run.flow_runner).submit_flow_run
        else:
            # TODO: We do a local run by default, but we should do something more
            #       interesting here like set a default type on the agent
            return SubprocessFlowRunner().submit_flow_run

    def submitted_callback(self, flow_run_id: UUID, success: bool, reason: str = None):
        message = f": {reason}" if reason else ""
        if success:
            self.logger.info(
                f"Completed submission of flow run '{flow_run_id}'" + message
            )
        else:
            self.logger.error(f"Failed to submit flow run '{flow_run_id}'" + message)

            self.submitting_flow_run_ids.remove(flow_run_id)

    # Context management ---------------------------------------------------------------

    async def start(self):
        self.started = True
        self.task_group = anyio.create_task_group()
        self.client = OrionClient()
        await self.client.__aenter__()
        await self.task_group.__aenter__()

    async def shutdown(self, *exc_info):
        self.started = False
        await self.task_group.__aexit__(*exc_info)
        await self.client.__aexit__(*exc_info)
        self.task_group = None
        self.client = None
        self.submitting_flow_run_ids = set()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc_info):
        await self.shutdown(*exc_info)
