"""
Orchestration logic that fires on state transitions.

`CoreFlowPolicy` and `CoreTaskPolicy` contain all default orchestration rules that Orion
enforces on a state transition.
"""

from typing import Optional

import pendulum
import sqlalchemy as sa
from sqlalchemy import select


from prefect.orion.orchestration.policies import BaseOrchestrationPolicy
from prefect.orion.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    TERMINAL_STATES,
    BaseOrchestrationRule,
    OrchestrationContext,
    TaskOrchestrationContext,
)
from prefect.orion.schemas import states
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


class CoreFlowPolicy(BaseOrchestrationPolicy):
    """
    Orchestration rules that run against flow-run-state transitions in priority order.
    """

    def priority():
        return [
            WaitForScheduledTime,
        ]


class CoreTaskPolicy(BaseOrchestrationPolicy):
    """
    Orchestration rules that run against task-run-state transitions in priority order.
    """

    def priority():
        return [
            CacheRetrieval,
            PreventTransitionsFromTerminalStates,
            WaitForScheduledTime,
            RetryPotentialFailures,
            RenameReruns,
            CacheInsertion,
        ]


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
            await context.session.flush()


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


class RetryPotentialFailures(BaseOrchestrationRule):
    """
    Rejects failed states and schedules a retry if the retry limit has not been reached.

    This rule rejects transitions into a failed state if `max_retries` has been
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
        if run_count <= run_settings.max_retries:
            retry_state = states.AwaitingRetry(
                scheduled_time=pendulum.now("UTC").add(
                    seconds=run_settings.retry_delay_seconds
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
