"""
Orchestration logic that fires on state transitions.

`CoreFlowPolicy` and `CoreTaskPolicy` contain all default orchestration rules that Orion
enforces on a state transition.
"""

from typing import Optional

import pendulum
import sqlalchemy as sa
from packaging.version import Version
from sqlalchemy import select

from prefect.orion import models
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.exceptions import ObjectNotFoundError
from prefect.orion.models import concurrency_limits
from prefect.orion.orchestration.policies import BaseOrchestrationPolicy
from prefect.orion.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    TERMINAL_STATES,
    BaseOrchestrationRule,
    BaseUniversalTransform,
    FlowOrchestrationContext,
    OrchestrationContext,
    TaskOrchestrationContext,
)
from prefect.orion.schemas import filters, states
from prefect.orion.schemas.states import StateType


class CoreFlowPolicy(BaseOrchestrationPolicy):
    """
    Orchestration rules that run against flow-run-state transitions in priority order.
    """

    def priority():
        return [
            HandleFlowTerminalStateTransitions,
            PreventRedundantTransitions,
            CopyScheduledTime,
            WaitForScheduledTime,
            RetryFailedFlows,
        ]


class CoreTaskPolicy(BaseOrchestrationPolicy):
    """
    Orchestration rules that run against task-run-state transitions in priority order.
    """

    def priority():
        return [
            CacheRetrieval,
            HandleTaskTerminalStateTransitions,
            PreventRedundantTransitions,
            SecureTaskConcurrencySlots,  # retrieve cached states even if slots are full
            CopyScheduledTime,
            WaitForScheduledTime,
            RetryFailedTasks,
            RenameReruns,
            UpdateFlowRunTrackerOnTasks,
            CacheInsertion,
            ReleaseTaskConcurrencySlots,
        ]


class MinimalFlowPolicy(BaseOrchestrationPolicy):
    def priority():
        return []


class MinimalTaskPolicy(BaseOrchestrationPolicy):
    def priority():
        return [
            ReleaseTaskConcurrencySlots,  # always release concurrency slots
        ]


class SecureTaskConcurrencySlots(BaseOrchestrationRule):
    """
    Checks relevant concurrency slots are available before entering a Running state.

    This rule checks if concurrency limits have been set on the tags associated with a
    TaskRun. If so, a concurrency slot will be secured against each concurrency limit
    before being allowed to transition into a running state. If a concurrency limit has
    been reached, the client will be instructed to delay the transition for 30 seconds
    before trying again. If the concurrency limit set on a tag is 0, the transition will
    be aborted to prevent deadlocks.
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = [states.StateType.RUNNING]

    async def before_transition(
        self,
        initial_state: Optional[states.State],
        validated_state: Optional[states.State],
        context: TaskOrchestrationContext,
    ) -> None:

        self._applied_limits = []
        filtered_limits = (
            await concurrency_limits.filter_concurrency_limits_for_orchestration(
                context.session, tags=context.run.tags
            )
        )
        run_limits = {limit.tag: limit for limit in filtered_limits}
        for tag, cl in run_limits.items():

            limit = cl.concurrency_limit
            if limit == 0:
                # limits of 0 will deadlock, and the transition needs to abort
                for stale_tag in self._applied_limits:
                    stale_limit = run_limits.get(stale_tag, None)
                    active_slots = set(stale_limit.active_slots)
                    active_slots.discard(str(context.run.id))
                    stale_limit.active_slots = list(active_slots)

                await self.abort_transition(
                    reason=f'The concurrency limit on tag "{tag}" is 0 and will deadlock if the task tries to run again.',
                )
            elif len(cl.active_slots) >= limit:
                # if the limit has already been reached, delay the transition
                for stale_tag in self._applied_limits:
                    stale_limit = run_limits.get(stale_tag, None)
                    active_slots = set(stale_limit.active_slots)
                    active_slots.discard(str(context.run.id))
                    stale_limit.active_slots = list(active_slots)

                await self.delay_transition(
                    30,
                    f"Concurrency limit for the {tag} tag has been reached",
                )
            else:
                # log the TaskRun ID to active_slots
                self._applied_limits.append(tag)
                active_slots = set(cl.active_slots)
                active_slots.add(str(context.run.id))
                cl.active_slots = list(active_slots)

    async def cleanup(
        self,
        initial_state: Optional[states.State],
        validated_state: Optional[states.State],
        context: OrchestrationContext,
    ) -> None:
        for tag in self._applied_limits:
            cl = await concurrency_limits.read_concurrency_limit_by_tag(
                context.session, tag
            )
            active_slots = set(cl.active_slots)
            active_slots.discard(str(context.run.id))
            cl.active_slots = list(active_slots)


class ReleaseTaskConcurrencySlots(BaseUniversalTransform):
    """
    Releases any concurrency slots held by a run upon exiting a Running state.
    """

    async def after_transition(
        self,
        context: OrchestrationContext,
    ):
        if self.nullified_transition():
            return

        if not context.validated_state.is_running():
            filtered_limits = (
                await concurrency_limits.filter_concurrency_limits_for_orchestration(
                    context.session, tags=context.run.tags
                )
            )
            run_limits = {limit.tag: limit for limit in filtered_limits}
            for tag, cl in run_limits.items():
                active_slots = set(cl.active_slots)
                active_slots.discard(str(context.run.id))
                cl.active_slots = list(active_slots)


class CacheInsertion(BaseOrchestrationRule):
    """
    Caches completed states with cache keys after they are validated.
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = [states.StateType.COMPLETED]

    @inject_db
    async def after_transition(
        self,
        initial_state: Optional[states.State],
        validated_state: Optional[states.State],
        context: TaskOrchestrationContext,
        db: OrionDBInterface,
    ) -> None:
        if not validated_state or not context.session:
            return

        cache_key = validated_state.state_details.cache_key
        if cache_key:
            new_cache_item = db.TaskRunStateCache(
                cache_key=cache_key,
                cache_expiration=validated_state.state_details.cache_expiration,
                task_run_state_id=validated_state.id,
            )
            context.session.add(new_cache_item)


