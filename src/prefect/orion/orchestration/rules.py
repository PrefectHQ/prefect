import contextlib
import pendulum
import sqlalchemy as sa
from pydantic import Field
from sqlalchemy import select
from typing import Optional, Any
from uuid import UUID

from prefect.orion.models import orm
from prefect.orion.orchestration import core_policy, global_policy
from prefect.orion.schemas import states
from prefect.orion.utilities.schemas import PrefectBaseModel

ALL_ORCHESTRATION_STATES = {*states.StateType, None}


class OrchestrationContext(PrefectBaseModel):
    initial_state: Optional[states.State]
    proposed_state: states.State
    validated_state: Optional[states.State]
    session: Any  # no validator for sa.orm.Session
    run: Any  # Optional[schemas.core.TaskRun] doesn't work for some reason
    task_run_id: UUID
    rule_signature: list[str] = Field(default_factory=list)
    finalization_signature: list[str] = Field(default_factory=list)

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
    def run_settings(self):
        return self.run.empirical_policy

    def entry_context(self):
        return {
            "initial_state": self.initial_state,
            "initial_state_type": self.initial_state_type,
            "proposed_state": self.proposed_state,
            "proposed_state_type": self.proposed_state_type,
            "session": self.session,
            "run_details": self.run_details,
            "run_settings": self.run_settings,
        }

    def exit_context(self):
        return {
            "initial_state": self.initial_state,
            "initial_state_type": self.initial_state_type,
            "proposed_state": self.proposed_state,
            "proposed_state_type": self.proposed_state_type,
            "session": self.session,
            "validated_state": self.validated_state,
            "run_details": self.run_details,
            "run_settings": self.run_settings,
        }

    def global_entry_context(self):
        ctx = self.entry_context()
        ctx.update({"run": self.run})
        ctx.update({"task_run_id": self.task_run_id})
        return ctx

    def global_exit_context(self):
        ctx = self.exit_context()
        ctx.update({"run": self.run})
        ctx.update({"task_run_id": self.task_run_id})
        return ctx

    def update(self, update_dict):
        for k, v in update_dict.items():
            try:
                self.__setattr__(k, v)
            except ValueError:
                pass


class BaseOrchestrationRule(contextlib.AbstractAsyncContextManager):
    FROM_STATES = []
    TO_STATES = []

    def __init__(self, context: OrchestrationContext, from_state, to_state):
        self.context = context
        self.from_state = from_state
        self.to_state = to_state
        self._invalid = None
        self._fizzled = None

    async def __aenter__(self):
        if await self.invalid():
            pass
        else:
            entry_context = self.context.entry_context()
            proposed_state = await self.before_transition(entry_context)
            await self.update_state(proposed_state)
            self.context.rule_signature.append(self.__class__)
        return self.context

    async def __aexit__(self, exc_type, exc_value, traceback):
        exit_context = self.context.exit_context()
        if await self.invalid():
            pass
        elif await self.fizzled():
            await self.cleanup(**exit_context)
        else:
            await self.after_transition(exit_context)
            self.context.finalization_signature.append(self.__class__)

    async def before_transition(self, entry_context) -> states.State:
        raise NotImplementedError

    async def after_transition(self, exit_context) -> None:
        raise NotImplementedError

    async def cleanup(self, exit_context) -> None:
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
            if self.context.initial_state is None
            else self.context.initial_state.type
        )
        proposed_state = (
            None
            if self.context.proposed_state is None
            else self.context.proposed_state.type
        )
        return (self.from_state != initial_state) or (self.to_state != proposed_state)

    async def update_state(self, proposed_state):
        # if the rule modified the proposed state, it should not fizzle
        if self.context.proposed_state_type != proposed_state.type:
            self.to_state = proposed_state.type
        self.context.update({"proposed_state": proposed_state})


class BaseUniversalRule(contextlib.AbstractAsyncContextManager):
    FROM_STATES = []
    TO_STATES = []

    def __init__(self, context, from_state, to_state):
        self.context = context
        self.from_state = from_state
        self.to_state = to_state

    async def __aenter__(self):
        global_entry_context = self.context.global_entry_context()
        context_update = await self.before_transition(global_entry_context)
        self.context.update(context_update)
        self.context.rule_signature.append(self.__class__)
        return self.context

    async def __aexit__(self, exc_type, exc_value, traceback):
        global_exit_context = self.context.global_exit_context()
        context_update = await self.after_transition(global_exit_context)
        self.context.update(context_update)
        self.context.finalization_signature.append(self.__class__)

    async def before_transition(self):
        raise NotImplementedError

    async def after_transition(self, exc_type, exc_value, traceback):
        raise NotImplementedError


@core_policy.register
class CacheRetrieval(BaseOrchestrationRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = [states.StateType.RUNNING]

    async def before_transition(self, entry_context):
        proposed_state = entry_context["proposed_state"]
        session = entry_context["session"]
        if proposed_state.state_details.cache_key:
            # Check for cached states matching the cache key
            cached_state = await get_cached_task_run_state(
                session, proposed_state.state_details.cache_key
            )
            if cached_state:
                proposed_state = cached_state.as_state().copy()
                proposed_state.name = "Cached"
        return proposed_state

    async def after_transition(self, exit_context):
        pass

    async def cleanup(self, exit_context):
        pass


@core_policy.register
class CacheInsertion(BaseOrchestrationRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = [states.StateType.COMPLETED]

    async def before_transition(self, entry_context):
        proposed_state = entry_context["proposed_state"]
        return proposed_state

    async def after_transition(self, exit_context):
        proposed_state = exit_context["proposed_state"]
        validated_state = exit_context["validated_state"]
        session = exit_context["session"]
        if proposed_state.state_details.cache_key:
            await cache_task_run_state(session, validated_state)

    async def cleanup(self, exit_context):
        pass


@core_policy.register
class RetryPotentialFailures(BaseOrchestrationRule):
    FROM_STATES = [states.StateType.RUNNING]
    TO_STATES = [states.StateType.FAILED]

    async def before_transition(self, entry_context):
        proposed_state = entry_context["proposed_state"]
        run_details = entry_context["run_details"]
        run_settings = entry_context["run_settings"]
        if run_details.run_count <= run_settings.max_retries:
            proposed_state = states.AwaitingRetry(
                scheduled_time=pendulum.now("UTC").add(
                    seconds=run_settings.retry_delay_seconds
                ),
                message=proposed_state.message,
                data=proposed_state.data,
            )
        return proposed_state

    async def after_transition(self, exit_context):
        pass

    async def cleanup(self, exit_context):
        pass


@global_policy.register
class UpdateRunDetails(BaseUniversalRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(self, entry_context):
        entry_context["proposed_state"].run_details = states.update_run_details(
            from_state=entry_context["initial_state"],
            to_state=entry_context["proposed_state"],
        )
        return entry_context

    async def after_transition(self, exit_context):
        if exit_context["run"] is not None:
            exit_context["run"].state = exit_context["validated_state"]
        return exit_context


@global_policy.register
class UpdateStateDetails(BaseUniversalRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(self, entry_context):
        entry_context["proposed_state"].state_details.flow_run_id = entry_context[
            "run"
        ].flow_run_id
        entry_context["proposed_state"].state_details.task_run_id = entry_context[
            "task_run_id"
        ]
        return entry_context

    async def after_transition(self, exit_context):
        return exit_context


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
