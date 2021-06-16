class PrefectSignal(BaseException):
    """
    Signals inherit from `BaseException` and will not be caught by normal error
    handling. This allows us to bypass typical error handling by raising signals.
    """

    pass


class VersionLockMismatchSignal(PrefectSignal):
    """
    Raised when version locking is enabled and a task run state version sent to Cloud
    does not match the version expected by the server.
    """

    pass


class TaskTimeoutSignal(PrefectSignal):
    """
    Raised when a task reaches a timeout limit
    """

    pass


class PrefectException(Exception):
    """
    The base exception type for all Prefect related exceptions
    """

    pass


class ClientError(PrefectException):
    """
    Raised when there is error in Prefect Client <-> Server communication
    """

    pass


class AuthorizationError(ClientError):
    """
    Raised when there is an issue authorizing with Prefect Cloud
    """

    pass


class FlowStorageError(PrefectException):
    """
    Raised when there is an error loading a flow from storage
    """

    pass
