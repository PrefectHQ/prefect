"""
The exception types in this module have been deprecated in favor of `prefect.exceptions`

Users should not be using these directly but we leave these for a version in case they
are being used in try/except clauses
"""

import warnings


class PrefectError(Exception):
    def __init__(self, *args: object) -> None:
        if type(self) == PrefectError:
            warnings.warn(
                "`prefect.utilities.exceptions.PrefectError` has been moved to "
                "`prefect.exceptions.PrefectException` and will be removed in a future "
                "release. Please update your imports.",
                stacklevel=2,
            )
        super().__init__(*args)


class TaskTimeoutError(PrefectError):
    def __init__(self, *args: object) -> None:
        warnings.warn(
            "`prefect.utilities.exceptions.TaskTimeoutError` has been moved to "
            "`prefect.exceptions.TaskTimeoutSignal` and will be removed in a future "
            "release. Please update your imports.",
            stacklevel=2,
        )
        super().__init__(*args)


class ContextError(KeyError, PrefectError):
    def __init__(self, *args: object) -> None:
        warnings.warn(
            "`prefect.utilities.exceptions.ContextError` has been deprecated "
            "and will be removed in a future release.",
            stacklevel=2,
        )
        super().__init__(*args)


class SerializationError(PrefectError):
    def __init__(self, *args: object) -> None:
        warnings.warn(
            "`prefect.utilities.exceptions.SerializationError` has been deprecated "
            "and will be removed in a future release.",
            stacklevel=2,
        )
        super().__init__(*args)


class PrefectWarning(UserWarning):
    def __init__(self, *args: object) -> None:
        if type(self) == PrefectWarning:
            warnings.warn(
                "`prefect.utilities.exceptions.PrefectWarning` has been deprecated "
                "and will be removed in a future release.",
                stacklevel=2,
            )
        super().__init__(*args)


class ClientError(PrefectError):
    def __init__(self, *args: object) -> None:
        if type(self) == ClientError:
            warnings.warn(
                "`prefect.utilities.exceptions.ClientError` has been moved to "
                "`prefect.exceptions.ClientError` and will be removed in a future "
                "release. Please update your imports.",
                stacklevel=2,
            )
        super().__init__(*args)


class VersionLockError(PrefectError):
    def __init__(self, *args: object) -> None:
        warnings.warn(
            "`prefect.utilities.exceptions.VersionLockError` has been moved to "
            "`prefect.exceptions.VersionLockMismatchSignal` and will be removed in a "
            "future release. Please update your imports.",
            stacklevel=2,
        )
        super().__init__(*args)


class AuthorizationError(ClientError):
    def __init__(self, *args: object) -> None:
        if type(self) == AuthorizationError:
            warnings.warn(
                "`prefect.utilities.exceptions.AuthorizationError` has been moved to "
                "`prefect.exceptions.AuthorizationError` and will be removed in a "
                "future release. Please update your imports.",
                stacklevel=2,
            )
        super().__init__(*args)


class StorageError(PrefectError):
    def __init__(self, *args: object) -> None:
        if type(self) == StorageError:
            warnings.warn(
                "`prefect.utilities.exceptions.StorageError` has been moved to "
                "`prefect.exceptions.FlowStorageError` and will be removed in a future "
                "release. Please update your imports.",
                stacklevel=2,
            )
        super().__init__(*args)
