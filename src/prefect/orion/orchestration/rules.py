import contextlib
import pendulum
import sqlalchemy as sa
from sqlalchemy import select
from typing import Optional

from prefect.orion.models import orm
from prefect.orion.orchestration import core_policy, global_policy
from prefect.orion.schemas import states


ALL_ORCHESTRATION_STATES = {*states.StateType, None}


class BaseOrchestrationRule(contextlib.AbstractAsyncContextManager):
    FROM_STATES = []
    TO_STATES = []

    def __init__(self, context, from_state, to_state):
        self.context = context
        self.from_state = from_state
        self.to_state = to_state
        self._invalid = None
        self._fizzled = None

    async def __aenter__(self):
        if await self.invalid():
            pass
        else:
            await self.before_transition()
            self.context["rule_signature"].append(self.__class__)
        return self.context

    async def __aexit__(self, exc_type, exc_value, traceback):
        if await self.invalid():
            pass
        elif await self.fizzled():
            await self.cleanup()
        else:
            await self.after_transition()
            self.context["finalization_signature"].append(self.__class__)

    async def before_transition(self):
        raise NotImplementedError

    async def after_transition(self):
        raise NotImplementedError

    async def cleanup(self):
        raise NotImplementedError

    async def invalid(self):
        if self._invalid is None:
            self._invalid = await self.invalid_transition()
        return self._invalid

    async def fizzled(self):
        if not await self.invalid() and self._fizzled is None:
            self._fizzled = False
        elif self._fizzled is None:
            self._fizzled = await self.invalid_transition()
        return self._fizzled

    async def invalid_transition(self):
        initial_state = (
            None
            if self.context["initial_state"] is None
            else self.context["initial_state"].type
        )
        proposed_state = (
            None
            if self.context["proposed_state"] is None
            else self.context["proposed_state"].type
        )
        return (self.from_state != initial_state) or (self.to_state != proposed_state)


class BaseUniversalRule(contextlib.AbstractAsyncContextManager):
    FROM_STATES = []
    TO_STATES = []

    def __init__(self, context, from_state, to_state):
        self.context = context
        self.from_state = from_state
        self.to_state = to_state

    async def __aenter__(self):
        await self.before_transition()
        self.context["rule_signature"].append(self.__class__)
        return self.context

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.after_transition()
        self.context["finalization_signature"].append(self.__class__)

    async def before_transition(self):
        raise NotImplementedError

    async def after_transition(self):
        raise NotImplementedError


@core_policy.register
class CacheRetrieval(BaseOrchestrationRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = [states.StateType.RUNNING]

    async def before_transition(self):
        context = self.context
        if context["proposed_state"].state_details.cache_key:
            # Check for cached states matching the cache key
            cached_state = await get_cached_task_run_state(
                context["session"], context["proposed_state"].state_details.cache_key
            )
            if cached_state:
                context["proposed_state"] = cached_state.as_state().copy()
                context["proposed_state"].name = "Cached"

    async def after_transition(self):
        pass

    async def cleanup(self):
        pass


@core_policy.register
class CacheInsertion(BaseOrchestrationRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = [states.StateType.COMPLETED]

    async def before_transition(self):
        pass

    async def after_transition(self):
        context = self.context
        if context["proposed_state"].state_details.cache_key:
            await cache_task_run_state(context["session"], context["validated_state"])

    async def cleanup(self):
        pass


@core_policy.register
class RetryPotentialFailures(BaseOrchestrationRule):
    FROM_STATES = [states.StateType.RUNNING]
    TO_STATES = [states.StateType.FAILED]

    async def before_transition(self):
        context = self.context
        if (
            context["run"].state.run_details.run_count
            <= context["run"].empirical_policy.max_retries
        ):
            context["proposed_state"] = states.AwaitingRetry(
                scheduled_time=pendulum.now("UTC").add(
                    seconds=context["run"].empirical_policy.retry_delay_seconds
                ),
                message=context["proposed_state"].message,
                data=context["proposed_state"].data,
            )

    async def after_transition(self):
        pass

    async def cleanup(self):
        pass


@global_policy.register
class UpdateRunDetails(BaseUniversalRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(self):
        context = self.context
        context["proposed_state"].run_details = states.update_run_details(
            from_state=context["initial_state"], to_state=context["proposed_state"]
        )

    async def after_transition(self):
        context = self.context
        if context["run"] is not None:
            context["run"].state = context["validated_state"]

    async def cleanup(self):
        pass


@global_policy.register
class UpdateStateDetails(BaseUniversalRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(self):
        context = self.context
        context["proposed_state"].state_details.flow_run_id = context["run"].flow_run_id
        context["proposed_state"].state_details.task_run_id = context["task_run_id"]

    async def after_transition(self):
        pass

    async def cleanup(self):
        pass


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


async def cache_task_run_state(
    session: sa.orm.Session, state: orm.TaskRunState
) -> None:
    # create the new task run state
    new_cache_item = orm.TaskRunStateCache(
        cache_key=state.state_details.cache_key,
        cache_expiration=state.state_details.cache_expiration,
        task_run_state_id=state.id,
    )
    session.add(new_cache_item)
    await session.flush()
