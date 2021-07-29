import concurrent.futures
from functools import partial
from typing import Any, Callable, Dict, Optional

import cloudpickle

from prefect.orion.schemas.core import State


class BaseExecutor:
    def __init__(self) -> None:
        pass

    def submit(
        self,
        fn: Callable,
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> str:
        """
        Submit a call for execution and return a tracking id
        """
        raise NotImplementedError()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False

    def shutdown(self) -> None:
        """
        Clean up resources associated with the executor

        Will block until submitted calls are completed
        """
        pass


class SyncExecutor(BaseExecutor):
    """
    A simple synchronous executor that executes calls as they are submitted
    """

    def __init__(self) -> None:
        super().__init__()

    def submit(
        self,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> Callable[[float], Optional[State]]:
        # Run immediately
        result = run_fn(*args, **kwargs)
        return partial(self._wait, result)

    def _wait(self, result: State, timeout: float = None):
        # Just return the given result
        return result


class ThreadPoolExecutor(BaseExecutor):
    """
    A parallel executor that submits calls to a thread pool
    """

    def __init__(self, debug: bool = False) -> None:
        super().__init__()
        self._pool = concurrent.futures.ThreadPoolExecutor()
        self.debug = debug

    def submit(
        self,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> Callable[[float], Optional[State]]:
        future = self._pool.submit(run_fn, *args, **kwargs)

        if self.debug:
            future.result()

        return partial(self._wait, future)

    def _wait(
        self,
        future: concurrent.futures.Future,
        timeout: float = None,
    ) -> Optional[State]:
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return None

    def shutdown(self) -> None:
        self._pool.shutdown(wait=True)


class ProcessPoolExecutor(BaseExecutor):
    """
    A parallel executor that submits calls to a process pool
    """

    def __init__(self, debug: bool = False) -> None:
        super().__init__()
        self._pool = concurrent.futures.ProcessPoolExecutor()
        self.debug = debug

    def submit(
        self,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> Callable[[float], Optional[State]]:
        payload = _serialize_call(run_fn, *args, **kwargs)
        future = self._pool.submit(_run_serialized_call, payload)

        if self.debug:
            future.result()

        return partial(self._wait, future)

    def _wait(
        self,
        future: concurrent.futures.Future,
        timeout: float = None,
    ) -> Optional[State]:
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return None

    def shutdown(self) -> None:
        self._pool.shutdown(wait=True)


def _serialize_call(fn, *args, **kwargs):
    return cloudpickle.dumps((fn, args, kwargs))


def _run_serialized_call(payload):
    fn, args, kwargs = cloudpickle.loads(payload)
    return fn(*args, **kwargs)
