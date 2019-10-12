"""
State is the main currency in the Prefect platform. It is used to represent the current
status of a flow or task.

This module contains all Prefect state classes, all ultimately inheriting from the base State class as follows:

![diagram of state inheritances](/state_inheritance_diagram.svg){.viz-padded}

Every run is initialized with the `Pending` state, meaning that it is waiting for
execution. During execution a run will enter a `Running` state. Finally, runs become `Finished`.
"""
import datetime
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union

import pendulum

import prefect
from prefect.engine.result import NoResult, Result, ResultInterface, SafeResult
from prefect.engine.result_handlers import ResultHandler


class State:
    """
    Base state class implementing the basic helper methods for checking state.

    **Note:** Each state-checking method (e.g., `is_failed()`) will also return `True`
    for all _subclasses_ of the parent state.  So, for example:
    ```python
    my_state = TriggerFailed()
    my_state.is_failed() # returns True

    another_state = Retrying()
    another_state.is_pending() # returns True
    ```

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#696969"

    def __init__(
        self,
        message: str = None,
        result: Any = NoResult,
        context: Dict[str, Any] = None,
    ):
        self.message = message
        self.result = result
        self.context = context or dict()
        if "task_tags" in prefect.context:
            self.context.setdefault("tags", list(prefect.context.task_tags))

    def __repr__(self) -> str:
        return '<{}: "{}">'.format(type(self).__name__, self.message)

    def __eq__(self, other: object) -> bool:
        """
        Equality depends on state type and data, but not message or context
        """
        if type(self) == type(other):
            assert isinstance(other, State)  # this assertion is here for MyPy only
            eq = self._result.value == other._result.value  # type: ignore
            for attr in self.__dict__:
                if attr.startswith("_") or attr in ["context", "message", "result"]:
                    continue
                eq &= getattr(self, attr, object()) == getattr(other, attr, object())
            return eq
        return False

    def __hash__(self) -> int:
        return id(self)

    @property
    def result(self) -> Any:
        return self._result.value  # type: ignore

    @result.setter
    def result(self, value: Any) -> None:
        if isinstance(value, ResultInterface):
            self._result = value
        else:
            self._result = Result(value=value)

    def is_pending(self) -> bool:
        """
        Checks if the state is currently in a pending state

        Returns:
            - bool: `True` if the state is pending, `False` otherwise
        """

        return isinstance(self, Pending)

    def is_queued(self) -> bool:
        """
        Checks if the state is currently in a queued state

        Returns:
            - bool: `True` if the state is queued, `False` otherwise
        """

        return isinstance(self, Queued)

    def is_retrying(self) -> bool:
        """
        Checks if the state is currently in a retrying state

        Returns:
            - bool: `True` if the state is retrying, `False` otherwise
        """

        return isinstance(self, Retrying)

    def is_running(self) -> bool:
        """
        Checks if the state is currently in a running state

        Returns:
            - bool: `True` if the state is running, `False` otherwise
        """
        return isinstance(self, Running)

    def is_cached(self) -> bool:
        """
        Checks if the state is currently in a Cached state

        Returns:
            - bool: `True` if the state is Cached, `False` otherwise
        """
        return isinstance(self, Cached)

    def is_finished(self) -> bool:
        """
        Checks if the state is currently in a finished state

        Returns:
            - bool: `True` if the state is finished, `False` otherwise
        """
        return isinstance(self, Finished)

    def is_looped(self) -> bool:
        """
        Checks if the state is currently in a looped state

        Returns:
            - bool: `True` if the state is looped, `False` otherwise
        """
        return isinstance(self, Looped)

    def is_scheduled(self) -> bool:
        """
        Checks if the state is currently in a scheduled state, which includes retrying.

        Returns:
            - bool: `True` if the state is skipped, `False` otherwise
        """
        return isinstance(self, Scheduled)

    def is_submitted(self) -> bool:
        """
        Checks if the state is currently in a submitted state.

        Returns:
            - bool: `True` if the state is submitted, `False` otherwise
        """
        return isinstance(self, Submitted)

    def is_skipped(self) -> bool:
        """
        Checks if the state is currently in a skipped state

        Returns:
            - bool: `True` if the state is skipped, `False` otherwise
        """
        return isinstance(self, Skipped)

    def is_successful(self) -> bool:
        """
        Checks if the state is currently in a successful state

        Returns:
            - bool: `True` if the state is successful, `False` otherwise
        """
        return isinstance(self, Success)

    def is_failed(self) -> bool:
        """
        Checks if the state is currently in a failed state

        Returns:
            - bool: `True` if the state is failed, `False` otherwise
        """
        return isinstance(self, Failed)

    def is_mapped(self) -> bool:
        """
        Checks if the state is currently in a mapped state

        Returns:
            - bool: `True` if the state is mapped, `False` otherwise
        """
        return isinstance(self, Mapped)

    def is_meta_state(self) -> bool:
        """
        Checks if the state is a meta state that wraps another state

        Returns:
            - bool: `True` if the state is a meta state, `False` otherwise
        """
        return isinstance(self, _MetaState)

    @staticmethod
    def deserialize(json_blob: dict) -> "State":
        """
        Deserializes the state from a dict.

        Args:
            - json_blob (dict): the JSON representing the serialized state
        """
        from prefect.serialization.state import StateSchema

        state = StateSchema().load(json_blob)
        return state

    def serialize(self) -> dict:
        """
        Serializes the state to a dict.

        Returns:
            - dict: a JSON representation of the state
        """
        from prefect.serialization.state import StateSchema

        json_blob = StateSchema().dump(self)
        return json_blob


# -------------------------------------------------------------------
# Pending States
# -------------------------------------------------------------------


class Pending(State):
    """
    Base Pending state; default state for new tasks.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to fully hydrated `Result`s.  Used / set if the Task requires Retries.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#7ebdff"

    def __init__(
        self,
        message: str = None,
        result: Any = NoResult,
        cached_inputs: Dict[str, Result] = None,
        context: Dict[str, Any] = None,
    ):
        super().__init__(message=message, result=result, context=context)
        self.cached_inputs = cached_inputs


