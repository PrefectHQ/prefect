"""
Orchestration logic that fires on state transitions.

`CoreFlowPolicy` and `CoreTaskPolicy` contain all default orchestration rules that Orion
enforces on a state transition.
"""

from typing import Optional

import pendulum
import sqlalchemy as sa
from sqlalchemy import select

from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.models import concurrency_limits
from prefect.orion.orchestration.policies import BaseOrchestrationPolicy
from prefect.orion.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    TERMINAL_STATES,
    BaseOrchestrationRule,
    FlowOrchestrationContext,
    OrchestrationContext,
    TaskOrchestrationContext,
)
from prefect.orion.schemas import filters, states


class CoreFlowPolicy(BaseOrchestrationPolicy):
    """
    Orchestration rules that run against flow-run-state transitions in priority order.
    """

    def priority():
        return [
            PreventTransitionsFromTerminalStates,
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
            SecureTaskConcurrencySlots,  # retrieve cached states even if slots are full
            PreventTransitionsFromTerminalStates,
            WaitForScheduledTime,
            RetryFailedTasks,
            RenameReruns,
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


class ReleaseTaskConcurrencySlots(BaseOrchestrationRule):
    """
    Releases any concurrency slots held by a run upon exiting a Running state.
    """

    FROM_STATES = [states.StateType.RUNNING]
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def after_transition(
        self,
        initial_state: Optional[states.State],
        validated_state: Optional[states.State],
        context: TaskOrchestrationContext,
    ) -> None:

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
        from prefect.orion.models import task_runs

        run_settings = context.run_settings
        run_count = context.run.run_count
        if run_settings.retries is None or run_count > run_settings.retries:
            return  # Retry count exceeded, allow transition to failed

        scheduled_start_time = pendulum.now("UTC").add(
            seconds=run_settings.retry_delay or 0
        )

        failed_task_runs = await task_runs.read_task_runs(
            context.session,
            flow_run_filter=filters.FlowRunFilter(id={"any_": [context.run.id]}),
            task_run_filter=filters.TaskRunFilter(state={"type": {"any_": ["FAILED"]}}),
        )
        for run in failed_task_runs:
            await task_runs.set_task_run_state(
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


class WaitForScheduledTime(BaseOrchestrationRule):
    """
    Prevents transitions from scheduled states that happen too early.

    This rule enforces that all scheduled states will only start with the machine clock
    used by the Orion instance. This rule will identify transitions from scheduled
    states that are too early and nullify them. Instead, no state will be written to the
    database and the client will be sent an instruction to wait for `delay_seconds`
    before attempting the transition again.
    """

    FROM_STATES = [states.StateType.SCHEDULED]
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        initial_state: Optional[states.State],
        proposed_state: Optional[states.State],
        context: OrchestrationContext,
    ) -> None:
        scheduled_time = initial_state.state_details.scheduled_time
        if not scheduled_time:
            raise ValueError("Received state without a scheduled time")

        # At this moment, we take the floor of the actual delay as the API schema
        # specifies an integer return value.
        delay_seconds = (scheduled_time - pendulum.now()).in_seconds()
        if delay_seconds > 0:
            await self.delay_transition(
                delay_seconds, reason="Scheduled time is in the future"
            )


class PreventTransitionsFromTerminalStates(BaseOrchestrationRule):
    """
    Prevents transitions from terminal states.

    Orchestration logic in Orion assumes that once runs enter a terminal state, no
    further action will be taken on them. This rule prevents unintended transitions out
    of terminal states and sents an instruction to the client to abort any execution.
    """

    FROM_STATES = TERMINAL_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        initial_state: Optional[states.State],
        proposed_state: Optional[states.State],
        context: OrchestrationContext,
    ) -> None:
        await self.abort_transition(reason="This run has already terminated.")
