# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import datetime
from contextlib import contextmanager
from queue import Queue
from typing import Any, Callable, Iterable, Iterator, List

import dask
import dask.bag
import warnings

from prefect.engine.executors.base import Executor
from prefect.utilities.executors import dict_to_list


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

    def map(
        self, fn: Callable, *args: Any, upstream_states: dict, **kwargs: Any
    ) -> Iterable[Any]:
        def mapper(
            fn: Callable, *args: Any, upstream_states: dict, **kwargs: Any
        ) -> List[dask.delayed]:
            states = dict_to_list(upstream_states)

            futures = []
            for map_index, elem in enumerate(states):
                futures.append(
                    dask.delayed(fn)(
                        *args, upstream_states=elem, map_index=map_index, **kwargs
                    )
                )
            return futures

        future_list = self.submit(
            mapper, fn, *args, upstream_states=upstream_states, **kwargs
        )
        return self.wait(future_list)

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
            - timeout (datetime.timedelta): maximum length of time to allow for execution

        Returns:
            - Iterable: an iterable of resolved futures
        """
        with dask.config.set(scheduler="synchronous"):
            computed = dask.compute(
                dask.compute(dask.compute(dask.compute(futures)[0])[0])[0]
            )
        return computed[0]
