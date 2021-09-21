"""
The agent implementation is consumed by both `orion` and `prefect` so that the agent
service included in Orion share code with the client-side agent.
"""
from typing import Awaitable, Callable, List, Optional

import anyio
import anyio.to_process
import pendulum
from anyio.abc import TaskGroup, TaskStatus

from prefect.orion.schemas.core import FlowRun
from prefect.orion.schemas.filters import FlowRunFilter
from prefect.orion.schemas.states import StateType
from prefect.utilities.logging import get_logger


class OrionAgent:
    def __init__(
        self,
        prefetch_seconds: int,
    ) -> None:
        self.prefetch_seconds = prefetch_seconds
        self.submitting_flow_run_ids = set()
        self.started = False
        self.logger = get_logger("agent")
        self.task_group: Optional[TaskGroup] = None

    def flow_run_query_filter(self) -> FlowRunFilter:
        return FlowRunFilter(
            states=[StateType.SCHEDULED],
            start_time_before=pendulum.now("utc").add(seconds=self.prefetch_seconds),
        )

    def filter_flow_runs(self, flow_runs: List[FlowRun]) -> List[FlowRun]:
        # Filter out runs that should not be submitted again but maintain ordering
        # TODO: Move this into the `FlowRunFilter` once it supports this; this method
        #       can then be removed entirely or just return the input in the base cls
        ready_runs = [
            run
            for run in flow_runs
            if run.id not in self.submitting_flow_run_ids
            and run.deployment_id is not None
            and (
                run.state.state_details.scheduled_time
                < pendulum.now("utc").add(seconds=self.prefetch_seconds)
            )
        ]
        return ready_runs

    async def get_and_submit_flow_runs(
        self, query_fn: Callable[[FlowRunFilter], Awaitable[List[FlowRun]]]
    ):
        if not self.started:
            raise RuntimeError("Agent is not set up yet. Use `async with Agent()...`")

        ready_runs = await query_fn(flow_run_filter=self.flow_run_query_filter())
        submittable_runs = self.filter_flow_runs(ready_runs)

        for flow_run in submittable_runs:
            self.logger.info(f"Submitting flow run '{flow_run.id}'")
            self.submitting_flow_run_ids.add(flow_run.id)
            self.task_group.start_soon(
                self.lookup_submission_method(flow_run),
                flow_run,
                self.submitted_callback,
            )

    def lookup_submission_method(self, flow_run: FlowRun) -> Callable[[FlowRun], None]:
        """
        Future hook for returning submission methods based on flow run configs
        """
        return self.submit_flow_run_to_subprocess

    async def submit_flow_run_to_subprocess(
        self,
        flow_run: FlowRun,
        submitted_callback: Callable[[FlowRun, bool], None],
    ) -> None:
        async def check_result(task, task_status: TaskStatus):
            """
            Here we await the result of the subprocess which will contain the final flow
            run state which we will log.

            This is useful for early development but is not feasible for all planned
            submission methods so I will not generalize it yet
            """
            task_status.started()

            state = await task

            if state.is_failed():
                self.logger.info(
                    f"Flow run '{state.state_details.flow_run_id}' failed!"
                )
            elif state.is_completed():
                self.logger.info(
                    f"Flow run '{state.state_details.flow_run_id}' completed."
                )

        import prefect.engine

        task = anyio.to_process.run_sync(
            prefect.engine.enter_flow_run_engine_from_subprocess,
            flow_run.id,
        )
        await self.task_group.start(check_result, task)
        await submitted_callback(flow_run, True)

    async def submitted_callback(self, flow_run: FlowRun, success: bool):
        if success:
            self.logger.info(f"Completed submission of flow run '{flow_run.id}'")
        else:
            self.logger.error(f"Failed to submit flow run '{flow_run.id}'")

            self.submitting_flow_run_ids.remove(flow_run.id)

    # Context management ---------------------------------------------------------------

    async def start(self):
        self.started = True
        self.task_group = anyio.create_task_group()
        self.lock = anyio.create_lock()
        await self.task_group.__aenter__()

    async def shutdown(self, *exc_info):
        self.started = False
        await self.task_group.__aexit__(*exc_info)
        self.task_group = None
        self.lock = None
        self.submitting_flow_run_ids = set()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc_info):
        await self.shutdown(*exc_info)
