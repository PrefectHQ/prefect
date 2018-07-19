class PrefectError(Exception):
    pass


class ContextError(KeyError, PrefectError):
    pass


class SerializationError(PrefectError):
    pass


# ------------------------------------------------------------------------------
# These classes are used to signal state changes when tasks or flows are running
# ------------------------------------------------------------------------------


class PrefectStateException(Exception):
    def __init__(self, *args, result=None, **kwargs) -> None:  # type: ignore
        self.result = result
        super().__init__(*args, **kwargs)


class FAIL(PrefectStateException):
    """
    Indicates that a task failed.
    """


class TRIGGERFAIL(FAIL):
    """
    Indicates that a task trigger failed.
    """


class SUCCESS(PrefectStateException):
    """
    Indicates that a task succeeded.
    """


class RETRY(PrefectStateException):
    """
    Used to indicate that a task should be retried
    """


class SKIP(PrefectStateException):
    """
    Indicates that a task was skipped. By default, downstream tasks will
    act as if skipped tasks succeeded.
    """


class SKIP_DOWNSTREAM(PrefectStateException):
    """
    Indicates that a task *and all downstream tasks* should be skipped.

    Downstream tasks will still evaluate their trigger functions, giving them
    a chance to interrupt the chain, but if the trigger fails they will also
    enter a SKIP_DOWNSTREAM state.
    """


class DONTRUN(PrefectStateException):
    """
    Indicates that a task should not run and its state should not be modified.
    """
