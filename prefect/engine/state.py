from prefect.utilities.serializers import Serializable

class State(Serializable):

    _default = None

    def __init__(self, state=None, result=None):
        self.result = None
        if isinstance(state, type(self)):
            self.set_state(state=state.state, result=state.result)
        else:
            self.set_state(state or self._default, result=result)

    def set_state(self, state, result=None):
        if not self.is_valid_state(state):
            raise ValueError(
                'Invalid state for {}: {}'.format(type(self).__name__, state))
        self.state = str(state)
        self.result = result

    def __eq__(self, other):
        if type(self) == type(other):
            return (self.state, self.result) == (other.state, other.result)
        elif isinstance(other, str):
            return self.state == other
        return False

    def __str__(self):
        return self.state

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, self.state)

    def __json__(self):
        return dict(state=self.state, result=self.result)


    @classmethod
    def all_states(cls):
        return frozenset(
            [
                k for k, v in cls.__dict__.items()
                if k == v and k == k.upper()
            ])

    def is_valid_state(self, state):
        """
        Valid states are uppercase class attributes that contain their own
        string value.
        """
        return str(state) in self.all_states()


class FlowState(State):

    ACTIVE = 'ACTIVE'
    PAUSED = _default = 'PAUSED'
    ARCHIVED = 'ARCHIVED'

    def activate(self):
        self.set_state(self.ACTIVE)

    def pause(self):
        self.set_state(self.PAUSED)

    def archive(self):
        self.set_state(self.ARCHIVED)

    def unarchive(self):
        self.set_state(self.PAUSED)



class FlowRunState(State):

    PENDING = _default = 'PENDING'
    SCHEDULED = 'SCHEDULED'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'
    SHUTDOWN = 'SHUTDOWN'

    _pending_states = frozenset([SCHEDULED, PENDING])
    _finished_states = frozenset([SUCCESS, FAILED, SKIPPED])
    _successful_states = frozenset([SUCCESS, SKIPPED])
    _running_states = frozenset([RUNNING])

    def is_pending(self):
        return self.state in self._pending_states

    def is_running(self):
        return self.state in self._running_states

    def is_finished(self):
        return self.state in self._finished_states

    def is_successful(self):
        return self.state in self._successful_states

    def is_failed(self):
        return self == self.FAILED

    def is_skipped(self):
        return self == self.SKIPPED



class TaskRunState(State):

    PENDING = _default = 'PENDING'
    PENDING_RETRY = 'PENDING_RETRY'
    SCHEDULED = 'SCHEDULED'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'
    SKIP_DOWNSTREAM = 'SKIP_DOWNSTREAM'
    SHUTDOWN = 'SHUTDOWN'

    _started_states = frozenset([RUNNING, SUCCESS, FAILED])
    _pending_states = frozenset([PENDING, PENDING_RETRY, SCHEDULED])
    _running_states = frozenset([RUNNING])
    _finished_states = frozenset([SUCCESS, FAILED, SKIPPED, SKIP_DOWNSTREAM])
    _skipped_states = frozenset([SKIPPED, SKIP_DOWNSTREAM])
    _successful_states = frozenset([SUCCESS, SKIPPED])
    _failed_states = frozenset([FAILED])

    def is_started(self):
        return str(self) in self._started_states

    def is_pending(self):
        return str(self) in self._pending_states

    def is_pending_retry(self):
        return self == self.PENDING_RETRY

    def is_running(self):
        return str(self) in self._running_states

    def is_finished(self):
        return str(self) in self._finished_states

    def is_successful(self):
        return str(self) in self._successful_states

    def is_skipped(self):
        return str(self) in self._skipped_states

    def is_failed(self):
        return str(self) in self._failed_states


class ScheduledFlowRunState(State):

    SCHEDULED = _default = 'SCHEDULED'
    RUNNING = 'RUNNING'
    FINISHED = 'FINISHED'
    CANCELED = 'CANCELED'

    def is_scheduled(self):
        return self == self.SCHEDULED

    def is_running(self):
        return self == self.RUNNING

    def is_finished(self):
        return self == self.FINISHED

    def is_canceled(self):
        return self == self.CANCELED


