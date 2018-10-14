import collections
import functools
from typing import Any, Callable, Iterable

import prefect
from prefect.engine import signals
from prefect.engine.state import State, Failed
from prefect.utilities import logging


class ENDRUN(Exception):
    """
    An ENDRUN exception is used by Runner steps to indicate that state processing should
    stop. The pipeline result should be the state contained in the exception.
    """

    def __init__(self, state: State = None) -> None:
        """
        Args
            - state (State): the state that should be used as the result of the Runner's run
        """
        self.state = state
        super().__init__()


def call_state_handlers(method: Callable[..., State]) -> Callable[..., State]:
    """
    Decorator that calls the Runner's `handle_state_change()` method.

    If used on a Runner method that has the signature:
        method(self, state: State, *args, **kwargs) -> State
    this decorator will inspect the provided State and the returned State and call
    the Runner's `handle_state_change()` method if they are different.

    For example:

    ```python
    @call_state_handlers
    def check_if_task_is_pending(self, state: State):
        if not state.is_pending()
            return Failed()
        return state
    ```

    Args:
        - method (Callable): a Runner method with the signature:
            method(self, state: State, *args, **kwargs) -> State

    Returns:
        Callable: a decorated method that calls Runner.handle_state_change() if the
            state it returns is different than the state it was passed.
    """

    @functools.wraps(method)
    def inner(self: "Runner", state: State, *args: Any, **kwargs: Any) -> State:
        new_state = method(self, state, *args, **kwargs)
        if new_state is state:
            return new_state
        else:
            return self.handle_state_change(old_state=state, new_state=new_state)

    return inner


class Runner:
    def __init__(
        self, state_handlers: Iterable[Callable] = None, logger_name: str = None
    ) -> None:
        if state_handlers is not None and not isinstance(
            state_handlers, collections.Sequence
        ):
            raise TypeError("state_handlers should be iterable.")
        self.state_handlers = state_handlers or []
        self.logger = logging.get_logger(logger_name or type(self).__name__)

    def call_runner_target_handlers(self, old_state: State, new_state: State) -> State:
        """
        Runners are used to execute a target object, usually a `Task` or a `Flow`, and those
        objects may have state handlers of their own. This method will always be called as
        the Runner's first state handler, and provides an entrypoint that can be overriden
        to target either a Task or Flow's own handlers.

        Args:
            - old_state (State): the old (previous) state
            - new_state (State): the new (current) state

        Returns:
            State: the new state
        """
        return new_state

    def handle_state_change(self, old_state: State, new_state: State) -> State:
        """
        Calls any handlers associated with the Runner

        This method will only be called when the state changes (`old_state is not new_state`)

        Args:
            - old_state (State): the old (previous) state of the task
            - new_state (State): the new (current) state of the task

        Returns:
            State: the updated state of the task

        Raises:
            - PAUSE: if raised by a handler
            - ENDRUN(Failed()): if any of the handlers fail

        """
        raise_on_exception = prefect.context.get("_raise_on_exception", False)

        try:
            # call runner's target handlers
            new_state = self.call_runner_target_handlers(old_state, new_state)

            # call runner's own handlers
            for handler in self.state_handlers:
                new_state = handler(self, old_state, new_state)

        # raise pauses
        except signals.PAUSE:
            raise

        # trap signals
        except signals.PrefectStateSignal as exc:
            if raise_on_exception:
                raise
            return exc.state

        # abort on errors
        except Exception as exc:
            if raise_on_exception:
                raise
            raise ENDRUN(
                Failed("Exception raised while calling state handlers.", message=exc)
            )
        return new_state
