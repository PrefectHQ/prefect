import abc
import asyncio
import atexit
import concurrent.futures
import contextlib
import sys
import threading
from collections import deque
from typing import Awaitable, Dict, Generic, List, Optional, Type, TypeVar, Union

import anyio
from typing_extensions import Self

from prefect._internal.concurrency.api import create_call, from_sync
from prefect._internal.concurrency.event_loop import call_in_loop, get_running_loop
from prefect._internal.concurrency.threads import get_global_loop
from prefect.logging import get_logger

T = TypeVar("T")


logger = get_logger("prefect._internal.concurrency.services")


class QueueService(abc.ABC, Generic[T]):
    _instances: Dict[int, Self] = {}

    def __init__(self, *args) -> None:
        self._queue: Optional[asyncio.Queue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._done_event: Optional[asyncio.Event] = None
        self._task: Optional[asyncio.Task] = None
        self._early_items = deque()
        self._stopped: bool = False
        self._started: bool = False
        self._key = hash(args)
        self._lock = threading.Lock()

    def start(self):
        logger.debug("Starting service %r", self)
        loop_thread = get_global_loop()

        if not asyncio.get_running_loop() == loop_thread._loop:
            raise RuntimeError("Services must run on the global loop thread.")

        self._queue = asyncio.Queue()
        self._loop = loop_thread._loop
        self._done_event = asyncio.Event()
        self._task = self._loop.create_task(self._run())
        self._started = True

        # Ensure that we wait for worker completion before loop thread shutdown
        loop_thread.add_shutdown_call(create_call(self.drain))

        # Put all early submissions in the queue
        while self._early_items:
            self.send(self._early_items.popleft())

        # Stop at interpreter exit by default
        if sys.version_info < (3, 9):
            atexit.register(self.drain)
        else:
            # See related issue at https://bugs.python.org/issue42647
            # Handling items may require spawning a thread and in 3.9  new threads
            # cannot be spawned after the interpreter finalizes threads which happens
            #  _before_ the normal `atexit` hook is called resulting in failure to
            # process items. This is particularly relevant for services which use an
            # httpx client.
            from threading import _register_atexit

            _register_atexit(self.drain)

    def _stop(self):
        """
        Stop running this instance.

        Does not wait for the instance to finish. See `drain`.
        """

        if self._stopped:
            return

        with self._lock:
            logger.debug("Stopping service %r", self)

            # Stop sending work to this instance
            self._remove_instance()

            self._stopped = True
            call_in_loop(self._loop, self._queue.put_nowait, None)

    def send(self, item: T):
        """
        Send an item to this instance of the service.
        """
        with self._lock:
            if self._stopped:
                raise RuntimeError("Cannot put items in a stopped service instance.")

            logger.debug("Service %r enqueing item %r", self, item)

            if not self._started:
                self._early_items.append(item)
            else:
                call_in_loop(
                    self._loop, self._queue.put_nowait, self._prepare_item(item)
                )

    def _prepare_item(self, item: T) -> T:
        """
        Prepare an item for submission to the service. This is called before
        the item is sent to the service.

        The default implementation returns the item unchanged.
        """
        return item

    async def _run(self):
        try:
            async with self._lifespan():
                await self._main_loop()
        except BaseException:
            self._remove_instance()
            # The logging call yields to another thread, so we must remove the instance
            # before reporting the failure to prevent retrieval of a dead instance
            logger.exception(
                "Service %r failed with %s pending items.",
                type(self).__name__,
                self._queue.qsize(),
            )
        finally:
            self._remove_instance()
            self._stopped = True
            self._done_event.set()

    async def _main_loop(self):
        while True:
            item: T = await self._queue.get()

            if item is None:
                break

            try:
                logger.debug("Service %r handling item %r", self, item)
                await self._handle(item)
            except Exception:
                logger.exception(
                    "Service %r failed to process item %r", type(self).__name__, item
                )

    @abc.abstractmethod
    async def _handle(self, item: T):
        """
        Process an item sent to the service.
        """

    @contextlib.asynccontextmanager
    async def _lifespan(self):
        """
        Perform any setup and teardown for the service.
        """
        yield

    def _drain(self) -> concurrent.futures.Future:
        """
        Internal implementation for `drain`. Returns a future for sync/async interfaces.
        """
        self._stop()
        if self._done_event.is_set():
            future = concurrent.futures.Future()
            future.set_result(None)
            return future

        future = asyncio.run_coroutine_threadsafe(self._done_event.wait(), self._loop)
        return future

    def drain(self) -> None:
        """
        Stop this instance of the service and wait for remaining work to be completed.

        Returns an awaitable if called from an async context.
        """
        future = self._drain()
        if get_running_loop() is not None:
            return asyncio.wrap_future(future)
        else:
            return future.result()

    @classmethod
    def drain_all(cls) -> Union[Awaitable, None]:
        """
        Stop all instances of the service and wait for all remaining work to be
        completed.

        Returns an awaitable if called from an async context.
        """
        futures = []
        instances = tuple(cls._instances.values())

        for instance in instances:
            futures.append(instance._drain())

        if get_running_loop() is not None:
            return asyncio.gather(*[asyncio.wrap_future(fut) for fut in futures])
        else:
            return concurrent.futures.wait(futures)

    @classmethod
    def instance(cls: Type[Self], *args) -> Self:
        """
        Get an instance of the service.

        If an instance already exists with the given arguments, it will be returned.
        """
        key = hash(args)
        if key not in cls._instances:
            cls._instances[key] = cls._new_instance(*args)

        return cls._instances[key]

    def _remove_instance(self):
        self._instances.pop(self._key, None)

    @classmethod
    def _new_instance(cls, *args):
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


class BatchedQueueService(QueueService[T]):
    """
    A queue service that handles a batch of items instead of a single item at a time.

    Items will be processed when the batch reaches the configured `_max_batch_size`
    or after an interval of `_min_interval` seconds (if set).
    """

    _max_batch_size: int
    _min_interval: Optional[float] = None

    async def _main_loop(self):
        done = False

        while not done:
            batch = []
            batch_size = 0

            # Process the batch after `min_interval` even if it is smaller than the
            # batch size
            with anyio.move_on_after(self._min_interval):
                # Pull items from the queue until we reach the batch size
                while batch_size < self._max_batch_size:
                    item = await self._queue.get()

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
                        self._max_batch_size,
                    )

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
                logger.exception(
                    "Service %r failed to process batch of size %s",
                    self,
                    batch_size,
                )

    @abc.abstractmethod
    async def _handle_batch(self, items: List[T]):
        """
        Process a batch of items sent to the service.
        """

    async def _handle(self, item: T):
        assert False, "`_handle` should never be called for batched queue services"

    def _get_size(self, item: T) -> int:
        """
        Calculate the size of a single item.
        """
        # By default, batch size is just the number of items
        return 1


@contextlib.contextmanager
def drain_on_exit(service: QueueService):
    yield
    service.drain_all()


@contextlib.asynccontextmanager
async def drain_on_exit_async(service: QueueService):
    yield
    await service.drain_all()
