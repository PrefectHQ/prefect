import logging
import uuid
import warnings
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Callable, Iterator, List, Union

from prefect import context
from prefect.engine.executors.base import Executor
from prefect.utilities.importtools import import_object

if TYPE_CHECKING:
    import dask
    from distributed import Future


# XXX: remove when deprecation of DaskExecutor kwargs is done
_valid_client_kwargs = {
    "timeout",
    "set_as_default",
    "scheduler_file",
    "security",
    "name",
    "direct_to_workers",
    "heartbeat_interval",
}


class DaskExecutor(Executor):
    """
    An executor that runs all functions using the `dask.distributed` scheduler.

    By default a temporary `distributed.LocalCluster` is created (and
    subsequently torn down) within the `start()` contextmanager. To use a
    different cluster class (e.g.
    [`dask_kubernetes.KubeCluster`](https://kubernetes.dask.org/)), you can
    specify `cluster_class`/`cluster_kwargs`.

    Alternatively, if you already have a dask cluster running, you can provide
    the address of the scheduler via the `address` kwarg.

    Note that if you have tasks with tags of the form `"dask-resource:KEY=NUM"`
    they will be parsed and passed as
    [Worker Resources](https://distributed.dask.org/en/latest/resources.html)
    of the form `{"KEY": float(NUM)}` to the Dask Scheduler.

    Args:
        - address (string, optional): address of a currently running dask
            scheduler; if one is not provided, a temporary cluster will be
            created in `executor.start()`.  Defaults to `None`.
        - cluster_class (string or callable, optional): the cluster class to use
            when creating a temporary dask cluster. Can be either the full
            class name (e.g. `"distributed.LocalCluster"`), or the class itself.
        - cluster_kwargs (dict, optional): addtional kwargs to pass to the
           `cluster_class` when creating a temporary dask cluster.
        - adapt_kwargs (dict, optional): additional kwargs to pass to ``cluster.adapt`
            when creating a temporary dask cluster. Note that adaptive scaling
            is only enabled if `adapt_kwargs` are provided.
        - client_kwargs (dict, optional): additional kwargs to use when creating a
            [`dask.distributed.Client`](https://distributed.dask.org/en/latest/api.html#client).
        - debug (bool, optional): When running with a local cluster, setting
            `debug=True` will increase dask's logging level, providing
            potentially useful debug info. Defaults to the `debug` value in
            your Prefect configuration.
        - **kwargs: DEPRECATED

    Example:

    Using a temporary local dask cluster:

    ```python
    executor = DaskExecutor()
    ```

    Using a temporary cluster running elsewhere. Any Dask cluster class should
    work, here we use [dask-cloudprovider](https://cloudprovider.dask.org):

    ```python
    executor = DaskExecutor(
        cluster_class="dask_cloudprovider.FargateCluster",
        cluster_kwargs={
            "image": "prefecthq/prefect:latest",
            "n_workers": 5,
            ...
        },
    )
    ```

    Connecting to an existing dask cluster

    ```python
    executor = DaskExecutor(address="192.0.2.255:8786")
    ```
    """

    def __init__(
        self,
        address: str = None,
        cluster_class: Union[str, Callable] = None,
        cluster_kwargs: dict = None,
        adapt_kwargs: dict = None,
        client_kwargs: dict = None,
        debug: bool = None,
        **kwargs: Any
    ):
        if address is None:
            address = context.config.engine.executor.dask.address or None
        # XXX: deprecated
        if address == "local":
            warnings.warn(
                "`address='local'` is deprecated. To use a local cluster, leave the "
                "`address` field empty."
            )
            address = None

        # XXX: deprecated
        local_processes = kwargs.pop("local_processes", None)
        if local_processes is None:
            local_processes = context.config.engine.executor.dask.get(
                "local_processes", None
            )
        if local_processes is not None:
            warnings.warn(
                "`local_processes` is deprecated, please use "
                "`cluster_kwargs={'processes': local_processes}`. The default is "
                "now `local_processes=True`."
            )

        if address is not None:
            if cluster_class is not None or cluster_kwargs is not None:
                raise ValueError(
                    "Cannot specify `address` and `cluster_class`/`cluster_kwargs`"
                )
        else:
            if cluster_class is None:
                cluster_class = context.config.engine.executor.dask.cluster_class
            if isinstance(cluster_class, str):
                cluster_class = import_object(cluster_class)
            if cluster_kwargs is None:
                cluster_kwargs = {}
            else:
                cluster_kwargs = cluster_kwargs.copy()

            from distributed.deploy.local import LocalCluster

            if cluster_class == LocalCluster:
                if debug is None:
                    debug = context.config.debug
                cluster_kwargs.setdefault(
                    "silence_logs", logging.CRITICAL if not debug else logging.WARNING
                )
                if local_processes is not None:
                    cluster_kwargs.setdefault("processes", local_processes)
                for_cluster = set(kwargs).difference(_valid_client_kwargs)
                if for_cluster:
                    warnings.warn(
                        "Forwarding executor kwargs to `LocalCluster` is now handled by the "
                        "`cluster_kwargs` parameter, please update accordingly"
                    )
                    for k in for_cluster:
                        cluster_kwargs[k] = kwargs.pop(k)

            if adapt_kwargs is None:
                adapt_kwargs = {}

        if client_kwargs is None:
            client_kwargs = {}
        if kwargs:
            warnings.warn(
                "Forwarding executor kwargs to `Client` is now handled by the "
                "`client_kwargs` parameter, please update accordingly"
            )
            client_kwargs.update(kwargs)

        self.address = address
        self.is_started = False
        self.cluster_class = cluster_class
        self.cluster_kwargs = cluster_kwargs
        self.adapt_kwargs = adapt_kwargs
        self.client_kwargs = client_kwargs

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
            if self.address is not None:
                with Client(self.address, **self.client_kwargs) as client:
                    self.client = client
                    self.is_started = True
                    yield self.client
            else:
                with self.cluster_class(**self.cluster_kwargs) as cluster:  # type: ignore
                    if self.adapt_kwargs:
                        cluster.adapt(**self.adapt_kwargs)
                    with Client(cluster, **self.client_kwargs) as client:
                        self.client = client
                        self.is_started = True
                        yield self.client
        finally:
            self.client = None
            self.is_started = False

    def _prep_dask_kwargs(self) -> dict:
        dask_kwargs = {"pure": False}  # type: dict

        # set a key for the dask scheduler UI
        if context.get("task_full_name"):
            key = "{}-{}".format(context.get("task_full_name", ""), str(uuid.uuid4()))
            dask_kwargs.update(key=key)

        # infer from context if dask resources are being utilized
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
        - scheduler (str): The local dask scheduler to use; common options are "synchronous", "threads" and "processes".  Defaults to "threads".
        - **kwargs (Any): Additional keyword arguments to pass to dask config
    """

    def __init__(self, scheduler: str = "threads", **kwargs: Any):
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

        with dask.config.set(scheduler=self.scheduler, **self.kwargs):
            return dask.compute(futures)[0]