class CacheRetrieval(BaseOrchestrationRule):
    """
    Rejects running states if a completed state has been cached.

    This rule rejects transitions into a running state with a cache key if the key
    has already been associated with a completed state in the cache table. The client
    will be instructed to transition into the cached completed state instead.
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = [states.StateType.RUNNING]

    @inject_db
    async def before_transition(
        self,
        initial_state: Optional[states.State],
        proposed_state: Optional[states.State],
        context: TaskOrchestrationContext,
        db: OrionDBInterface,
    ) -> None:
        cache_key = proposed_state.state_details.cache_key
        if cache_key:
            # Check for cached states matching the cache key
            cached_state_id = (
                select(db.TaskRunStateCache.task_run_state_id)
                .where(
                    sa.and_(
                        db.TaskRunStateCache.cache_key == cache_key,
                        sa.or_(
                            db.TaskRunStateCache.cache_expiration.is_(None),
                            db.TaskRunStateCache.cache_expiration > pendulum.now("utc"),
                        ),
                    ),
                )
                .order_by(db.TaskRunStateCache.created.desc())
                .limit(1)
            ).scalar_subquery()
            query = select(db.TaskRunState).where(db.TaskRunState.id == cached_state_id)
            cached_state = (await context.session.execute(query)).scalar()
            if cached_state:
                new_state = cached_state.as_state().copy(reset_fields=True)
                new_state.name = "Cached"
                await self.reject_transition(
                    state=new_state, reason="Retrieved state from cache"
                )


class RetryFailedFlows(BaseOrchestrationRule):
    """
    Rejects failed states and schedules a retry if the retry limit has not been reached.

    This rule rejects transitions into a failed state if `retries` has been
    set and the run count has not reached the specified limit. The client will be
    instructed to transition into a scheduled state to retry flow execution.
    """

    FROM_STATES = [states.StateType.RUNNING]
    TO_STATES = [states.StateType.FAILED]

    async def before_transition(
        self,
        initial_state: Optional[states.State],
        proposed_state: Optional[states.State],
        context: FlowOrchestrationContext,
    ) -> None:
        run_settings = context.run_settings
        run_count = context.run.run_count

        if run_settings.retries is None or run_count > run_settings.retries:
            return  # Retry count exceeded, allow transition to failed

        scheduled_start_time = pendulum.now("UTC").add(
            seconds=run_settings.retry_delay or 0
        )

        # support old-style flow run retries for older clients
        # older flow retries require us to loop over failed tasks to update their state
        # this is not required after API version 0.8.3
        api_version = context.parameters.get("api-version", None)
        if api_version and api_version < Version("0.8.3"):
            failed_task_runs = await models.task_runs.read_task_runs(
                context.session,
                flow_run_filter=filters.FlowRunFilter(id={"any_": [context.run.id]}),
                task_run_filter=filters.TaskRunFilter(
                    state={"type": {"any_": ["FAILED"]}}
                ),
            )
            for run in failed_task_runs:
                await models.task_runs.set_task_run_state(
                    context.session,
                    run.id,
                    state=states.AwaitingRetry(scheduled_time=scheduled_start_time),
                    force=True,
                )
                # Reset the run count so that the task run retries still work correctly
                run.run_count = 0

        # Generate a new state for the flow
        retry_state = states.AwaitingRetry(
            scheduled_time=scheduled_start_time,
            message=proposed_state.message,
            data=proposed_state.data,
        )
        await self.reject_transition(state=retry_state, reason="Retrying")


class RetryFailedTasks(BaseOrchestrationRule):
    """
    Rejects failed states and schedules a retry if the retry limit has not been reached.

    This rule rejects transitions into a failed state if `retries` has been
    set and the run count has not reached the specified limit. The client will be
    instructed to transition into a scheduled state to retry task execution.
    """

    FROM_STATES = [states.StateType.RUNNING]
    TO_STATES = [states.StateType.FAILED]

    async def before_transition(
        self,
        initial_state: Optional[states.State],
        proposed_state: Optional[states.State],
        context: TaskOrchestrationContext,
    ) -> None:
        run_settings = context.run_settings
        run_count = context.run.run_count
        if run_settings.retries is not None and run_count <= run_settings.retries:
            retry_state = states.AwaitingRetry(
                scheduled_time=pendulum.now("UTC").add(
                    seconds=run_settings.retry_delay or 0
                ),
                message=proposed_state.message,
                data=proposed_state.data,
            )
            await self.reject_transition(state=retry_state, reason="Retrying")


class RenameReruns(BaseOrchestrationRule):
    """
    Name the states if they have run more than once.

    In the special case where the initial state is an "AwaitingRetry" scheduled state,
    the proposed state will be renamed to "Retrying" instead.
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = [states.StateType.RUNNING]

    async def before_transition(
        self,
        initial_state: Optional[states.State],
        proposed_state: Optional[states.State],
        context: TaskOrchestrationContext,
    ) -> None:
        run_count = context.run.run_count
        if run_count > 0:
            if initial_state.name == "AwaitingRetry":
                await self.rename_state("Retrying")
            else:
                await self.rename_state("Rerunning")


