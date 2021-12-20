class PrefectSignal(BaseException):
    """
    Signals inherit from `BaseException` and will not be caught by normal error
    handling. This allows us to bypass typical error handling by raising signals.

    See `prefect.engine.signals` for additional subclasses used for raising state
    transitions.

    Args:
        - message: A message with additional information about the error
    """

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class VersionLockMismatchSignal(PrefectSignal):
    """
    Raised when version locking is enabled and a task run state version sent to Cloud
    does not match the version expected by the server.

    This is not backwards compatible with `prefect.utilities.exceptions.VersionLockError`

    Args:
        - message: A message with additional information about the error
    """

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class TaskTimeoutSignal(PrefectSignal):
    """
    Raised when a task reaches a timeout limit

    This is not backwards compatible with `prefect.utilities.exceptions.TaskTimeoutError`

    Args:
        - message: A message with additional information about the error
    """

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class PrefectException(Exception):
    """
    The base exception type for all Prefect related exceptions

    Args:
        - message: A message with additional information about the error
    """

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class ClientError(PrefectException):
    """
    Raised when there is error in Prefect Client <-> Server communication

    Args:
        - message: A message with additional information about the error
    """

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class ObjectNotFoundError(ClientError):
    """
    Raised when an object is not found on the Server

    Args:
        - message: A message with additional information about the error
    """

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class AuthorizationError(ClientError):
    """
    Raised when there is an issue authorizing with Prefect Cloud

    Args:
        - message: A message with additional information about the error
    """

    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class FlowStorageError(PrefectException):
    """
    Raised when there is an error loading a flow from storage

    Args:
        - message: A message with additional information about the error
    """

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
