import asyncio
import logging
import uuid
import sys
import weakref
from contextlib import contextmanager
from typing import Any, Callable, Iterator, TYPE_CHECKING, Union, Optional, Dict

from prefect import context
from prefect.executors.base import Executor
from prefect.utilities.importtools import import_object

if TYPE_CHECKING:
    import dask
    from distributed import Future, Event
    import multiprocessing.pool
    import concurrent.futures


__any__ = ("DaskExecutor", "LocalDaskExecutor")


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


def _maybe_run(event_name: str, fn: Callable, *args: Any, **kwargs: Any) -> Any:
    """Check if the task should run against a `distributed.Event` before
    starting the task. This offers stronger guarantees than distributed's
    current cancellation mechanism, which only cancels pending tasks."""
    import dask
    from distributed import Event, get_client

    try:
        # Explicitly pass in the timeout from dask's config. Some versions of
        # distributed hardcode this rather than using the value from the
        # config.  Can be removed once we bump our min requirements for
        # distributed to >= 2.31.0.
        timeout = dask.config.get("distributed.comm.timeouts.connect")
        event = Event(event_name, client=get_client(timeout=timeout))
        should_run = event.is_set()
    except Exception:
        # Failure to create an event is usually due to connection errors. These
        # are either due to flaky behavior in distributed's comms under high
        # loads, or due to the scheduler shutting down. Either way, the safest
        # course here is to assume we *should* run the task still. If we guess
        # wrong, we're either doing a bit of unnecessary work, or the cluster
        # is shutting down and the task will be cancelled anyway.
        should_run = True

    if should_run:
        return fn(*args, **kwargs)


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
        - adapt_kwargs (dict, optional): additional kwargs to pass to `cluster.adapt`
            when creating a temporary dask cluster. Note that adaptive scaling
            is only enabled if `adapt_kwargs` are provided.
        - client_kwargs (dict, optional): additional kwargs to use when creating a
            [`dask.distributed.Client`](https://distributed.dask.org/en/latest/api.html#client).
        - debug (bool, optional): When running with a local cluster, setting
            `debug=True` will increase dask's logging level, providing
            potentially useful debug info. Defaults to the `debug` value in
            your Prefect configuration.

    Examples:

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
    ):
        if address is None:
            address = context.config.engine.executor.dask.address or None

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

            if adapt_kwargs is None:
                adapt_kwargs = {}

        if client_kwargs is None:
            client_kwargs = {}
        else:
            client_kwargs = client_kwargs.copy()
        client_kwargs.setdefault("set_as_default", False)

        self.address = address
        self.cluster_class = cluster_class
        self.cluster_kwargs = cluster_kwargs
        self.adapt_kwargs = adapt_kwargs
        self.client_kwargs = client_kwargs
        # Runtime attributes
        self.client = None
        # These are coupled - they're either both None, or both non-None.
        # They're used in the case we can't forcibly kill all the dask workers,
        # and need to wait for all the dask tasks to cleanup before exiting.
        self._futures = None  # type: Optional[weakref.WeakSet[Future]]
        self._should_run_event = None  # type: Optional[Event]
        # A ref to a background task subscribing to dask cluster events
        self._watch_dask_events_task = None  # type: Optional[concurrent.futures.Future]

        super().__init__()

    @contextmanager
    def start(self) -> Iterator[None]:
        """
        Context manager for initializing execution.

        Creates a `dask.distributed.Client` and yields it.
        """
        if sys.platform != "win32":
            # Fix for https://github.com/dask/distributed/issues/4168
            import multiprocessing.popen_spawn_posix  # noqa
        from distributed import Client

        try:
            if self.address is not None:
                self.logger.info(
                    "Connecting to an existing Dask cluster at %s", self.address
                )
                with Client(self.address, **self.client_kwargs) as client:
                    self.client = client
                    try:
                        self._pre_start_yield()
                        yield
                    finally:
                        self._post_start_yield()
            else:
                assert callable(self.cluster_class)  # mypy
                assert isinstance(self.cluster_kwargs, dict)  # mypy
                self.logger.info(
                    "Creating a new Dask cluster with `%s.%s`...",
                    self.cluster_class.__module__,
                    self.cluster_class.__qualname__,
                )
                with self.cluster_class(**self.cluster_kwargs) as cluster:
                    if getattr(cluster, "dashboard_link", None):
                        self.logger.info(
                            "The Dask dashboard is available at %s",
                            cluster.dashboard_link,
                        )
                    if self.adapt_kwargs:
                        cluster.adapt(**self.adapt_kwargs)
                    with Client(cluster, **self.client_kwargs) as client:
                        self.client = client
                        try:
                            self._pre_start_yield()
                            yield
                        finally:
                            self._post_start_yield()
        finally:
            self.client = None

    async def _watch_dask_events(self) -> None:
        scheduler_comm = None
        comm = None
        from distributed.core import rpc

        try:
            scheduler_comm = rpc(
                self.client.scheduler.address,  # type: ignore
                connection_args=self.client.security.get_connection_args("client"),  # type: ignore
            )
            # due to a bug in distributed's inproc comms, letting cancellation
            # bubble up here will kill the listener. wrap with a shield to
            # prevent that.
            comm = await asyncio.shield(scheduler_comm.live_comm())
            await comm.write({"op": "subscribe_worker_status"})
            _ = await comm.read()
            while True:
                try:
                    msgs = await comm.read()
                except OSError:
                    break
                for op, msg in msgs:
                    if op == "add":
                        for worker in msg.get("workers", ()):
                            self.logger.debug("Worker %s added", worker)
                    elif op == "remove":
                        self.logger.debug("Worker %s removed", msg)
        except asyncio.CancelledError:
            pass
        except Exception:
            self.logger.debug(
                "Failure while watching dask worker events", exc_info=True
            )
        finally:
            if comm is not None:
                try:
                    await comm.close()
                except Exception:
                    pass
            if scheduler_comm is not None:
                scheduler_comm.close_rpc()

    def _pre_start_yield(self) -> None:
        from distributed import Event

        is_inproc = self.client.scheduler.address.startswith("inproc")  # type: ignore
        if self.address is not None or is_inproc:
            self._futures = weakref.WeakSet()
            self._should_run_event = Event(
                f"prefect-{uuid.uuid4().hex}", client=self.client
            )
            self._should_run_event.set()

        self._watch_dask_events_task = asyncio.run_coroutine_threadsafe(
            self._watch_dask_events(), self.client.loop.asyncio_loop  # type: ignore
        )

    def _post_start_yield(self) -> None:
        from distributed import wait

        if self._watch_dask_events_task is not None:
            try:
                self._watch_dask_events_task.cancel()
            except Exception:
                pass
            self._watch_dask_events_task = None

        if self._should_run_event is not None:
            # Multipart cleanup, ignoring exceptions in each stage
            # 1.) Stop pending tasks from starting
            try:
                self._should_run_event.clear()
            except Exception:
                pass
            # 2.) Wait for all running tasks to complete
            try:
                futures = [f for f in list(self._futures) if not f.done()]  # type: ignore
                if futures:
                    self.logger.info(
                        "Stopping executor, waiting for %d active tasks to complete",
                        len(futures),
                    )
                    wait(futures)
            except Exception:
                pass
        self._should_run_event = None
        self._futures = None

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
        state.update(
            {
                k: None
                for k in [
                    "client",
                    "_futures",
                    "_should_run_event",
                    "_watch_dask_events_task",
                ]
            }
        )
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
            - extra_context (dict, optional): an optional dictionary with extra information
                about the submitted task
            - **kwargs (Any): keyword arguments to be passed to `fn`

        Returns:
            - Future: a Future-like object that represents the computation of `fn(*args, **kwargs)`
        """
        if self.client is None:
            raise ValueError("This executor has not been started.")

        kwargs.update(self._prep_dask_kwargs(extra_context))
        if self._should_run_event is None:
            fut = self.client.submit(fn, *args, **kwargs)
        else:
            fut = self.client.submit(
                _maybe_run, self._should_run_event.name, fn, *args, **kwargs
            )
            self._futures.add(fut)
        return fut

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


def _multiprocessing_pool_initializer() -> None:
    """Initialize a process used in a `multiprocssing.Pool`.

    Ensures the standard atexit handlers are run."""
    import signal

    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit())


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
        self.scheduler = self._normalize_scheduler(scheduler)
        self.dask_config = kwargs
        self._pool = None  # type: Optional[multiprocessing.pool.Pool]
        super().__init__()

    @staticmethod
    def _normalize_scheduler(scheduler: str) -> str:
        scheduler = scheduler.lower()
        if scheduler in ("threads", "threading"):
            return "threads"
        elif scheduler in ("processes", "multiprocessing"):
            return "processes"
        elif scheduler in ("sync", "synchronous", "single-threaded"):
            return "synchronous"
        else:
            raise ValueError(f"Unknown scheduler {scheduler!r}")

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        state["_pool"] = None
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)

    def _interrupt_pool(self) -> None:
        """Interrupt all tasks in the backing `pool`, if any."""
        if self._pool is None:
            return

        # Terminate the pool
        self._pool.terminate()

        if self.scheduler == "threads":
            # `ThreadPool.terminate()` doesn't stop running tasks, only
            # prevents new tasks from running. In CPython we can attempt to
            # raise an exception in all threads. This exception will be raised
            # the next time the task does something with the Python api.
            # However, if the task is currently blocked in a c extension, it
            # will not immediately be interrupted. There isn't a good way
            # around this unfortunately.
            import platform

            if platform.python_implementation() != "CPython":
                self.logger.warning(
                    "Interrupting a running threadpool is only supported in CPython, "
                    "all currently running tasks will continue to completion"
                )
                return

            self.logger.info("Attempting to interrupt and cancel all running tasks...")

            import sys
            import ctypes

            # signature of this method changed in python 3.7
            if sys.version_info >= (3, 7):
                id_type = ctypes.c_ulong
            else:
                id_type = ctypes.c_long

            for t in self._pool._pool:  # type: ignore
                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    id_type(t.ident), ctypes.py_object(KeyboardInterrupt)
                )

    @contextmanager
    def start(self) -> Iterator:
        """Context manager for initializing execution."""
        # import dask here to reduce prefect import times
        import dask.config
        from dask.callbacks import Callback
        from dask.system import CPU_COUNT

        class PrefectCallback(Callback):
            def __init__(self):  # type: ignore
                self.cache = {}

            def _start(self, dsk):  # type: ignore
                overlap = set(dsk) & set(self.cache)
                for key in overlap:
                    dsk[key] = self.cache[key]

            def _posttask(self, key, value, dsk, state, id):  # type: ignore
                self.cache[key] = value

        with PrefectCallback(), dask.config.set(**self.dask_config):
            if self.scheduler == "synchronous":
                self._pool = None
            else:
                num_workers = dask.config.get("num_workers", None) or CPU_COUNT
                if self.scheduler == "threads":
                    from multiprocessing.pool import ThreadPool

                    self._pool = ThreadPool(num_workers)
                else:
                    from dask.multiprocessing import get_context

                    context = get_context()
                    self._pool = context.Pool(
                        num_workers, initializer=_multiprocessing_pool_initializer
                    )
            try:
                exiting_early = False
                yield
            except BaseException:
                exiting_early = True
                raise
            finally:
                if self._pool is not None:
                    if exiting_early:
                        self._interrupt_pool()
                    else:
                        self._pool.close()
                    self._pool.join()
                    self._pool = None

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

        config: Dict[str, Any] = {}  # Extra config options for dask

        # dask's multiprocessing scheduler hardcodes task fusion in a way
        # that's not exposed via a `compute` kwarg. Until that's fixed, we
        # disable fusion globally for the multiprocessing scheduler only.
        # Since multiprocessing tasks execute in a remote process, this
        # shouldn't affect user code.
        if self.scheduler == "processes":

            @contextmanager
            def patch() -> Iterator[None]:
                # Patch around https://github.com/PrefectHQ/prefect/issues/4086
                # We can remove this after we drop support for dask 2021.02.0
                from dask.optimization import cull

                def cull2(dsk, keys):  # type: ignore
                    return cull(dsk if type(dsk) is dict else dict(dsk), keys)

                dask.multiprocessing.cull = cull2
                try:
                    yield
                finally:
                    dask.multiprocessing.cull = cull

            config["optimization.fuse.active"] = False
        else:

            @contextmanager
            def patch() -> Iterator[None]:
                yield

        # Patch around https://github.com/PrefectHQ/prefect/issues/4537
        # dask >= 2021.04.0 adds task submission batching in the multiprocessing case
        # to offset performance concerns from switching to a concurrent.Futures based
        # process pool. Since we are using our own pool to handle cancellation robustly,
        # we do not gain anything from the batched submission and the default task
        # submission batch size of 6 makes users think their flows will not run in
        # parallel. When/if we switch to using the new futures based multiprocessing in
        # dask, we should remove this to retain performance
        if self.scheduler == "processes":
            config["chunksize"] = 1

        with patch(), dask.config.set(config):
            return dask.compute(
                futures, scheduler=self.scheduler, pool=self._pool, optimize_graph=False
            )[0]
