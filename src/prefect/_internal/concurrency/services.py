from __future__ import annotations

import abc
import asyncio
import concurrent.futures
import contextlib
import logging
import queue
import threading
from collections.abc import AsyncGenerator, Awaitable, Coroutine, Generator, Hashable
from typing import TYPE_CHECKING, Any, Generic, NoReturn, Optional, Union, cast

from typing_extensions import Self, TypeVar, TypeVarTuple, Unpack

from prefect._internal.concurrency import logger
from prefect._internal.concurrency.api import create_call, from_sync
from prefect._internal.concurrency.cancellation import get_deadline, get_timeout
from prefect._internal.concurrency.event_loop import get_running_loop
from prefect._internal.concurrency.threads import WorkerThread, get_global_loop

T = TypeVar("T")
Ts = TypeVarTuple("Ts")
R = TypeVar("R", infer_variance=True)


class _QueueServiceBase(abc.ABC, Generic[T]):
    _instances: dict[int, Self] = {}
    _instance_lock = threading.Lock()

    def __init__(self, *args: Hashable) -> None:
        self._queue: queue.Queue[Optional[T]] = queue.Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._done_event: Optional[asyncio.Event] = None
        self._task: Optional[asyncio.Task[None]] = None
        self._stopped: bool = False
        self._started: bool = False
        self._key = hash((self.__class__, *args))
        self._lock = threading.Lock()
        self._queue_get_thread = WorkerThread(
            # TODO: This thread should not need to be a daemon but when it is not, it
            #       can prevent the interpreter from exiting.
            daemon=True,
            name=f"{type(self).__name__}Thread",
        )
        self._logger = logging.getLogger(f"{type(self).__name__}")

    def start(self) -> None:
        logger.debug("Starting service %r", self)
        loop_thread = get_global_loop()

        if not asyncio.get_running_loop() == getattr(loop_thread, "_loop"):
            raise RuntimeError("Services must run on the global loop thread.")

        self._loop = asyncio.get_running_loop()
        self._done_event = asyncio.Event()
        self._task = self._loop.create_task(self._run())
        self._queue_get_thread.start()
        self._started = True

        # Ensure that we wait for worker completion before loop thread shutdown
        loop_thread.add_shutdown_call(create_call(self.drain))

        # Stop at interpreter exit by default
        # Handling items may require spawning a thread and in 3.9 new threads
        # cannot be spawned after the interpreter finalizes threads which
        #  happens _before_ the normal `atexit` hook is called resulting in
        # failure to process items. This is particularly relevant for services
        # which use an httpx client. See related issue at
        # https://github.com/python/cpython/issues/86813
        threading._register_atexit(self._at_exit)  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

    def _at_exit(self) -> None:
        self.drain(at_exit=True)

    def _stop(self, at_exit: bool = False) -> None:
        """
        Stop running this instance.

        Does not wait for the instance to finish. See `drain`.
        """

        if self._stopped:
            return

        with self._lock:
            if not at_exit:  # The logger may not be available during interpreter exit
                logger.debug("Stopping service %r", self)

            # Stop sending work to this instance
            self._remove_instance()
            self._stopped = True

            # Allow asyncio task to be garbage-collected. Its context may contain
            # references to all Prefect Task calls made during a flow run, through
            # EngineContext. Issue #10338.
            self._task = None

            # Signal completion to the loop
            self._queue.put_nowait(None)

    @abc.abstractmethod
    def send(self, item: Any) -> Any:
        raise NotImplementedError

    async def _run(self) -> None:
        try:
            async with self._lifespan():
                await self._main_loop()
        except BaseException:
            self._remove_instance()
            # The logging call yields to another thread, so we must remove the instance
            # before reporting the failure to prevent retrieval of a dead instance
            log_traceback = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Service %r failed with %s pending items.",
                type(self).__name__,
                self._queue.qsize(),
                exc_info=log_traceback,
            )
        finally:
            self._remove_instance()

            # Shutdown the worker thread
            self._queue_get_thread.shutdown()

            self._stopped = True
            assert self._done_event is not None
            self._done_event.set()

    async def _main_loop(self) -> None:
        last_log_time = 0
        log_interval = 4  # log every 4 seconds

        while True:
            item: Optional[T] = await self._queue_get_thread.submit(
                create_call(self._queue.get)
            ).aresult()

            if self._stopped:
                current_time = asyncio.get_event_loop().time()
                queue_size = self._queue.qsize()

                if current_time - last_log_time >= log_interval and queue_size > 0:
                    self._logger.warning(
                        f"Still processing items: {queue_size} items remaining..."
                    )
                    last_log_time = current_time

            if item is None:
                logger.debug("Exiting service %r", self)
                self._queue.task_done()
                break

            try:
                logger.debug("Service %r handling item %r", self, item)
                await self._handle(item)
            except Exception:
                log_traceback = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Service %r failed to process item %r",
                    type(self).__name__,
                    item,
                    exc_info=log_traceback,
                )
            finally:
                self._queue.task_done()

    @abc.abstractmethod
    async def _handle(self, item: Any) -> Any:
        raise NotImplementedError

    @contextlib.asynccontextmanager
    async def _lifespan(self) -> AsyncGenerator[None, Any]:
        """
        Perform any setup and teardown for the service.
        """
        yield

    def _drain(self, at_exit: bool = False) -> concurrent.futures.Future[bool]:
        """
        Internal implementation for `drain`. Returns a future for sync/async interfaces.
        """
        if not at_exit:  # The logger may not be available during interpreter exit
            logger.debug("Draining service %r", self)

        self._stop(at_exit=at_exit)

        assert self._done_event is not None
        if self._done_event.is_set():
            future: concurrent.futures.Future[bool] = concurrent.futures.Future()
            future.set_result(False)
            return future

        assert self._loop is not None
        task = cast(Coroutine[Any, Any, bool], self._done_event.wait())
        return asyncio.run_coroutine_threadsafe(task, self._loop)

    def drain(self, at_exit: bool = False) -> Union[bool, Awaitable[bool]]:
        """
        Stop this instance of the service and wait for remaining work to be completed.

        Returns an awaitable if called from an async context.
        """
        future = self._drain(at_exit=at_exit)
        if get_running_loop() is not None:
            return asyncio.wrap_future(future)
        else:
            return future.result()

    @classmethod
    def drain_all(
        cls, timeout: Optional[float] = None, at_exit: bool = True
    ) -> Union[
        tuple[
            set[concurrent.futures.Future[bool]], set[concurrent.futures.Future[bool]]
        ],
        Coroutine[
            Any,
            Any,
            Optional[tuple[set[asyncio.Future[bool]], set[asyncio.Future[bool]]]],
        ],
    ]:
        """
        Stop all instances of the service and wait for all remaining work to be
        completed.

        Returns an awaitable if called from an async context.
        """
        futures: list[concurrent.futures.Future[bool]] = []
        with cls._instance_lock:
            instances = tuple(cls._instances.values())

            for instance in instances:
                futures.append(instance._drain(at_exit=at_exit))

        if get_running_loop() is not None:
            if futures:
                return asyncio.wait(
                    [asyncio.wrap_future(fut) for fut in futures], timeout=timeout
                )
            # `wait` errors if it receives an empty list but we need to return a
            # coroutine still
            return asyncio.sleep(0)
        else:
            return concurrent.futures.wait(futures, timeout=timeout)

    def wait_until_empty(self) -> None:
        """
        Wait until the queue is empty and all items have been processed.
        """
        self._queue.join()

    @classmethod
    def instance(cls, *args: Hashable) -> Self:
        """
        Get an instance of the service.

        If an instance already exists with the given arguments, it will be returned.
        """
        with cls._instance_lock:
            key = hash((cls, *args))
            if key not in cls._instances:
                cls._instances[key] = cls._new_instance(*args)

            return cls._instances[key]

    def _remove_instance(self):
        self._instances.pop(self._key, None)

    @classmethod
    def _new_instance(cls, *args: Hashable) -> Self:
        """
        Create and start a new instance of the service.
        """
        instance = cls(*args)

        # If already on the global loop, just start it here to avoid deadlock
        if threading.get_ident() == get_global_loop().thread.ident:
            instance.start()

        # Otherwise, bind the service to the global loop
        else:
            from_sync.call_soon_in_loop_thread(create_call(instance.start)).result()

        return instance


