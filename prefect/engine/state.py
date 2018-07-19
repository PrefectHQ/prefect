import datetime
from typing import Any, Dict, List

from prefect.utilities.json import Serializable


class State(Serializable):
    def __init__(self, data: Any = None, message: str = None) -> None:
        """
        Create a new State object.
            data (Any, optional): Defaults to None. A data payload for the state.
            message (str, optional): Defaults to None. A message about the state.
        """
        self.data = data
        self.message = message
        self._timestamp = datetime.datetime.utcnow()

    def __repr__(self) -> str:
        return "<{}>".format(type(self).__name__)

    def __eq__(self, other: object) -> bool:
        """
        Equality depends on state type and data, not message or timestamp
        """
        if type(self) == type(other):
            assert isinstance(other, State)  # this assertion is here for MyPy only
            return self.data == other.data
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


class Scheduled(Pending):
    """Pending state indicating the object has been scheduled to run"""


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
