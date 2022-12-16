import asyncio
import contextvars
import functools
import inspect
import threading
from concurrent.futures import Executor as BaseExecutor
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional, Tuple, Type, TypeVar

import cloudpickle
from typing_extensions import Literal, ParamSpec

T = TypeVar("T")
P = ParamSpec("P")
WorkerType = Literal["thread", "process"]

threadlocals = threading.local()


class _FakeContext:
    def run(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)


def cloudpickle_wrapped_call(
    __fn: Callable, *args: Any, **kwargs: Any
) -> Callable[[], bytes]:
    """
    Serializes a function call using cloudpickle then returns a callable which will
    execute that call and return a cloudpickle serialized return value

    This is particularly useful for sending calls to libraries that only use the Python
    built-in pickler (e.g. `anyio.to_process` and `multiprocessing`) but may require
    a wider range of pickling support.
    """
    payload = cloudpickle.dumps((__fn, args, kwargs))
    return functools.partial(_run_serialized_call, payload)


def _run_serialized_call(payload) -> bytes:
    """
    Defined at the top-level so it can be pickled by the Python pickler.
    Used by `cloudpickle_wrapped_call`.
    """
    fn, args, kwargs = cloudpickle.loads(payload)
    retval = fn(*args, **kwargs)
    return cloudpickle.dumps(retval)


def _initialize_worker():
    threadlocals.is_worker = True


class Executor(BaseExecutor):
    """
    An executor compatible with usage from asynchronous contexts.
    """

    def __init__(
        self,
        worker_type: WorkerType = "thread",
        max_workers: Optional[int] = None,
    ) -> None:
        super().__init__()

        if worker_type == "thread":
            worker_pool_cls = ThreadPoolExecutor
            worker_pool_kwargs = {"thread_name_prefix": "PrefectWorkerThread-"}
        elif worker_type == "process":
            worker_pool_cls = ProcessPoolExecutor
            worker_pool_kwargs = {}
        else:
            raise ValueError(
                f"Unknown worker type {worker_type}; "
                "expected one of 'thread' or 'process'."
            )

        self._worker_type = worker_type
        self._worker_pool = worker_pool_cls(
            max_workers=max_workers,
            initializer=_initialize_worker,
            **worker_pool_kwargs,
        )

    def submit(
        self, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> Future[T]:
        future = self._worker_pool.submit(
            self._wrap_submitted_call(fn, *args, **kwargs)
        )
        return self._wrap_future(future)

    def shutdown(self, wait=True, *, cancel_futures=False) -> None:
        self._worker_pool.shutdown(wait=wait, cancel_futures=cancel_futures)

    def _wrap_submitted_call(
        self, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> Callable[[], T]:
        """
        Extends run of work items submitted to executors to:
        - Run returned coroutines to completion in a new event loop
        - Run functions with the context from submission
        """

        if self._worker_type == "thread":
            context = contextvars.copy_context()

            def wrapped():
                result = context.run(fn, *args, **kwargs)

                # Check for a returned coroutine; run to completion in a new loop
                if inspect.iscoroutine(result):
                    result = context.run(asyncio.run, result)

                return result

            return wrapped

        else:
            # We should support pickling of some context variables eventually; see
            # - https://github.com/akruis/cvpickle
            # - https://peps.python.org/pep-0567/#making-context-objects-picklable

            @functools.wraps(fn)
            def wrapped():
                result = context.run(fn, *args, **kwargs)

                # Check for a returned coroutine; run to completion in a new loop
                if inspect.iscoroutine(result):
                    result = context.run(asyncio.run, result)

                return result

        return wrapped

    def _wrap_future(self, future: Future) -> Future:

        if self._worker_type == "thread":
            return future

        else:
            result = future.result

            def result(timeout: 

        return wrapped

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        with ThreadPoolExecutor(1) as executor:
            future = executor.submit(self.shutdown)
            await asyncio.wrap_future(future)
