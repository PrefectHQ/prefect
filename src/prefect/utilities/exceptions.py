"""
The exception types in this module have been deprecated in favor of `prefect.exceptions`

They all inherit from the new exception types for backwards compatibility for now

Users should not be using these directly but we leave these for a version in case they
are being used in try/except clauses
"""

import warnings

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
    def __init__(self, *args: object) -> None:
        warnings.warn(
            "`prefect.utilities.exceptions.PrefectError` has been moved to "
            "`prefect.exceptions.PrefectException` and will be removed in a future "
            "release. Please update your imports.",
            stacklevel=2,
        )
        super().__init__(*args)


class TaskTimeoutError(PrefectError, TaskTimeoutSignal):
    def __init__(self, *args: object) -> None:
        warnings.warn(
            "`prefect.utilities.exceptions.PrefectError` has been moved to "
            "`prefect.exceptions.PrefectException` and will be removed in a future "
            "release. Please update your imports.",
            stacklevel=2,
        )
        super().__init__(*args)


class ContextError(KeyError, PrefectError):
    def __init__(self, *args: object) -> None:
        warnings.warn(
            "`prefect.utilities.exceptions.PrefectWarning` has been deprecated "
            "and will be removed in a future release.",
            stacklevel=2,
        )
        super().__init__(*args)


class SerializationError(PrefectError):
    def __init__(self, *args: object) -> None:
        warnings.warn(
            "`prefect.utilities.exceptions.PrefectWarning` has been deprecated "
            "and will be removed in a future release.",
            stacklevel=2,
        )
        super().__init__(*args)


class PrefectWarning(UserWarning):
    def __init__(self, *args: object) -> None:
        warnings.warn(
            "`prefect.utilities.exceptions.PrefectWarning` has been deprecated "
            "and will be removed in a future release.",
            stacklevel=2,
        )
        super().__init__(*args)


class ClientError(PrefectError, ClientError_):
    def __init__(self, *args: object) -> None:
        warnings.warn(
            "`prefect.utilities.exceptions.ClientError` has been moved to "
            "`prefect.exceptions.ClientError` and will be removed in a future "
            "release. Please update your imports.",
            stacklevel=2,
        )
        super().__init__(*args)


class VersionLockError(PrefectError, VersionLockMismatchSignal):
    def __init__(self, *args: object) -> None:
        warnings.warn(
            "`prefect.utilities.exceptions.VersionLockError` has been moved to "
            "`prefect.exceptions.VersionLockMismatchSignal` and will be removed in a "
            "future release. Please update your imports.",
            stacklevel=2,
        )
        super().__init__(*args)


class AuthorizationError(ClientError, AuthorizationError_):
    def __init__(self, *args: object) -> None:
        warnings.warn(
            "`prefect.utilities.exceptions.AuthorizationError` has been moved to "
            "`prefect.exceptions.AuthorizationError` and will be removed in a future "
            "release. Please update your imports.",
            stacklevel=2,
        )
        super().__init__(*args)


class StorageError(PrefectError, FlowStorageError):
    def __init__(self, *args: object) -> None:
        warnings.warn(
            "`prefect.utilities.exceptions.StorageError` has been moved to "
            "`prefect.exceptions.FlowStorageError` and will be removed in a future "
            "release. Please update your imports.",
            stacklevel=2,
        )
        super().__init__(*args)