class Scheduled(Pending):
    """
    Pending state indicating the object has been scheduled to run.

    Scheduled states have a `start_time` that indicates when they are scheduled to run.
    Only scheduled states have this property; this is important because non-Python systems
    identify scheduled states by the presence of this property.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - start_time (datetime): time at which the task is scheduled to run
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to fully hydrated `Result`s.  Used / set if the Task requires Retries.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#ffab00"

    def __init__(
        self,
        message: str = None,
        result: Any = NoResult,
        start_time: datetime.datetime = None,
        cached_inputs: Dict[str, Result] = None,
        context: Dict[str, Any] = None,
    ):
        super().__init__(
            message=message, result=result, cached_inputs=cached_inputs, context=context
        )
        self.start_time = pendulum.instance(start_time or pendulum.now("utc"))
        run_count = prefect.context.get("task_run_count")
        if run_count is not None:
            self.context.update(task_run_count=run_count)


class Paused(Scheduled):
    """
    Paused state for tasks. This allows manual intervention or pausing for a set amount of
    time.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - start_time (datetime): time at which the task is scheduled to resume; defaults
            to 10 years from now if not provided.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to fully hydrated `Result`s.  Used / set if the Task requires Retries.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#cfd8dc"

    def __init__(
        self,
        message: str = None,
        result: Any = NoResult,
        start_time: datetime.datetime = None,
        cached_inputs: Dict[str, Result] = None,
        context: Dict[str, Any] = None,
    ):
        if start_time is None:
            start_time = pendulum.now().add(years=10)

        super().__init__(
            message=message,
            result=result,
            start_time=start_time,
            cached_inputs=cached_inputs,
            context=context,
        )


