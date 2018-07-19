import datetime
from typing import Any, Dict, List

from prefect.utilities.json import Serializable


class State(Serializable):
    def __init__(self, message: str = None, data: Any = None) -> None:
        """
        Create a new State object.
            message (str, optional): Defaults to None. A message about the state.
            data (Any, optional): Defaults to None. A data payload for the state.
        """
        self.message = message
        self.data = data
        self._timestamp = datetime.datetime.utcnow()

    @property
    def timestamp(self) -> datetime.datetime:
        return self._timestamp

    def __repr__(self) -> str:
        return "<{}>".format(type(self).__name__)

    def __eq__(self, other: object) -> bool:
        if type(self) == type(other):
            assert isinstance(other, State)  # this assertion is here for MyPy only
            self_dct = self.__dict__.copy()
            self_dct.pop("_timestamp")
            other_dct = other.__dict__.copy()
            other_dct.pop("_timestamp")
            return self_dct == other_dct
        return False

    def __hash__(self):
        return id(self)

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

    def __init__(
        self, scheduled_time: datetime.datetime, message: str = None, data: Any = None
    ) -> None:
        """
        Args:
            scheduled_time (datetime.datetime): the time the state is scheduled to run
            data (any, optional): a data payload
        """
        self.scheduled_time = scheduled_time
        super().__init__(message=message, data=data)


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

