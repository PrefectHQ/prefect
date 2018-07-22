
"""
These classes are used to signal state changes when tasks or flows are running
"""

from prefect.utilities.exceptions import PrefectError
from prefect.engine import state


class PrefectStateSignal(PrefectError):
    _state_cls = state.State

    def __init__(self, message=None, data=None, **kwargs) -> None:  # type: ignore
        self.data = data
        self.message = self
        self.state = self._state_cls(data=data, message=message)
        super().__init__(message, **kwargs)


class FAIL(PrefectStateSignal):
    """
    Indicates that a task failed.
    """

    _state_cls = state.Failed


class TRIGGERFAIL(FAIL):
    """
    Indicates that a task trigger failed.
    """

    _state_cls = state.TriggerFailed


class SUCCESS(PrefectStateSignal):
    """
    Indicates that a task succeeded.
    """

    _state_cls = state.Success


class RETRY(PrefectStateSignal):
    """
    Used to indicate that a task should be retried
    """

    _state_cls = state.Retrying



class SKIP(PrefectStateSignal):
    """
    Indicates that a task was skipped. By default, downstream tasks will
    act as if skipped tasks succeeded.
    """

    _state_cls = state.Skipped


class DONTRUN(PrefectStateSignal):
    """
    Indicates that a task should not run and its state should not be modified.
    """
