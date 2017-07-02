class PrefectError(Exception):
    pass


class PrefectSignal(Exception):
    pass


# ------------------------------------------------------------------------------
# These classes are used to signal state changes to Runners
# ------------------------------------------------------------------------------



class RETRY(PrefectSignal):
    """
    Used to indicate that a task should be retried
    """
    pass


class SKIP(PrefectSignal):
    """
    Indicates that a task was skipped. Generally this is considered a "success"
    and downstream tasks will run.
    """
    pass


class FAIL(PrefectSignal):
    """
    Indicates that a task failed.
    """
    pass


class SUCCESS(PrefectSignal):
    """
    Indicates that a task succeeded.
    """

    def __init__(self, *args, result=None, **kwargs):
        self.result = result
        super().__init__(*args, **kwargs)


class DONTRUN(PrefectSignal):
    """
    Aborts the task without changing its state. Used to avoid
    running multiple tasks simultaneously.
    """
    pass


class SHUTDOWN(PrefectSignal):
    """
    Indicates that a task was shutdown externally.
    """
    pass
