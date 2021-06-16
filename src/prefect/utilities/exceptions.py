"""
The exception types in this module have been deprecated in favor of `prefect.exceptions`

They all inherit from the new exception types for backwards compatibility for now

Users should not be using these directly but we leave these for a version in case they
are being used in try/except clauses
"""

# Import new exceptions for compat inheritance
from prefect.exceptions import (
    PrefectException,
    TaskTimeoutSignal,
    ClientError as ClientError_,
    VersionLockMismatchSignal,
    AuthorizationError as AuthorizationError_,
    FlowStorageError,
)


class PrefectError(PrefectException):
    pass


class TaskTimeoutError(PrefectError, TaskTimeoutSignal):
    pass


class ContextError(KeyError, PrefectError):
    pass


class SerializationError(PrefectError):
    pass


class PrefectWarning(UserWarning):
    pass


class ClientError(PrefectError, ClientError_):
    pass


class VersionLockError(PrefectError, VersionLockMismatchSignal):
    pass


class AuthorizationError(ClientError, AuthorizationError_):
    pass


class StorageError(PrefectError, FlowStorageError):
    pass
