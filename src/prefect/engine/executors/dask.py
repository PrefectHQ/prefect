# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import logging
import multiprocessing
import sys

if sys.version_info < (3, 5):
    raise ImportError(
        """The DaskExecutor is only locally compatible with Python 3.5+"""
    )

import datetime
from contextlib import contextmanager
from distributed import Client, fire_and_forget, Future, Queue, worker_client
from typing import Any, Callable, Iterable

import queue
import warnings

from prefect import config
from prefect.engine.executors.base import Executor
from prefect.engine.state import Failed
from prefect.utilities.executors import dict_to_list


class DaskExecutor(Executor):
    """
    An executor that runs all functions using the `dask.distributed` scheduler on
    a (possibly local) dask cluster.  If you already have one running, simply provide the
    address of the scheduler upon initialization; otherwise, one will be created
    (and subsequently torn down) within the `start()` contextmanager.

    Args:
        - address (string, optional): address of a currently running dask
            scheduler; if one is not provided, a `distributed.LocalCluster()` will be created in `executor.start()`.
            Defaults to `None`
        - processes (bool, optional): whether to use multiprocessing or not
            (computations will still be multithreaded). Ignored if address is provided.
            Defaults to `False`.
        - debug (bool, optional): whether to operate in debug mode; `debug=True`
            will produce many additional dask logs. Defaults to the `debug` value in your Prefect configuration
        - **kwargs (dict, optional): additional kwargs to be passed to the
            `dask.distributed.Client` upon initialization (e.g., `n_workers`)
    """

    def __init__(self, address=None, processes=False, debug=config.debug, **kwargs):
        self.address = address
        self.processes = processes
        self.debug = debug
        self.kwargs = kwargs
        super().__init__()

    @contextmanager
    def start(self) -> Iterable[None]:
        """
        Context manager for initializing execution.

        Creates a `dask.distributed.Client` and yields it.
        """
        try:
            self.kwargs.update(
                silence_logs=logging.CRITICAL if not self.debug else logging.WARNING
            )
            with Client(
                self.address, processes=self.processes, **self.kwargs
            ) as client:
                self.client = client
                yield self.client
        finally:
            self.client = None

    def queue(self, maxsize=0, client=None) -> Queue:
        """
        Creates an executor-compatible Queue object which can share state
        across tasks.

        Args:
            - maxsize (int, optional): `maxsize` for the Queue; defaults to 0
                (interpreted as no size limitation)
            - client (dask.distributed.Client, optional): which client to
                associate the Queue with; defaults to `self.client`
        """
        q = Queue(maxsize=maxsize, client=client or self.client)
        return q

    def map(
        self, fn: Callable, *args: Any, upstream_states=None, **kwargs: Any
    ) -> Future:
        def mapper(fn, *args, upstream_states, **kwargs):
            states = dict_to_list(upstream_states)

            with worker_client() as client:
                futures = []
                for elem in states:
                    futures.append(
                        client.submit(fn, *args, upstream_states=elem, **kwargs)
                    )
                fire_and_forget(
                    futures
                )  # tells dask we dont expect worker_client to track these
            return futures

        future_list = self.client.submit(
            mapper, fn, *args, upstream_states=upstream_states, **kwargs
        )
        return future_list

    def submit(self, fn: Callable, *args: Any, timeout: datetime.timedelta = None, **kwargs: Any) -> Future:
        """
        Submit a function to the executor for execution. Returns a Future object.

        Args:
            - fn (Callable): function which is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - Future: a Future-like object which represents the computation of `fn(*args, **kwargs)`
        """

        if timeout:
            return self.submit_with_timeout(fn, *args, timeout.total_seconds(), **kwargs)
        return self.client.submit(fn, *args, pure=False, **kwargs)

    def submit_with_timeout(self, fn, *args, timeout: int, **kwargs):

        def retrieve_value(*args, _container, **kwargs):
            _container.put(fn(*args, **kwargs))

        def handler(*args, **kwargs):
            q = multiprocessing.Queue()
            kwargs['_container'] = q
            p = multiprocessing.Process(target=retrieve_value, args=args, kwargs=kwargs)
            p.start()
            p.join(timeout)
            p.terminate()
            if not q.empty():
                return q.get()
            else:
                return Failed(message=TimeoutError("Execution timed out."))

        return self.client.submit(handler, *args, **kwargs)

    def wait(self, futures: Iterable, timeout: datetime.timedelta = None) -> Iterable:
        """
        Resolves the Future objects to their values. Blocks until the computation is complete.

        Args:
            - futures (Iterable): iterable of future-like objects to compute
            - timeout (datetime.timedelta): maximum length of time to allow for
                execution

        Returns:
            - Iterable: an iterable of resolved futures
        """
        return self.client.gather(
            self.client.gather(futures)
        )  # we expect worker_client submitted futures
