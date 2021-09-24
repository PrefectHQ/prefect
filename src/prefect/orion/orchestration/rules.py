import contextlib
from types import TracebackType
from typing import Dict, Iterable, List, Optional, Type, Union

import sqlalchemy as sa

from pydantic import Field

from prefect.orion.models import orm
from prefect.orion.schemas import states
from prefect.orion.schemas.responses import (
    SetStateStatus,
    StateAbortDetails,
    StateAcceptDetails,
    StateRejectDetails,
    StateWaitDetails,
)
from prefect.orion.utilities.schemas import PrefectBaseModel

ALL_ORCHESTRATION_STATES = {*states.StateType, None}
TERMINAL_STATES = states.TERMINAL_STATES


StateResponseDetails = Union[
    StateAcceptDetails, StateWaitDetails, StateRejectDetails, StateAbortDetails
]


class OrchestrationResult(PrefectBaseModel):
    state: Optional[states.State]
    status: SetStateStatus
    details: StateResponseDetails


class OrchestrationContext(PrefectBaseModel):
    """
    A container for a state transition, governed by orchestration rules.

    NOTE: An `OrchestrationContext` should not be instantiated directly, instead
    use the Flow- or Task- specific subclasses, `FlowOrchestrationContext` and
    `TaskOrchestrationContext`.

    When a Flow- or Task- run attempts to change state, Orion has an opportunity
    to decide whether this transition can proceed. All the relevant information
    associated with the state transition is stored in an `OrchestrationContext`,
    which is subsequently governed by nested orchestration rules implemented using
    the `BaseOrchestrationRule` ABC.

    `OrchestrationContext` introduces the concept of a state being `None` in the
    context of an intended state transition. An initial state can be `None` if a run
    is is attempting to set a state for the first time. The proposed state might be
    `None` if a rule governing the transition determines that no state change
    should occur at all and nothing is written to the database.

    Attributes:
        session: a SQLAlchemy database session
        initial_state: the initial state of a run
        proposed_state: the proposed state a run is transitioning into
        validated_state: a proposed state that has committed to the database
        rule_signature: a record of rules that have fired on entry into a
            managed context, currently only used for debugging purposes
        finalization_signature: a record of rules that have fired on exit from a
            managed context, currently only used for debugging purposes
        response_status: a SetStateStatus object used to build the API response
        response_details:a StateResponseDetails object use to build the API response

    Args:
        session: a SQLAlchemy database session
        initial_state: the initial state of a run
        proposed_state: the proposed state a run is transitioning into
    """

    class Config:
        arbitrary_types_allowed = True

    session: Optional[Union[sa.orm.Session, sa.ext.asyncio.AsyncSession]] = ...
    initial_state: Optional[states.State] = ...
    proposed_state: Optional[states.State] = ...
    validated_state: Optional[states.State]
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
        return safe_copy

    def entry_context(self):
        safe_context = self.safe_copy()
        return safe_context.initial_state, safe_context.proposed_state, safe_context

    def exit_context(self):
        safe_context = self.safe_copy()
        return safe_context.initial_state, safe_context.validated_state, safe_context


class TaskOrchestrationContext(OrchestrationContext):
    run: orm.TaskRun

    async def validate_proposed_state(self) -> orm.TaskRunState:
        if self.proposed_state is not None:
            validated_orm_state = orm.TaskRunState(
                task_run_id=self.run.id,
                **self.proposed_state.dict(shallow=True),
            )
            self.session.add(validated_orm_state)
            self.run.set_state(validated_orm_state)
        else:
            validated_orm_state = None
        validated_state = (
            validated_orm_state.as_state() if validated_orm_state else None
        )

        await self.session.flush()
        self.validated_state = validated_state

        return validated_orm_state

    @property
    def run_settings(self) -> Dict:
        return self.run.empirical_policy


