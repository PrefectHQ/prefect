"""
The agent is responsible for checking for flow runs that are ready to run and starting
their execution.
"""
from typing import Iterator, List, Optional, Set, Union
from uuid import UUID

import anyio
import anyio.abc
import anyio.to_process
import pendulum

from prefect.blocks.core import Block
from prefect.client import OrionClient, get_client
from prefect.engine import propose_state
from prefect.exceptions import Abort, ObjectNotFound
from prefect.infrastructure import Infrastructure, InfrastructureResult, Process
from prefect.logging import get_logger
from prefect.orion.schemas.core import BlockDocument, FlowRun, WorkQueue
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import Failed, Pending
from prefect.settings import PREFECT_AGENT_PREFETCH_SECONDS


class OrionAgent:
    def __init__(
        self,
        work_queues: List[str],
        prefetch_seconds: int = None,
        default_infrastructure: Infrastructure = None,
        default_infrastructure_document_id: UUID = None,
    ) -> None:

        if default_infrastructure and default_infrastructure_document_id:
            raise ValueError(
                "Provide only one of 'default_infrastructure' and 'default_infrastructure_document_id'."
            )

        self.work_queues: Set[str] = set(work_queues)
        self.prefetch_seconds = prefetch_seconds
        self.submitting_flow_run_ids = set()
        self.started = False
        self.logger = get_logger("agent")
        self.task_group: Optional[anyio.abc.TaskGroup] = None
        self.client: Optional[OrionClient] = None

        self._work_queue_cache_expiration: pendulum.DateTime = None
        self._work_queue_cache: List[WorkQueue] = []

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

    async def get_work_queues(self) -> Iterator[WorkQueue]:
        """
        Loads the work queue objects corresponding to the agent's target work
        queues. If any of them don't exist, they are created.
        """

        # if the queue cache has not expired, yield queues from the cache
        now = pendulum.now("UTC")
        if (self._work_queue_cache_expiration or now) > now:
            for queue in self._work_queue_cache:
                yield queue
            return

        # otherwise clear the cache, set the expiration for 30 seconds, and
        # reload the work queues
        self._work_queue_cache.clear()
        self._work_queue_cache_expiration = now.add(seconds=30)

        for name in self.work_queues:
            try:
                work_queue = await self.client.read_work_queue_by_name(name)
            except ObjectNotFound:

                # if the work queue wasn't found, create it
                try:
                    work_queue = await self.client.create_work_queue(name=name)
                    self.logger.info(f"Created work queue '{name}'.")

                # if creating it raises an exception, it was probably just
                # created by some other agent; rather than entering a re-read
                # loop with new error handling, we log the exception and
                # continue.
                except Exception as exc:
                    self.logger.exception(f"Failed to create work queue {name!r}.")
                    continue

            self._work_queue_cache.append(work_queue)
            yield work_queue

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

        submittable_runs = []

        # load runs from each work queue
        async for work_queue in self.get_work_queues():

            # print a nice message if the work queue is paused
            if work_queue.is_paused:
                self.logger.info(
                    f"Work queue {work_queue.name!r} ({work_queue.id}) is paused."
                )

            else:
                try:
                    queue_runs = await self.client.get_runs_in_work_queue(
                        id=work_queue.id, limit=10, scheduled_before=before
                    )
                    submittable_runs.extend(queue_runs)
                except ObjectNotFound:
                    self.logger.error(
                        f"Work queue {work_queue.name!r} ({work_queue.id}) not found."
                    )
                except Exception as exc:
                    self.logger.exception(exc)

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

        # overrides only apply when configuring known infra blocks
        if not deployment.infrastructure_document_id:
            if self.default_infrastructure:
                return self.default_infrastructure
            else:
                infra_document = await self.client.read_block_document(
                    self.default_infrastructure_document_id
                )
                return Block._from_block_document(infra_document)

        ## get infra
        infra_document = await self.client.read_block_document(
            deployment.infrastructure_document_id
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

        prepared_infrastructure = infrastructure_block.prepare_for_flow_run(flow_run)
        return prepared_infrastructure

    async def submit_run(self, flow_run: FlowRun) -> None:
        """
        Submit a flow run to the infrastructure
        """
        ready_to_submit = await self._propose_pending_state(flow_run)

        if ready_to_submit:
            infrastructure = await self.get_infrastructure(flow_run)

            # Wait for submission to be completed. Note that the submission function
            # may continue to run in the background after this exits.
            await self.task_group.start(
                self._submit_run_and_capture_errors, flow_run, infrastructure
            )
            self.logger.info(f"Completed submission of flow run '{flow_run.id}'")

        self.submitting_flow_run_ids.remove(flow_run.id)

    async def _submit_run_and_capture_errors(
        self,
        flow_run: FlowRun,
        infrastructure: Infrastructure,
        task_status: anyio.abc.TaskStatus = None,
    ) -> Union[InfrastructureResult, Exception]:

        # Note: There is not a clear way to determine if task_status.started() has been
        #       called without peeking at the internal `_future`. Ideally we could just
        #       check if the flow run id has been removed from `submitting_flow_run_ids`
        #       but it is not so simple to guarantee that this coroutine yields back
        #       to `submit_run` to execute that line when exceptions are raised during
        #       submission.
        try:
            result = await infrastructure.run(task_status=task_status)
        except Exception as exc:
            if not task_status._future.done():
                # This flow run was being submitted and did not start successfully
                self.logger.exception(
                    f"Failed to submit flow run '{flow_run.id}' to infrastructure."
                )
                # Mark the task as started to prevent agent crash
                task_status.started(exc)
                await self._propose_failed_state(flow_run, exc)
            else:
                self.logger.exception(
                    f"An error occured while monitoring flow run '{flow_run.id}'. "
                    "The flow run will not be marked as failed, but an issue may have "
                    "occurred."
                )
            return exc

        if not task_status._future.done():
            self.logger.error(
                f"Infrastructure returned without reporting flow run '{flow_run.id}' "
                "as started or raising an error. This behavior is not expected and "
                "generally indicates improper implementation of infrastructure. The "
                "flow run will not be marked as failed, but an issue may have occurred."
            )
            # Mark the task as started to prevent agent crash
            task_status.started()

        # TODO: Check the result for a bad exit code and proposing a crashed state for the
        #       run
        return result

    async def _propose_pending_state(self, flow_run: FlowRun) -> bool:
        state = flow_run.state
        try:
            state = await propose_state(self.client, Pending(), flow_run_id=flow_run.id)
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
            await propose_state(
                self.client,
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

    async def shutdown(self, *exc_info):
        self.started = False
        await self.task_group.__aexit__(*exc_info)
        await self.client.__aexit__(*exc_info)
        self.task_group = None
        self.client = None
        self.submitting_flow_run_ids = set()
        self._work_queue_cache_expiration = None
        self._work_queue_cache = []

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc_info):
        await self.shutdown(*exc_info)
