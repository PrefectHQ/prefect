import datetime
from prefect.utilities.json import Serializable
from typing import List, Any


class State(Serializable):

    _default_state = None # type: str

    def __init__(self, state: str = None, data: Any = None) -> None:

        if state is None:
            state = self._default_state
        assert state is not None

        self._validate_state(state)
        self._state = state
        self._data = data
        self._timestamp = datetime.datetime.utcnow()

    def __repr__(self) -> str:
        return "{}({})".format(type(self).__name__, self.state)

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


class FlowState(State):

    PENDING = _default_state = "PENDING"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    SHUTDOWN = "SHUTDOWN"

    _pending_states = frozenset([SCHEDULED, PENDING])
    _finished_states = frozenset([SUCCESS, FAILED, SKIPPED])
    _successful_states = frozenset([SUCCESS, SKIPPED])
    _running_states = frozenset([RUNNING])

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


class TaskState(State):

    PENDING = _default_state = "PENDING"
    PENDING_RETRY = "PENDING_RETRY"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    SKIP_DOWNSTREAM = "SKIP_DOWNSTREAM"
    SHUTDOWN = "SHUTDOWN"

    _pending_states = frozenset([PENDING, PENDING_RETRY, SCHEDULED])
    _running_states = frozenset([RUNNING])
    _finished_states = frozenset([SUCCESS, FAILED, SKIPPED, SKIP_DOWNSTREAM])
    _skipped_states = frozenset([SKIPPED, SKIP_DOWNSTREAM])
    _successful_states = frozenset([SUCCESS, SKIPPED])
    _failed_states = frozenset([FAILED])

    def is_pending(self) -> bool:
        return self.state in self._pending_states

    def is_pending_retry(self) -> bool:
        return self.state == self.PENDING_RETRY

    def is_running(self) -> bool:
        return self.state in self._running_states

    def is_finished(self) -> bool:
        return self.state in self._finished_states

    def is_successful(self) -> bool:
        return self.state in self._successful_states

    def is_failed(self) -> bool:
        return self.state in self._failed_states

    def is_skipped(self) -> bool:
        return self.state in self._skipped_states