class FlowOrchestrationContext(OrchestrationContext):
    run: orm.FlowRun

    async def validate_proposed_state(self) -> orm.FlowRunState:
        if self.proposed_state is not None:
            validated_orm_state = orm.FlowRunState(
                flow_run_id=self.run.id,
                **self.proposed_state.dict(shallow=True),
            )
            self.session.add(validated_orm_state)
            self.run.set_state(validated_orm_state)
        else:
            validated_orm_state = None
        validated_state = (
            validated_orm_state.as_state() if validated_orm_state else None
        )

        await self.session.flush()
        self.validated_state = validated_state

        return validated_orm_state

    @property
    def run_settings(self) -> Dict:
        return self.run.empirical_policy


class BaseOrchestrationRule(contextlib.AbstractAsyncContextManager):
    FROM_STATES: Iterable = []
    TO_STATES: Iterable = []

    def __init__(
        self,
        context: OrchestrationContext,
        from_state_type: Optional[states.StateType],
        to_state_type: Optional[states.StateType],
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
        initial_state: Optional[states.State],
        proposed_state: Optional[states.State],
        context: OrchestrationContext,
    ) -> states.State:
        pass

    async def after_transition(
        self,
        initial_state: Optional[states.State],
        validated_state: Optional[states.State],
        context: OrchestrationContext,
    ) -> None:
        pass

    async def cleanup(
        self,
        initial_state: Optional[states.State],
        validated_state: Optional[states.State],
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
    """
    An abstract base class used to implement privileged bookkeeping logic.

    NOTE: In almost all cases, use the `BaseOrchestrationRule` base class instead.

    Beyond the orchestration rules implemented with the `BaseOrchestrationRule` ABC,
    Universal rules are not stateful, and fire their before- and after- transition hooks
    on every state transition unless the proposed state is `None`, indicating that no
    state should be written to the database. Because there are no guardrails in place
    to prevent directly mutating state or other parts of the orchestration context,
    universal rules should only be used with care.

    Attributes:
        FROM_STATES: list of valid initial state types this rule governs
        TO_STATES: list of valid proposed state types this rule governs
        context: the orchestration context

    Args:
        context: A `FlowOrchestrationContext` or `TaskOrchestrationContext` that is
            passed between rules
        from_state_type: The state type of the initial state of a run
        to_state_type: The state type of the proposed state before orchestration
    """

    FROM_STATES: Iterable = ALL_ORCHESTRATION_STATES
    TO_STATES: Iterable = ALL_ORCHESTRATION_STATES

    def __init__(
        self,
        context: OrchestrationContext,
        from_state_type: Optional[states.StateType],
        to_state_type: Optional[states.StateType],
    ):
        self.context = context

    async def __aenter__(self):
        """
        Enter an async runtime context governed by this rule.

        The `with` statement will bind a governed `OrchestrationContext` to the target
        specified by the `as` clause. If the transition proposed by the
        `OrchestrationContext` has been nullified on entry and `context.proposed_state`
        is `None`, entering this context will do nothing. Otherwise
        `self.before_transition` will fire.
        """

        if not self.nullified_transition():
            await self.before_transition(self.context)
            self.context.rule_signature.append(str(self.__class__))
        return self.context

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """
        Exit the async runtime context governed by this rule.

        If the transition has been nullified upon exiting this rule's context, nothing
        happens. Otherwise, `self.after_transition` will fire on every non-null
        proposed_state.
        """

        if not self.nullified_transition():
            await self.after_transition(self.context)
            self.context.finalization_signature.append(str(self.__class__))

    async def before_transition(self, context) -> None:
        """
        Implements a hook that fires before a state is committed to the database.

        Args:
            context: the `OrchestrationContext` that contains transition details

        Returns:
            None
        """

        pass

    async def after_transition(self, context) -> None:
        """
        Implements a hook that can fire after a state is committed to the database.

        Args:
            context: the `OrchestrationContext` that contains transition details

        Returns:
            None
        """

        pass

    def nullified_transition(self) -> bool:
        """
        Determines if the transition has been nullified.

        Transitions are nullified if the proposed state is `None`, indicating that
        nothing should be written to the database.

        Returns:
            True if the transition is nullified, False otherwise.
        """

        return self.context.proposed_state is None
