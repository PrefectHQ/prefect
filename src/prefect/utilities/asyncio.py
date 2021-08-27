import asyncio
import functools
import threading
import inspect
from multiprocessing import current_process
from typing import Any, Callable, Tuple, Dict, Hashable


async def run_in_threadpool(fn: Callable, *args, **kwargs) -> Any:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))


class ThreadedEventLoop:
    """
    Spawns an event loop in a daemonic thread.

    Creating a new event loop that runs in a child thread prevents us from throwing
    exceptions when there is already an event loop in the main thread and prevents
    synchronous code in the main thread from blocking the event loop from executing.

    These _cannot_ be shared across processes. We use an `EVENT_LOOPS` global to ensure
    that there is a single instance available per process.
    """

    def __init__(self) -> None:
        self._thread, self._loop = self._create_threaded_event_loop()

    def _create_threaded_event_loop(
        self,
    ) -> Tuple[threading.Thread, asyncio.AbstractEventLoop]:
        def start_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        loop = asyncio.new_event_loop()

        t = threading.Thread(target=start_loop, args=(loop,), daemon=True)
        t.start()

        return t, loop

    def run_coro(self, coro):
        if not self._loop:
            raise ValueError("Event loop has not been created.")
        if not self._loop.is_running():
            raise ValueError("Event loop is not running.")

        future = asyncio.run_coroutine_threadsafe(coro, loop=self._loop)
        result = future.result()

        return result

    def __del__(self):
        if self._loop and self._loop.is_running():
            self._loop.stop()


# Mapping of KEY, PID to a lazily instantiated shared event-loop per process
EVENT_LOOPS: Dict[Tuple[Hashable, int], ThreadedEventLoop] = {}


def get_prefect_event_loop(key: Hashable = None):
    """
    Get or create a `ThreadedEventLoop` for the current process; multiple event loops
    per process can be managed by providing a hashable 'key'
    """
    pid = current_process().pid
    if (key, pid) not in EVENT_LOOPS:
        EVENT_LOOPS[(key, pid)] = ThreadedEventLoop()

    return EVENT_LOOPS[(key, pid)]
