from prefect.utilities.json import Serializable
from typing import FrozenSet, Any, Union


class State(Serializable):

    _default = None  # type: str

    def __init__(self, state: Union[str, "State"] = None, result: Any = None) -> None:
        if isinstance(state, State):
            self.set_state(state=state.state, result=state.result)
        else:
            self.set_state(state or self._default, result=result)

    def set_state(self, state: str, result: Any = None) -> None:
        if not self.is_valid_state(state):
            raise ValueError(
                "Invalid state for {}: {}".format(type(self).__name__, state)
            )
        self._state = str(state)
        self._result = result

    @property
    def state(self) -> str:
        return self._state

    @property
    def result(self) -> Any:
        return self._result

    def __eq__(self, other: Any) -> bool:
        if type(self) == type(other):
            return (self.state, self.result) == (other.state, other.result)
        elif isinstance(other, str):
            return self.state == other
        return False

    def __str__(self) -> str:
        return self.state

    def __repr__(self) -> str:
        return "{}({})".format(type(self).__name__, self.state)

    @classmethod
    def all_states(cls) -> FrozenSet[str]:
        return frozenset(
            [k for k, v in cls.__dict__.items() if k == v and k == k.upper()]
        )

    def is_valid_state(self, state: str) -> bool:
        """
        Valid states are uppercase class attributes that contain their own
        string value.
        """
        return state in self.all_states()


class FlowState(State):

    ACTIVE = "ACTIVE"
    PAUSED = _default = "PAUSED"
    ARCHIVED = "ARCHIVED"


class FlowRunState(State):

    PENDING = _default = "PENDING"
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
        return self == self.FAILED

    def is_skipped(self) -> bool:
        return self == self.SKIPPED


class TaskRunState(State):

    PENDING = _default = "PENDING"
    PENDING_RETRY = "PENDING_RETRY"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    SKIP_DOWNSTREAM = "SKIP_DOWNSTREAM"
    SHUTDOWN = "SHUTDOWN"

    _started_states = frozenset([RUNNING, SUCCESS, FAILED])
    _pending_states = frozenset([PENDING, PENDING_RETRY, SCHEDULED])
    _running_states = frozenset([RUNNING])
    _finished_states = frozenset([SUCCESS, FAILED, SKIPPED, SKIP_DOWNSTREAM])
    _skipped_states = frozenset([SKIPPED, SKIP_DOWNSTREAM])
    _successful_states = frozenset([SUCCESS, SKIPPED])
    _failed_states = frozenset([FAILED])

    def is_started(self) -> bool:
        return str(self) in self._started_states

    def is_pending(self) -> bool:
        return str(self) in self._pending_states

    def is_pending_retry(self) -> bool:
        return self == self.PENDING_RETRY

    def is_running(self) -> bool:
        return str(self) in self._running_states

    def is_finished(self) -> bool:
        return str(self) in self._finished_states

    def is_successful(self) -> bool:
        return str(self) in self._successful_states

    def is_skipped(self) -> bool:
        return str(self) in self._skipped_states

    def is_failed(self) -> bool:
        return str(self) in self._failed_states


class ScheduledFlowRunState(State):

    SCHEDULED = _default = "SCHEDULED"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    CANCELED = "CANCELED"

    def is_scheduled(self) -> bool:
        return self == self.SCHEDULED

    def is_running(self) -> bool:
        return self == self.RUNNING

    def is_finished(self) -> bool:
        return self == self.FINISHED

    def is_canceled(self) -> bool:
        return self == self.CANCELED
