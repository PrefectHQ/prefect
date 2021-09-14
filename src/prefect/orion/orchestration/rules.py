import contextlib
from types import TracebackType
from typing import Iterable, List, Optional, Type, Union
from uuid import UUID

import sqlalchemy as sa

from pydantic import Field
from typing_extensions import Literal

from prefect.orion.models import orm
from prefect.orion.schemas import core, states
from prefect.orion.schemas.responses import (
    SetStateStatus,
    StateAbortDetails,
    StateAcceptDetails,
    StateRejectDetails,
    StateWaitDetails,
)
from prefect.orion.utilities.schemas import PrefectBaseModel

ALL_ORCHESTRATION_STATES = {*states.StateType, None}


StateResponseDetails = Union[StateAcceptDetails, StateWaitDetails, StateRejectDetails]


class OrchestrationResult(PrefectBaseModel):
    state: Optional[states.State]
    status: SetStateStatus
    details: StateResponseDetails


class OrchestrationContext(PrefectBaseModel):
    class Config:
        arbitrary_types_allowed = True

    initial_state: Optional[states.State]
    proposed_state: Optional[states.State]
    validated_state: Optional[states.State]
    session: Optional[Union[sa.orm.Session, sa.ext.asyncio.AsyncSession]]
    run: Optional[Union[core.TaskRun, core.FlowRun]]
    run_type: Optional[Literal["task_run", "flow_run"]]
    task_run_id: Optional[UUID]
    flow_run_id: Optional[UUID]
    rule_signature: List[str] = Field(default_factory=list)
    finalization_signature: List[str] = Field(default_factory=list)
    response_status: SetStateStatus = Field(default=SetStateStatus.ACCEPT)
    response_details: StateResponseDetails = Field(default_factory=StateAcceptDetails)

    @property
    def initial_state_type(self) -> Optional[states.StateType]:
        return self.initial_state.type if self.initial_state else None

    @property
    def proposed_state_type(self) -> Optional[states.StateType]:
        return self.proposed_state.type if self.proposed_state else None

    @property
    def validated_state_type(self) -> Optional[states.StateType]:
        return self.validated_state.type if self.validated_state else None

    @property
    def run_settings(self):
        return self.run.empirical_policy

    def safe_copy(self):
        safe_copy = self.copy()

        safe_copy.initial_state = (
            self.initial_state.copy() if self.initial_state else None
        )
        safe_copy.proposed_state = (
            self.proposed_state.copy() if self.proposed_state else None
        )
        safe_copy.validated_state = (
            self.validated_state.copy() if self.validated_state else None
        )
        safe_copy.run = self.run.copy()
        return safe_copy

    def entry_context(self):
        safe_context = self.safe_copy()
        return safe_context.initial_state, safe_context.proposed_state, safe_context

    def exit_context(self):
        safe_context = self.safe_copy()
        return safe_context.initial_state, safe_context.validated_state, safe_context


class TaskOrchestrationContext(OrchestrationContext):
    run_id: UUID

    def __init__(self, **data):
        super().__init__(**data)
        self.task_run_id = self.run_id
        self.flow_run_id = self.run.flow_run_id

    async def validate_proposed_state(self):
        if self.proposed_state is not None:
            validated_orm_state = orm.TaskRunState(
                task_run_id=self.task_run_id,
                **self.proposed_state.dict(shallow=True),
            )
            self.session.add(validated_orm_state)
        else:
            validated_orm_state = None
        validated_state = (
            validated_orm_state.as_state() if validated_orm_state else None
        )

        await self.session.flush()
        self.validated_state = validated_state

        return validated_orm_state

    async def orm_run(self):
        run = await self.session.get(orm.TaskRun, self.task_run_id)
        if not run:
            raise ValueError("Run not found.")
        return run


