"""
The agent is responsible for checking for flow runs that are ready to run and starting
their execution.
"""
from typing import List, Optional

import anyio
import anyio.to_process
import pendulum
from anyio.abc import TaskGroup

from prefect import settings
from prefect.client import OrionClient
from prefect.exceptions import Abort
from prefect.flow_runners import FlowRunner
from prefect.orion.schemas.core import FlowRun, FlowRunnerSettings
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.filters import FlowRunFilter
from prefect.orion.schemas.sorting import FlowRunSort
from prefect.orion.schemas.states import Failed, Pending, State, StateType
from prefect.logging import get_logger


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
        """
        Queries for scheduled flow runs and submits them for execution in parallel
        """
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
                self.submit_run,
                flow_run,
            )
        return submittable_runs

    def get_flow_runner(self, flow_run: FlowRun):
        # TODO: Here, the agent may merge settings with those contained in the
        #       flow_run.flow_runner settings object

        flow_runner_settings = flow_run.flow_runner.copy() or FlowRunnerSettings()
        if not flow_runner_settings.type or flow_runner_settings.type == "universal":
            flow_runner_settings.type = "subprocess"

        return FlowRunner.from_settings(flow_runner_settings)

    async def submit_run(self, flow_run: FlowRun) -> None:
        """
        Submit a flow run to the flow runner
        """
        ready_to_submit = await self._propose_pending_state(flow_run)

        if ready_to_submit:
            # Successfully entered a pending state; submit to flow runner
            flow_runner = self.get_flow_runner(flow_run)

            try:
                # Wait for submission to be completed. Note that the submission function
                # may continue to run in the background after this exits.
                await self.task_group.start(flow_runner.submit_flow_run, flow_run)
                self.logger.info(f"Completed submission of flow run '{flow_run.id}'")
            except Exception as exc:
                self.logger.error(
                    f"Flow runner failed to submit flow run '{flow_run.id}'",
                    exc_info=True,
                )
                await self._propose_failed_state(flow_run, exc)

        self.submitting_flow_run_ids.remove(flow_run.id)

    async def _propose_pending_state(self, flow_run: FlowRun) -> bool:
        state = flow_run.state
        try:
            state = await self.client.propose_state(Pending(), flow_run_id=flow_run.id)
        except Abort as exc:
            self.logger.info(
                f"Aborted submission of flow run '{flow_run.id}'. "
                f"Server sent an abort signal: {exc}",
            )
            return False
        except Exception as exc:
            self.logger.error(
                f"Failed to update state of flow run '{flow_run.id}'",
                exc_info=True,
            )
            return False

        if not state.is_pending():
            self.logger.info(
                f"Aborted submission of flow run '{flow_run.id}': "
                f"Server returned a non-pending state {state.type.value!r}",
            )
            return False

        return True

    async def _propose_failed_state(self, flow_run: FlowRun, exc: Exception) -> None:
        try:
            await self.client.propose_state(
                Failed(
                    message="Submission failed.",
                    data=DataDocument.encode("cloudpickle", exc),
                ),
                flow_run_id=flow_run.id,
            )
        except Abort:
            # We've already failed, no need to note the abort but we don't want it to
            # raise in the agent process
            pass
        except Exception:
            self.logger.error(
                f"Failed to update state of flow run '{flow_run.id}'",
                exc_info=True,
            )

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
