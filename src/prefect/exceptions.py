"""
Prefect-specific exceptions.
"""
from types import ModuleType, TracebackType
from typing import TYPE_CHECKING, Iterable, Optional, Type

from httpx._exceptions import HTTPStatusError
from rich.traceback import Traceback
from typing_extensions import Self

import prefect

if TYPE_CHECKING:
    from prefect.deployments import DeploymentSpec


def _trim_traceback(
    tb: TracebackType, remove_modules: Iterable[ModuleType]
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
    strip_paths = [module.__file__ for module in remove_modules]

    while tb and any(
        module_path in str(tb.tb_frame.f_globals.get("__file__", ""))
        for module_path in strip_paths
    ):
        tb = tb.tb_next

    return tb


class PrefectException(Exception):
    """
    Base exception type for Prefect errors.
    """


class MissingFlowError(PrefectException):
    """
    Raised when a given flow name is not found in the expected script.
    """


class UnspecifiedFlowError(PrefectException):
    """
    Raised when multiple flows are found in the expected script and no name is given.
    """


class MissingDeploymentError(PrefectException):
    """
    Raised when a given deployment name is not found in the expected script.
    """


class UnspecifiedDeploymentError(PrefectException):
    """
    Raised when multiple deployments are found in the expected script and no name is given.
    """


class DeploymentValidationError(PrefectException, ValueError):
    """
    Raised when a value for a specification is incorrect
    """

    def __init__(self, message: str, deployment: "DeploymentSpec") -> None:
        self.message = message
        self.deployment = deployment

    def __str__(self) -> str:
        # Attempt to recover a helpful name
        if self.deployment.flow_name and self.deployment.name:
            identifier = f"{self.deployment.flow_name}/{self.deployment.name}"
        elif self.deployment.name:
            identifier = f"{self.deployment.name}"
        elif self.deployment._source:
            identifier = f"{str(self.deployment._source['file'])!r}, line {self.deployment._source['line']}"
        else:
            identifier = ""

        if identifier:
            identifier = f" {identifier!r}"

        return f"Deployment specification{identifier} failed validation: {self.message}"


class ScriptError(PrefectException):
    """
    Raised when a script errors during evaluation while attempting to load data
    """

    def __init__(
        self,
        user_exc: Exception,
        path: str,
    ) -> None:
        message = f"Script at {str(path)!r} encountered an exception"
        super().__init__(message)
        self.user_exc = user_exc

        import runpy

        # Strip script run information from the traceback
        self.user_exc.__traceback__ = _trim_traceback(
            self.user_exc.__traceback__,
            remove_modules=[prefect.utilities.importtools, runpy],
        )


class FlowScriptError(PrefectException):
    """
    Raised when a script errors during evaluation while attempting to load a flow.
    """

    def __init__(
        self,
        user_exc: Exception,
        script_path: str,
    ) -> None:
        message = f"Flow script at {script_path!r} encountered an exception"
        super().__init__(message)

        self.user_exc = user_exc

    def rich_user_traceback(self, **kwargs):
        trace = Traceback.extract(
            type(self.user_exc),
            self.user_exc,
            self.user_exc.__traceback__.tb_next.tb_next.tb_next.tb_next,
        )
        return Traceback(trace, **kwargs)


class ParameterTypeError(PrefectException):
    """
    Raised when a value passed as a flow parameter does not pass validation.
    """


class ObjectNotFound(PrefectException):
    """
    Raised when the client receives a 404 (not found) from the API.
    """

    def __init__(self, http_exc: Exception, *args, **kwargs):
        self.http_exc = http_exc
        super().__init__(*args, **kwargs)


class ObjectAlreadyExists(PrefectException):
    """
    Raised when the client receives a 409 (conflict) from the API.
    """

    def __init__(self, http_exc: Exception, *args, **kwargs):
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


class PrefectHTTPStatusError(HTTPStatusError):
    """
    Raised when client receives a `Response` that contains an HTTPStatusError.

    Used to include API error details in the error messages that the client provides users.
    """

    @classmethod
    def from_httpx_error(cls: Type[Self], httpx_error: HTTPStatusError) -> Self:
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
