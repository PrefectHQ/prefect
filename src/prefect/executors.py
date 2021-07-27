from typing import Callable, Tuple, Any, Dict
from typing import NamedTuple
from uuid import uuid4


class Call(NamedTuple):
    fn: Callable
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]


class Executor:
    _calls: Dict[str, Call]

    def __init__(self) -> None:
        self._calls = {}

    def submit(
        self,
        fn: Callable,
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> str:
        call_id = str(uuid4())
        self._calls[call_id] = Call(fn, args, kwargs)

        # STUB: Execute immediately
        self._execute(call_id)

        return call_id

    def _execute(self, call_id: str) -> None:
        call = self._calls[call_id]

        try:
            call.fn(*call.args, **call.kwargs)
        except Exception as exc:
            # This is a Prefect exception at this point
            raise RuntimeError(
                f"Encountered an exception while executing {call.fn}"
            ) from exc
