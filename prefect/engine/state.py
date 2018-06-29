import datetime
from typing import Any, Dict, List

from prefect.utilities.json import Serializable


class State(Serializable):

    PENDING = _default_state = "PENDING"
    RETRYING = "RETRYING"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

    _pending_states = frozenset([SCHEDULED, PENDING, RETRYING, SCHEDULED])
    _finished_states = frozenset([SUCCESS, FAILED, SKIPPED])
    _successful_states = frozenset([SUCCESS, SKIPPED])
    _running_states = frozenset([RUNNING])

    def __init__(self, state: str = None, data: Any = None, meta: Dict = None) -> None:
        """
        Create a new State object.
            state (str, optional): Defaults to None. One of the State class's valid state types. If None is provided, the State's default will be used.

            data (Any, optional): Defaults to None. A data payload for the state.

            meta (Dict, optional): Defaults to None. State metadata.
        """

        if state is None:
            state = self._default_state
        assert state is not None

        self._validate_state(state)
        self._state = state
        self._data = data
        self._meta = meta or {}
        self._timestamp = datetime.datetime.utcnow()

    def __repr__(self) -> str:
        msg = self.data.get('message')
        if msg:
            return "{}({}, {})".format(type(self).__name__, self.state, msg)
        return "{}({})".format(type(self).__name__, self.state)

    def __eq__(self, other: object) -> bool:
        if type(self) == type(other):
            assert isinstance(other, State)  # this assertion is here for MyPy only
            return (self.state, self.data) == (other.state, other.data)
        return False

    def __hash__(self) -> int:
        return id(self)

    @property
    def state(self) -> str:
        return self._state

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
        return self.state in self._pending_states

    def is_running(self) -> bool:
        return self.state in self._running_states

    def is_finished(self) -> bool:
        return self.state in self._finished_states

    def is_successful(self) -> bool:
        return self.state in self._successful_states

    def is_failed(self) -> bool:
        return self.state == self.FAILED

    def is_skipped(self) -> bool:
        return self.state == self.SKIPPED
