# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

"""
State is the main currency in the Prefect platform. It is used to represent the current
status of a task.

This module contains all Prefect state classes, all ultimately inheriting from the base State class as follows:

![](/state_inheritance_diagram.svg) {style="text-align: center;"}

Every task is initialized with the `Pending` state, meaning that it is waiting for
execution. The other types of `Pending` states are `CachedState`, `Paused`, `Scheduled`, and
`Retrying`.

When a task is running it will enter a `Running` state which means that the task is
currently being executed.

The six types of `Finished` states are `Success`, `Failed`, `TriggerFailed`, `TimedOut`, `Mapped` and
`Skipped`.
"""
import datetime
import pendulum
from typing import Any, Dict, Union

import prefect
from prefect.client.result_handlers import ResultHandler
from prefect.utilities.datetimes import ensure_tz_aware


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
    """

    color = "#000000"

    def __init__(self, message: str = None, result: Any = None) -> None:
        self.message = message
        self.result = result

    def __repr__(self) -> str:
        if self.message:
            return '{}("{}")'.format(type(self).__name__, self.message)
        else:
            return "{}()".format(type(self).__name__)

    def __eq__(self, other: object) -> bool:
        """
        Equality depends on state type and data, but not message
        """
        if type(self) == type(other):
            assert isinstance(other, State)  # this assertion is here for MyPy only
            eq = True
            for attr in self.__dict__:
                if attr.startswith("_") or attr == "message":
                    continue
                eq &= getattr(self, attr, object()) == getattr(other, attr, object())
            return eq
        return False

    def __hash__(self) -> int:
        return id(self)

    def is_pending(self) -> bool:
        """
        Checks if the object is currently in a pending state

        Returns:
            - bool: `True` if the state is pending, `False` otherwise
        """
        return isinstance(self, Pending)

    def is_running(self) -> bool:
        """
        Checks if the object is currently in a running state

        Returns:
            - bool: `True` if the state is running, `False` otherwise
        """
        return isinstance(self, Running)

    def is_finished(self) -> bool:
        """
        Checks if the object is currently in a finished state

        Returns:
            - bool: `True` if the state is finished, `False` otherwise
        """
        return isinstance(self, Finished)

    def is_scheduled(self) -> bool:
        """
        Checks if the object is currently in a scheduled state, which includes retrying.

        Returns:
            - bool: `True` if the state is skipped, `False` otherwise
        """
        return isinstance(self, Scheduled)

    def is_skipped(self) -> bool:
        """
        Checks if the object is currently in a skipped state

        Returns:
            - bool: `True` if the state is skipped, `False` otherwise
        """
        return isinstance(self, Skipped)

    def is_successful(self) -> bool:
        """
        Checks if the object is currently in a successful state

        Returns:
            - bool: `True` if the state is successful, `False` otherwise
        """
        return isinstance(self, Success)

    def is_failed(self) -> bool:
        """
        Checks if the object is currently in a failed state

        Returns:
            - bool: `True` if the state is failed, `False` otherwise
        """
        return isinstance(self, Failed)

    def serialize(self, result_handler: ResultHandler = None) -> dict:
        """
        Serializes the state to a dict.

        Args:
            - result_handler (ResultHandler, optional): if provided, used to
                handle private attributes of state classes (e.g., results)
        """
        from prefect.serialization.state import StateSchema

        if result_handler is not None:
            json_blob = StateSchema(context=dict(result_handler=result_handler)).dump(
                self
            )
        else:
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
        keys to values.  Used / set if the Task requires Retries.
    """

    color = "#d3d3d3"

    def __init__(
        self,
        message: str = None,
        result: Any = None,
        cached_inputs: Dict[str, Any] = None,
    ) -> None:
        super().__init__(message=message, result=result)
        self.cached_inputs = cached_inputs


class Paused(Pending):
    """
    Paused state for tasks which require manual execution.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
        keys to values.  Used / set if the Task requires Retries.
    """

    color = "#800000"


