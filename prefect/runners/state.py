from collections import namedtuple
import functools
import prefect


def set_from(source_states):
    """
    Method decorator that indicates valid source states for a state transition

    @set_from(['A'])
    def to_b(self):
        self.set_state('B')

    assert obj.state == 'A'
    obj.to_b()  # works

    assert obj.state == 'C'
    obj.to_b()  # fails
    """
    if isinstance(source_states, str):
        source_states = [source_states]

    def decorator(method):
        @functools.wraps(method)
        def inner(self, *args, **kwargs):
            if self.state not in source_states:
                raise ValueError(
                    f"Can't call '{method.__name__}()' when '{self.state}'")
            method(self, *args, **kwargs)
        return inner
    return decorator


class State:

    _default_state = ''

    def __init__(self, state=None):

        if not hasattr(type(self), '_default_state'):
            'State classes require a `_default_state` state class attribute.'

        if state is None:
            state = self._default_state
        elif isinstance(state, State):
            state = state.state
        self.set_state(state)

    def set_state(self, state):
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


class FlowState(State):
    ACTIVE = 'ACTIVE'
    TESTING = 'TESTING'
    PAUSED = 'PAUSED'
    ARCHIVED = 'ARCHIVED'

    if prefect.config.get('flows', 'default_active'):
        _default_state = ACTIVE
    else:
        _default_state = PAUSED

    _all_states = set([
        ACTIVE,
        TESTING,
        PAUSED,
        ARCHIVED,
    ])

    _unarchived_states = set([ACTIVE, PAUSED, TESTING])

    @set_from([PAUSED, TESTING])
    def activate(self):
        self.set_state(self.ACTIVE)

    @set_from([PAUSED, ACTIVE])
    def test(self):
        self.set_state(self.TESTING)

    @set_from([ACTIVE, TESTING])
    def pause(self):
        self.set_state(self.PAUSED)

    @set_from(_unarchived_states)
    def archive(self):
        self.set_state(self.ARCHIVED)

    @set_from(ARCHIVED)
    def unarchive(self):
        self.set_state(self.PAUSED)


class FlowRunState(State):
    SCHEDULED = 'SCHEDULED'
    PENDING = _default_state = 'PENDING'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    WAITING = 'WAITING'
    SHUTDOWN = 'SHUTDOWN'

    _all_states = set(
        [
            SCHEDULED,
            PENDING,
            RUNNING,
            SUCCESS,
            FAILED,
            WAITING,
            SHUTDOWN,
        ])

    _pending_states = set([SCHEDULED, PENDING, WAITING])
    _finished_states = set([SUCCESS, FAILED])

    @set_from(_pending_states)
    def start(self):
        self.set_state(self.RUNNING)

    @set_from(_pending_states)
    def schedule(self):
        self.set_state(self.SCHEDULED)

    @set_from(_pending_states.union([RUNNING]))
    def succeed(self):
        self.set_state(self.SUCCESS)

    @set_from(_pending_states.union([RUNNING]))
    def fail(self):
        self.set_state(self.FAILED)

    @set_from(RUNNING)
    def wait(self):
        self.set_state(self.WAITING)

    @set_from(_all_states)
    def shutdown(self):
        self.set_state(self.SHUTDOWN)

    def is_pending(self):
        return str(self) in self._pending_states

    def is_finished(self):
        return str(self) in self._finished_states

    def is_successful(self):
        return self == self.SUCCESS

    def is_failed(self):
        return self == self.FAILED

    def is_waiting(self):
        return self == self.WAITING


class TaskRunState(State):

    PENDING = _default_state = 'PENDING'
    PENDING_RETRY = 'PENDING_RETRY'
    SCHEDULED = 'SCHEDULED'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'
    WAITING = 'WAITING'
    SHUTDOWN = 'SHUTDOWN'

    _all_states = set(
        [
            SCHEDULED,
            PENDING,
            PENDING_RETRY,
            RUNNING,
            SUCCESS,
            FAILED,
            SKIPPED,
            WAITING,
            SHUTDOWN,
        ])
    _started_states = set([RUNNING, SUCCESS, FAILED])
    _pending_states = set(
        [PENDING, PENDING_RETRY, SCHEDULED, WAITING, SHUTDOWN])
    _running_states = set([RUNNING])
    _finished_states = set([SUCCESS, FAILED, SKIPPED])
    _skipped_states = set([SKIPPED])
    _successful_states = set([SUCCESS, SKIPPED])
    _failed_states = set([FAILED])
    _waiting_states = set([WAITING])

    @set_from(_pending_states)
    def start(self):
        self.set_state(self.RUNNING)

    @set_from(_pending_states.union(_running_states))
    def succeed(self):
        self.set_state(self.SUCCESS)

    @set_from(_pending_states.union(_running_states))
    def fail(self):
        self.set_state(self.FAILED)

    @set_from(_pending_states)
    def skip(self):
        self.set_state(self.SKIPPED)

    @set_from(FAILED)
    def retry(self):
        self.set_state(self.PENDING_RETRY)

    @set_from(_pending_states)
    def schedule(self):
        self.set_state(self.SCHEDULED)

    @set_from(_all_states)
    def shutdown(self):
        self.set_state(self.SHUTDOWN)

    @set_from(_running_states)
    def wait(self):
        self.set_state(self.WAITING)

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

    def is_waiting(self):
        return str(self) in self._waiting_states
