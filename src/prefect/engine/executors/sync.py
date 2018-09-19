# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import datetime
from contextlib import contextmanager
from typing import Any, Callable, Iterable

import dask
import dask.bag
import queue
import warnings

from prefect.engine.executors.base import Executor
from prefect.utilities.executors import (
    state_to_list,
    unpack_dict_to_bag,
)


class SynchronousExecutor(Executor):
    """
    An executor that runs all functions synchronously using `dask`.
    """

    @contextmanager
    def start(self) -> Iterable[None]:
        """
        Context manager for initializing execution.

        Configures `dask` and yields the `dask.config` contextmanager.
        """
        with dask.config.set(scheduler="synchronous") as cfg:
            yield cfg

    def queue(self, maxsize=0):
        q = queue.Queue(maxsize=maxsize)
        return q

    def map(
        self, fn: Callable, *args: Any, upstream_states=None, **kwargs: Any
    ) -> dask.bag:
        # every task which is being mapped over needs its state represented as a
        # dask.bag; there are two situations: 1.) the task being mapped over is
        # itself a result of a mapped task, in which case it will already be a
        # bag 2.) the task being mapped over will return a list, in which case
        # we need to pull apart the list into a list of states and then a dask.bag
        needs_bagging = {
            edge: dask.bag.from_delayed(dask.delayed(state_to_list)(v))
            for edge, v in upstream_states.items()
            if edge.mapped and not isinstance(v, dask.bag.Bag)
        }
        upstream_states.update(needs_bagging)

        # in order to call `dask.bag.map()` on the provided function `fn`,
        # we need a dask.bag to map over; moreover, because the keys of
        # upstream_states are Edges (not strings), we can't just splat them into a
        # function call --> hence, we unpack them (maintaining order) and
        # convert them to a bag
        keys, values = list(zip(*upstream_states.items()))
        bagged_states = dask.bag.map(unpack_dict_to_bag, *values, keys=keys)

        return dask.bag.map(fn, *args, upstream_states=bagged_states, **kwargs)

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
