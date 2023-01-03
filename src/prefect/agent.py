"""
The agent is responsible for checking for flow runs that are ready to run and starting
their execution.
"""
import inspect
from typing import Iterator, List, Optional, Set, Union
from uuid import UUID

import anyio
import anyio.abc
import anyio.to_process
import pendulum

from prefect.blocks.core import Block
from prefect.client.orion import OrionClient, get_client
from prefect.engine import propose_state
from prefect.exceptions import (
    Abort,
    InfrastructureNotAvailable,
    InfrastructureNotFound,
    ObjectNotFound,
)
from prefect.infrastructure import Infrastructure, InfrastructureResult, Process
from prefect.logging import get_logger
from prefect.orion.schemas.core import BlockDocument, FlowRun, WorkQueue
from prefect.orion.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterId,
    FlowRunFilterState,
    FlowRunFilterStateName,
    FlowRunFilterStateType,
    FlowRunFilterWorkQueueName,
)
from prefect.settings import PREFECT_AGENT_PREFETCH_SECONDS
from prefect.states import Crashed, Pending, StateType, exception_to_failed_state


class OrionAgent:
    def __init__(
        self,
        work_queues: List[str] = None,
        work_queue_prefix: Union[str, List[str]] = None,
        prefetch_seconds: int = None,
        default_infrastructure: Infrastructure = None,
        default_infrastructure_document_id: UUID = None,
        limit: Optional[int] = None,
    ) -> None:

        if default_infrastructure and default_infrastructure_document_id:
            raise ValueError(
                "Provide only one of 'default_infrastructure' and 'default_infrastructure_document_id'."
            )

        self.work_queues: Set[str] = set(work_queues) if work_queues else set()
        self.prefetch_seconds = prefetch_seconds
        self.submitting_flow_run_ids = set()
        self.cancelling_flow_run_ids = set()
        self.scheduled_task_scopes = set()
        self.started = False
        self.logger = get_logger("agent")
        self.task_group: Optional[anyio.abc.TaskGroup] = None
        self.limit: Optional[int] = limit
        self.limiter: Optional[anyio.CapacityLimiter] = None
        self.client: Optional[OrionClient] = None

        if isinstance(work_queue_prefix, str):
            work_queue_prefix = [work_queue_prefix]
        self.work_queue_prefix = work_queue_prefix

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

    async def update_matched_agent_work_queues(self):
        if self.work_queue_prefix:
            matched_queues = await self.client.match_work_queues(self.work_queue_prefix)
            matched_queues = set(q.name for q in matched_queues)
            if matched_queues != self.work_queues:
                new_queues = matched_queues - self.work_queues
                removed_queues = self.work_queues - matched_queues
                if new_queues:
                    self.logger.info(
                        f"Matched new work queues: {', '.join(new_queues)}"
                    )
                if removed_queues:
                    self.logger.info(
                        f"Work queues no longer matched: {', '.join(removed_queues)}"
                    )
            self.work_queues = matched_queues

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

        await self.update_matched_agent_work_queues()

        for name in self.work_queues:
            try:
                work_queue = await self.client.read_work_queue_by_name(name)
            except ObjectNotFound:

                # if the work queue wasn't found, create it
                if not self.work_queue_prefix:
                    # do not attempt to create work queues if the agent is polling for
                    # queues using a regex
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

        self.logger.debug("Checking for scheduled flow runs...")

        before = pendulum.now("utc").add(
            seconds=self.prefetch_seconds or PREFECT_AGENT_PREFETCH_SECONDS.value()
        )

        submittable_runs: List[FlowRun] = []

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

        submittable_runs.sort(key=lambda run: run.next_scheduled_start_time)

        for flow_run in submittable_runs:

            # don't resubmit a run
            if flow_run.id in self.submitting_flow_run_ids:
                continue

            try:
                if self.limiter:
                    self.limiter.acquire_on_behalf_of_nowait(flow_run.id)
            except anyio.WouldBlock:
                self.logger.info(
                    f"Flow run limit reached; {self.limiter.borrowed_tokens} flow runs in progress."
                )
                break
            else:
                self.logger.info(f"Submitting flow run '{flow_run.id}'")
                self.submitting_flow_run_ids.add(flow_run.id)
                self.task_group.start_soon(
                    self.submit_run,
                    flow_run,
                )

        return list(
            filter(lambda run: run.id in self.submitting_flow_run_ids, submittable_runs)
        )

    async def check_for_cancelled_flow_runs(self):
        if not self.started:
            raise RuntimeError("Agent is not started. Use `async with OrionAgent()...`")

        self.logger.debug("Checking for cancelled flow runs...")

        work_queue_names = set()
        async for work_queue in self.get_work_queues():
            work_queue_names.add(work_queue.name)

        cancelling_flow_runs = await self.client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                state=FlowRunFilterState(
                    type=FlowRunFilterStateType(any_=[StateType.CANCELLED]),
                    name=FlowRunFilterStateName(any_=["Cancelling"]),
                ),
                work_queue_name=FlowRunFilterWorkQueueName(any_=list(work_queue_names)),
                # Avoid duplicate cancellation calls
                id=FlowRunFilterId(not_any_=list(self.cancelling_flow_run_ids)),
            ),
        )

        if cancelling_flow_runs:
            self.logger.info(
                f"Found {len(cancelling_flow_runs)} flow runs awaiting cancellation."
            )

        for flow_run in cancelling_flow_runs:
            self.cancelling_flow_run_ids.add(flow_run.id)
            self.task_group.start_soon(self.cancel_run, flow_run)

        return cancelling_flow_runs

    async def cancel_run(self, flow_run: FlowRun) -> None:
        """
        Cancel a flow run by killing its infrastructure
        """
        if not flow_run.infrastructure_pid:
            self.logger.error(
                f"Flow run '{flow_run.id}' does not have an infrastructure pid attached. Cancellation cannot be guaranteed."
            )
            await self._mark_flow_run_as_cancelled(
                flow_run,
                state_updates={
                    "message": "This flow run is missing infrastructure tracking information and cancellation cannot be guaranteed."
                },
            )
            return

        try:
            infrastructure = await self.get_infrastructure(flow_run)
        except Exception:
            self.logger.exception(
                f"Failed to get infrastructure for flow run '{flow_run.id}'. "
                "Flow run cannot be cancelled."
            )
            # Note: We leave this flow run in the cancelling set because it cannot be
            #       cancelled and this will prevent additional attempts.
            return

        if not hasattr(infrastructure, "kill"):
            self.logger.error(
                f"Flow run '{flow_run.id}' infrastructure {infrastructure.type!r} "
                "does not support killing created infrastructure. "
                "Cancellation cannot be guaranteed."
            )
            return

        self.logger.info(
            f"Killing {infrastructure.type} {flow_run.infrastructure_pid} for flow run "
            f"'{flow_run.id}'..."
        )
        try:
            await infrastructure.kill(flow_run.infrastructure_pid)
        except InfrastructureNotFound as exc:
            self.logger.warning(f"{exc} Marking flow run as cancelled.")
            await self._mark_flow_run_as_cancelled(flow_run)
        except InfrastructureNotAvailable as exc:
            self.logger.warning(f"{exc} Flow run cannot be cancelled by this agent.")
        except Exception:
            self.logger.exception(
                f"Encountered exception while killing infrastructure for flow run "
                f"'{flow_run.id}'. Flow run may not be cancelled."
            )
            # We will try again on generic exceptions
            self.cancelling_flow_run_ids.remove(flow_run.id)
            return
        else:
            await self._mark_flow_run_as_cancelled(flow_run)
            self.logger.info(f"Cancelled flow run '{flow_run.id}'!")

    async def _mark_flow_run_as_cancelled(
        self, flow_run: FlowRun, state_updates: Optional[dict] = None
    ) -> None:
        state_updates = state_updates or {}
        state_updates.setdefault("name", "Cancelled")
        state = flow_run.state.copy(update=state_updates)

        await self.client.set_flow_run_state(flow_run.id, state, force=True)

        # Do not remove the flow run from the cancelling set immediately because
        # the API caches responses for the `read_flow_runs` and we do not want to
        # duplicate cancellations.
        await self._schedule_task(
            60 * 10, self.cancelling_flow_run_ids.remove, flow_run.id
        )

    async def get_infrastructure(self, flow_run: FlowRun) -> Infrastructure:
        deployment = await self.client.read_deployment(flow_run.deployment_id)
        flow = await self.client.read_flow(deployment.flow_id)

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

        # Add flow run metadata to the infrastructure
        prepared_infrastructure = infrastructure_block.prepare_for_flow_run(
            flow_run, deployment=deployment, flow=flow
        )

        return prepared_infrastructure

    async def submit_run(self, flow_run: FlowRun) -> None:
        """
        Submit a flow run to the infrastructure
        """
        ready_to_submit = await self._propose_pending_state(flow_run)

        if ready_to_submit:
            try:
                infrastructure = await self.get_infrastructure(flow_run)
            except Exception as exc:
                self.logger.exception(
                    f"Failed to get infrastructure for flow run '{flow_run.id}'."
                )
                await self._propose_failed_state(flow_run, exc)
                if self.limiter:
                    self.limiter.release_on_behalf_of(flow_run.id)
            else:
                # Wait for submission to be completed. Note that the submission function
                # may continue to run in the background after this exits.
                readiness_result = await self.task_group.start(
                    self._submit_run_and_capture_errors, flow_run, infrastructure
                )

                if readiness_result and not isinstance(readiness_result, Exception):
                    try:
                        await self.client.update_flow_run(
                            flow_run_id=flow_run.id,
                            infrastructure_pid=str(readiness_result),
                        )
                    except Exception as exc:
                        self.logger.exception(
                            "An error occured while setting the `infrastructure_pid` on "
                            f"flow run {flow_run.id!r}. The flow run will not be cancellable."
                        )

                self.logger.info(f"Completed submission of flow run '{flow_run.id}'")

        else:
            # If the run is not ready to submit, release the concurrency slot
            if self.limiter:
                self.limiter.release_on_behalf_of(flow_run.id)

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
        finally:
            if self.limiter:
                self.limiter.release_on_behalf_of(flow_run.id)

        if not task_status._future.done():
            self.logger.error(
                f"Infrastructure returned without reporting flow run '{flow_run.id}' "
                "as started or raising an error. This behavior is not expected and "
                "generally indicates improper implementation of infrastructure. The "
                "flow run will not be marked as failed, but an issue may have occurred."
            )
            # Mark the task as started to prevent agent crash
            task_status.started()

        if result.status_code != 0:
            await self._propose_crashed_state(
                flow_run,
                f"Flow run infrastructure exited with non-zero status code {result.status_code}.",
            )

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
                await exception_to_failed_state(message="Submission failed.", exc=exc),
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

    async def _propose_crashed_state(self, flow_run: FlowRun, message: str) -> None:
        try:
            state = await propose_state(
                self.client,
                Crashed(message=message),
                flow_run_id=flow_run.id,
            )
        except Abort:
            # Flow run already marked as failed
            pass
        except Exception:
            self.logger.exception(f"Failed to update state of flow run '{flow_run.id}'")
        else:
            if state.is_crashed():
                self.logger.info(
                    f"Reported flow run '{flow_run.id}' as crashed: {message}"
                )

    async def _schedule_task(self, __in_seconds: int, fn, *args, **kwargs):
        """
        Schedule a background task to start after some time.

        These tasks will be run immediately when the agent exits instead of waiting.

        The function may be async or sync. Async functions will be awaited.
        """

        async def wrapper(task_status):
            # If we are shutting down, do not sleep; otherwise sleep until the scheduled
            # time or shutdown
            if self.started:
                with anyio.CancelScope() as scope:
                    self.scheduled_task_scopes.add(scope)
                    task_status.started()
                    await anyio.sleep(__in_seconds)

                self.scheduled_task_scopes.remove(scope)
            else:
                task_status.started()

            result = fn(*args, **kwargs)
            if inspect.iscoroutine(result):
                await result

        await self.task_group.start(wrapper)

    # Context management ---------------------------------------------------------------

    async def start(self):
        self.started = True
        self.task_group = anyio.create_task_group()
        self.limiter = (
            anyio.CapacityLimiter(self.limit) if self.limit is not None else None
        )
        self.client = get_client()
        await self.client.__aenter__()
        await self.task_group.__aenter__()

    async def shutdown(self, *exc_info):
        self.started = False
        # We must cancel scheduled task scopes before closing the task group
        for scope in self.scheduled_task_scopes:
            scope.cancel()
        await self.task_group.__aexit__(*exc_info)
        await self.client.__aexit__(*exc_info)
        self.task_group = None
        self.client = None
        self.submitting_flow_run_ids.clear()
        self.cancelling_flow_run_ids.clear()
        self.scheduled_task_scopes.clear()
        self._work_queue_cache_expiration = None
        self._work_queue_cache = []

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc_info):
        await self.shutdown(*exc_info)
