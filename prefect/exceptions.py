class PrefectError(Exception):
    pass

class Retry(PrefectError):
    """
    Used to indicate that a task should be retried
    """
    pass

class Skip(PrefectError):
    pass

class Fail(PrefectError):
    pass

class Success(PrefectError):
    pass

class TriggerFailed(PrefectError):
    """
    Used to indicate that a task's trigger condition was not met
    """
    pass
