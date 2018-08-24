# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import datetime
from contextlib import contextmanager
from multiprocessing import Manager
from typing import Any, Callable, Iterable

import dask
import dask.bag
import queue

from prefect.engine.executors.base import Executor


@dask.delayed
def state_to_list(s):
    return [type(s)(result=elem) for elem in s.result]


@dask.delayed
def bagged_list(ss):
    expanded = [[type(s)(result=elem) for elem in s.result] for s in ss]
    wat = [list(zz) for zz in zip(*expanded)]
    return wat


class DaskExecutor(Executor):
    """
    An executor that runs all functions synchronously using `dask`.

    Args:
        - scheduler (string, optional): which dask scheduler to use; defaults to
            `"synchronous"`.  Other available options are `"threads"` for multithreading and `"processes"` for multiprocessing.
    """

    def __init__(self, scheduler="synchronous"):
        self.scheduler = scheduler
        super().__init__()
        if self.scheduler == "processes":
            self.manager = Manager()

    @contextmanager
    def start(self) -> Iterable[None]:
        """
        Context manager for initializing execution.

        Configures `dask` to run using the provided scheduler and yields the `dask.config` contextmanager.
        """
        with dask.config.set(scheduler=self.scheduler) as cfg:
            yield cfg

    def queue(self, maxsize=0):
        if self.scheduler == "processes":
            q = self.manager.Queue(maxsize=maxsize)
        else:
            q = queue.Queue(maxsize=maxsize)

        return q

    def map(self, fn: Callable, *args: Any, **kwargs: Any) -> dask.bag:
        maps = kwargs.pop("maps", dict())
        upstream_states = kwargs.pop("upstream_states") or {}

        non_keyed = upstream_states.pop(None, [])
        mapped_non_keyed = maps.pop(None, [])

        needs_bagging = {
            k: dask.bag.from_delayed(state_to_list(v))
            for k, v in maps.items()
            if k in maps and not isinstance(v, dask.bag.Bag)
        }
        maps.update(needs_bagging)

        if mapped_non_keyed:
            bag_key = None
            to_bag = [s for s in mapped_non_keyed if not isinstance(s, dask.bag.Bag)]
            if to_bag:
                bag = dask.bag.map(
                    lambda *args, x, y: x + y + list(args),
                    *[s for s in mapped_non_keyed if s not in to_bag],
                    x=dask.bag.from_delayed(bagged_list(to_bag)),
                    y=non_keyed
                )
            else:
                bag = dask.bag.map(
                    lambda *args, x, y: x + y + list(args),
                    *[s for s in mapped_non_keyed if s not in to_bag],
                    x=[],
                    y=non_keyed
                )
        else:
            bag_key, bag = maps.popitem()

        transform = lambda bag, bag_key, **kwargs: {bag_key: bag, **kwargs}
        bagged_states = dask.bag.map(transform, bag, bag_key, **maps, **upstream_states)
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
