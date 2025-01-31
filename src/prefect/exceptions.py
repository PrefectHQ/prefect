"""
Prefect-specific exceptions.
"""

import inspect
import traceback
from collections.abc import Iterable
from types import ModuleType, TracebackType
from typing import TYPE_CHECKING, Any, Callable, Optional

from httpx._exceptions import HTTPStatusError
from pydantic import ValidationError
from typing_extensions import Self

if TYPE_CHECKING:
    from prefect.states import State


def _trim_traceback(
    tb: Optional[TracebackType], remove_modules: Iterable[ModuleType]
) -> Optional[TracebackType]:
    """
    Utility to remove frames from specific modules from a traceback.

    Only frames from the front of the traceback are removed. Once a traceback frame
    is reached that does not originate from `remove_modules`, it is returned.

    Args:
        tb: The traceback to trim.
        remove_modules: An iterable of module objects to remove.

    Returns:
        A traceback, or `None` if all traceback frames originate from an excluded module

    """
    strip_paths = [
        module.__file__ for module in remove_modules if module.__file__ is not None
    ]
    while tb and any(
        module_path in str(tb.tb_frame.f_globals.get("__file__", ""))
        for module_path in strip_paths
    ):
        tb = tb.tb_next

    return tb


def exception_traceback(exc: Exception) -> str:
    """
    Convert an exception to a printable string with a traceback
    """
    tb = traceback.TracebackException.from_exception(exc)
    return "".join(list(tb.format()))


class PrefectException(Exception):
    """
    Base exception type for Prefect errors.
    """


class CrashedRun(PrefectException):
    """
    Raised when the result from a crashed run is retrieved.

    This occurs when a string is attached to the state instead of an exception or if
    the state's data is null.
    """


class FailedRun(PrefectException):
    """
    Raised when the result from a failed run is retrieved and an exception is not
    attached.

    This occurs when a string is attached to the state instead of an exception or if
    the state's data is null.
    """


class CancelledRun(PrefectException):
    """
    Raised when the result from a cancelled run is retrieved and an exception
    is not attached.

    This occurs when a string is attached to the state instead of an exception
    or if the state's data is null.
    """


