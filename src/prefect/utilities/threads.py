import collections
import threading

import queue
from typing import Any, Dict, List, Callable, Optional, Generator, Type
from contextlib import contextmanager


def terminate_thread(
    thread: "threading.Thread", exc_type: "Exception" = SystemExit
) -> bool:

    # check for the existence of the c-api (e.g. Jython and PyPy will fail here)
    try:
        import ctypes

        set_async_exec = ctypes.pythonapi.PyThreadState_SetAsyncExc
    except Exception:
        return False

    # cannot kill what is not alive...
    if not thread.isAlive():
        return True

    exc = ctypes.py_object(exc_type)
    res = set_async_exec(ctypes.c_long(thread.ident), exc)

    # the thread did not exist
    if res == 0:
        return False

    # we should have only affected a single thread, if it's more than one, undo!
    elif res > 1:
        set_async_exec(thread.ident, None)
        return False
    return True


QueueItem = collections.namedtuple("QueueItem", "event payload")


class ThreadEventLoop:
    def __init__(self, logger) -> None:
        self.logger = logger
        self.event_handlers = collections.defaultdict(
            list
        )  # type: Dict[str, List[Callable]]
        self.threads = (
            collections.OrderedDict()
        )  # type: Dict[threading.Thread, Optional[Callable]]
        self.running = False
        self.queue = queue.Queue()  # type: queue.Queue

        def raise_to_exit(
            event_loop: "ThreadEventLoop", event: str, payload: Any
        ) -> None:
            raise SystemExit()

        self.add_event_handler("exit", raise_to_exit)

    def exit(self) -> None:
        if not self.running:
            return
        self.emit(event="exit", payload=None)

    @contextmanager
    def _start(self) -> Generator:
        self.running = True

        for t in self.threads:
            if isinstance(t, threading.Thread):
                t.start()
            else:
                t.start()

        yield

        try:
            self.logger.debug("EventLoop stopping...")
            for t, shutdown_handler in self.threads.items():
                self.logger.debug(
                    "Shutting down {} (handler: {})".format(t, shutdown_handler)
                )

                if shutdown_handler:
                    shutdown_handler()
                elif isinstance(t, threading.Thread):
                    if not terminate_thread(t):
                        self.logger.warning("Failed to terminate {}".format(t))
                else:
                    self.logger.warning("No way to terminate thread {}".format(t))

        except Exception:
            self.logger.exception("Error when attempting to stop threads")
        finally:
            self.running = False

        self.logger.debug("EventLoop exiting")

    # This accepts any thread or thread-like object.
    # There are two kinds of thread's we're distincting: threads or thread-like objects with a shutdown handler (cooporative)
    # and threading.Threads without a guarentee for shutdown control (independent).
    def add_thread(
        self, thread: Any, shutdown_handler: Optional[Callable] = None
    ) -> None:
        if not isinstance(thread, threading.Thread) and not shutdown_handler:
            raise ValueError(
                "Given a potentially thread-like object without a shutdown callback"
            )

        self.threads[thread] = shutdown_handler

    def add_event_handler(self, event: str, handler: Callable) -> None:
        self.event_handlers[event].append(handler)

    def emit(self, event: str, payload: Any = None) -> None:
        self.logger.debug("Event: {} ({})".format(event, repr(payload)))
        self.queue.put(QueueItem(event=event, payload=payload))

    def run(self, **kwargs: Any) -> None:

        with self._start():
            try:
                while True:
                    item = self.queue.get()

                    if item is None:
                        break
                    elif not isinstance(item, QueueItem):
                        self.logger.warning("Bad event type: {}".format(repr(item)))
                    elif item.event not in self.event_handlers.keys():
                        self.logger.warning("Unhandled event: {}".format(item))
                        continue

                    for handler in self.event_handlers[item.event]:
                        handler(event_loop=self, event=item.event, payload=item.payload)

            except SystemExit:
                pass

            except Exception:
                self.logger.exception("Unhandled exception in the event loop")

            self.logger.debug("No longer accepting further commands")
