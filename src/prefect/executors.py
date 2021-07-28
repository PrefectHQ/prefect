from typing import Callable, Tuple, Any, Dict
from typing import NamedTuple
from uuid import uuid4

from prefect.futures import PrefectFuture

import concurrent.futures


class BaseExecutor:
    def __init__(self) -> None:
        pass

    def submit(
        self,
        fn: Callable,
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> None:
        raise NotImplementedError()

    def __enter__(self):
        yield self

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
        fn: Callable,
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> None:
        # Just immediately run the function
        fn(*args, **kwargs)


class ThreadPoolExecutor(BaseExecutor):
    """
    A parallel executor that submits calls to a thread pool
    """

    def __init__(self) -> None:
        super().__init__()
        self._pool = concurrent.futures.ThreadPoolExecutor()

    def submit(
        self,
        fn: Callable,
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> None:
        self._pool.submit(fn, *args, **kwargs)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=True)


class ProcessPoolExecutor(BaseExecutor):
    """
    A parallel executor that submits calls to a process pool
    """

    def __init__(self) -> None:
        super().__init__()
        self._pool = concurrent.futures.ProcessPoolExecutor()

    def submit(
        self,
        fn: Callable,
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> None:
        self._pool.submit(fn, *args, **kwargs)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=True)