class _MetaState(State):
    """
    Meta states are used to provide meta-information about other states. For example,
    the Submitted state wraps another state to show that it has been handled. The Queued
    state wraps states to show that they have been queued for execution.

    This parent class should NOT generally be used, but allows all meta states to be
    easily identified.
    """

    def __init__(
        self,
        message: str = None,
        result: Any = NoResult,
        state: State = None,
        context: Dict[str, Any] = None,
    ):
        super().__init__(message=message, result=result, context=context)
        self.state = state


class ClientFailed(_MetaState):
    """
    The `ClientFailed` state is used to indicate that the Prefect Client failed
    to set a task run state, and thus this task run should exit, without triggering any
    downstream task runs.

    The `ClientFailed` state should be initialized with another state, which it wraps. The
    wrapped state is the state which the client attempted to set in the database, but failed to
    for some reason.

    Args:
        - message (string): a message for the state.
        - result (Any, optional): Defaults to `None`.
        - state (State): the `State` state that the task run ended in
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible

    """

    color = "#eb0000"


class Submitted(_MetaState):
    """
    The `Submitted` state is used to indicate that another state, usually a `Scheduled`
    state, has been handled. For example, if a task is in a `Retrying` state, then at
    the appropriate time it may be put into a `Submitted` state referencing the
    `Retrying` state. This communicates to the system that the retry has been handled,
    without losing the information contained in the `Retry` state.

    The `Submitted` state should be initialized with another state, which it wraps. The
    wrapped state is extracted at the beginning of a task run.

    Args:
        - message (string): a message for the state.
        - result (Any, optional): Defaults to `None`.
        - state (State): the `State` state that has been marked as "submitted".
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible

    """

    color = "#ffdf5d"


class Queued(_MetaState):
    """
    The `Queued` state is used to indicate that another state could not transition to a
    `Running` state for some reason, often a lack of available resources.

    The `Queued` state should be initialized with another state, which it wraps. The
    wrapped state is extracted at the beginning of a task run.

    Args:
        - message (string): a message for the state.
        - result (Any, optional): Defaults to `None`.
        - state (State): the `State` state that has been marked as
            "queued".
        - start_time (datetime): a time the state is queued until. Defaults to `now`.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible

    """

    color = "#ffea7f"

    def __init__(
        self,
        message: str = None,
        result: Any = NoResult,
        state: State = None,
        start_time: datetime.datetime = None,
        context: Dict[str, Any] = None,
    ):
        super().__init__(message=message, result=result, state=state, context=context)
        self.start_time = start_time or pendulum.now("utc")


class Resume(Scheduled):
    """
    Resume state indicating the object can resume execution (presumably from a `Paused` state).

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - start_time (datetime): time at which the task is scheduled to run
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to fully hydrated `Result`s.  Used / set if the Task requires Retries.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#fb8532"


class Retrying(Scheduled):
    """
    Pending state indicating the object has been scheduled to be retried.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - start_time (datetime): time at which the task is scheduled to be retried
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to fully hydrated `Result`s.  Used / set if the Task requires Retries.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
        - run_count (int): The number of runs that had been attempted at the time of this
            Retry. Defaults to the value stored in context under "task_run_count" or 1,
            if that value isn't found.
    """

    color = "#f66a0a"

    def __init__(
        self,
        message: str = None,
        result: Any = NoResult,
        start_time: datetime.datetime = None,
        cached_inputs: Dict[str, Result] = None,
        context: Dict[str, Any] = None,
        run_count: int = None,
    ):
        super().__init__(
            result=result,
            message=message,
            start_time=start_time,
            cached_inputs=cached_inputs,
            context=context,
        )
        if run_count is None:
            run_count = prefect.context.get("task_run_count", 1)
        assert run_count is not None  # mypy assert
        self.run_count = run_count  # type: int


# -------------------------------------------------------------------
# Running States
# -------------------------------------------------------------------


class Running(State):
    """
    Base running state. Indicates that a task is currently running.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#3d67ff"


# -------------------------------------------------------------------
# Finished States
# -------------------------------------------------------------------


