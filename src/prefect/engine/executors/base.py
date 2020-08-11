from contextlib import contextmanager
from typing import Any, Callable, Iterator

from prefect.utilities.logging import get_logger


class Executor:
    """
    Base Executor class that all other executors inherit from.
    """

    def __init__(self) -> None:
        self.logger = get_logger(type(self).__name__)

    def __repr__(self) -> str:
        return "<Executor: {}>".format(type(self).__name__)

    @contextmanager
    def start(self, on_cleanup: Callable = None) -> Iterator[None]:
        """
        Context manager for initializing execution.

        Any initialization this executor needs to perform should be done in this
        context manager, and torn down after yielding.

        Args:
            - on_cleanup (Callable, optional): callback to call in every executor process
                upon completion of a flow run. The callback execution is best-effort, and
                may be skipped in certain cases (e.g. a worker process dies).
        """
        yield

    def submit(
        self, fn: Callable, *args: Any, extra_context: dict = None, **kwargs: Any
    ) -> Any:
        """
        Submit a function to the executor for execution. Returns a future-like object.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - extra_context (dict, optional): an optional dictionary with extra information
                about the submitted task
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
