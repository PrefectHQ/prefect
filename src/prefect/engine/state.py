# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

"""
State is the main currency in the Prefect platform. It is used to represent the current
status of a task.

This module contains is a series of objects, all inheriting from the base State class.

Every task is initialized with the `Pending` state meaning that it is waiting for
execution. The other types of `Pending` states are `CachedState`, `Scheduled`, and
`Retrying`.

When a task is running it will enter a `Running` state which means that the task is
currently being executed.

The four types of `Finished` states are `Success`, `Failed`, `TriggerFailed`, and
`Skipped`.
"""
import datetime
from typing import Any, Dict, Iterable, List, Union

from prefect.utilities.json import Serializable

MessageType = Union[str, Exception]


class State(Serializable):
    """
    Create a new State object.

    Args:
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
    """

    def __init__(self, result: Any = None, message: MessageType = None) -> None:
        self.result = result
        self.message = message
        self._timestamp = datetime.datetime.utcnow()

    #    def __iter__(self):
    #        yield from (type(self)(result=val) for val in self.result)

    def __repr__(self) -> str:
        if self.message:
            return '{}("{}")'.format(type(self).__name__, self.message)
        else:
            return "{}()".format(type(self).__name__)

    def __eq__(self, other: object) -> bool:
        """
        Equality depends on state type and data, not message or timestamp
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

    @property
    def timestamp(self) -> datetime.datetime:
        return self._timestamp

    def is_pending(self) -> bool:
        """Checks if the object is currently in a pending state

        Returns:
            - True (bool) if the state is Pending, False otherwise
        """
        return isinstance(self, Pending)

    def is_running(self) -> bool:
        """Checks if the object is currently in a running state

        Returns:
            - True (bool) if the state is Running, False otherwise
        """
        return isinstance(self, Running)

    def is_finished(self) -> bool:
        """Checks if the object is currently in a finished state

        Returns:
            - True (bool) if the state is Finished, False otherwise
        """
        return isinstance(self, Finished)

    def is_successful(self) -> bool:
        """Checks if the object is currently in a successful state

        Returns:
            - True (bool) if the state is Success, False otherwise
        """
        return isinstance(self, Success)

    def is_failed(self) -> bool:
        """Checks if the object is currently in a failed state

        Returns:
            - True (bool) if the state is Failed, False otherwise
        """
        return isinstance(self, Failed)


# -------------------------------------------------------------------
# Pending States
# -------------------------------------------------------------------


class Pending(State):
    """
    Base Pending state; default state for new tasks.

    Args:
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
        keys to values.  Used / set if the Task requires Retries.
    """

    def __init__(
        self,
        result: Any = None,
        message: MessageType = None,
        cached_inputs: Dict[str, Any] = None,
    ) -> None:
        super().__init__(result=result, message=message)
        self.cached_inputs = cached_inputs


class CachedState(Pending):
    """
    CachedState, which represents a Task whose outputs have been cached.

    Args:
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
        keys to values.  Used / set if the Task requires Retries.
        - cached_result (Any): Defaults to `None`. Cached result from a
        successful Task run.
        - cached_parameters (dict): Defaults to `None`
        - cached_result_expiration (datetime): Defaults to `None`
    """

    def __init__(
        self,
        result: Any = None,
        message: MessageType = None,
        cached_inputs: Dict[str, Any] = None,
        cached_result: Any = None,
        cached_parameters: Dict[str, Any] = None,
        cached_result_expiration: datetime.datetime = None,
    ) -> None:
        super().__init__(result=result, message=message, cached_inputs=cached_inputs)
        self.cached_result = cached_result
        self.cached_parameters = cached_parameters
        self.cached_result_expiration = cached_result_expiration


class Scheduled(Pending):
    """Pending state indicating the object has been scheduled to run"""

    def __init__(
        self,
        result: Any = None,
        message: MessageType = None,
        scheduled_time: datetime.datetime = None,
        cached_inputs: Dict[str, Any] = None,
    ) -> None:
        super().__init__(result=result, message=message, cached_inputs=cached_inputs)
        self.scheduled_time = scheduled_time


class Retrying(Scheduled):
    """Pending state indicating the object has been scheduled to be retried"""


# -------------------------------------------------------------------
# Running States
# -------------------------------------------------------------------


class Running(State):
    """Base running state. Indicates that a task is currently running."""


# -------------------------------------------------------------------
# Finished States
# -------------------------------------------------------------------


class Finished(State):
    """Base finished state. Indicates when a class has reached some for of completion."""


class Success(Finished):
    """Finished state indicating success"""

    def __init__(
        self,
        result: Any = None,
        message: MessageType = None,
        cached: CachedState = None,
    ) -> None:
        super().__init__(result=result, message=message)
        self.cached = cached


class Failed(Finished):
    """Finished state indicating failure"""


class TriggerFailed(Failed):
    """Finished state indicating failure due to trigger"""


class Skipped(Success):
    """Finished state indicating success on account of being skipped"""
