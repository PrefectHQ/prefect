from typing import List, Set
from uuid import UUID

from prefect.agent import OrionAgent
from prefect.orion import schemas
from prefect.orion.models import workers_migration
from prefect.workers.base import BaseWorker


class AgentWorker(BaseWorker):
    """
    A worker that wraps a Prefect Agent to handle legacy (agent-compatible)
    deployments.
    """

    default_pool_name = workers_migration.AGENT_WORKER_POOL_NAME
    type = "AGENT"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.submitted_flow_run_ids: Set[UUID] = set()

    async def _on_start(self):
        """
        Enter an agent context on start.
        """
        await super()._on_start()
        self._agent = OrionAgent()
        await self._agent.__aenter__()

    async def _on_stop(self):
        """
        Close the agent context
        """
        await super()._on_stop()
        await self._agent.__aexit__(None, None, None)
        self._agent = None

    async def submit_scheduled_flow_runs(
        self, flow_run_response: List[schemas.responses.WorkerFlowRunResponse]
    ):
        for r in flow_run_response:
            self.logger.debug(f"Submitting flow run '{r.flow_run.id}'")

            # don't resubmit a run
            if r.flow_run.id in self._agent.submitting_flow_run_ids:
                continue

            self._agent.submitting_flow_run_ids.add(r.flow_run.id)
            self._agent.task_group.start_soon(
                self._agent.submit_run,
                r.flow_run,
            )
