import datetime
from typing import Any, Callable, Iterable, List

from prefect.engine.executors.base import Executor
from prefect.utilities.executors import main_thread_timeout


class LocalExecutor(Executor):
    """
    An executor that runs all functions synchronously and immediately in
    the main thread.  To be used mainly for debugging purposes.
    """

    timeout_handler = staticmethod(main_thread_timeout)

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Submit a function to the executor for execution. Returns the result of the computation.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - Any: the result of `fn(*args, **kwargs)`
        """
        return fn(*args, **kwargs)

    def map(self, fn: Callable, *args: Any) -> List[Any]:
        """
        Submit a function to be mapped over its iterable arguments.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments that the function will be mapped over

        Returns:
            - List[Any]: the result of computating the function over the arguments

        """
        results = []
        for args_i in zip(*args):
            results.append(fn(*args_i))
        return results

    def wait(self, futures: Any) -> Any:
        """
        Returns the results of the provided futures.

        Args:
            - futures (Any): objects to wait on

        Returns:
            - Any: whatever `futures` were provided
        """
        return futures
