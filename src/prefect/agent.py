"""
The agent is responsible for checking for flow runs that are ready to run and starting
their execution.
"""
from typing import List, Optional
from uuid import UUID

import anyio
import anyio.to_process
import httpx
import pendulum
from anyio.abc import TaskGroup
from fastapi import status

from prefect.blocks.core import Block
from prefect.client import OrionClient, get_client
from prefect.exceptions import Abort
from prefect.infrastructure import Infrastructure, Process
from prefect.infrastructure.submission import submit_flow_run
from prefect.logging import get_logger
from prefect.orion.schemas.core import BlockDocument, FlowRun
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import Failed, Pending
from prefect.settings import PREFECT_AGENT_PREFETCH_SECONDS


class OrionAgent:
    def __init__(
        self,
        work_queue_id: UUID = None,
        work_queue_name: str = None,
        prefetch_seconds: int = None,
        default_infrastructure: Infrastructure = None,
        default_infrastructure_document_id: UUID = None,
    ) -> None:
        if not work_queue_id and not work_queue_name:
            raise ValueError(
                "Either work_queue_id or work_queue_name must be provided."
            )
        if work_queue_id and work_queue_name:
            raise ValueError("Provide only one of work_queue_id and work_queue_name.")

        if default_infrastructure and default_infrastructure_document_id:
            raise ValueError(
                "Provide only one of 'default_infrastructure' and 'default_infrastructure_document_id'."
            )

        self.work_queue_id = work_queue_id
        self.work_queue_name = work_queue_name
        self.prefetch_seconds = prefetch_seconds
        self.submitting_flow_run_ids = set()
        self.started = False
        self.logger = get_logger("agent")
        self.task_group: Optional[TaskGroup] = None
        self.client: Optional[OrionClient] = None

        if default_infrastructure:
            self.default_infrastructure_document_id = (
                default_infrastructure._block_document_id
            )
            self.default_infrastructure = default_infrastructure
        elif default_infrastructure_document_id:
            self.default_infrastructure_document_id = default_infrastructure_document_id
            self.default_infrastructure = None
        else:
            self.default_infrastructure = Process()
            self.default_infrastructure_document_id = None

    async def work_queue_id_from_name(self) -> Optional[UUID]:
        """
        For agents that were provided a work_queue_name, rather than a work_queue_id,
        this function will retrieve the work queue ID corresponding to that name.
        If no matching queue is found, a warning is logged and `None` is returned.
        """
        if not self.work_queue_name:
            raise ValueError("No work queue name provided.")
        try:
            work_queue = await self.client.read_work_queue_by_name(self.work_queue_name)
            return work_queue.id
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                self.logger.warning(
                    f"No work queue found named {self.work_queue_name!r}"
                )
                return None
            else:
                raise

    async def get_and_submit_flow_runs(self) -> List[FlowRun]:
        """
        The principle method on agents. Queries for scheduled flow runs and submits
        them for execution in parallel.
        """
        if not self.started:
            raise RuntimeError("Agent is not started. Use `async with OrionAgent()...`")

        self.logger.debug("Checking for flow runs...")

        before = pendulum.now("utc").add(
            seconds=self.prefetch_seconds or PREFECT_AGENT_PREFETCH_SECONDS.value()
        )

        # Use the work queue id or load one from the name
        work_queue_id = self.work_queue_id or await self.work_queue_id_from_name()
        if not work_queue_id:
            return []

        try:
            submittable_runs = await self.client.get_runs_in_work_queue(
                id=work_queue_id, limit=10, scheduled_before=before
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                raise ValueError(
                    f"No work queue found with id '{work_queue_id}'"
                ) from None
            else:
                raise

        # Check for a paused work queue for display purposes
        if not submittable_runs:
            work_queue = await self.client.read_work_queue(work_queue_id)
            if work_queue.is_paused:
                self.logger.info(
                    f"Work queue {work_queue.name!r} ({work_queue.id}) is paused."
                )

        for flow_run in submittable_runs:
            self.logger.info(f"Submitting flow run '{flow_run.id}'")

            # don't resubmit a run
            if flow_run.id in self.submitting_flow_run_ids:
                continue

            self.submitting_flow_run_ids.add(flow_run.id)
            self.task_group.start_soon(
                self.submit_run,
                flow_run,
            )
        return submittable_runs

    async def get_infrastructure(self, flow_run: FlowRun) -> Infrastructure:
        deployment = await self.client.read_deployment(flow_run.deployment_id)

        ## get infra
        infrastructure_document_id = (
            deployment.infrastructure_document_id
            or self.default_infrastructure_document_id
        )
        infra_document = await self.client.read_block_document(
            infrastructure_document_id
        )

        # this piece of logic applies any overrides that may have been set on the deployment;
        # overrides are defined as dot.delimited paths on possibly nested attributes of the
        # infrastructure block
        doc_dict = infra_document.dict()
        infra_dict = doc_dict.get("data", {})
        for override, value in (deployment.infra_overrides or {}).items():
            nested_fields = override.split(".")
            data = infra_dict
            for field in nested_fields[:-1]:
                data = data[field]

            # once we reach the end, set the value
            data[nested_fields[-1]] = value

        # reconstruct the infra block
        doc_dict["data"] = infra_dict
        infra_document = BlockDocument(**doc_dict)
        infrastructure_block = Block._from_block_document(infra_document)
        # TODO: Here the agent may update the infrastructure with agent-level settings
        return infrastructure_block

    async def submit_run(self, flow_run: FlowRun) -> None:
        """
        Submit a flow run to the flow runner
        """
        ready_to_submit = await self._propose_pending_state(flow_run)

        if ready_to_submit:
            infrastructure = await self.get_infrastructure(flow_run)

            try:
                # Wait for submission to be completed. Note that the submission function
                # may continue to run in the background after this exits.
                await self.task_group.start(submit_flow_run, flow_run, infrastructure)
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
        self.client = get_client()
        await self.client.__aenter__()
        await self.task_group.__aenter__()

        # Convert the passed default infrastructure to an id
        if self.default_infrastructure and not self.default_infrastructure_document_id:
            self.default_infrastructure_document_id = (
                await self.default_infrastructure._save(is_anonymous=True)
            )

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