class PausedRun(PrefectException):
    """
    Raised when the result from a paused run is retrieved.
    """

    def __init__(
        self, *args: Any, state: Optional["State[Any]"] = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.state = state


class UnfinishedRun(PrefectException):
    """
    Raised when the result from a run that is not finished is retrieved.

    For example, if a run is in a SCHEDULED, PENDING, CANCELLING, or RUNNING state.
    """


class MissingFlowError(PrefectException):
    """
    Raised when a given flow name is not found in the expected script.
    """


class UnspecifiedFlowError(PrefectException):
    """
    Raised when multiple flows are found in the expected script and no name is given.
    """


class MissingResult(PrefectException):
    """
    Raised when a result is missing from a state; often when result persistence is
    disabled and the state is retrieved from the API.
    """


class ScriptError(PrefectException):
    """
    Raised when a script errors during evaluation while attempting to load data
    """

    def __init__(
        self,
        user_exc: Exception,
        path: str,
    ) -> None:
        import prefect.utilities.importtools

        message = f"Script at {str(path)!r} encountered an exception: {user_exc!r}"
        super().__init__(message)
        self.user_exc = user_exc

        # Strip script run information from the traceback
        self.user_exc.__traceback__ = _trim_traceback(
            self.user_exc.__traceback__,
            remove_modules=[prefect.utilities.importtools],
        )


class ParameterTypeError(PrefectException):
    """
    Raised when a parameter does not pass Pydantic type validation.
    """

    def __init__(self, msg: str):
        super().__init__(msg)

    @classmethod
    def from_validation_error(cls, exc: ValidationError) -> Self:
        bad_params = [
            f"{'.'.join(str(item) for item in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        msg = "Flow run received invalid parameters:\n - " + "\n - ".join(bad_params)
        return cls(msg)


class ParameterBindError(TypeError, PrefectException):
    """
    Raised when args and kwargs cannot be converted to parameters.
    """

    def __init__(self, msg: str):
        super().__init__(msg)

    @classmethod
    def from_bind_failure(
        cls,
        fn: Callable[..., Any],
        exc: TypeError,
        call_args: tuple[Any, ...],
        call_kwargs: dict[str, Any],
    ) -> Self:
        fn_signature = str(inspect.signature(fn)).strip("()")

        base = f"Error binding parameters for function '{fn.__name__}': {exc}"
        signature = f"Function '{fn.__name__}' has signature '{fn_signature}'"
        received = f"received args: {call_args} and kwargs: {list(call_kwargs.keys())}"
        msg = f"{base}.\n{signature} but {received}."
        return cls(msg)


class SignatureMismatchError(PrefectException, TypeError):
    """Raised when parameters passed to a function do not match its signature."""

    def __init__(self, msg: str):
        super().__init__(msg)

    @classmethod
    def from_bad_params(
        cls, expected_params: list[str], provided_params: list[str]
    ) -> Self:
        msg = (
            f"Function expects parameters {expected_params} but was provided with"
            f" parameters {provided_params}"
        )
        return cls(msg)


class ObjectNotFound(PrefectException):
    """
    Raised when the client receives a 404 (not found) from the API.
    """

    def __init__(
        self,
        http_exc: Exception,
        help_message: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.http_exc = http_exc
        self.help_message = help_message
        super().__init__(help_message, *args, **kwargs)

    def __str__(self) -> str:
        return self.help_message or super().__str__()


class ObjectAlreadyExists(PrefectException):
    """
    Raised when the client receives a 409 (conflict) from the API.
    """

    def __init__(self, http_exc: Exception, *args: Any, **kwargs: Any) -> None:
        self.http_exc = http_exc
        super().__init__(*args, **kwargs)


class UpstreamTaskError(PrefectException):
    """
    Raised when a task relies on the result of another task but that task is not
    'COMPLETE'
    """


class MissingContextError(PrefectException, RuntimeError):
    """
    Raised when a method is called that requires a task or flow run context to be
    active but one cannot be found.
    """


class MissingProfileError(PrefectException, ValueError):
    """
    Raised when a profile name does not exist.
    """


class ReservedArgumentError(PrefectException, TypeError):
    """
    Raised when a function used with Prefect has an argument with a name that is
    reserved for a Prefect feature
    """


class InvalidNameError(PrefectException, ValueError):
    """
    Raised when a name contains characters that are not permitted.
    """


class PrefectSignal(BaseException):
    """
    Base type for signal-like exceptions that should never be caught by users.
    """


class Abort(PrefectSignal):
    """
    Raised when the API sends an 'ABORT' instruction during state proposal.

    Indicates that the run should exit immediately.
    """


class Pause(PrefectSignal):
    """
    Raised when a flow run is PAUSED and needs to exit for resubmission.
    """

    def __init__(
        self, *args: Any, state: Optional["State[Any]"] = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.state = state


class ExternalSignal(BaseException):
    """
    Base type for external signal-like exceptions that should never be caught by users.
    """


class TerminationSignal(ExternalSignal):
    """
    Raised when a flow run receives a termination signal.
    """

    def __init__(self, signal: int):
        self.signal = signal


class PrefectHTTPStatusError(HTTPStatusError):
    """
    Raised when client receives a `Response` that contains an HTTPStatusError.

    Used to include API error details in the error messages that the client provides users.
    """

    @classmethod
    def from_httpx_error(cls: type[Self], httpx_error: HTTPStatusError) -> Self:
        """
        Generate a `PrefectHTTPStatusError` from an `httpx.HTTPStatusError`.
        """
        try:
            details = httpx_error.response.json()
        except Exception:
            details = None

        error_message, *more_info = str(httpx_error).split("\n")

        if details:
            message_components = [error_message, f"Response: {details}", *more_info]
        else:
            message_components = [error_message, *more_info]

        new_message = "\n".join(message_components)

        return cls(
            new_message, request=httpx_error.request, response=httpx_error.response
        )


class MappingLengthMismatch(PrefectException):
    """
    Raised when attempting to call Task.map with arguments of different lengths.
    """


class MappingMissingIterable(PrefectException):
    """
    Raised when attempting to call Task.map with all static arguments
    """


class BlockMissingCapabilities(PrefectException):
    """
    Raised when a block does not have required capabilities for a given operation.
    """


class ProtectedBlockError(PrefectException):
    """
    Raised when an operation is prevented due to block protection.
    """


class InvalidRepositoryURLError(PrefectException):
    """Raised when an incorrect URL is provided to a GitHub filesystem block."""


class InfrastructureError(PrefectException):
    """
    A base class for exceptions related to infrastructure blocks
    """


class InfrastructureNotFound(PrefectException):
    """
    Raised when infrastructure is missing, likely because it has exited or been
    deleted.
    """


class InfrastructureNotAvailable(PrefectException):
    """
    Raised when infrastructure is not accessible from the current machine. For example,
    if a process was spawned on another machine it cannot be managed.
    """


class NotPausedError(PrefectException):
    """Raised when attempting to unpause a run that isn't paused."""


class FlowPauseTimeout(PrefectException):
    """Raised when a flow pause times out"""


class FlowRunWaitTimeout(PrefectException):
    """Raised when a flow run takes longer than a given timeout"""


class PrefectImportError(ImportError):
    """
    An error raised when a Prefect object cannot be imported due to a move or removal.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class SerializationError(PrefectException):
    """
    Raised when an object cannot be serialized.
    """


class ConfigurationError(PrefectException):
    """
    Raised when a configuration is invalid.
    """


class ProfileSettingsValidationError(PrefectException):
    """
    Raised when a profile settings are invalid.
    """

    def __init__(self, errors: list[tuple[Any, ValidationError]]) -> None:
        self.errors = errors


class HashError(PrefectException):
    """Raised when hashing objects fails"""
