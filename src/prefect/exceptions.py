"""
Prefect-specific exceptions.
"""
from rich.traceback import Traceback


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

    pass


class MissingContextError(PrefectException, RuntimeError):
    """
    Raised when a method is called that requires a task or flow run context to be
    active but one cannot be found.
    """

    pass


class MissingProfileError(PrefectException, ValueError):
    """
    Raised when a profile name does not exist.
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
