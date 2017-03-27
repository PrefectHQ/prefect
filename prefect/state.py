import transitions


class State:
    NONE = 'none'
    SCHEDULED = 'scheduled'
    PENDING = 'pending'
    PENDING_RETRY = 'pending_retry'
    RUNNING = 'running'
    SUCCESS = 'success'
    FAILED = 'failed'
    SKIPPED = 'skipped'

    @classmethod
    def all(cls):
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
            ])

    @classmethod
    def pending(cls):
        return set([cls.NONE, cls.PENDING, cls.PENDING_RETRY, cls.SCHEDULED])

    @classmethod
    def running(cls):
        return set([cls.RUNNING])

    @classmethod
    def finished(cls):
        return set([cls.SUCCESS, cls.FAILED, cls.SKIPPED])

    def __init__(self, initial_state=None):
        if initial_state is None:
            initial_state = self.NONE

        self._fsm = transitions.Machine(
            model=self,
            states=list(self.all()),
            initial=initial_state,)

        self._fsm.add_transition(
            trigger='succeed',
            source=list(self.pending()) + list(self.running()),
            dest=self.SUCCESS,)

        self._fsm.add_transition(
            trigger='fail',
            source=list(self.pending()) + list(self.running()),
            dest=self.FAILED,)

        self._fsm.add_transition(
            trigger='skip',
            source=list(self.pending()),
            dest=self.SKIPPED,)

        self._fsm.add_transition(
            trigger='retry',
            source=list(self.finished()),
            dest=self.PENDING_RETRY,)

        self._fsm.add_transition(
            trigger='schedule',
            source=list(self.pending()),
            dest=self.SCHEDULED,)

        self._fsm.add_transition(
            trigger='start',
            source=list(self.pending()),
            dest=self.RUNNING,)

        self._fsm.add_transition(
            trigger='clear',
            source=list(self.all()),
            dest=self.NONE
        )

    def __eq__(self, other):
        return getattr(self, 'state', None) == other

    def __str__(self):
        return self.state
