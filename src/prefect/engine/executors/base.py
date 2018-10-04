import datetime
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterable, Union

import prefect
from prefect.engine.state import Failed
from prefect.utilities.json import Serializable


time_type = Union[datetime.timedelta, int]


class Executor(Serializable):
    """
    Base Executor class which all other executors inherit from.
    """

    def __init__(self):
        self.executor_id = type(self).__name__ + ": " + str(uuid.uuid4())

    @contextmanager
    def start(self) -> Iterable[None]:
        """
        Context manager for initializing execution.

        Any initialization this executor needs to perform should be done in this
        context manager, and torn down after yielding.
        """
        yield

    def map(self, fn: Callable, *args: Any, upstream_states=None, **kwargs: Any) -> Any:
        """
        Submit a function to be mapped over.

        Args:
            - fn (Callable): function which is being submitted for execution
            - *args (Any): arguments to be passed to `fn` with each call
            - upstream_states ({Edge: State}): a dictionary of upstream
                dependencies, keyed by Edge; the values are upstream states (or lists of states).
                This dictionary is used to determine which upstream depdencies should be mapped over,
                and under what keys (if any).
            - **kwargs (Any): keyword arguments to be passed to `fn` with each
                call

        Returns:
            - [Futures]: an iterable of future-like objects
        """
        raise NotImplementedError()

    def submit(
        self, fn: Callable, *args: Any, timeout: time_type = None, **kwargs: Any
    ) -> Any:
        """
        Submit a function to the executor for execution. Returns a future-like object.

        Args:
            - fn (Callable): function which is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - timeout (datetime.timedelta or int): maximum length of time to allow for
                execution; if `int` is provided, interpreted as seconds.
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - Any: a future-like object
        """
        raise NotImplementedError()

    def wait(self, futures: Iterable, timeout: time_type = None) -> Iterable:
        """
        Resolves futures to their values. Blocks until the future is complete.

        Args:
            - futures (Iterable): iterable of futures to compute
            - timeout (datetime.timedelta or int): maximum length of time to allow for
                execution; if `int` is provided, interpreted as seconds.

        Returns:
            - Iterable: an iterable of resolved futures
        """
        raise NotImplementedError()

    def queue(self, maxsize=0):
        """
        Creates an executor-compatible Queue object which can share state across tasks.

        Args:
            - maxsize (int): maxsize of the queue; defaults to 0 (infinite)

        Returns:
            - Queue: an executor compatible queue which can be shared among tasks
        """
        raise NotImplementedError()

    def submit_with_context(
        self, fn: Callable, *args: Any, context: Dict, **kwargs: Any
    ) -> Any:
        """
        Submit a function to the executor that will be run in a specific Prefect context.

        Args:
            - fn (Callable): function which is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - context (dict): `prefect.utilities.Context` to be used in function execution
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - Any: a future-like object
        """

        def run_fn_in_context(*args, context, **kwargs):
            with prefect.context(context):
                return fn(*args, **kwargs)

        return self.submit(run_fn_in_context, *args, context=context, **kwargs)
