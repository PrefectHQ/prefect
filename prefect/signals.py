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
    pass


class FAIL(PrefectSignal):
    pass


class SHUTDOWN(PrefectSignal):
    pass


class SUCCESS(PrefectSignal):

    def __init__(self, result=None):
        self.result = result
        super().__init__()


class WAIT(PrefectSignal):
    pass


class WAIT_FOR_UPSTREAM(PrefectSignal):
    pass
