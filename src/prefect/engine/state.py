import datetime
from typing import Any, Dict, List, Union

from prefect.utilities.json import Serializable

MessageType = Union[str, Exception]


class State(Serializable):
    def __init__(self, result: Any = None, message: MessageType = None) -> None:
        """
        Create a new State object.
            result (Any, optional): Defaults to None. A data payload for the state.
            message (str or Exception, optional): Defaults to None. A message about the
                state, which could be an Exception (or Signal) that caused it.
        """
        self.result = result
        self.message = message
        self._timestamp = datetime.datetime.utcnow()

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
        return isinstance(self, Pending)

    def is_running(self) -> bool:
        return isinstance(self, Running)

    def is_finished(self) -> bool:
        return isinstance(self, Finished)

    def is_successful(self) -> bool:
        return isinstance(self, Success)

    def is_failed(self) -> bool:
        return isinstance(self, Failed)


# -------------------------------------------------------------------
# Pending States
# -------------------------------------------------------------------


class Pending(State):
    """Base pending state"""

    def __init__(
        self,
        result: Any = None,
        message: MessageType = None,
        cached_inputs: Dict[str, Any] = None,
    ) -> None:
        """
        Create a new State object.
            result (Any, optional): Defaults to None. A data payload for the state.
            message (str or Exception, optional): Defaults to None. A message about the
                state, which could be an Exception (or Signal) that caused it.
        """
        super().__init__(result=result, message=message)
        self.cached_inputs = cached_inputs


class CachedState(Pending):
    def __init__(
        self,
        result: Any = None,
        message: MessageType = None,
        cached_inputs: Dict[str, Any] = None,
        cached_outputs: Dict[str, Any] = None,
        cache_expiry: datetime.datetime = None,
    ) -> None:
        super().__init__(result=result, message=message, cached_inputs=cached_inputs)
        self.cached_outputs = cached_outputs
        self.cache_expiry = cache_expiry


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
    """Base running state"""


# -------------------------------------------------------------------
# Finished States
# -------------------------------------------------------------------


class Finished(State):
    """Base finished state"""


class Success(Finished):
    """Finished state indicating success"""


class Failed(Finished):
    """Finished state indicating failure"""


class TriggerFailed(Failed):
    """Finished state indicating failure due to trigger"""


class Skipped(Success):
    """Finished state indicating success on account of being skipped"""
