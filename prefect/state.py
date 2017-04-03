import logging
import transitions
transitions.logger.setLevel(logging.WARNING)


class State:
    NONE = 0
    SCHEDULED = 1
    PENDING = 2
    PENDING_RETRY = 3
    RUNNING = 4
    SUCCESS = 5
    FAILED = 6
    SKIPPED = 7
    WAITING_FOR_SUBTASKS = 8

    @classmethod
    def all_states(cls):
        return set(
            [
                cls.NONE,
                cls.SCHEDULED,
                cls.PENDING,
                cls.PENDING_RETRY,
                cls.RUNNING,
                cls.SUCCESS,
                cls.FAILED,
                cls.SKIPPED,
                cls.WAITING_FOR_SUBTASKS,
            ])

    @classmethod
    def started_states(cls):
        return cls.all_states().difference([cls.NONE])

    @classmethod
    def pending_states(cls):
        return set([cls.NONE, cls.PENDING, cls.PENDING_RETRY, cls.SCHEDULED])

    @classmethod
    def running_states(cls):
        return set([cls.RUNNING, cls.WAITING_FOR_SUBTASKS])

    @classmethod
    def finished_states(cls):
        return set([cls.SUCCESS, cls.FAILED, cls.SKIPPED])

    @classmethod
    def skipped_states(cls):
        return set([cls.SKIPPED])

    @classmethod
    def successful_states(cls):
        return set([cls.SUCCESS, cls.SKIPPED])

    @classmethod
    def failed_states(cls):
        return set([cls.FAILED])

    def __init__(self, initial_state=None):
        if initial_state is None:
            initial_state = self.NONE

        self._fsm = transitions.Machine(
            model=self,
            states=list(self.all_states()),
            initial=initial_state,)

        self._fsm.add_transition(
            trigger='succeed',
            source=list(self.pending_states()) + list(self.running_states()),
            dest=self.SUCCESS,)

        self._fsm.add_transition(
            trigger='fail',
            source=list(self.pending_states()) + list(self.running_states()),
            dest=self.FAILED,)

        self._fsm.add_transition(
            trigger='skip',
            source=list(self.pending_states()),
            dest=self.SKIPPED,)

        self._fsm.add_transition(
            trigger='retry',
            source=list(self.finished_states()),
            dest=self.PENDING_RETRY,)

        self._fsm.add_transition(
            trigger='schedule',
            source=list(self.pending_states()),
            dest=self.SCHEDULED,)

        self._fsm.add_transition(
            trigger='start',
            source=list(self.pending_states()),
            dest=self.RUNNING,)

        self._fsm.add_transition(
            trigger='wait_for_subtasks',
            source=list(self.running_states()),
            dest=self.WAITING_FOR_SUBTASKS,)

        self._fsm.add_transition(
            trigger='resume',
            source=self.WAITING_FOR_SUBTASKS,
            dest=self.RUNNING,)

        self._fsm.add_transition(
            trigger='clear', source=list(self.all_states()), dest=self.NONE)

        self._fsm.add_transition(
            trigger='pending',
            source=[self.NONE],
            dest=self.PENDING,)

    def __eq__(self, other):
        return getattr(self, 'state', None) == other

    def __str__(self):
        return self.state

    def __repr__(self):
        return 'State({})'.format(self.state)

    def is_started(self):
        return str(self) in self.started_states()

    def is_pending(self):
        return str(self) in self.pending_states()

    def is_running(self):
        return str(self) in self.running_states()

    def is_finished(self):
        return str(self) in self.finished_states()

    def is_successful(self):
        return str(self) in self.successful_states()

    def is_skipped(self):
        return str(self) in self.skipped_states()

    def is_failed(self):
        return str(self) in self.failed_states()
