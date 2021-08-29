import contextlib
from types import TracebackType
from typing import Iterable, List, Optional, Type, Union
from uuid import UUID

import sqlalchemy as sa
from pydantic import Field

from prefect.orion.schemas import core, states
from prefect.orion.utilities.schemas import PrefectBaseModel

ALL_ORCHESTRATION_STATES = {*states.StateType, None}


class OrchestrationContext(PrefectBaseModel):
    class Config:
        arbitrary_types_allowed = True

    initial_state: Optional[states.State]
    proposed_state: states.State
    validated_state: Optional[states.State]
    session: Optional[Union[sa.orm.Session, sa.ext.asyncio.AsyncSession]]
    run: Optional[Union[core.TaskRun, core.FlowRun]]
    task_run_id: Optional[UUID]
    flow_run_id: Optional[UUID]
    rule_signature: List[str] = Field(default_factory=list)
    finalization_signature: List[str] = Field(default_factory=list)

    def __post_init__(self, **kwargs):
        if self.flow_run_id is None and self.run is not None:
            self.flow_run_id = self.run.flow_run_id

    @property
    def initial_state_type(self) -> Optional[states.StateType]:
        return None if self.initial_state is None else self.initial_state.type

    @property
    def proposed_state_type(self) -> Optional[states.StateType]:
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
        return self.initial_state, self.proposed_state, self.copy()

    def exit_context(self):
        return self.initial_state, self.validated_state, self.copy()


class BaseOrchestrationRule(contextlib.AbstractAsyncContextManager):
    FROM_STATES: Iterable = []
    TO_STATES: Iterable = []

    def __init__(
        self,
        context: OrchestrationContext,
        from_state: states.StateType,
        to_state: states.StateType,
    ):
        self.context = context
        self.from_state = from_state
        self.to_state = to_state
        self._not_fizzleable = None

    async def __aenter__(self) -> OrchestrationContext:
        if await self.invalid():
            pass
        else:
            entry_context = self.context.entry_context()
            proposed_state = await self.before_transition(*entry_context)
            await self.update_state(proposed_state)
            self.context.rule_signature.append(str(self.__class__))
        return self.context

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        exit_context = self.context.exit_context()
        if await self.invalid():
            pass
        elif await self.fizzled():
            await self.cleanup(*exit_context)
        else:
            await self.after_transition(*exit_context)
            self.context.finalization_signature.append(str(self.__class__))

    async def before_transition(
        self,
        initial_state: states.State,
        proposed_state: states.State,
        context: OrchestrationContext,
    ) -> states.State:
        return proposed_state

    async def after_transition(
        self,
        initial_state: states.State,
        validated_state: states.State,
        context: OrchestrationContext,
    ) -> None:
        pass

    async def cleanup(
        self,
        initial_state: states.State,
        validated_state: states.State,
        context: OrchestrationContext,
    ) -> None:
        pass

    async def invalid(self) -> bool:
        # invalid and fizzled states are mutually exclusive, `_not_fizzeable` holds this statefulness
        if self._not_fizzleable is None:
            self._not_fizzleable = await self.invalid_transition()
        return self._not_fizzleable

    async def fizzled(self) -> bool:
        if self._not_fizzleable:
            return False
        return await self.invalid_transition()

    async def invalid_transition(self) -> bool:
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

    async def update_state(self, proposed_state: states.State) -> None:
        # if a rule modifies the proposed state, it should not fizzle itself
        if self.context.proposed_state_type != proposed_state.type:
            self.to_state = proposed_state.type
        self.context.proposed_state = proposed_state


class BaseUniversalRule(contextlib.AbstractAsyncContextManager):
    FROM_STATES: Iterable = []
    TO_STATES: Iterable = []

    def __init__(
        self,
        context: OrchestrationContext,
        from_state: states.State,
        to_state: states.State,
    ):
        self.context = context
        self.from_state = from_state
        self.to_state = to_state

    async def __aenter__(self):
        entry_context = self.context.entry_context()
        proposed_state = await self.before_transition(*entry_context)
        self.context.proposed_state = proposed_state
        self.context.rule_signature.append(str(self.__class__))
        return self.context

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        exit_context = self.context.exit_context()
        await self.after_transition(*exit_context)
        self.context.finalization_signature.append(str(self.__class__))

    async def before_transition(
        self,
        initial_state: states.State,
        proposed_state: states.State,
        context: OrchestrationContext,
    ) -> states.State:
        return proposed_state

    async def after_transition(
        self,
        initial_state: states.State,
        validated_state: states.State,
        context: OrchestrationContext,
    ) -> None:
        pass
