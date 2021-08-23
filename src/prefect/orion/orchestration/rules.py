import contextlib
import pendulum
import sqlalchemy as sa
from pydantic import Field
from sqlalchemy import select
from typing import Optional, Any, List
from uuid import UUID

from prefect.orion.models import orm
from prefect.orion.orchestration import core_policy, global_policy
from prefect.orion.schemas import states, core
from prefect.orion.models import orm
from prefect.orion.utilities.schemas import PrefectBaseModel

ALL_ORCHESTRATION_STATES = {*states.StateType, None}


class OrchestrationContext(PrefectBaseModel):
    initial_state: Optional[states.State]
    proposed_state: states.State
    validated_state: Optional[states.State]
    session: Any  # no validator for sa.orm.Session
    run: Optional[core.TaskRun]
    task_run_id: UUID
    rule_signature: List[str] = Field(default_factory=list)
    finalization_signature: List[str] = Field(default_factory=list)

    @property
    def initial_state_type(self):
        return None if self.initial_state is None else self.initial_state.type

    @property
    def proposed_state_type(self):
        return self.proposed_state.type

    @property
    def run_details(self):
        try:
            return self.run.state.run_details
        except AttributeError:
            return None

    @property
    def flow_run_id(self):
        self.run.flow_run_id

    @property
    def run_settings(self):
        return self.run.empirical_policy

    def entry_context(self):
        return (
            self.initial_state,
            self.proposed_state,
            {
                "initial_state_type": self.initial_state_type,
                "proposed_state_type": self.proposed_state_type,
                "session": self.session,
                "run": self.run,
                "run_details": self.run_details,
                "run_settings": self.run_settings,
                "task_run_id": self.task_run_id,
                "flow_run_id": self.flow_run_id,
            },
        )

    def exit_context(self):
        return (
            self.initial_state,
            self.validated_state,
            {
                "initial_state_type": self.initial_state_type,
                "validated_state_type": self.proposed_state_type,
                "session": self.session,
                "run": self.run,
                "run_details": self.run_details,
                "run_settings": self.run_settings,
                "task_run_id": self.task_run_id,
                "flow_run_id": self.flow_run_id,
            },
        )


class BaseOrchestrationRule(contextlib.AbstractAsyncContextManager):
    FROM_STATES = []
    TO_STATES = []

    def __init__(self, context: OrchestrationContext, from_state, to_state):
        self.context = context
        self.from_state = from_state
        self.to_state = to_state
        self._not_fizzleable = None

    async def __aenter__(self):
        if await self.invalid():
            pass
        else:
            entry_context = self.context.entry_context()
            proposed_state = await self.before_transition(*entry_context)
            await self.update_state(proposed_state)
            self.context.rule_signature.append(self.__class__)
        return self.context

    async def __aexit__(self, exc_type, exc_value, traceback):
        exit_context = self.context.exit_context()
        if await self.invalid():
            pass
        elif await self.fizzled():
            await self.cleanup(*exit_context)
        else:
            await self.after_transition(*exit_context)
            self.context.finalization_signature.append(self.__class__)

    async def before_transition(
        self, initial_state, proposed_state, context
    ) -> states.State:
        return proposed_state

    async def after_transition(self, initial_state, validated_state, context) -> None:
        pass

    async def cleanup(self, initial_state, validated_state, context) -> None:
        pass

    async def invalid(self):
        if self._not_fizzleable is None:
            self._not_fizzleable = await self.invalid_transition()
        return self._not_fizzleable

    async def fizzled(self):
        if self._not_fizzleable:
            return False
        return await self.invalid_transition()

    async def invalid_transition(self):
        initial_state_type = (
            None
            if self.context.initial_state is None
            else self.context.initial_state.type
        )
        proposed_state_type = (
            None
            if self.context.proposed_state is None
            else self.context.proposed_state.type
        )
        return (self.from_state != initial_state_type) or (
            self.to_state != proposed_state_type
        )

    async def update_state(self, proposed_state):
        # if a rule modifies the proposed state, it should not fizzle itself
        if self.context.proposed_state_type != proposed_state.type:
            self.to_state = proposed_state.type
        self.context.proposed_state = proposed_state


class BaseUniversalRule(contextlib.AbstractAsyncContextManager):
    FROM_STATES = []
    TO_STATES = []

    def __init__(self, context, from_state, to_state):
        self.context = context
        self.from_state = from_state
        self.to_state = to_state

    async def __aenter__(self):
        entry_context = self.context.entry_context()
        proposed_state = await self.before_transition(*entry_context)
        self.context.proposed_state = proposed_state
        self.context.rule_signature.append(self.__class__)
        return self.context

    async def __aexit__(self, exc_type, exc_value, traceback):
        exit_context = self.context.exit_context()
        await self.after_transition(*exit_context)
        self.context.finalization_signature.append(self.__class__)

    async def before_transition(self, initial_state, proposed_state, context):
        return proposed_state

    async def after_transition(self, initial_state, validated_state, context):
        pass


@core_policy.register
class CacheRetrieval(BaseOrchestrationRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = [states.StateType.RUNNING]

    async def before_transition(self, initial_state, proposed_state, context):
        session = context["session"]
        if proposed_state.state_details.cache_key:
            # Check for cached states matching the cache key
            cached_state = await get_cached_task_run_state(
                session, proposed_state.state_details.cache_key
            )
            if cached_state:
                proposed_state = cached_state.as_state().copy()
                proposed_state.name = "Cached"
        return proposed_state


@core_policy.register
class CacheInsertion(BaseOrchestrationRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = [states.StateType.COMPLETED]

    async def before_transition(self, initial_state, proposed_state, context):
        return proposed_state

    async def after_transition(self, initial_state, validated_state, context):
        session = context["session"]
        if validated_state.state_details.cache_key:
            await cache_task_run_state(session, validated_state)


@core_policy.register
class RetryPotentialFailures(BaseOrchestrationRule):
    FROM_STATES = [states.StateType.RUNNING]
    TO_STATES = [states.StateType.FAILED]

    async def before_transition(self, initial_state, proposed_state, context):
        run_details = context["run_details"]
        run_settings = context["run_settings"]
        if run_details.run_count <= run_settings.max_retries:
            proposed_state = states.AwaitingRetry(
                scheduled_time=pendulum.now("UTC").add(
                    seconds=run_settings.retry_delay_seconds
                ),
                message=proposed_state.message,
                data=proposed_state.data,
            )
        return proposed_state


@global_policy.register
class UpdateRunDetails(BaseUniversalRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(self, initial_state, proposed_state, context):
        proposed_state.run_details = states.update_run_details(
            from_state=initial_state,
            to_state=proposed_state,
        )
        return proposed_state


@global_policy.register
class UpdateStateDetails(BaseUniversalRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(self, initial_state, proposed_state, context):
        proposed_state.state_details.flow_run_id = context["flow_run_id"]
        proposed_state.state_details.task_run_id = context["task_run_id"]
        return proposed_state


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
