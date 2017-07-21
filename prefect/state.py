from collections import namedtuple
import functools
import prefect


class State:

    _default_state = ''

    # transitions is a dictionary of { state: source_state } pairs
    # in order to transition to a new state, the current state must be one of
    # its source_states
    _transitions = {}

    def __init__(self, state=None):

        if not hasattr(type(self), '_default_state'):
            'State classes require a `_default_state` state class attribute.'

        if state is None:
            state = self._default_state
        elif isinstance(state, State):
            state = state.state
        self.set_state(state)

    def set_state(self, state):
        old_state = getattr(self, 'state', None)
        if not self.is_valid_state(state):
            raise ValueError(f'Invalid state: {state}')
        elif old_state and not self.is_valid_transition(old_state, state):
            raise ValueError(f'Invalid transition: {self.state} to {state}')
        self.state = state

    def __eq__(self, other):

        return (
            # match other State types
            (type(self) == type(other) and (self.state == other.state))
            # match strings directly
            or (isinstance(other, str) and str(self) == other))

    def __str__(self):
        return self.state

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, self.state)

    def is_valid_state(self, state):
        return state in self._transitions

    def is_valid_transition(self, old_state, new_state):
        return old_state in self._transitions.get(new_state, [])


class FlowState(State):
    ACTIVE = 'ACTIVE'
    PAUSED = _default_state = 'PAUSED'
    ARCHIVED = 'ARCHIVED'

    _transitions = {
        ACTIVE: [PAUSED],
        PAUSED: [ACTIVE, ARCHIVED],
        ARCHIVED: [ACTIVE, PAUSED],
    }

    def activate(self):
        self.set_state(self.ACTIVE)

    def pause(self):
        self.set_state(self.PAUSED)

    def archive(self):
        self.set_state(self.ARCHIVED)

    def unarchive(self):
        self.set_state(self.PAUSED)


class FlowRunState(State):
    SCHEDULED = 'SCHEDULED'
    PENDING = _default_state = 'PENDING'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'
    SHUTDOWN = 'SHUTDOWN'

    _pending_states = set([SCHEDULED, PENDING])
    _finished_states = set([SUCCESS, FAILED, SKIPPED])
    _successful_states = set([SUCCESS, SKIPPED])
    _running_states = set([RUNNING])

    _transitions = {
        SCHEDULED: _pending_states,
        PENDING: _pending_states,
        RUNNING: _pending_states,
        SUCCESS: [RUNNING],
        FAILED: [RUNNING],
        SKIPPED: _pending_states.union(_running_states),
        SHUTDOWN: _pending_states.union(_running_states),
    }

    def start(self):
        self.set_state(self.RUNNING)

    def schedule(self):
        self.set_state(self.SCHEDULED)

    def succeed(self):
        self.set_state(self.SUCCESS)

    def fail(self):
        self.set_state(self.FAILED)

    def shutdown(self):
        self.set_state(self.SHUTDOWN)

    def skip(self):
        self.set_state(self.SKIPPED)

    def is_pending(self):
        return str(self) in self._pending_states

    def is_running(self):
        return str(self) in self._running_states

    def is_finished(self):
        return str(self) in self._finished_states

    def is_successful(self):
        return str(self) in self._successful_states

    def is_failed(self):
        return self == self.FAILED

    def is_skipped(self):
        return self == self.SKIPPED


class TaskRunState(State):

    PENDING = _default_state = 'PENDING'
    PENDING_RETRY = 'PENDING_RETRY'
    SCHEDULED = 'SCHEDULED'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'
    SHUTDOWN = 'SHUTDOWN'

    _started_states = set([RUNNING, SUCCESS, FAILED])
    _pending_states = set([PENDING, PENDING_RETRY, SCHEDULED, SHUTDOWN])
    _running_states = set([RUNNING])
    _finished_states = set([SUCCESS, FAILED, SKIPPED])
    _skipped_states = set([SKIPPED])
    _successful_states = set([SUCCESS, SKIPPED])
    _failed_states = set([FAILED])

    _transitions = {
        SCHEDULED: _pending_states,
        PENDING: _pending_states,
        RUNNING: _pending_states,
        SUCCESS: _pending_states.union(_running_states),
        FAILED: _pending_states.union(_running_states),
        PENDING_RETRY: _failed_states,
        SKIPPED: _pending_states.union(_running_states),
        SHUTDOWN: _pending_states.union(_running_states),
    }

    def start(self):
        self.set_state(self.RUNNING)

    def succeed(self):
        self.set_state(self.SUCCESS)

    def fail(self):
        self.set_state(self.FAILED)

    def skip(self):
        self.set_state(self.SKIPPED)

    def retry(self):
        self.set_state(self.PENDING_RETRY)

    def schedule(self):
        self.set_state(self.SCHEDULED)

    def shutdown(self):
        self.set_state(self.SHUTDOWN)

    def is_started(self):
        return str(self) in self._started_states

    def is_pending(self):
        return str(self) in self._pending_states

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
