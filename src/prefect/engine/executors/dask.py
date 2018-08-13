import dask
import datetime
from contextlib import contextmanager
from typing import Any, Callable, Iterable

from prefect.engine.executors.base import Executor


class DaskExecutor(Executor):
    """
    An executor that runs all functions synchronously using `dask`.
    """

    @contextmanager
    def start(self) -> Iterable[None]:
        """
        Configures `dask` to run synchronously and yields the `dask.config` contextmanager.
        """
        with dask.config.set(scheduler="synchronous") as cfg:
            yield cfg

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> dask.delayed:
        """
        Submit a function to the executor for execution. Returns a `dask.delayed` object.
        """
        return dask.delayed(fn)(*args, **kwargs)

    def wait(self, futures: Iterable, timeout: datetime.timedelta = None) -> Iterable:
        """
        Resolves futures to their values. Blocks until the future is complete.
        """
        computed = dask.compute(futures)
        return computed[0]
