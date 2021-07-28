from typing import Callable, Tuple, Any, Dict
from typing import NamedTuple
from uuid import uuid4

from concurrent.futures import ThreadPoolExecutor, Future


class Call(NamedTuple):
    id: str
    fn: Callable
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]


class BaseExecutor:
    _calls: Dict[str, Call]

    def __init__(self) -> None:
        self._calls = {}

    def submit(
        self,
        fn: Callable,
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> str:
        call = Call(str(uuid4()), fn, args, kwargs)
        self._calls[call.id] = call

        # Call child hook
        self._submit(call)

        return call.id

    def result(self, call_id: str):
        return self._result(call_id)

    def _submit(self, call: Call) -> None:
        raise NotImplementedError

    def _result(self, call_id: str) -> Any:
        raise NotImplementedError


class SyncExecutor(BaseExecutor):
    """
    A simple synchronous executor that executes calls as they are submitted
    """

    def __init__(self) -> None:
        super().__init__()
        self._results: Dict[str, Any] = {}

    def _submit(self, call: Call) -> None:
        try:
            self._results[call.id] = call.fn(*call.args, **call.kwargs)
        except Exception as exc:
            # This is a Prefect exception at this point
            raise RuntimeError(
                f"Encountered an exception while executing {call.fn}"
            ) from exc

    def _result(self, call: Call) -> None:
        return self._results[call.id]


class ThreadedExecutor(BaseExecutor):
    """
    A simple synchronous executor that executes calls as they are submitted
    """

    def __init__(self) -> None:
        super().__init__()
        self._pool = ThreadPoolExecutor()
        self._futures: Dict[str, Future] = {}

    def _submit(self, call: Call) -> None:
        self._futures[call.id] = self._pool.submit(call.fn, *call.args, *call.kwargs)

    def _result(self, call_id: str) -> None:
        return self._futures[call_id].result()
