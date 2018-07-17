import datetime
from typing import Any, Dict, List

from prefect.utilities.json import Serializable


class State(Serializable):

    def __init__(self, data: Any = None) -> None:
        """
        Create a new State object.
            state (str, optional): Defaults to None. One of the State class's valid state types. If None is provided, the State's default will be used.

            data (Any, optional): Defaults to None. A data payload for the state.
        """

        self._data = data
        self._timestamp = datetime.datetime.utcnow()

    def __repr__(self) -> str:
        return "{}()".format(type(self).__name__)

    def __eq__(self, other: object) -> bool:
        if type(self) == type(other):
            assert isinstance(other, State)  # this assertion is here for MyPy only
            return self.data == other.data
        return False

    def __hash__(self) -> int:
        return id(self)

    @property
    def data(self) -> Any:
        return self._data

    @property
    def timestamp(self) -> datetime.datetime:
        return self._timestamp

    @classmethod
    def all_states(cls) -> List[str]:
        """
        States are class instances with uppercase names that refer to their own name as a
        string
        """
        return [k for k, v in cls.__dict__.items() if k == v and k == k.upper()]

    def _validate_state(self, state: str) -> bool:
        if state not in self.all_states():
            raise ValueError('Invalid state: "{}"'.format(state))

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

    def is_skipped(self) -> bool:
        return isinstance(self, Skipped)


class Pending(State):
    pass

class Retrying(Pending):
    pass

class Scheduled(Pending):
    pass

class Running(State):
    pass

class Finished(State):
    pass

class Success(Finished):
    pass

class Failed(Finished):
    pass

class Skipped(Success):
    pass
