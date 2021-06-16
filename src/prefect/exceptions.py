# Import old exceptions for compatibility
from prefect.utilities.exceptions import (
    PrefectError,
    ClientError as ClientError_,
    AuthorizationError as AuthorizationError_,
    StorageError,
)


class PrefectSignal(BaseException):
    """
    Signals inherit from `BaseException` and will not be caught by normal error
    handling. This allows us to bypass typical error handling by raising signals.

    See `prefect.engine.signals` for additional subclasses used for raising state
    transitions.
    """

    pass


class VersionLockMismatchSignal(PrefectSignal):
    """
    Raised when version locking is enabled and a task run state version sent to Cloud
    does not match the version expected by the server.

    This is not backwards compatible with `prefect.utilities.exceptions.VersionLockError`
    """

    pass


class TaskTimeoutSignal(PrefectSignal):
    """
    Raised when a task reaches a timeout limit

    This is not backwards compatible with `prefect.utilities.exceptions.TaskTimeoutError`
    """

    pass


class PrefectException(PrefectError):
    """
    The base exception type for all Prefect related exceptions
    """

    # NOTE: Should be updated to inherit from `Exception` when `PrefectError` is removed

    pass


class ClientError(PrefectException, ClientError_):
    """
    Raised when there is error in Prefect Client <-> Server communication
    """

    pass


class AuthorizationError(ClientError, AuthorizationError_):
    """
    Raised when there is an issue authorizing with Prefect Cloud
    """

    pass


class FlowStorageError(PrefectException, StorageError):
    """
    Raised when there is an error loading a flow from storage
    """

    pass