class QueueService(_QueueServiceBase[T]):
    def send(self, item: T) -> None:
        """
        Send an item to this instance of the service.
        """
        with self._lock:
            if self._stopped:
                raise RuntimeError("Cannot put items in a stopped service instance.")

            logger.debug("Service %r enqueuing item %r", self, item)
            self._queue.put_nowait(self._prepare_item(item))

    def _prepare_item(self, item: T) -> T:
        """
        Prepare an item for submission to the service. This is called before
        the item is sent to the service.

        The default implementation returns the item unchanged.
        """
        return item

    @abc.abstractmethod
    async def _handle(self, item: T) -> None:
        """
        Process an item sent to the service.
        """


class FutureQueueService(
    _QueueServiceBase[tuple[Unpack[Ts], concurrent.futures.Future[R]]]
):
    """Queued service that provides a future that is signalled with the acquired result for each item

    If there was a failure acquiring, the future result is set to the exception.

    Type Parameters:
        Ts: the tuple of types that make up sent arguments
        R: the type returned for each item once acquired

    """

    async def _handle(
        self, item: tuple[Unpack[Ts], concurrent.futures.Future[R]]
    ) -> None:
        send_item, future = item[:-1], item[-1]
        try:
            response = await self.acquire(*send_item)
        except Exception as exc:
            # If the request to the increment endpoint fails in a non-standard
            # way, we need to set the future's result so it'll be re-raised in
            # the context of the caller.
            future.set_exception(exc)
            raise exc
        else:
            future.set_result(response)

    @abc.abstractmethod
    async def acquire(self, *args: Unpack[Ts]) -> R:
        raise NotImplementedError

    def send(self, item: tuple[Unpack[Ts]]) -> concurrent.futures.Future[R]:
        with self._lock:
            if self._stopped:
                raise RuntimeError("Cannot put items in a stopped service instance.")

            logger.debug("Service %r enqueuing item %r", self, item)
            future: concurrent.futures.Future[R] = concurrent.futures.Future()
            self._queue.put_nowait((*self._prepare_item(item), future))

        return future

    def _prepare_item(self, item: tuple[Unpack[Ts]]) -> tuple[Unpack[Ts]]:
        """
        Prepare an item for submission to the service. This is called before
        the item is sent to the service.

        The default implementation returns the item unchanged.
        """
        return item