class CachedState(Pending):
    """
    CachedState, which represents a Task whose outputs have been cached.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
        keys to values.  Used / set if the Task requires Retries.
        - cached_result (Any): Defaults to `None`. Cached result from a
        successful Task run.
        - cached_parameters (dict): Defaults to `None`
        - cached_result_expiration (datetime): The time at which this cache
            expires and can no longer be used. Defaults to `None`
    """

    color = "#ffa500"

    def __init__(
        self,
        message: str = None,
        result: Any = None,
        cached_inputs: Dict[str, Any] = None,
        cached_result: Any = None,
        cached_parameters: Dict[str, Any] = None,
        cached_result_expiration: datetime.datetime = None,
    ) -> None:
        super().__init__(message=message, result=result, cached_inputs=cached_inputs)
        self.cached_result = cached_result
        self.cached_parameters = cached_parameters
        if cached_result_expiration is not None:
            cached_result_expiration = ensure_tz_aware(cached_result_expiration)
        self.cached_result_expiration = cached_result_expiration


class Scheduled(Pending):
    """
    Pending state indicating the object has been scheduled to run.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - start_time (datetime): time at which the task is scheduled to run
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to values.  Used / set if the Task requires Retries.
    """

    color = "#b0c4de"

    def __init__(
        self,
        message: str = None,
        result: Any = None,
        start_time: datetime.datetime = None,
        cached_inputs: Dict[str, Any] = None,
    ) -> None:
        super().__init__(message=message, result=result, cached_inputs=cached_inputs)
        self.start_time = ensure_tz_aware(start_time or pendulum.now("utc"))


class Retrying(Scheduled):
    """
    Pending state indicating the object has been scheduled to be retried.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - start_time (datetime): time at which the task is scheduled to be retried
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to values.  Used / set if the Task requires Retries.
        - run_count (int): The number of runs that had been attempted at the time of this
            Retry. Defaults to the value stored in context under "_task_run_count" or 1,
            if that value isn't found.
    """

    color = "#FFFF00"

    def __init__(
        self,
        message: str = None,
        result: Any = None,
        start_time: datetime.datetime = None,
        cached_inputs: Dict[str, Any] = None,
        run_count: int = None,
    ) -> None:
        super().__init__(
            result=result,
            message=message,
            start_time=start_time,
            cached_inputs=cached_inputs,
        )
        if run_count is None:
            run_count = prefect.context.get("_task_run_count", 1)
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
    """

    color = "#00FF00"


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
    """

    color = "#BA55D3"


class Success(Finished):
    """
    Finished state indicating success.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - cached (CachedState): a `CachedState` which can be used for future
            runs of this task (if the cache is still valid); this attribute should only be set
            by the task runner.
    """

    color = "#008000"

    def __init__(
        self, message: str = None, result: Any = None, cached: CachedState = None
    ) -> None:
        super().__init__(message=message, result=result)
        self.cached = cached


class Mapped(Success):
    """
    State indicated this task was mapped over, and all mapped tasks were _submitted_ successfully.
    Note that this does _not_ imply the individual mapped tasks were successful, just that they
    have been submitted.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - cached (CachedState): a `CachedState` which can be used for future
            runs of this task (if the cache is still valid); this attribute should only be set
            by the task runner.
    """

    color = "#97FFFF"


class Failed(Finished):
    """
    Finished state indicating failure.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
    """

    color = "#FF0000"


class TimedOut(Failed):
    """
    Finished state indicating failure due to execution timeout.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
        keys to values.  Used / set if the Task requires Retries.
    """

    color = "#CDC9A5"

    def __init__(
        self,
        message: str = None,
        result: Any = None,
        cached_inputs: Dict[str, Any] = None,
    ) -> None:
        super().__init__(message=message, result=result)
        self.cached_inputs = cached_inputs


class TriggerFailed(Failed):
    """
    Finished state indicating failure due to trigger.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
    """

    color = "#F08080"


class Skipped(Success):
    """
    Finished state indicating success on account of being skipped.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
    """

    color = "#F0FFF0"

    # note: this does not allow setting "cached" as Success states do
    def __init__(self, message: str = None, result: Any = None) -> None:
        super().__init__(message=message, result=result)
