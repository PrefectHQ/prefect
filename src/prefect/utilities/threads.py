import collections

from queue import Queue
from typing import Any
from contextlib import contextmanager


def terminate_thread(thread, exc_type=SystemExit):
    import ctypes

    if not thread.isAlive():
        return

    exc = ctypes.py_object(exc_type)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread.ident), exc)

    if res == 0:
        raise ValueError("Thread does not exist")
    elif res > 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


QueueItem = collections.namedtuple("QueueItem", "event payload")


class ThreadEventLoop:
    def __init__(self, logger) -> None:
        self.logger = logger
        self.event_handlers = collections.defaultdict(
            list
        )  # { event : [handler, ...] }
        self.threads = collections.OrderedDict()  # { thread: shutdown handler }
        self.running = False
        self.queue = Queue()

        def exit(manager, event, payload):
            raise SystemExit()

        # TODO: this wont allow multiple event handlers... should we?
        self.add_event_handler("exit", exit)

    def exit(self) -> None:
        if not self.running:
            raise RuntimeError("Threads not activated")
        self.queue.put(QueueItem(event="exit", payload=None))

    @contextmanager
    def _start(self) -> None:
        self.running = True

        for t in self.threads:
            # TODO: set more useful name_prefix
            t.start()

        yield

        try:
            self.logger.debug("Stopping threads...")
            for t, shutdown_handler in self.threads.items():
                try:
                    if t.isAlive():
                        if shutdown_handler:
                            shutdown_handler()
                            # TODO: join all, with timeout, on timeout do terminate
                        else:
                            # TODO: catch SystemError and exit anyway.... depends on daemon threads
                            terminate_thread(t)
                # TODO: get periodic monitor to work
                except AttributeError:
                    continue
        except Exception:
            self.logger.exception("Error when attempting to stop threads")
        finally:
            self.running = False
            self.logger.debug("Stopped")

    # there are two kinds of thread's we're distincting: threads with a shutdown handler (cooporative)
    # and threads without a guarentee for shutdown control (independent).
    def add_thread(self, thread, shutdown_handler=None):
        # if not shutdown_handler:
        #     thread.daemon = True

        # TODO: assert thread type
        self.threads[thread] = shutdown_handler

    def add_event_handler(self, event, handler):
        self.event_handlers[event].append(handler)

    def emit(self, event, payload=None):
        self.queue.put(QueueItem(event=event, payload=payload))

    def run(self, **kwargs: Any):

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
                        handler(manager=self, event=item.event, payload=item.payload)

            except SystemExit:
                pass

            except Exception:
                self.logger.exception("Unhandled exception in the event loop")

            self.logger.debug("No longer accepting further commands")
