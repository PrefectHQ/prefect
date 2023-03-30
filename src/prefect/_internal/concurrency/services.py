import abc
import asyncio
import atexit
import concurrent.futures
import contextlib
import threading
from collections import deque
from typing import Generic, Optional, Set, Type, TypeVar

from typing_extensions import Self

from prefect._internal.concurrency.api import create_call, from_sync
from prefect._internal.concurrency.calls import Call
from prefect._internal.concurrency.event_loop import call_soon_in_loop, get_running_loop
from prefect._internal.concurrency.threads import get_global_loop

T = TypeVar("T")


class QueueService(abc.ABC, Generic[T]):
    _instance: Optional[Self] = None
    _instances: Set[Self] = set()
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._queue: Optional[asyncio.Queue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._done_event: Optional[asyncio.Event] = None
        self._task: Optional[asyncio.Task] = None
        self._early_items = deque()
        self._lock = threading.Lock()
        self._stopped: bool = False
        self._started: bool = False

    def start(self):
        self._queue = asyncio.Queue()
        self._loop = asyncio.get_running_loop()
        self._done_event = asyncio.Event()
        self._task = self._loop.create_task(self._run())
        self._started = True
        self._start_call: Optional[Call] = None

        # Put all early submissions in the queue
        while self._early_items:
            self.send(self._early_items.pop())

        # Stop at interpreter exit by default
        atexit.register(self.drain)

    def _stop(self):
        """
        Stop running this instance.

        Does not wait for the instance to finish. See `drain`.
        """
        # Stop sending work to this instance
        self._clear_instance(self)

        if not self._started:
            # Wait for start to finish before stopping
            self._start_call.result()

        self._stopped = True
        call_soon_in_loop(self._loop, self._queue.put_nowait, None)

    def _send(self, item: T):
        """
        Send an item to the instance.
        """
        if self._stopped:
            raise RuntimeError("Cannot put items in a stopped service.")

        if not self._started:
            self._early_items.append(item)
        else:
            call_soon_in_loop(self._loop, self._queue.put_nowait, item)

    async def _run(self):
        while True:
            item: T = await self._queue.get()

            if item is None:
                break

            await self._handle(item)

        self._done_event.set()

    @abc.abstractmethod
    async def _handle(self, item: T):
        """
        Process an item sent to the service.
        """

    @classmethod
    def send(cls, item: T) -> None:
        """
        Send an item to an instance of the service.
        """
        cls.get_instance()._send(item)

    @classmethod
    def drain(cls, wait: bool = True):
        """
        Stop all instances of the service and wait for all remaining work to be
        completed.

        This method is not safe to call from an asynchronous context unless `wait` is
        set to `False`.
        """
        if wait and get_running_loop() is not None:
            raise RuntimeError(
                "Queue services cannot be drained from an async context without "
                "`wait=False`."
            )

        futures = []

        with cls._instance_lock:
            instances = tuple(cls._instances)

        for instance in instances:
            if not instance._stopped:
                instance._stop()

            futures.append(
                asyncio.run_coroutine_threadsafe(
                    instance._done_event.wait(), instance._loop
                )
            )

            cls._instances.discard(instance)

        if wait:
            concurrent.futures.wait(futures)

        return futures

    @classmethod
    def get_instance(cls: Type[Self]) -> Self:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls._new_instance()

            return cls._instance

    @classmethod
    def _clear_instance(cls, instance: Optional[Self] = None):
        with cls._instance_lock:
            if instance is None or instance == cls._instance:
                cls._instance = None

    @classmethod
    def _new_instance(cls):
        """
        Create and start a new instance of the service.
        """
        instance = cls()

        # If already on the global loop, just start it here to avoid deadlock
        if threading.get_ident() == get_global_loop().thread.ident:
            instance.start()

        # Otherwise, bind the service to the global loop
        else:
            from_sync.call_soon_in_loop_thread(create_call(instance.start)).result()

        cls._instances.add(instance)

        return instance


@contextlib.contextmanager
def drain_on_exit(service: QueueService):
    yield
    service.drain()


@contextlib.asynccontextmanager
async def drain_on_exit_async(service: QueueService):
    yield
    futures = [asyncio.wrap_future(fut) for fut in service.drain(wait=False)]
    await asyncio.gather(*futures)