class FlowOrchestrationContext(OrchestrationContext):
    run_id: UUID

    def __init__(self, **data):
        super().__init__(**data)
        self.flow_run_id = self.run_id

    async def validate_proposed_state(self):
        if self.proposed_state is not None:
            validated_orm_state = orm.FlowRunState(
                flow_run_id=self.flow_run_id,
                **self.proposed_state.dict(shallow=True),
            )
            self.session.add(validated_orm_state)
        else:
            validated_orm_state = None
        validated_state = (
            validated_orm_state.as_state() if validated_orm_state else None
        )

        await self.session.flush()
        self.validated_state = validated_state

        return validated_orm_state

    async def orm_run(self):
        run = await self.session.get(orm.FlowRun, self.flow_run_id)
        if not run:
            raise ValueError("Run not found.")
        return run


class BaseOrchestrationRule(contextlib.AbstractAsyncContextManager):
    FROM_STATES: Iterable = []
    TO_STATES: Iterable = []

    def __init__(
        self,
        context: OrchestrationContext,
        from_state_type: states.StateType,
        to_state_type: states.StateType,
    ):
        self.context = context
        self.from_state_type = from_state_type
        self.to_state_type = to_state_type
        self._invalid_on_entry = None

    async def __aenter__(self) -> OrchestrationContext:
        if await self.invalid():
            pass
        else:
            entry_context = self.context.entry_context()
            await self.before_transition(*entry_context)
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
        pass

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
        # invalid and fizzled states are mutually exclusive,
        # `_invalid_on_entry` holds this statefulness
        if self.from_state_type not in self.FROM_STATES:
            self._invalid_on_entry = True
        if self.to_state_type not in self.TO_STATES:
            self._invalid_on_entry = True

        if self._invalid_on_entry is None:
            self._invalid_on_entry = await self.invalid_transition()
        return self._invalid_on_entry

    async def fizzled(self) -> bool:
        if self._invalid_on_entry:
            return False
        return await self.invalid_transition()

    async def invalid_transition(self) -> bool:
        initial_state_type = self.context.initial_state_type
        proposed_state_type = self.context.proposed_state_type
        return (self.from_state_type != initial_state_type) or (
            self.to_state_type != proposed_state_type
        )

    async def reject_transition(self, state: states.State, reason: str):
        # don't run if the transition is already validated
        if self.context.validated_state:
            raise RuntimeError("The transition is already validated")

        # a rule that mutates state should not fizzle itself
        self.to_state_type = state.type
        self.context.proposed_state = state
        self.context.response_status = SetStateStatus.REJECT
        self.context.response_details = StateRejectDetails(reason=reason)

    async def delay_transition(self, delay_seconds: int, reason: str):
        # don't run if the transition is already validated
        if self.context.validated_state:
            raise RuntimeError("The transition is already validated")

        # a rule that mutates state should not fizzle itself
        self.to_state_type = None
        self.context.proposed_state = None
        self.context.response_status = SetStateStatus.WAIT
        self.context.response_details = StateWaitDetails(
            delay_seconds=delay_seconds, reason=reason
        )

    async def abort_transition(self, reason: str):
        # don't run if the transition is already validated
        if self.context.validated_state:
            raise RuntimeError("The transition is already validated")

        # a rule that mutates state should not fizzle itself
        self.to_state_type = None
        self.context.proposed_state = None
        self.context.response_status = SetStateStatus.ABORT
        self.context.response_details = StateAbortDetails(reason=reason)


class BaseUniversalRule(contextlib.AbstractAsyncContextManager):
    FROM_STATES: Iterable = []
    TO_STATES: Iterable = []

    def __init__(
        self,
        context: OrchestrationContext,
        from_state_type: states.State,
        to_state_type: states.State,
    ):
        self.context = context

    async def __aenter__(self):
        await self.before_transition(self.context)
        self.context.rule_signature.append(str(self.__class__))
        return self.context

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.after_transition(self.context)
        self.context.finalization_signature.append(str(self.__class__))

    async def before_transition(self, context) -> None:
        pass

    async def after_transition(self, context) -> None:
        pass
