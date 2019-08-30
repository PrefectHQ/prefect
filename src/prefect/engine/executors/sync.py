import datetime
import warnings
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Iterator, List

import dask
import dask.bag

from prefect.engine.executors.dask import LocalDaskExecutor


class SynchronousExecutor(LocalDaskExecutor):
    """
    An executor that runs all functions synchronously using `dask`.  Note that
    this executor is known to occasionally run tasks twice when using multi-level mapping.

    NOTE: this class is deprecated and maintained only for backwards-compatibility.
    """

    def __init__(self) -> None:
        warnings.warn(
            "The SynchronousExecutor is deprecated and will be removed from "
            "Prefect. Use a LocalDaskExecutor with a 'synchronous' scheduler instead.",
            UserWarning,
        )
        super().__init__(scheduler="synchronous")
