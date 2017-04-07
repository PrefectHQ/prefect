class PrefectError(Exception):
    pass

# ------------------------------------------------------------------------------
# These classes are used to signal state changes to TaskRunners
# ------------------------------------------------------------------------------

class DONOTHING(PrefectError):
    pass

class RETRY(PrefectError):
    """
    Used to indicate that a task should be retried
    """
    pass

class SKIP(PrefectError):
    pass

class FAIL(PrefectError):
    pass

class SUCCESS(PrefectError):
    pass
