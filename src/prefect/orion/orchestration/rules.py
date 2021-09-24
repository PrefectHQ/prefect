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
    class Config:
        arbitrary_types_allowed = True

    initial_state: Optional[states.State]
    proposed_state: Optional[states.State]
    validated_state: Optional[states.State]
    session: Optional[Union[sa.orm.Session, sa.ext.asyncio.AsyncSession]]
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
    """
    An abstract base class used to implement a discrete piece of orchestration logic.

    An `OrchestrationRule` is a stateful context manager that directly governs a state
    transition. Complex orchestration is achieved by nesting multiple rules.
    Each rule runs against an `OrchestrationContext` that contains the transition
    details; this context is then passed to subsequent rules. The context can be
    modified by hooks that fire before and after a new state is validated and committed
    to the database. These hooks will fire as long as the state transition is
    considered "valid" and govern a transition by either modifying the proposed state
    before it is validated or by producing a side-effect.

    A state transition occurs whenever a Flow- or Task- run changes state, prompting
    Orion to decide whether or not this transition can proceed. The current state of
    the run is referred to as the "initial state", and the state a run is
    attempting to transition into is the "proposed state". Together, the initial state
    transitioning into the proposed state is the intended transition that is governed
    by these orchestration rules. After using rules to enter a runtime context, the
    `OrchestrationContext` will contain a proposed state that has been governed by
    each rule, and at that point can validate the proposed state and commit it to
    the database. The validated state will be set on the context as
    `context.validated_state`, and rules will call the `self.after_transition` hook
    upon exiting the managed context.

    Examples:

        Create a rule

        >>> class BasicRule(BaseOrchestrationRule):
        >>>     # allowed initial state types
        >>>     FROM_STATES = [StateType.RUNNING]
        >>>     # allowed proposed state types
        >>>     TO_STATES = [StateType.COMPLETED, StateType.FAILED]
        >>>
        >>>     async def before_transition(initial_state, proposed_state, ctx):
        >>>         # side effects and proposed state mutation can happen here
        >>>
        >>>     async def after_transition(initial_state, validated_state, ctx):
        >>>         # operations on states that have been validated can happen here
        >>>
        >>>     async def cleanup(intitial_state, validated_state, ctx):
        >>>         # reverts side effects generated by `before_transition` if necessary

        Use a rule

        >>> intended_transition = (StateType.RUNNING, StateType.COMPLETED)
        >>> async with BasicRule(context, *intended_transition):
        >>>     # context.proposed_state has been governed by BasicRule

        Use multiple rules

        >>> rules = [BasicRule, BasicRule]
        >>> intended_transition = (StateType.RUNNING, StateType.COMPLETED)
        >>> async with contextlib.AsyncExitStack() as stack:
        >>>     for rule in rules:
        >>>         stack.enter_async_context(rule(context, *intended_transition))
        >>>
        >>>     # context.proposed_state has been governed by all rules

    Attributes:
        FROM_STATES: list of valid initial state types this rule governs
        TO_STATES: list of valid proposed state types this rule governs
        context: the orchestration context
        from_state_type: the state type a run is currently in
        to_state_type: the proposed state type a run is transitioning into

    Args:
        context: A `FlowOrchestrationContext` or `TaskOrchestrationContext` that is
            passed between rules
        from_state_type: The state type of the initial state of a run, if this
            state type is not contained in `FROM_STATES`, no hooks will fire
        to_state_type: The state type of the proposed state before orchestration, if
            this state type is not contained in `TO_STATES`, no hooks will fire
    """

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
        """
        Enter an async runtime context governed by this rule.

        The `with` statement will bind a governed `OrchestrationContext` to the target
        specified by the `as` clause. If the transition proposed by the
        `OrchestrationContext` is considered invalid on entry, entering this context
        will do nothing. Otherwise, `self.before_transition` will fire.
        """

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
        """
        Exit the async runtime context governed by this rule.

        One of three outcomes can happen upon exiting this rule's context depending on
        the state of the rule. If the rule was found to be invalid on entry, nothing
        happens. If the rule was valid on entry and continues to be valid on exit,
        `self.after_transition` will fire. If the rule was valid on entry but invalid
        on exit, the rule will "fizzle" and `self.cleanup` will fire in order to revert
        any side-effects produced by `self.before_transition`.
        """

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
    ) -> None:
        """
        Implements a hook that can fire before a state is committed to the database.

        This hook may produce side-effects or mutate the proposed state of a
        transition using one of three methods: `self.reject_transition`,
        `self.delay_transition`, and `self.abort_transition`.

        NOTE: As currently implemented, the `before_transition` hook is not
        perfectly isolated from mutating the transition. It is a standard instance
        method that has access to `self`, and therefore `self.context`. This should
        never be modified directly. Furthermore, `context.run` is an ORM model, and
        mutating the run can also cause unintended writes to the database.

        Args:
            initial_state: The initial state of a transtion
            proposed_state: The proposed state of a transition
            context: A safe copy of the `OrchestrationContext`, with the exception of
                `context.run`, mutating this context will have no effect on the broader
                orchestration environment.

        Returns:
            None
        """

        pass

    async def after_transition(
        self,
        initial_state: Optional[states.State],
        validated_state: Optional[states.State],
        context: OrchestrationContext,
    ) -> None:
        """
        Implements a hook that can fire after a state is committed to the database.

        Args:
            initial_state: The initial state of a transtion
            validated_state: The governed state that has been committed to the database
            context: A safe copy of the `OrchestrationContext`, with the exception of
                `context.run`, mutating this context will have no effect on the broader
                orchestration environment.

        Returns:
            None
        """
        pass

    async def cleanup(
        self,
        initial_state: Optional[states.State],
        validated_state: Optional[states.State],
        context: OrchestrationContext,
    ) -> None:
        """
        Implements a hook that can fire after a state is committed to the database.

        The intended use of this method is to revert side-effects produced by
        `self.before_transition` when the transition is found to be invalid on exit.
        This allows multiple rules to be gracefully run in sequence, without logic that
        keeps track of all other rules that might govern a transition.

        Args:
            initial_state: The initial state of a transtion
            validated_state: The governed state that has been committed to the database
            context: A safe copy of the `OrchestrationContext`, with the exception of
                `context.run`, mutating this context will have no effect on the broader
                orchestration environment.

        Returns:
            None
        """
        pass

    async def invalid(self) -> bool:
        """
        Determines if a rule is invalid.

        Invalid rules do nothing and no hooks fire upon entering or exiting a governed
        context. Rules are invalid if the transition states types are not contained in
        `self.FROM_STATES` and `self.TO_STATES`, or if the context is proposing
        a transition that differs from the transition the rule was instantiated with.

        Returns:
            True if the rules in invalid, False otherwise.
        """
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
        """
        Determines if a rule is fizzled and side-effects need to be reverted.

        Rules are fizzled if the transitions were valid on entry (thus firing
        `self.before_transition`) but are invalid upon exiting the governed context,
        most likely caused by another rule mutating the transition.

        Returns:
            True if the rule is fizzled, False otherwise.
        """

        if self._invalid_on_entry:
            return False
        return await self.invalid_transition()

    async def invalid_transition(self) -> bool:
        """
        Determines if the transition proposed by the `OrchestrationContext` is invalid.

        If the `OrchestrationContext` is attempting to manage a transition with this
        rule that differs from the transition the rule was instantiated with, the
        transition is considered to be invalid. Depending on the context, this either
        renders the state of the rule "invalid" or "fizzled".

        Returns:
            True if the transition is invalid, False otherwise.
        """

        initial_state_type = self.context.initial_state_type
        proposed_state_type = self.context.proposed_state_type
        return (self.from_state_type != initial_state_type) or (
            self.to_state_type != proposed_state_type
        )

    async def reject_transition(self, state: states.State, reason: str):
        """
        Rejects a proposed transition before the transition is validated.

        This method will reject a proposed transition, mutating the proposed state to
        the provided `state`. A reason for rejecting the transition is also passed on
        to the `OrchestrationContext`. Rules that reject the transition will not fizzle,
        despite the proposed state type changing.

        Args:
            state: The new proposed state
            reason: The reason for rejecting the transition
        """

        # don't run if the transition is already validated
        if self.context.validated_state:
            raise RuntimeError("The transition is already validated")

        # a rule that mutates state should not fizzle itself
        self.to_state_type = state.type
        self.context.proposed_state = state
        self.context.response_status = SetStateStatus.REJECT
        self.context.response_details = StateRejectDetails(reason=reason)

    async def delay_transition(self, delay_seconds: int, reason: str):
        """
        Delays a proposed transition before the transition is validated.

        This method will delay a proposed transition, setting the proposed state to
        `None`, signaling to the `OrchestrationContext` that no state should be
        written to the database. The number of seconds a transition should be delayed is
        passed to the `OrchestrationContext`. A reason for delaying the transition is
        also provided.

        Args:
            delay_seconds: The number of seconds the transition should be delayed
            reason: The reason for delaying the transition
        """

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
        """
        Aborts a proposed transition before the transition is validated.

        This method will abort a proposed transition, expecting no further action to
        occur for this run. The proposed state is set to `None`, signaling to the
        `OrchestrationContext` that no state should be written to the database. A
        reason for aborting the transition is also provided.

        Args:
            reason: The reason for aborting the transition
        """

        # don't run if the transition is already validated
        if self.context.validated_state:
            raise RuntimeError("The transition is already validated")

        # a rule that mutates state should not fizzle itself
        self.to_state_type = None
        self.context.proposed_state = None
        self.context.response_status = SetStateStatus.ABORT
        self.context.response_details = StateAbortDetails(reason=reason)


class BaseUniversalRule(contextlib.AbstractAsyncContextManager):
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
        if not self.nullified_transition():
            await self.after_transition(self.context)
            self.context.finalization_signature.append(str(self.__class__))

    async def before_transition(self, context) -> None:
        pass

    async def after_transition(self, context) -> None:
        pass

    def nullified_transition(self) -> bool:
        return self.context.proposed_state is None
