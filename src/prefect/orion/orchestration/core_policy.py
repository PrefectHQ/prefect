from typing import Optional

import pendulum
import sqlalchemy as sa
from sqlalchemy import select

from prefect.orion.models import orm
from prefect.orion.orchestration.policies import BaseOrchestrationPolicy
from prefect.orion.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    BaseOrchestrationRule,
    OrchestrationContext,
)
from prefect.orion.schemas import states


class CorePolicy(BaseOrchestrationPolicy):
    def priority():
        return [
            RetryPotentialFailures,
            CacheInsertion,
            CacheRetrieval,
            WaitIfScheduled,
        ]


class CacheRetrieval(BaseOrchestrationRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = [states.StateType.RUNNING]

    async def before_transition(
        self,
        initial_state: states.State,
        proposed_state: states.State,
        context: OrchestrationContext,
    ) -> None:
        session = context.session
        if proposed_state.state_details.cache_key:
            # Check for cached states matching the cache key
            cached_state = await get_cached_task_run_state(
                session, proposed_state.state_details.cache_key
            )
            if cached_state:
                new_state = cached_state.as_state().copy(reset_fields=True)
                new_state.name = "Cached"
                await self.reject_transition(
                    state=new_state, reason="Retrieved state from cache"
                )


class CacheInsertion(BaseOrchestrationRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = [states.StateType.COMPLETED]

    async def after_transition(
        self,
        initial_state: states.State,
        validated_state: states.State,
        context: OrchestrationContext,
    ) -> None:
        session = context.session
        if validated_state.state_details.cache_key:
            await cache_task_run_state(session, validated_state)


class RetryPotentialFailures(BaseOrchestrationRule):
    FROM_STATES = [states.StateType.RUNNING]
    TO_STATES = [states.StateType.FAILED]

    async def before_transition(
        self,
        initial_state: states.State,
        proposed_state: states.State,
        context: OrchestrationContext,
    ) -> None:
        run_details = context.run_details
        run_settings = context.run_settings
        if run_details.run_count <= run_settings.max_retries:
            retry_state = states.AwaitingRetry(
                scheduled_time=pendulum.now("UTC").add(
                    seconds=run_settings.retry_delay_seconds
                ),
                message=proposed_state.message,
                data=proposed_state.data,
            )
            await self.reject_transition(state=retry_state, reason="Retying")


class WaitIfScheduled(BaseOrchestrationRule):
    FROM_STATES = [states.StateType.SCHEDULED]
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        initial_state: states.State,
        proposed_state: states.State,
        context: OrchestrationContext,
    ) -> None:
        scheduled_time = pendulum.instance(initial_state.state_details.scheduled_time)
        delay_seconds = (scheduled_time - pendulum.now()).in_seconds()
        if delay_seconds > 0:
            await self.delay_transition(
                delay_seconds, reason="Scheduled time is in the future"
            )


async def get_cached_task_run_state(
    session: sa.orm.Session, cache_key: str
) -> Optional[orm.TaskRunState]:
    task_run_state_id = (
        select(orm.TaskRunStateCache.task_run_state_id)
        .filter(
            sa.and_(
                orm.TaskRunStateCache.cache_key == cache_key,
                sa.or_(
                    orm.TaskRunStateCache.cache_expiration.is_(None),
                    orm.TaskRunStateCache.cache_expiration > pendulum.now("utc"),
                ),
            ),
        )
        .order_by(orm.TaskRunStateCache.created.desc())
        .limit(1)
    ).scalar_subquery()
    query = select(orm.TaskRunState).filter(orm.TaskRunState.id == task_run_state_id)
    result = await session.execute(query)
    return result.scalar()


async def cache_task_run_state(session: sa.orm.Session, state: states.State) -> None:
    # create the new task run state
    new_cache_item = orm.TaskRunStateCache(
        cache_key=state.state_details.cache_key,
        cache_expiration=state.state_details.cache_expiration,
        task_run_state_id=state.id,
    )
    session.add(new_cache_item)
    await session.flush()
