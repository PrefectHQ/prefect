import datetime
import logging
import queue
import warnings
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Iterator, List

from distributed import Client, Future, Queue, fire_and_forget, worker_client

from prefect import config
from prefect.engine.executors.base import Executor


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
        - local_processes (bool, optional): whether to use multiprocessing or not
            (computations will still be multithreaded). Ignored if address is provided.
            Defaults to `False`. Note that timeouts are not supported if `local_processes=True`
        - debug (bool, optional): whether to operate in debug mode; `debug=True`
            will produce many additional dask logs. Defaults to the `debug` value in your Prefect configuration
        - **kwargs (dict, optional): additional kwargs to be passed to the
            `dask.distributed.Client` upon initialization (e.g., `n_workers`)
    """

    def __init__(
        self,
        address: str = None,
        local_processes: bool = None,
        debug: bool = None,
        **kwargs: Any
    ):
        if address is None:
            address = config.engine.executor.dask.address
        if address == "local":
            address = None
        if local_processes is None:
            local_processes = config.engine.executor.dask.local_processes
        if debug is None:
            debug = config.debug
        self.address = address
        self.local_processes = local_processes
        self.debug = debug
        self.is_started = False
        self.kwargs = kwargs
        super().__init__()

    @contextmanager
    def start(self) -> Iterator[None]:
        """
        Context manager for initializing execution.

        Creates a `dask.distributed.Client` and yields it.
        """
        try:
            self.kwargs.update(
                silence_logs=logging.CRITICAL if not self.debug else logging.WARNING
            )
            with Client(
                self.address, processes=self.local_processes, **self.kwargs
            ) as client:
                self.client = client
                self.is_started = True
                yield self.client
        finally:
            self.client = None
            self.is_started = False

    def queue(self, maxsize: int = 0, client: Client = None) -> Queue:
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

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        if "client" in state:
            del state["client"]
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> Future:
        """
        Submit a function to the executor for execution. Returns a Future object.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - Future: a Future-like object which represents the computation of `fn(*args, **kwargs)`
        """
        if self.is_started and hasattr(self, "client"):

            future = self.client.submit(fn, *args, pure=False, **kwargs)
        elif self.is_started:
            with worker_client(separate_thread=True) as client:
                future = client.submit(fn, *args, pure=False, **kwargs)
        else:
            raise ValueError("This executor has not been started.")

        fire_and_forget(future)
        return future

    def map(self, fn: Callable, *args: Any) -> List[Future]:
        """
        Submit a function to be mapped over its iterable arguments.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments that the function will be mapped over

        Returns:
            - List[Future]: a list of Future-like objects that represent each computation of
                fn(*a), where a = zip(*args)[i]

        """
        if not args:
            return []

        if self.is_started and hasattr(self, "client"):
            futures = self.client.map(fn, *args, pure=False)
        elif self.is_started:
            with worker_client(separate_thread=True) as client:
                futures = client.map(fn, *args, pure=False)
        else:
            raise ValueError("This executor has not been started.")

        fire_and_forget(futures)
        return futures

    def wait(self, futures: Any) -> Any:
        """
        Resolves the Future objects to their values. Blocks until the computation is complete.

        Args:
            - futures (Any): single or iterable of future-like objects to compute

        Returns:
            - Any: an iterable of resolved futures with similar shape to the input
        """
        if self.is_started and hasattr(self, "client"):
            return self.client.gather(futures)
        elif self.is_started:
            with worker_client(separate_thread=True) as client:
                return client.gather(futures)
        else:
            raise ValueError("This executor has not been started.")
