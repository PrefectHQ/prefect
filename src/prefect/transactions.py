from contextlib import contextmanager
from contextvars import ContextVar
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
)
from uuid import UUID

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field
else:
    from pydantic import Field

from prefect.context import ContextModel, TaskRunContext
from prefect.tasks import Task

T = TypeVar("T")


class Transaction(ContextModel):
    """
    A base model for transaction state.
    """

    key: str = None
    tasks: List[Task] = Field(default_factory=list)
    state: Dict[UUID, Dict[str, Any]] = Field(default_factory=dict)
    rolled_back: bool = False
    __var__ = ContextVar("transaction")

    def __enter__(self):
        if self._token is not None:
            raise RuntimeError(
                "Context already entered. Context enter calls cannot be nested."
            )
        self._token = self.__var__.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        if not self._token:
            raise RuntimeError(
                "Asymmetric use of context. Context exit called without an enter."
            )
        self.__var__.reset(self._token)
        self._token = None

        # if exiting a nested transaction with un-committed tasks,
        # merge that state data with the parent for correct rollback behavior
        parent = self.get_active()
        if parent:
            if self.rolled_back:
                parent.rollback()
            else:
                parent.tasks.extend(self.tasks)
                parent.state.update(self.state)

    def rollback(self) -> None:
        for tsk in reversed(self.tasks):
            for hook in tsk.on_rollback_hooks:
                hook(tsk)
        self.rolled_back = True

    def add_task(self, task: Task, task_run_id: UUID) -> None:
        self.tasks.append(task)
        self.state[task_run_id] = {}

    @classmethod
    def get_active(cls: Type[T]) -> Optional[T]:
        return cls.__var__.get(None)

    def get(self, var: str) -> Any:
        ctx = TaskRunContext.get()
        if not ctx:
            raise RuntimeError(
                "Transaction state can only be set from within a task run context."
            )
        if ctx.task_run not in self.state:
            raise RuntimeError(
                "Task run initiated outside the scope of this transcation."
            )
        return self.state[ctx.task_run].get(var)

    def set(self, var: str, val: Any) -> None:
        ctx = TaskRunContext.get()
        if not ctx:
            raise RuntimeError(
                "Transaction state can only be set from within a task run context."
            )
        if ctx.task_run not in self.state:
            raise RuntimeError(
                "Task run initiated outside the scope of this transcation."
            )

        self.state[ctx.task_run][var] = val


def get_transaction() -> Transaction:
    return Transaction.get_active()


@contextmanager
def transaction() -> Transaction:
    with Transaction() as txn:
        return txn
