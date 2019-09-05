import datetime
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, List

import prefect
from prefect.utilities.executors import timeout_handler


class Executor:
    """
    Base Executor class that all other executors inherit from.
    """

    timeout_handler = staticmethod(timeout_handler)

    def __init__(self) -> None:
        self.executor_id = type(self).__name__ + ": " + str(uuid.uuid4())

    def __repr__(self) -> str:
        return "<Executor: {}>".format(type(self).__name__)

    @contextmanager
    def start(self) -> Iterator[None]:
        """
        Context manager for initializing execution.

        Any initialization this executor needs to perform should be done in this
        context manager, and torn down after yielding.
        """
        yield

    def map(self, fn: Callable, *args: Any) -> List[Any]:
        """
        Submit a function to be mapped over its iterable arguments.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments that the function will be mapped over

        Returns:
            - List[Any]: the result of computating the function over the arguments

        """
        raise NotImplementedError()

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Submit a function to the executor for execution. Returns a future-like object.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - Any: a future-like object
        """
        raise NotImplementedError()

    def wait(self, futures: Any) -> Any:
        """
        Resolves futures to their values. Blocks until the future is complete.

        Args:
            - futures (Any): iterable of futures to compute

        Returns:
            - Any: an iterable of resolved futures
        """
        raise NotImplementedError()
