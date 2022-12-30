import asyncio
import contextvars
import functools
import inspect
from concurrent.futures import Executor as BaseExecutor
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any, Callable, TypeVar

from typing_extensions import Literal, ParamSpec

T = TypeVar("T")
P = ParamSpec("P")
WorkerType = Literal["thread", "process"]


def _run(__fn, *args, **kwargs):
    """
    Internal utility to run a function on a worker.

    Defined at the top-level to support multiprocess pickling.
    """
    result = __fn(*args, **kwargs)

    # Check for a returned coroutine; run to completion in a new loop
    if inspect.iscoroutine(result):
        result = asyncio.run(result)

    return result


class Executor(BaseExecutor):
    """
    An executor compatible with use from asynchronous contexts.
    """

    def __init__(
        self,
        worker_type: WorkerType = "thread",
        **worker_pool_kwargs: Any,
    ) -> None:
        super().__init__()

        if worker_type == "thread":
            worker_pool_cls = ThreadPoolExecutor
        elif worker_type == "process":
            worker_pool_cls = ProcessPoolExecutor
        else:
            raise ValueError(
                f"Unknown worker type {worker_type}; "
                "expected one of 'thread' or 'process'."
            )

        self._worker_type = worker_type
        self._worker_pool = worker_pool_cls(**worker_pool_kwargs)

    def submit(
        self, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> "Future[T]":
        return self._worker_pool.submit(self._wrap_submitted_call(fn, *args, **kwargs))

    def shutdown(self, wait=True) -> None:
        self._worker_pool.shutdown(wait=wait)

    def _wrap_submitted_call(
        self, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> Callable[[], T]:
        """
        Extends execution of submitted work items.

        - Run returned coroutines to completion in a new event loop
        - Run functions with the context from submission (threads only)
        """
        wrapped = functools.partial(_run, fn, *args, **kwargs)

        if self._worker_type == "thread":
            context = contextvars.copy_context()
            wrapped = functools.partial(context.run, wrapped)

        # We should support pickling of context variables for processes eventually, but
        # it looks pretty complicated; see
        # - https://peps.python.org/pep-0567/#making-context-objects-picklable
        # - https://github.com/akruis/cvpickle

        return wrapped

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        with ThreadPoolExecutor(1, thread_name_prefix="ExecutorShutdown-") as executor:
            future = executor.submit(self.shutdown)
            await asyncio.wrap_future(future)
