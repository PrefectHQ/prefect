import pytest

from prefect.utilities.exceptions import (
    PrefectError,
    ClientError as OldClientError,
    AuthorizationError as OldAuthorizationError,
    StorageError,
    SerializationError,
    TaskTimeoutError,
    ContextError,
    VersionLockError,
)
from prefect.exceptions import (
    PrefectException,
    ClientError,
    AuthorizationError,
    VersionLockMismatchSignal,
    TaskTimeoutSignal,
    FlowStorageError,
)


@pytest.mark.parametrize(
    "old_err,new_err",
    [
        (PrefectError, PrefectException),
        (OldClientError, ClientError),
        (OldAuthorizationError, AuthorizationError),
        (StorageError, FlowStorageError),
    ],
)
def test_new_exceptions_can_be_caught_by_old(old_err, new_err):
    raises = False
    try:
        raise new_err("message")
    except old_err as exc:
        assert str(exc) == "message"
        raises = True

    assert raises


@pytest.mark.parametrize(
    "err_cls",
    [
        PrefectError,
        OldClientError,
        OldAuthorizationError,
        SerializationError,
        TaskTimeoutError,
        StorageError,
        VersionLockError,
        ContextError,
        VersionLockError,
    ],
)
def test_old_exceptions_warn_on_creation(err_cls):
    with pytest.warns(UserWarning, match=f"prefect.utilities.exceptions"):
        err_cls()


@pytest.mark.parametrize(
    "err_cls",
    [
        PrefectException,
        ClientError,
        AuthorizationError,
        FlowStorageError,
        VersionLockMismatchSignal,
        TaskTimeoutSignal,
    ],
)
def test_new_exceptions_do_not_warn_on_creation(err_cls):
    with pytest.warns(None) as warnings:
        err_cls()
    if warnings:
        raise AssertionError(
            "Warnings raised:\n" + "\n".join([str(w) for w in warnings])
        )
