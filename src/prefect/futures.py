from collections import OrderedDict
from collections.abc import Iterator as IteratorABC
from dataclasses import fields, is_dataclass
from typing import Any, Callable, Optional, TYPE_CHECKING
from uuid import UUID

from prefect.client import OrionClient
from prefect.orion.schemas.states import State

if TYPE_CHECKING:
    from prefect.executors import BaseExecutor


class PrefectFuture:
    def __init__(
        self,
        flow_run_id: UUID,
        client: OrionClient,
        executor: "BaseExecutor",
        task_run_id: UUID = None,
        _result: State = None,  # Exposed for flow futures which do not call `executor.wait`
    ) -> None:
        self.flow_run_id = flow_run_id
        self.task_run_id = task_run_id
        self.run_id = self.task_run_id or self.flow_run_id
        self._client = client
        self._result: Any = None
        self._exception: Optional[Exception] = None
        self._executor = executor
        self._result = _result

    def result(self, timeout: float = None) -> Optional[State]:
        """
        Return the state of the run the future represents
        """
        if self._result:
            return self._result

        state = self.get_state()
        if (state.is_completed() or state.is_failed()) and state.data:
            return state

        self._result = self._executor.wait(self, timeout)
        return self._result

    def get_state(self) -> State:
        method = (
            self._client.read_task_run_states
            if self.task_run_id
            else self._client.read_flow_run_states
        )
        states = method(self.run_id)
        if not states:
            raise RuntimeError("Future has no associated state in the server.")
        return states[-1]

    def __hash__(self) -> int:
        return hash(self.run_id)


def future_to_data(future: PrefectFuture) -> Any:
    return future.result().data


def resolve_futures(expr, resolve_fn: Callable[[PrefectFuture], Any] = future_to_data):
    """
    Given a Python built-in collection, recursively find `PrefectFutures` and build a
    new collection with the same structure with futures resolved by `resolve_fn`.

    Unsupported object types will be returned without modification.

    By default, futures are resolved into their underlying data which may wait for
    execution to complete. `resolve_fn` can be passed to convert `PrefectFutures` into
    futures native to another executor.
    """
    if isinstance(expr, PrefectFuture):
        return resolve_fn(expr)

    # Get the expression type; treat iterators like lists
    typ = list if isinstance(expr, IteratorABC) else type(expr)

    # If it's a python collection, recursively create a collection of the same type with
    # resolved futures

    if typ in (list, tuple, set):
        return typ([resolve_futures(o) for o in expr])

    if typ in (dict, OrderedDict):
        return typ([[resolve_futures(k), resolve_futures(v)] for k, v in expr.items()])

    if is_dataclass(expr) and not isinstance(expr, type):
        return typ(
            **{f.name: resolve_futures(getattr(expr, f.name)) for f in fields(expr)},
        )

    # If not a supported type, just return it
    return expr
