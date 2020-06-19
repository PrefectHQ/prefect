import logging
import uuid
import warnings
from contextlib import contextmanager
from typing import Any, Callable, Iterator, TYPE_CHECKING, Union, Optional

from prefect import context
from prefect.engine.executors.base import Executor
from prefect.utilities.importtools import import_object

if TYPE_CHECKING:
    import dask
    from distributed import Future


__any__ = ("DaskExecutor", "LocalDaskExecutor")


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


def _make_task_key(
    task_name: str = "", task_index: int = None, **kwargs: Any
) -> Optional[str]:
    """A helper for generating a dask task key from fields set in `extra_context`"""
    if task_name:
        suffix = uuid.uuid4().hex
        if task_index is not None:
            return f"{task_name}-{task_index}-{suffix}"
        return f"{task_name}-{suffix}"
    return None


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
        **kwargs: Any,
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
        self.cluster_class = cluster_class
        self.cluster_kwargs = cluster_kwargs
        self.adapt_kwargs = adapt_kwargs
        self.client_kwargs = client_kwargs
        self.client = None

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
                    yield self.client
            else:
                with self.cluster_class(**self.cluster_kwargs) as cluster:  # type: ignore
                    if self.adapt_kwargs:
                        cluster.adapt(**self.adapt_kwargs)
                    with Client(cluster, **self.client_kwargs) as client:
                        self.client = client
                        yield self.client
        finally:
            self.client = None

    def _prep_dask_kwargs(self, extra_context: dict = None) -> dict:
        if extra_context is None:
            extra_context = {}

        dask_kwargs = {"pure": False}  # type: dict

        # set a key for the dask scheduler UI
        key = _make_task_key(**extra_context)
        if key is not None:
            dask_kwargs["key"] = key

        # infer from context if dask resources are being utilized
        task_tags = extra_context.get("task_tags", [])
        dask_resource_tags = [
            tag for tag in task_tags if tag.lower().startswith("dask-resource")
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
        state["client"] = None
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)

    def submit(
        self, fn: Callable, *args: Any, extra_context: dict = None, **kwargs: Any
    ) -> "Future":
        """
        Submit a function to the executor for execution. Returns a Future object.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - extra_context (dict, optional): an optional dictionary with extra information about the submitted task
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - Future: a Future-like object that represents the computation of `fn(*args, **kwargs)`
        """
        if self.client is None:
            raise ValueError("This executor has not been started.")

        kwargs.update(self._prep_dask_kwargs(extra_context))
        return self.client.submit(fn, *args, **kwargs)

    def wait(self, futures: Any) -> Any:
        """
        Resolves the Future objects to their values. Blocks until the computation is complete.

        Args:
            - futures (Any): single or iterable of future-like objects to compute

        Returns:
            - Any: an iterable of resolved futures with similar shape to the input
        """
        if self.client is None:
            raise ValueError("This executor has not been started.")

        return self.client.gather(futures)


class LocalDaskExecutor(Executor):
    """
    An executor that runs all functions locally using `dask` and a configurable
    dask scheduler.

    Args:
        - scheduler (str): The local dask scheduler to use; common options are
            "threads", "processes", and "synchronous".  Defaults to "threads".
        - **kwargs (Any): Additional keyword arguments to pass to dask config
    """

    def __init__(self, scheduler: str = "threads", **kwargs: Any):
        self._callback = None
        self.scheduler = scheduler
        self.dask_config = kwargs
        super().__init__()

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        state["_callback"] = None
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)

    @contextmanager
    def start(self) -> Iterator:
        """Context manager for initializing execution."""
        # import dask here to reduce prefect import times
        from dask.callbacks import Callback

        class PrefectCallback(Callback):
            def __init__(self):  # type: ignore
                self.cache = {}

            def _start(self, dsk):  # type: ignore
                overlap = set(dsk) & set(self.cache)
                for key in overlap:
                    dsk[key] = self.cache[key]

            def _posttask(self, key, value, dsk, state, id):  # type: ignore
                self.cache[key] = value

        try:
            self._callback = PrefectCallback()  # type: ignore
            yield
        finally:
            self._callback = None

    def submit(
        self, fn: Callable, *args: Any, extra_context: dict = None, **kwargs: Any
    ) -> "dask.delayed":
        """
        Submit a function to the executor for execution. Returns a `dask.delayed` object.

        Args:
            - fn (Callable): function that is being submitted for execution
            - *args (Any): arguments to be passed to `fn`
            - extra_context (dict, optional): an optional dictionary with extra
                information about the submitted task
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - dask.delayed: a `dask.delayed` object that represents the
                computation of `fn(*args, **kwargs)`
        """
        # import dask here to reduce prefect import times
        import dask

        extra_kwargs = {}
        key = _make_task_key(**(extra_context or {}))
        if key is not None:
            extra_kwargs["dask_key_name"] = key
        return dask.delayed(fn, pure=False)(*args, **kwargs, **extra_kwargs)

    def wait(self, futures: Any) -> Any:
        """
        Resolves a (potentially nested) collection of `dask.delayed` object to
        its values. Blocks until the computation is complete.

        Args:
            - futures (Any): iterable of `dask.delayed` objects to compute

        Returns:
            - Any: an iterable of resolved futures
        """
        # import dask here to reduce prefect import times
        import dask

        with self._callback, dask.config.set(**self.dask_config):  # type: ignore
            return dask.compute(futures, scheduler=self.scheduler)[0]
