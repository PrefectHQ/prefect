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
        return set(k for k in cls.__dict__ if k == k.upper())

    @classmethod
    def pending(cls):
        return set([cls.NONE, cls.PENDING, cls.PENDING_RETRY, cls.SCHEDULED])

    @classmethod
    def running(cls):
        return set([cls.RUNNING])

    @classmethod
    def finished(cls):
        return set([cls.SUCCESS, cls.FAILED, cls.SKIPPED])
