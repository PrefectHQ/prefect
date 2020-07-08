"""
These Exceptions, when raised, are used to signal state changes when tasks or flows are
running. Signals are used in TaskRunners and FlowRunners as a way of communicating the changes
in states.
"""

from typing import Type

from prefect.engine import state
from prefect.utilities.exceptions import PrefectError


def signal_from_state(state: state.State) -> Type["PrefectStateSignal"]:
    """
    Given a state instance, returns the corresponding Signal type.

    Args:
        - state (State): an instance of a Prefect State

    Returns:
        - PrefectStateSignal: the Prefect Signal corresponding to
            the provided state

    Raises:
        - ValueError: if no signal matches the provided state
    """
    unprocessed = set(PrefectStateSignal.__subclasses__())
    signals = dict()
    while unprocessed:
        sig = unprocessed.pop()
        signals[sig._state_cls.__name__] = sig
        unprocessed = unprocessed.union(sig.__subclasses__())
    try:
        return signals[type(state).__name__]
    except KeyError:
        raise ValueError(f"No signal matches the provided state: {state}") from None


class ENDRUN(Exception):
    """
    An ENDRUN exception is used to indicate that _all_ state processing should
    stop. The pipeline result should be the state contained in the exception.

    Args:
        - state (State): the state that should be used as the result of the Runner's run
    """

    def __init__(self, state: state.State):
        self.state = state
        super().__init__()


class PrefectStateSignal(PrefectError):
    """
    Create a new PrefectStateSignal object.

    Args:
        - message (Any, optional): Defaults to `None`. A message about the signal.
        - *args (Any, optional): additional arguments to pass to this Signal's
            associated state constructor
        - **kwargs (Any, optional): additional keyword arguments to pass to this Signal's
            associated state constructor
    """

    _state_cls = state.State  # type: type

    def __init__(self, message: str = None, *args, **kwargs):  # type: ignore
        super().__init__(message)  # type: ignore
        kwargs.setdefault("result", self)
        self.state = self._state_cls(message=message, *args, **kwargs)  # type: ignore


class FAIL(PrefectStateSignal):
    """
    Indicates that a task failed.

    Args:
        - message (Any, optional): Defaults to `None`. A message about the signal.
        - *args (Any, optional): additional arguments to pass to this Signal's
            associated state constructor
        - **kwargs (Any, optional): additional keyword arguments to pass to this Signal's
            associated state constructor
    """

    _state_cls = state.Failed


class LOOP(PrefectStateSignal):
    """
    Indicates that a task should loop with the provided result.  Note that the result
    included in the `LOOP` signal will be available in Prefect context during the next iteration
    under the key `"task_loop_result"`.

    Args:
        - message (Any, optional): Defaults to `None`. A message about the signal.
        - *args (Any, optional): additional arguments to pass to this Signal's
            associated state constructor
        - **kwargs (Any, optional): additional keyword arguments to pass to this Signal's
            associated state constructor

    Example:
    ```python
    import prefect
    from prefect import task, Flow
    from prefect.engine.signals import LOOP

    @task
    def accumulate(x: int) -> int:
        current = prefect.context.get("task_loop_result", x)
        if current < 100:
            # if current < 100, rerun this task with the task's loop result incremented
            # by 5
            raise LOOP(result=current + 5)
        return current

    with Flow("Looper") as flow:
        output = accumulate(5)

    flow_state = flow.run()
    print(flow_state.result[output].result) # '100'
    ```
    """

    _state_cls = state.Looped

    def __init__(self, message: str = None, *args, **kwargs):  # type: ignore
        kwargs.setdefault(
            "result", repr(self)
        )  # looped results are always result handled
        super().__init__(message, *args, **kwargs)  # type: ignore


class TRIGGERFAIL(FAIL):
    """
    Indicates that a task trigger failed.

    Args:
        - message (Any, optional): Defaults to `None`. A message about the signal.
        - *args (Any, optional): additional arguments to pass to this Signal's
            associated state constructor
        - **kwargs (Any, optional): additional keyword arguments to pass to this Signal's
            associated state constructor
    """

    _state_cls = state.TriggerFailed


class VALIDATIONFAIL(FAIL):
    """
    Indicates that a task's result validation failed.

    Args:
        - message (Any, optional): Defaults to `None`. A message about the signal.
        - *args (Any, optional): additional arguments to pass to this Signal's
            associated state constructor
        - **kwargs (Any, optional): additional keyword arguments to pass to this Signal's
            associated state constructor
    """

    _state_cls = state.ValidationFailed


class SUCCESS(PrefectStateSignal):
    """
    Indicates that a task succeeded.

    Args:
        - message (Any, optional): Defaults to `None`. A message about the signal.
        - *args (Any, optional): additional arguments to pass to this Signal's
            associated state constructor
        - **kwargs (Any, optional): additional keyword arguments to pass to this Signal's
            associated state constructor
    """

    _state_cls = state.Success


class RETRY(PrefectStateSignal):
    """
    Used to indicate that a task should be retried.

    Args:
        - message (Any, optional): Defaults to `None`. A message about the signal.
        - *args (Any, optional): additional arguments to pass to this Signal's
            associated state constructor
        - **kwargs (Any, optional): additional keyword arguments to pass to this Signal's
            associated state constructor
    """

    _state_cls = state.Retrying


class SKIP(PrefectStateSignal):
    """
    Indicates that a task was skipped. By default, downstream tasks will
    act as if skipped tasks succeeded.

    Args:
        - message (Any, optional): Defaults to `None`. A message about the signal.
        - *args (Any, optional): additional arguments to pass to this Signal's
            associated state constructor
        - **kwargs (Any, optional): additional keyword arguments to pass to this Signal's
            associated state constructor
    """

    _state_cls = state.Skipped


class PAUSE(PrefectStateSignal):
    """
    Indicates that a task should not run and wait for manual execution.

    Args:
        - message (Any, optional): Defaults to `None`. A message about the signal.
        - *args (Any, optional): additional arguments to pass to this Signal's
            associated state constructor
        - **kwargs (Any, optional): additional keyword arguments to pass to this Signal's
            associated state constructor
    """

    _state_cls = state.Paused
