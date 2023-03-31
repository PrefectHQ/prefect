import abc
import asyncio
import atexit
import concurrent.futures
import contextlib
import threading
from collections import deque
from typing import Awaitable, Dict, Generic, Optional, Type, TypeVar, Union

from typing_extensions import Self

from prefect._internal.concurrency.api import create_call, from_sync
from prefect._internal.concurrency.calls import Call
from prefect._internal.concurrency.event_loop import call_soon_in_loop, get_running_loop
from prefect._internal.concurrency.threads import get_global_loop

T = TypeVar("T")


class QueueService(abc.ABC, Generic[T]):
    _instances: Dict[int, Self] = {}
    _instance_lock = threading.Lock()

    def __init__(self, *args) -> None:
        self._queue: Optional[asyncio.Queue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._done_event: Optional[asyncio.Event] = None
        self._task: Optional[asyncio.Task] = None
        self._early_items = deque()
        self._lock = threading.Lock()
        self._stopped: bool = False
        self._started: bool = False
        self._key = hash(args)

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
        atexit.register(self.drain_all)

    def _stop(self):
        """
        Stop running this instance.

        Does not wait for the instance to finish. See `drain`.
        """
        if self._stopped:
            return

        # Stop sending work to this instance
        self._remove_instance()

        if not self._started:
            # Wait for start to finish before stopping
            self._start_call.result()

        self._stopped = True
        call_soon_in_loop(self._loop, self._queue.put_nowait, None)

    def send(self, item: T):
        """
        Send an item to this instance of the service.
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

    def _drain(self) -> concurrent.futures.Future:
        """
        Internal implementation for `drain`. Returns a future for sync/async interfaces.
        """
        self._stop()
        future = asyncio.run_coroutine_threadsafe(self._done_event.wait(), self._loop)
        return future

    def drain(self) -> concurrent.futures.Future:
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


@contextlib.contextmanager
def drain_on_exit(service: QueueService):
    yield
    service.drain_all()


@contextlib.asynccontextmanager
async def drain_on_exit_async(service: QueueService):
    yield
    await service.drain_all()
