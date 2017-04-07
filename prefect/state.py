import logging
import transitions
import prefect
transitions.logger.setLevel(logging.WARNING)


class Transition:
    """
    Helper class for building transition dictionaries.
    Adds autocomplete/arg checking.
    """

    def __init__(self, trigger, source, dest):
        self.trigger = trigger
        if isinstance(source, str):
            source = [source]
        self.source = list(source)
        self.dest = dest

    def as_dict(self):
        return {
            'trigger': self.trigger,
            'source': self.source,
            'dest': self.dest
        }


class State:

    _default_state = ''
    _all_states = set([])
    _transitions = []

    def __init__(self, initial_state=None, after_state_change=None):
        if not hasattr(type(self), '_default_state'):
            'State classes require a `_default_state` state class attribute.'
        if not hasattr(type(self), '_all_states'):
            'State classes require an `_all_states` class attribute.'
        if not hasattr(type(self), '_transitions'):
            'State classes require an `_transitions` class attribute.'

        if initial_state is None:
            initial_state = self._default_state

        self._fsm = transitions.Machine(
            model=self,
            states=list(self._all_states),
            transitions=[t.as_dict() for t in self._transitions],
            initial=initial_state,
            auto_transitions=False,
            after_state_change=after_state_change)

    def __eq__(self, other):
        return hasattr(self, 'state') and getattr(self, 'state') == other

    def __str__(self):
        return self.state

    def __repr__(self):
        return '{}({})'.format(type(self).__name__, self.state)


class FlowState(State):
    ACTIVE = 'ACTIVE'
    PAUSED = 'PAUSED'
    ARCHIVED = 'ARCHIVED'

    if prefect.config.get('flows', 'default_active'):
        _default_state = ACTIVE
    else:
        _default_state = PAUSED

    _all_states = set([
        ACTIVE,
        PAUSED,
        ARCHIVED,
    ])

    _unarchived_states = set([ACTIVE, PAUSED])

    _transitions = [
        Transition(trigger='activate', source=PAUSED, dest=ACTIVE),
        Transition(trigger='pause', source=ACTIVE, dest=PAUSED),
        Transition(trigger='archive', source=_unarchived_states, dest=ARCHIVED),
        Transition(trigger='unarchive', source=ARCHIVED, dest=PAUSED)
    ]


class TaskRunState(State):

    PENDING = _default_state = 'PENDING'
    PENDING_RETRY = 'PENDING_RETRY'
    SCHEDULED = 'SCHEDULED'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'
    WAITING_FOR_SUBTASKS = 'WAITING_FOR_SUBTASKS'

    _all_states = set(
        [
            SCHEDULED,
            PENDING,
            PENDING_RETRY,
            RUNNING,
            SUCCESS,
            FAILED,
            SKIPPED,
            WAITING_FOR_SUBTASKS,
        ])
    _started_states = set([RUNNING, SUCCESS, FAILED, WAITING_FOR_SUBTASKS])
    _pending_states = set([PENDING, PENDING_RETRY, SCHEDULED])
    _running_states = set([RUNNING, WAITING_FOR_SUBTASKS])
    _finished_states = set([SUCCESS, FAILED, SKIPPED])
    _skipped_states = set([SKIPPED])
    _successful_states = set([SUCCESS, SKIPPED])
    _failed_states = set([FAILED])

    _transitions = [
        Transition(
            trigger='start',
            source=_pending_states,
            dest=RUNNING,),
        Transition(
            trigger='succeed',
            source=_pending_states.union(_running_states),
            dest=SUCCESS,),
        Transition(
            trigger='fail',
            source=_pending_states.union(_running_states),
            dest=FAILED,),
        Transition(
            trigger='skip',
            source=_pending_states,
            dest=SKIPPED,),
        Transition(
            trigger='retry',
            source=_finished_states,
            dest=PENDING_RETRY,),
        Transition(
            trigger='schedule',
            source=_pending_states,
            dest=SCHEDULED,),
        Transition(
            trigger='wait_for_subtasks',
            source=_running_states,
            dest=WAITING_FOR_SUBTASKS,),
        Transition(
            trigger='resume_after_subtasks',
            source=[WAITING_FOR_SUBTASKS],
            dest=RUNNING,),
    ]

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


class FlowRunState(State):
    SCHEDULED = 'SCHEDULED'
    PENDING = _default_state = 'PENDING'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'

    _all_states = set([
        SCHEDULED,
        PENDING,
        RUNNING,
        SUCCESS,
        FAILED,
    ])
    _pending_states = set([SCHEDULED, PENDING])

    _transitions = [
        Transition(
            trigger='start',
            source=_pending_states,
            dest=RUNNING,),
        Transition(
            trigger='schedule',
            source=_pending_states,
            dest=SCHEDULED,),
        Transition(
            trigger='succeed',
            source=_pending_states.union([RUNNING]),
            dest=SUCCESS,),
        Transition(
            trigger='fail',
            source=_pending_states.union([RUNNING]),
            dest=FAILED,),
    ]
