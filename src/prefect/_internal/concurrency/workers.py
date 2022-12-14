import asyncio
import contextvars
import dataclasses
import threading
import weakref
from queue import Queue
from typing import Callable, Dict, Optional, Set, Tuple, TypeVar, Union

import anyio.abc
from typing_extensions import ParamSpec

from prefect._internal.concurrency.primitives import Future

T = TypeVar("T")
P = ParamSpec("P")


@dataclasses.dataclass
class _WorkItem:
    """
    A representation of work sent to a worker thread.
    """

    future: Future
    fn: Callable
    args: Tuple
    kwargs: Dict
    context: contextvars.Context

    def run(self):
        if not self.future.set_running_or_notify_cancel():
            return
        try:
            result = self.context.run(self.fn, *self.args, **self.kwargs)
        except BaseException as exc:
            self.future.set_exception(exc)
            # Prevent reference cycle in `exc`
            self = None
        else:
            self.future.set_result(result)


class _WorkerThread(threading.Thread):
    def __init__(
        self,
        queue: "Queue[Union[_WorkItem, None]]",  # Typing only supported in Python 3.9+
        idle: threading.Semaphore,
        name: str = None,
    ):
        super().__init__(name=name)
        self._queue = queue
        self._idle = idle

    def run(self) -> None:
        while True:
            work_item = self._queue.get()
            if work_item is None:
                # Shutdown command received; forward to other workers and exit
                self._queue.put_nowait(None)
                return

            work_item.run()
            self._idle.release()

            del work_item


class WorkerThreadPool:
    def __init__(self, max_workers: int = 40) -> None:
        self._queue: "Queue[Union[_WorkItem, None]]" = Queue()
        self._workers: Set[_WorkerThread] = set()
        self._max_workers = max_workers
        self._idle = threading.Semaphore(0)
        self._lock = asyncio.Lock()
        self._shutdown = False

        # On garbage collection of the pool, signal shutdown to workers
        weakref.finalize(self, self._queue.put_nowait, None)

    async def submit(
        self, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> Future[T]:
        """
        Submit a function to run in a worker thread.

        Returns a future which can be used to retrieve the result of the function.
        """
        async with self._lock:
            if self._shutdown:
                raise RuntimeError("Work cannot be submitted to pool after shutdown.")

            future = Future()

            work_item = _WorkItem(
                future=future,
                fn=fn,
                args=args,
                kwargs=kwargs,
                context=contextvars.copy_context(),
            )

            # Place the new work item on the work queue
            self._queue.put_nowait(work_item)

            # Ensure there are workers available to run the work
            self._adjust_worker_count()

            return future

    async def shutdown(self, task_status: Optional[anyio.abc.TaskStatus] = None):
        """
        Shutdown the pool, waiting for all workers to complete before returning.

        If work is submitted before shutdown, they will run to completion.
        After shutdown, new work may not be submitted.

        When called with `TaskGroup.start(...)`, the task will be reported as started
        after signalling shutdown to workers.
        """
        async with self._lock:
            self._shutdown = True
            self._queue.put_nowait(None)

            if task_status:
                task_status.started()

            # Avoid blocking the event loop while waiting for threads to join by
            # joining in another thread; we use a new instance of ourself to avoid
            # reimplementing threaded work.
            pool = WorkerThreadPool(max_workers=1)
            futures = [await pool.submit(worker.join) for worker in self._workers]
            await asyncio.gather(*[future.aresult() for future in futures])

            self._workers.clear()

    def _adjust_worker_count(self):
        """
        This method should called after work is added to the queue.

        If no workers are idle and the maximum worker count is not reached, add a new
        worker. Otherwise, decrement the idle worker count since work as been added
        to the queue and a worker will be busy.

        Note on cleanup of workers:
            Workers are only removed on shutdown. Workers could be shutdown after a
            period of idle. However, we expect usage in Prefect to generally be
            incurred in a workflow that will not have idle workers once they are
            created. As long as the maximum number of workers remains relatively small,
            the overhead of idle workers should be negligable.
        """
        if (
            # `acquire` returns false if the idle count is at zero; otherwise, it
            # decrements the idle count and returns true
            not self._idle.acquire(blocking=False)
            and len(self._workers) < self._max_workers
        ):
            self._add_worker()

    def _add_worker(self):
        worker = _WorkerThread(
            queue=self._queue,
            idle=self._idle,
            name=f"PrefectWorker-{len(self._workers)}",
        )
        self._workers.add(worker)
        worker.start()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.shutdown()