class CopyScheduledTime(BaseOrchestrationRule):
    """
    Ensures scheduled time is copied from scheduled states to pending states.

    If a new scheduled time has been proposed on the pending state, the scheduled time
    on the scheduled state will be ignored.
    """

    FROM_STATES = [states.StateType.SCHEDULED]
    TO_STATES = [states.StateType.PENDING]

    async def before_transition(
        self,
        initial_state: Optional[states.State],
        proposed_state: Optional[states.State],
        context: OrchestrationContext,
    ) -> None:
        if not proposed_state.state_details.scheduled_time:
            proposed_state.state_details.scheduled_time = (
                initial_state.state_details.scheduled_time
            )


class WaitForScheduledTime(BaseOrchestrationRule):
    """
    Prevents transitions to running states from happening to early.

    This rule enforces that all scheduled states will only start with the machine clock
    used by the Orion instance. This rule will identify transitions from scheduled
    states that are too early and nullify them. Instead, no state will be written to the
    database and the client will be sent an instruction to wait for `delay_seconds`
    before attempting the transition again.
    """

    FROM_STATES = [states.StateType.SCHEDULED, states.StateType.PENDING]
    TO_STATES = [states.StateType.RUNNING]

    async def before_transition(
        self,
        initial_state: Optional[states.State],
        proposed_state: Optional[states.State],
        context: OrchestrationContext,
    ) -> None:
        scheduled_time = initial_state.state_details.scheduled_time
        if not scheduled_time:
            return

        # At this moment, we take the floor of the actual delay as the API schema
        # specifies an integer return value.
        delay_seconds = (scheduled_time - pendulum.now()).in_seconds()
        if delay_seconds > 0:
            await self.delay_transition(
                delay_seconds, reason="Scheduled time is in the future"
            )


