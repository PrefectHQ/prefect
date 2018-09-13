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
    create_bagged_list,
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
        self, fn: Callable, *args: Any, maps=None, upstream_states=None, **kwargs: Any
    ) -> dask.bag:
        mapped_non_keyed = maps.pop(None, [])
        non_keyed = upstream_states.pop(None, [])

        # every task which is being mapped over needs its state represented as a
        # dask.bag; there are two situations: 1.) the task being mapped over is
        # itself a result of a mapped task, in which case it will already be a
        # bag 2.) the task being mapped over will return a list, in which case
        # we need to pull apart the list into a list of states and then a dask.bag
        needs_bagging = {
            k: dask.bag.from_delayed(dask.delayed(state_to_list)(v))
            for k, v in maps.items()
            if k in maps and not isinstance(v, dask.bag.Bag)
        }
        maps.update(needs_bagging)
        upstream_states.update(maps)

        if mapped_non_keyed:
            # if there are mapped tasks that don't belong to a keyed Edge,
            # we must convert them to bags
            upstreams = create_bagged_list(mapped_non_keyed, non_keyed)
            other = []
        else:
            # otherwise, non_keyed is a simple list of Delayed objects
            # which we must unpack so that `dask.bag.map()` knows they're there
            # (otherwise dask.bag.map would treat non_keyed as a list and never
            # compute them)
            # TODO: mapping a task with non-mapped upstream tasks
            # causes a bottleneck in the execution model
            other, upstreams = non_keyed, None

        bagged_states = dask.bag.map(
            unpack_dict_to_bag, *other, upstreams=upstreams, **upstream_states
        )

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
