from contextlib import contextmanager
from contextvars import ContextVar, Token
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
from prefect.records import Record
from prefect.tasks import Task
from prefect.utilities.collections import AutoEnum

T = TypeVar("T")


class CommitMode(AutoEnum):
    EAGER = AutoEnum.auto()
    LAZY = AutoEnum.auto()
    OFF = AutoEnum.auto()


class Transaction(ContextModel):
    """
    A base model for transaction state.
    """

    record: Record = None
    tasks: List[Task] = Field(default_factory=list)
    state: Dict[UUID, Dict[str, Any]] = Field(default_factory=dict)
    children: List["Transaction"] = Field(default_factory=list)
    commit_mode: Optional[CommitMode] = None
    committed: bool = False
    rolled_back: bool = False
    __var__ = ContextVar("transaction")

    def __enter__(self):
        if self._token is not None:
            raise RuntimeError(
                "Context already entered. Context enter calls cannot be nested."
            )
        # set default commit behavior
        if self.commit_mode is None:
            parent = get_transaction()

            # either inherit from parent or set a default of eager
            if parent:
                self.commit_mode = parent.commit_mode
            else:
                self.commit_mode = CommitMode.EAGER

        self._token = self.__var__.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._token:
            raise RuntimeError(
                "Asymmetric use of context. Context exit called without an enter."
            )
        if exc_type:
            self.rollback()
            self.reset()
            raise exc_val

        if self.commit_mode == CommitMode.EAGER:
            self.commit()

        parent = self.get_parent()

        if parent:
            # parent takes responsibility
            parent.add_child(self)
        elif self.commit_mode == CommitMode.OFF:
            # no one took responsibility to commit, rolling back
            self.rollback()
        elif self.commit_mode == CommitMode.LAZY:
            # no one left to take responsibility for committing
            self.commit()

        self.reset()

        # do this below reset so that get_transaction() returns the relevant txn
        if parent and self.rolled_back:
            parent.rollback()

    def reset(self) -> None:
        self.__var__.reset(self._token)
        self._token = None

    def add_child(self, transaction: "Transaction") -> None:
        self.children.append(transaction)

    def get_parent(self) -> Optional["Transaction"]:
        prev_var = getattr(self._token, "old_value")
        if prev_var != Token.MISSING:
            parent = prev_var
        else:
            parent = None
        return parent

    def commit(self) -> bool:
        if self.rolled_back or self.committed:
            return False

        try:
            for child in self.children:
                child.commit()

            for tsk in self.tasks:
                for hook in tsk.on_commit_hooks:
                    hook(self)

            self.committed = True
            return True
        except Exception:
            self.rollback()
            return False

    def rollback(self) -> bool:
        if self.rolled_back or self.committed:
            return False

        for tsk in reversed(self.tasks):
            for hook in tsk.on_rollback_hooks:
                hook(self)

        self.rolled_back = True

        for child in reversed(self.children):
            child.rollback()

        return True

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
def transaction(
    record: Record = None, commit_mode: CommitMode = CommitMode.LAZY
) -> Transaction:
    with Transaction(record=record, commit_mode=commit_mode) as txn:
        yield txn