class UpdateFlowRunTrackerOnTasks(BaseOrchestrationRule):
    """
    Tracks the flow run attempt a task run state is associated with.
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = [states.StateType.RUNNING]

    async def after_transition(
        self,
        initial_state: Optional[states.State],
        proposed_state: Optional[states.State],
        context: TaskOrchestrationContext,
    ) -> None:
        self.flow_run = await context.flow_run()
        if self.flow_run:
            context.run.flow_run_run_count = self.flow_run.run_count
        else:
            raise ObjectNotFoundError(
                f"Unable to read flow run associated with task run: {context.run.id}, this flow run might have been deleted",
            )


class HandleTaskTerminalStateTransitions(BaseOrchestrationRule):
    """
    Prevents transitions from terminal states.

    Orchestration logic in Orion assumes that once runs enter a terminal state, no
    further action will be taken on them. This rule prevents unintended transitions out
    of terminal states and sents an instruction to the client to abort any execution.

    While rerunning a flow, the client will attempt to re-orchestrate tasks that may
    have previously failed. This rule will permit transitions back into a running state
    if the parent flow run is either currently restarting or retrying. The task run's
    run count will also be reset so task-level retries can still fire and tracking
    metadata is updated.
    """

    FROM_STATES = TERMINAL_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        initial_state: Optional[states.State],
        proposed_state: Optional[states.State],
        context: TaskOrchestrationContext,
    ) -> None:

        # permit rerunning a task if the flow is retrying
        if proposed_state.is_running() and (
            initial_state.is_failed()
            or initial_state.is_crashed()
            or initial_state.is_cancelled()
        ):
            self.original_run_count = context.run.run_count
            self.original_retry_attempt = context.run.flow_run_run_count

            self.flow_run = await context.flow_run()
            flow_retrying = context.run.flow_run_run_count < self.flow_run.run_count

            if flow_retrying:
                context.run.run_count = 0  # reset run count to preserve retry behavior
                await self.rename_state("Retrying")
                return

        await self.abort_transition(reason="This run has already terminated.")

    async def cleanup(
        self,
        initial_state: Optional[states.State],
        validated_state: Optional[states.State],
        context: OrchestrationContext,
    ):
        # reset run count
        context.run.run_count = self.original_run_count


class HandleFlowTerminalStateTransitions(BaseOrchestrationRule):
    """
    Prevents transitions from terminal states.

    Orchestration logic in Orion assumes that once runs enter a terminal state, no
    further action will be taken on them. This rule prevents unintended transitions out
    of terminal states and sents an instruction to the client to abort any execution.

    If the orchestrated flow run has an associated deployment, this rule will permit a
    transition back into a scheduled state as well as performing all necessary
    bookkeeping such as: tracking the number of times a flow run has been restarted and
    resetting the run count so flow-level retries can still fire.
    """

    FROM_STATES = TERMINAL_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        initial_state: Optional[states.State],
        proposed_state: Optional[states.State],
        context: FlowOrchestrationContext,
    ) -> None:

        # permit transitions into back into a scheduled state for manual retries
        if proposed_state.is_scheduled() and proposed_state.name == "AwaitingRetry":
            if not context.run.deployment_id:
                await self.abort_transition(
                    "Cannot restart a run without an associated deployment."
                )
        else:
            await self.abort_transition(reason="This run has already terminated.")


class PreventRedundantTransitions(BaseOrchestrationRule):
    """
    Prevents redundant transitions.

    Under normal operation, this rule prevents the "backwards" progress of a run. This
    rule will also help prevent multiple agents from attempting to orchestrate a run by
    preventing transitions into the same state type. If any of these disallowed
    transitions are attempted, this rule will abort the transition.
    """

    STATE_PROGRESS = {
        None: 0,
        StateType.SCHEDULED: 1,
        StateType.PENDING: 2,
        StateType.RUNNING: 3,
    }

    FROM_STATES = [StateType.SCHEDULED, StateType.PENDING, StateType.RUNNING, None]
    TO_STATES = [StateType.SCHEDULED, StateType.PENDING, StateType.RUNNING, None]

    async def before_transition(
        self,
        initial_state: Optional[states.State],
        proposed_state: Optional[states.State],
        context: OrchestrationContext,
    ) -> None:
        initial_state_type = initial_state.type if initial_state else None
        proposed_state_type = proposed_state.type if proposed_state else None
        if (
            self.STATE_PROGRESS[proposed_state_type]
            <= self.STATE_PROGRESS[initial_state_type]
        ):
            await self.abort_transition(
                reason=f"This run cannot transition to the {proposed_state_type} state from the {initial_state_type} state."
            )
