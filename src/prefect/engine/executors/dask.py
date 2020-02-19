import logging
import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Callable, Iterator, List

from prefect import context
from prefect.engine.executors.base import Executor

if TYPE_CHECKING:
    import dask
    from distributed import Future


class DaskExecutor(Executor):
    """
    An executor that runs all functions using the `dask.distributed` scheduler on
    a (possibly local) dask cluster.  If you already have one running, provide the
    address of the scheduler upon initialization; otherwise, one will be created
    (and subsequently torn down) within the `start()` contextmanager.

    Note that if you have tasks with tags of the form `"dask-resource:KEY=NUM"` they will be parsed
    and passed as [Worker Resources](https://distributed.dask.org/en/latest/resources.html) of the form
    `{"KEY": float(NUM)}` to the Dask Scheduler.

    Args:
        - address (string, optional): address of a currently running dask
            scheduler; if one is not provided, a `distributed.LocalCluster()` will be created in `executor.start()`.
            Defaults to `None`
        - local_processes (bool, optional): whether to use multiprocessing or not
            (computations will still be multithreaded). Ignored if address is provided.
            Defaults to `False`.
        - debug (bool, optional): whether to operate in debug mode; `debug=True`
            will produce many additional dask logs. Defaults to the `debug` value in your Prefect configuration
        - **kwargs (dict, optional): additional kwargs to be passed to the [`dask.distributed.Client`](https://distributed.dask.org/en/latest/api.html#client) upon 
            initialization (e.g., `n_workers`, `security`, etc.), which will also pass any unmatched kwargs down to child objects such as 
            [`distributed.deploy.local.LocalCluster`](https://docs.dask.org/en/latest/setup/single-distributed.html#distributed.deploy.local.LocalCluster).
            Please see the Dask docs to see all of the options that child objects will respond to.
    """

    def __init__(
        self,
        address: str = None,
        local_processes: bool = None,
        debug: bool = None,
        **kwargs: Any
    ):
        if address is None:
            address = context.config.engine.executor.dask.address
        if address == "local":
            address = None
        if local_processes is None:
            local_processes = context.config.engine.executor.dask.local_processes
        if debug is None:
            debug = context.config.debug
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
        # import dask client here to decrease our import times
        from distributed import Client

        try:
            if self.address is None:
                self.kwargs.update(
                    silence_logs=logging.CRITICAL if not self.debug else logging.WARNING
                )
                self.kwargs.update(processes=self.local_processes)
            with Client(self.address, **self.kwargs) as client:
                self.client = client
                self.is_started = True
                yield self.client
        finally:
            self.client = None
            self.is_started = False

    def _prep_dask_kwargs(self) -> dict:
        dask_kwargs = {"pure": False}  # type: dict

        ## set a key for the dask scheduler UI
        if context.get("task_full_name"):
            key = "{}-{}".format(context.get("task_full_name", ""), str(uuid.uuid4()))
            dask_kwargs.update(key=key)

        ## infer from context if dask resources are being utilized
        dask_resource_tags = [
            tag
            for tag in context.get("task_tags", [])
            if tag.lower().startswith("dask-resource")
        ]
        if dask_resource_tags:
            resources = {}
            for tag in dask_resource_tags:
                prefix, val = tag.split("=")
                resources.update({prefix.split(":")[1]: float(val)})
            dask_kwargs.update(resources=resources)

        return dask_kwargs

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        if "client" in state:
            del state["client"]
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> "Future":
        """
        Submit a function to the executor for execution. Returns a Future object.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - Future: a Future-like object that represents the computation of `fn(*args, **kwargs)`
        """
        # import dask functions here to decrease our import times
        from distributed import fire_and_forget, worker_client

        dask_kwargs = self._prep_dask_kwargs()
        kwargs.update(dask_kwargs)

        if self.is_started and hasattr(self, "client"):
            future = self.client.submit(fn, *args, **kwargs)
        elif self.is_started:
            with worker_client(separate_thread=True) as client:
                future = client.submit(fn, *args, **kwargs)
        else:
            raise ValueError("This executor has not been started.")

        fire_and_forget(future)
        return future

    def map(self, fn: Callable, *args: Any, **kwargs: Any) -> List["Future"]:
        """
        Submit a function to be mapped over its iterable arguments.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments that the function will be mapped over
            - **kwargs (Any): additional keyword arguments that will be passed to the Dask Client

        Returns:
            - List[Future]: a list of Future-like objects that represent each computation of
                fn(*a), where a = zip(*args)[i]

        """
        if not args:
            return []

        # import dask functions here to decrease our import times
        from distributed import fire_and_forget, worker_client

        dask_kwargs = self._prep_dask_kwargs()
        kwargs.update(dask_kwargs)

        if self.is_started and hasattr(self, "client"):
            futures = self.client.map(fn, *args, **kwargs)
        elif self.is_started:
            with worker_client(separate_thread=True) as client:
                futures = client.map(fn, *args, **kwargs)
                return client.gather(futures)
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
        # import dask functions here to decrease our import times
        from distributed import worker_client

        if self.is_started and hasattr(self, "client"):
            return self.client.gather(futures)
        elif self.is_started:
            with worker_client(separate_thread=True) as client:
                return client.gather(futures)
        else:
            raise ValueError("This executor has not been started.")


class LocalDaskExecutor(Executor):
    """
    An executor that runs all functions locally using `dask` and a configurable dask scheduler.  Note that
    this executor is known to occasionally run tasks twice when using multi-level mapping.

    Prefect's mapping feature will not work in conjunction with setting `scheduler="processes"`.

    Args:
        - scheduler (str): The local dask scheduler to use; common options are "synchronous", "threads" and "processes".  Defaults to "synchronous".
        - **kwargs (Any): Additional keyword arguments to pass to dask config
    """

    def __init__(self, scheduler: str = "synchronous", **kwargs: Any):
        self.scheduler = scheduler
        self.kwargs = kwargs
        super().__init__()

    @contextmanager
    def start(self) -> Iterator:
        """
        Context manager for initializing execution.

        Configures `dask` and yields the `dask.config` contextmanager.
        """
        # import dask here to reduce prefect import times
        import dask

        with dask.config.set(scheduler=self.scheduler, **self.kwargs) as cfg:
            yield cfg

    def submit(self, fn: Callable, *args: Any, **kwargs: Any) -> "dask.delayed":
        """
        Submit a function to the executor for execution. Returns a `dask.delayed` object.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - dask.delayed: a `dask.delayed` object that represents the computation of `fn(*args, **kwargs)`
        """
        # import dask here to reduce prefect import times
        import dask

        return dask.delayed(fn)(*args, **kwargs)

    def map(self, fn: Callable, *args: Any) -> List["dask.delayed"]:
        """
        Submit a function to be mapped over its iterable arguments.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments that the function will be mapped over

        Returns:
            - List[dask.delayed]: the result of computating the function over the arguments

        """
        if self.scheduler == "processes":
            raise RuntimeError(
                "LocalDaskExecutor cannot map if scheduler='processes'. Please set to either 'synchronous' or 'threads'."
            )

        results = []
        for args_i in zip(*args):
            results.append(self.submit(fn, *args_i))
        return results

    def wait(self, futures: Any) -> Any:
        """
        Resolves a `dask.delayed` object to its values. Blocks until the computation is complete.

        Args:
            - futures (Any): iterable of `dask.delayed` objects to compute

        Returns:
            - Any: an iterable of resolved futures
        """
        # import dask here to reduce prefect import times
        import dask

        with dask.config.set(scheduler=self.scheduler, **self.kwargs) as cfg:
            return dask.compute(futures)[0]
