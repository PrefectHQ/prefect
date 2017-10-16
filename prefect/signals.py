class PrefectError(Exception):
    pass


# ------------------------------------------------------------------------------
# These classes are used to signal state changes when tasks are running
# ------------------------------------------------------------------------------
class PrefectStateException(Exception):

    def __init__(self, result=None, *args, **kwargs):
        self.result = result
        super().__init__(*args, **kwargs)


class RETRY(PrefectStateException):
    """
    Used to indicate that a task should be retried
    """
    pass


class SKIP(PrefectStateException):
    """
    Indicates that a task was skipped.
    """
    pass


class FAIL(PrefectStateException):
    """
    Indicates that a task failed.
    """
    pass


class SUCCESS(PrefectStateException):
    """
    Indicates that a task succeeded.
    """
    pass


class DONTRUN(PrefectStateException):
    """
    Aborts the task without changing its state. Used to avoid
    running multiple tasks simultaneously.
    """
    pass


class SHUTDOWN(PrefectStateException):
    """
    Indicates that a task was shutdown externally.
    """
    pass