class Finished(State):
    """
    Base finished state. Indicates when a class has reached some form of completion.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#003ccb"


class Looped(Finished):
    """
    Finished state indicating one successful run of a looped task - if a Task is in this state, it will
    run the next iteration of the loop immediately after.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - loop_count (int): The iteration number of the looping task.
            Defaults to the value stored in context under "task_loop_count" or 1,
            if that value isn't found.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#003ccb"

    def __init__(
        self,
        message: str = None,
        result: Any = NoResult,
        loop_count: int = None,
        context: Dict[str, Any] = None,
    ):
        super().__init__(result=result, message=message, context=context)
        if loop_count is None:
            loop_count = prefect.context.get("task_loop_count", 1)
        assert loop_count is not None  # mypy assert
        self.loop_count = loop_count  # type: int


class Success(Finished):
    """
    Finished state indicating success.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#28a745"


class Cached(Success):
    """
    Cached, which represents a Task whose outputs have been cached.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the
            state, which will be cached.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to fully hydrated `Result`s.  Used / set if the Task requires Retries.
        - cached_parameters (dict): Defaults to `None`
        - cached_result_expiration (datetime): The time at which this cache
            expires and can no longer be used. Defaults to `None`
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#34d058"

    def __init__(
        self,
        message: str = None,
        result: Any = NoResult,
        cached_inputs: Dict[str, Result] = None,
        cached_parameters: Dict[str, Any] = None,
        cached_result_expiration: datetime.datetime = None,
        context: Dict[str, Any] = None,
    ):
        super().__init__(message=message, result=result, context=context)
        self.cached_inputs = cached_inputs
        self.cached_parameters = cached_parameters  # type: Optional[Dict[str, Any]]
        if cached_result_expiration is not None:
            cached_result_expiration = pendulum.instance(cached_result_expiration)
        self.cached_result_expiration = (
            cached_result_expiration
        )  # type: Optional[datetime.datetime]


class Mapped(Success):
    """
    State indicated this task was mapped over, and all mapped tasks were _submitted_ successfully.
    Note that this does _not_ imply the individual mapped tasks were successful, just that they
    have been submitted.

    You can not set the `result` of a Mapped state; it is determined by the results of its
    children states.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `[]`. A data payload for the state.
        - map_states (List): A list containing the states of any "children" of this task. When
            a task enters a Mapped state, it indicates that it has dynamically created copies
            of itself to map its operation over its inputs. Those copies are the children.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#003ccb"

    def __init__(
        self,
        message: str = None,
        result: Any = NoResult,
        map_states: List[State] = None,
        context: Dict[str, Any] = None,
    ):
        super().__init__(message=message, result=result, context=context)
        self.map_states = map_states or []  # type: List[State]

    @property
    def n_map_states(self) -> int:
        return len(self.map_states)


class Failed(Finished):
    """
    Finished state indicating failure.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to fully hydrated `Result`s.  Used / set if the Task might require manual Retries.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#eb0000"

    def __init__(
        self,
        message: str = None,
        result: Any = NoResult,
        cached_inputs: Dict[str, Result] = None,
        context: Dict[str, Any] = None,
    ):
        super().__init__(message=message, result=result, context=context)
        self.cached_inputs = cached_inputs


class Aborted(Failed):
    """
    Finished state indicating that a user aborted the flow run manually.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to fully hydrated `Result`s.  Used / set if the Task requires Retries.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#c42800"


class TimedOut(Failed):
    """
    Finished state indicating failure due to execution timeout.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to fully hydrated `Result`s.  Used / set if the Task requires Retries.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#ff4e33"


class TriggerFailed(Failed):
    """
    Finished state indicating failure due to trigger.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to fully hydrated `Result`s.  Used / set if the Task requires Retries.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#ff5131"


class Skipped(Success):
    """
    Finished state indicating success on account of being skipped.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - context (dict, optional): A dictionary of execution context information; values
            should be JSON compatible
    """

    color = "#62757f"

    # note: this does not allow setting "cached" as Success states do
    def __init__(
        self,
        message: str = None,
        result: Any = NoResult,
        context: Dict[str, Any] = None,
    ):
        super().__init__(message=message, result=result, context=context)
