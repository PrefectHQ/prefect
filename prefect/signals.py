class PrefectError(Exception):
    pass


class PrefectSignal(Exception):
    pass


# ------------------------------------------------------------------------------
# These classes are used to signal state changes to TaskRunners
# ------------------------------------------------------------------------------


class TaskError(PrefectSignal):

    def __init__(self, result=None, msg=''):
        self.result = result
        super.__init__(msg)


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

    def __init__(self, result=None):
        self.result = result
        super().__init__()


class WAIT(PrefectSignal):
    """
    Indicates that a Task is waiting to proceed. Task execution will halt
    and the task / flow will need to be rerun to resume.
    """
    pass


class WAIT_FOR_UPSTREAM(PrefectSignal):
    """
    Indicates that an upstream task is in a WAITING state.
    """
    pass


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
