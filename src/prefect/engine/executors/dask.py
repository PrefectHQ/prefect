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


def unpack_dict_to_bag(bag, bag_key, **kwargs):
    "Convenience function for packaging up all keywords into a dictionary"
    return dict({bag_key: bag}, **kwargs)


def merge_lists_to_bag(*args, x, y):
    "Convenience function for concatenating lists."
    return (x + y + list(args),)


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

        # now we need to choose a (key, result) to unpack so that we can
        # convert upstream_states from a dict into a dask.bag
        if mapped_non_keyed:
            to_bag = [s for s in mapped_non_keyed if not isinstance(s, dask.bag.Bag)]
            if to_bag:
                # convert [upstream_tasks which are not mapped] +
                # [upstream_tasks which are mapped] into an appropriate dask.bag
                upstreams = dask.bag.map(
                    merge_lists_to_bag,
                    *[s for s in mapped_non_keyed if s not in to_bag],
                    x=dask.bag.from_delayed(
                        bagged_list(to_bag)
                    ),  # those upstream tasks which need to be converted
                    y=non_keyed
                )
            else:
                upstreams = dask.bag.map(
                    merge_lists_to_bag,
                    *[s for s in mapped_non_keyed if s not in to_bag],
                    x=[],
                    y=non_keyed
                )
        else:
            upstreams = dask.delayed(list)(
                non_keyed
            )  # necessary so dask.bag.map knows this is a list of _delayed_ objects

        # dask.bag.map requires string keywords, and `None` is not a string
        upstream_states.update(maps)
        bagged_states = dask.bag.map(
            unpack_dict_to_bag, upstreams, None, **upstream_states
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
