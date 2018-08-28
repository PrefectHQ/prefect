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
    "Converts a State `s` with a list as its result to a list of states of the same type"
    if isinstance(s, list):
        return s
    return [type(s)(result=elem) for elem in s.result]


@dask.delayed
def bagged_list(ss):
    """Converts a list of states, each of which returns a list of the same size, to
    a list of lists of states.
    E.g. [State(result=[1, 2]), State(result=[7, 8])] -> [[State(result=1), State(result=7)], [State(result=2), State(result=8)]]
    """
    expanded = [[type(s)(result=elem) for elem in s.result] for s in ss]
    return [list(zz) for zz in zip(*expanded)]


def unpack_dict_to_bag(*other, upstreams=None, **kwargs):
    "Convenience function for packaging up all keywords into a dictionary"
    bag = list(other) or upstreams or []
    return dict({None: bag}, **kwargs)


def create_bagged_list(mapped, unmapped):
    to_bag = [s for s in mapped if not isinstance(s, dask.bag.Bag)]
    upstreams = dask.bag.map(
        lambda *args, x: list(args) + x,
        *[s for s in mapped + unmapped if s not in to_bag],
        x=dask.bag.from_delayed(bagged_list(to_bag)) if to_bag else []
    )
    return upstreams


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

    @contextmanager
    def start(self) -> Iterable[None]:
        """
        Context manager for initializing execution.

        Configures `dask` to run using the provided scheduler and yields the `dask.config` contextmanager.
        """
        try:
            if self.scheduler == "processes":
                self.manager = Manager()

            with dask.config.set(scheduler=self.scheduler) as cfg:
                yield cfg

        finally:
            if self.scheduler == "processes":
                self.manager.shutdown()
                del self.manager

    def queue(self, maxsize=0):
        if self.scheduler == "processes":
            q = self.manager.Queue(maxsize=maxsize)
        else:
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
            k: dask.bag.from_delayed(state_to_list(v))
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
