import dask
import datetime
import uuid
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Iterable, List, TypeVar, Union

import prefect
from prefect.engine.executors.base import Executor
from prefect.utilities.json import Serializable


class DaskExecutor(Executor):
    @contextmanager
    def start(self) -> Iterable[None]:
        """
        Any initialization this executor needs to perform should be done in this
        context manager, and torn down after yielding.
        """
        with dask.config.set(scheduler="synchronous") as cfg:
            yield cfg

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Submit a function to the executor for execution. Returns a future
        """
        return dask.delayed(fn)(*args, **kwargs)

    def wait(self, futures: Iterable, timeout: datetime.timedelta = None) -> Iterable:
        """
        Resolves futures to their values. Blocks until the future is complete.
        """
        computed = dask.compute(futures)
        return computed[0]
