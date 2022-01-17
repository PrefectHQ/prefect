"""
Prefect-specific exceptions.
"""
from rich.traceback import Traceback
import prefect
from typing import Iterable
from types import ModuleType, TracebackType


def _trim_traceback(tb: TracebackType, remove_modules: Iterable[ModuleType]):
    strip_paths = [module.__file__ for module in remove_modules]

    while any(
        module_path in str(tb.tb_frame.f_globals["__file__"])
        for module_path in strip_paths
    ):
        tb = tb.tb_next

    return tb


class PrefectException(Exception):
    """
    Base exception type for Prefect errors.
    """

    pass


class MissingFlowError(PrefectException):
    """
    Raised when a given flow name is not found in the expected script.
    """

    pass


class UnspecifiedFlowError(PrefectException):
    """
    Raised when multiple flows are found in the expected script and no name is given.
    """

    pass


class MissingDeploymentError(PrefectException):
    """
    Raised when a given deployment name is not found in the expected script.
    """

    pass


class UnspecifiedDeploymentError(PrefectException):
    """
    Raised when multiple deployments are found in the expected script and no name is given.
    """

    pass


class SpecValidationError(PrefectException, ValueError):
    """
    Raised when a value for a specification is inorrect
    """

    pass


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

    pass


class UpstreamTaskError(PrefectException):
    """
    Raised when a task relies on the result of another task but that task is not
    'COMPLETE'
    """

    pass


class ReservedArgumentError(PrefectException, TypeError):
    """
    Raised when a function used with Prefect has an argument with a name that is
    reserved for a Prefect feature
    """

    pass


class PrefectSignal(BaseException):
    """
    Base type for signal-like exceptions that should never be caught by users.
    """

    pass


class Abort(PrefectSignal):
    """
    Raised when the API sends an 'ABORT' instruction during state proposal.

    Indicates that the run should exit immediately.
    """

    pass
