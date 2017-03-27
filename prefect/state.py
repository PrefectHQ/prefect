class State:
    NONE = 'NONE'
    SCHEDULED = 'SCHEDULED'
    PENDING = 'PENDING'
    PENDING_RETRY = 'PENDING_RETRY'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'

    @classmethod
    def all(cls):
        return set(k for k in cls.__dict__ if k == k.upper())

    @classmethod
    def pending(cls):
        return set([cls.PENDING, cls.PENDING_RETRY, cls.SCHEDULED])

    @classmethod
    def running(cls):
        return set([cls.RUNNING])

    @classmethod
    def finished(cls):
        return set([cls.SUCCESS, cls.FAILED, cls.SKIPPED])