class BatchedQueueService(QueueService[T]):
    """
    A queue service that handles a batch of items instead of a single item at a time.

    Items will be processed when the batch reaches the configured `_max_batch_size`
    or after an interval of `_min_interval` seconds (if set).
    """

    _max_batch_size: int
    _min_interval: Optional[float] = None

    @property
    def min_interval(self) -> float | None:
        return self.__class__._min_interval

    @property
    def max_batch_size(self) -> int:
        return self.__class__._max_batch_size

    async def _main_loop(self):
        done = False

        while not done:
            batch: list[T] = []
            batch_size = 0

            # Pull items from the queue until we reach the batch size
            deadline = get_deadline(self.min_interval)
            while batch_size < self.max_batch_size:
                try:
                    item = await self._queue_get_thread.submit(
                        create_call(self._queue.get, timeout=get_timeout(deadline))
                    ).aresult()

                    if item is None:
                        done = True
                        break

                    batch.append(item)
                    batch_size += self._get_size(item)
                    logger.debug(
                        "Service %r added item %r to batch (size %s/%s)",
                        self,
                        item,
                        batch_size,
                        self.max_batch_size,
                    )
                except queue.Empty:
                    # Process the batch after `min_interval` even if it is smaller than
                    # the batch size
                    break

            if not batch:
                continue

            logger.debug(
                "Service %r processing batch of size %s",
                self,
                batch_size,
            )
            try:
                await self._handle_batch(batch)
            except Exception:
                log_traceback = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Service %r failed to process batch of size %s",
                    self,
                    batch_size,
                    exc_info=log_traceback,
                )

    @abc.abstractmethod
    async def _handle_batch(self, items: list[T]) -> None:
        """
        Process a batch of items sent to the service.
        """

    async def _handle(self, item: T) -> NoReturn:
        raise AssertionError(
            "`_handle` should never be called for batched queue services"
        )

    def _get_size(self, item: T) -> int:
        """
        Calculate the size of a single item.
        """
        # By default, batch size is just the number of items
        return 1


@contextlib.contextmanager
def drain_on_exit(service: QueueService[Any]) -> Generator[None, Any, None]:
    yield
    service.drain_all(at_exit=True)


@contextlib.asynccontextmanager
async def drain_on_exit_async(service: QueueService[Any]) -> AsyncGenerator[None, Any]:
    yield
    drain_all = service.drain_all(at_exit=True)
    if TYPE_CHECKING:
        assert not isinstance(drain_all, tuple)
    await drain_all
