import datetime
import warnings
from contextlib import contextmanager
from queue import Queue
from typing import Any, Callable, Iterable, Iterator, List

import dask
import dask.bag

from prefect.engine.executors.base import Executor


class SynchronousExecutor(Executor):
    """
    An executor that runs all functions synchronously using `dask`.
    """

    @contextmanager
    def start(self) -> Iterator:
        """
        Context manager for initializing execution.

        Configures `dask` and yields the `dask.config` contextmanager.
        """
        with dask.config.set(scheduler="synchronous") as cfg:
            yield cfg

    def queue(self, maxsize: int = 0) -> Queue:
        q = Queue(maxsize=maxsize)  # type: Queue
        return q

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> dask.delayed:
        """
        Submit a function to the executor for execution. Returns a `dask.delayed` object.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - dask.delayed: a `dask.delayed` object which represents the computation of `fn(*args, **kwargs)`
        """
        return dask.delayed(fn)(*args, **kwargs)

    def map(self, fn: Callable, *args: Any) -> List[dask.delayed]:
        """
        Submit a function to be mapped over its iterable arguments.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments that the function will be mapped over

        Returns:
            - List[dask.delayed]: the result of computating the function over the arguments

        """
        results = []
        for args_i in zip(*args):
            results.append(self.submit(fn, *args_i))
        return results

    def wait(self, futures: Any) -> Any:
        """
        Resolves a `dask.delayed` object to its values. Blocks until the computation is complete.

        Args:
            - futures (Any): iterable of `dask.delayed` objects to compute

        Returns:
            - Any: an iterable of resolved futures
        """
        with dask.config.set(scheduler="synchronous"):
            return dask.compute(futures)[0]
