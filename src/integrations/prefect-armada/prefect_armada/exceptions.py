"""Module to define common exceptions within `prefect_armada`."""

from __future__ import annotations

import grpc


class ArmadaError(Exception):
    """Base exception for all errors raised by `prefect_armada`."""


class ArmadaJobDefinitionError(ArmadaError):
    """An exception for when an Armada job definition is invalid."""


class ArmadaJobFailedError(ArmadaError):
    """An exception for when an Armada job fails."""


class ArmadaResourceNotFoundError(ArmadaError):
    """An exception for when an Armada resource cannot be found by a client."""


class ArmadaJobTimeoutError(ArmadaError):
    """An exception for when an Armada job times out."""


def rpc_status_code(exc: BaseException) -> grpc.StatusCode | None:
    """Returns the gRPC status code for an exception, if it has one.

    Both `grpc.RpcError` (sync) and `grpc.aio.AioRpcError` (async) expose a
    `code()` method, but neither is guaranteed to be present on an arbitrary
    exception, so this helper degrades to `None`.

    Args:
        exc: The exception to inspect.

    Returns:
        The gRPC status code, or `None` if the exception does not have one.
    """
    code = getattr(exc, "code", None)
    if not callable(code):
        return None
    try:
        status_code = code()
    except NotImplementedError:
        return None
    return status_code if isinstance(status_code, grpc.StatusCode) else None


def rpc_details(exc: BaseException) -> str:
    """Returns the gRPC details string for an exception, or an empty string.

    Args:
        exc: The exception to inspect.

    Returns:
        The `details()` of the exception, or an empty string when unavailable.
    """
    details = getattr(exc, "details", None)
    if not callable(details):
        return ""
    try:
        return details() or ""
    except NotImplementedError:
        return ""
