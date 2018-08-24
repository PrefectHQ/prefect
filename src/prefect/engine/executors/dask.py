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
def transpose(d, maps):
# assumes same sized lists; otherwise just filter by which keys need it then
# do an update step
    mapped_d = {k: v for k, v in d.items() if k in maps}
    fixed = {k: v for k, v in d.items() if k not in maps}
    return [dict(zip(mapped_d, elem), **fixed) for elem in zip(*mapped_d.values())]


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
        maps = kwargs.pop('maps', set())
        if maps:
            upstream_states = kwargs.pop('upstream_states') or {}
            bagged_states = dask.bag.from_delayed(transpose(upstream_states, maps=maps))
            return dask.bag.map(fn, *args, upstream_states=bagged_states, **kwargs)
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
