# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import datetime
from contextlib import contextmanager
from typing import Any, Callable, Iterable

import dask

from prefect.engine.executors.base import Executor


class DaskExecutor(Executor):
    """
    An executor that runs all functions synchronously using `dask`.
    """

    @contextmanager
    def start(self) -> Iterable[None]:
        """
        Context manager for initializing execution.

        Configures `dask` to run synchronously and yields the `dask.config` contextmanager.
        """
        with dask.config.set(scheduler="synchronous") as cfg:
            yield cfg

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> dask.delayed:
        """
        Submit a function to the executor for execution. Returns a `dask.delayed` object.

        Args:
            - fn (Callable): function which is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - dask.delayed: a `dask.delayed` object which represents the computation of `fn(*args, **kwargs)`
        """
        return dask.delayed(fn)(*args, **kwargs)

    def wait(self, futures: Iterable, timeout: datetime.timedelta = None) -> Iterable:
        """
        Resolves the `dask.delayed` objects to their values. Blocks until the computation is complete.

        Args:
            - futures (Iterable): iterable of `dask.delayed` objects to compute
            - timeout (datetime.timedelta): maximum length of time to allow for
                execution

        Returns:
            - Iterable: an iterable of resolved futures
        """
        computed = dask.compute(futures)
        return computed[0]
