from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Type,
    TypeVar,
)
from uuid import UUID

from pydantic import Field

from prefect.context import ContextModel
from prefect.exceptions import RollBack
from prefect.records import RecordStore
from prefect.utilities.collections import AutoEnum

if TYPE_CHECKING:
    from prefect.tasks import Task

T = TypeVar("T")


class IsolationLevel(AutoEnum):
    READ_COMMITTED = AutoEnum.auto()
    SERIALIZABLE = AutoEnum.auto()


class CommitMode(AutoEnum):
    EAGER = AutoEnum.auto()
    LAZY = AutoEnum.auto()
    OFF = AutoEnum.auto()


class Transaction(ContextModel):
    """
    A base model for transaction state.
    """

    store: Optional[RecordStore] = None
    key: Optional[str] = None
    tasks: List["Task"] = Field(default_factory=list)
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

        self.begin()
        self._token = self.__var__.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._token:
            raise RuntimeError(
                "Asymmetric use of context. Context exit called without an enter."
            )
        if exc_type:
            if exc_type == RollBack:
                self.rollback()
            self.reset()
            raise exc_val

        if self.commit_mode == CommitMode.EAGER:
            self.commit()

        # if parent, let them take responsibility
        if self.get_parent():
            self.reset()
            return

        if self.commit_mode == CommitMode.OFF:
            # if no one took responsibility to commit, rolling back
            # note that rollback returns if already committed
            self.rollback()
        elif self.commit_mode == CommitMode.LAZY:
            # no one left to take responsibility for committing
            self.commit()

        self.reset()

    def begin(self):
        # currently we only support READ_COMMITTED isolation
        # i.e., no locking behavior
        if self.store and self.store.exists(key=self.key):
            self.committed = True

    def read(self) -> dict:
        return self.store.read(key=self.key)

    def reset(self) -> None:
        parent = self.get_parent()

        if parent:
            # parent takes responsibility
            parent.add_child(self)

        self.__var__.reset(self._token)
        self._token = None

        # do this below reset so that get_transaction() returns the relevant txn
        if parent and self.rolled_back:
            parent.rollback()

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

            if self.store:
                self.store.write(key=self.key, value=self.state.get("_staged_value"))
            self.committed = True
            return True
        except Exception:
            self.rollback()
            return False

    def stage(self, value: dict) -> None:
        """
        Stage a value to be committed later.
        """
        if not self.committed:
            self.state["_staged_value"] = value  # ??

    def rollback(self) -> bool:
        if self.rolled_back or self.committed:
            return False

        try:
            for tsk in reversed(self.tasks):
                for hook in tsk.on_rollback_hooks:
                    hook(self)

            self.rolled_back = True

            for child in reversed(self.children):
                child.rollback()

            return True
        except Exception:
            return False

    def add_task(self, task: "Task") -> None:
        self.tasks.append(task)

    @classmethod
    def get_active(cls: Type[T]) -> Optional[T]:
        return cls.__var__.get(None)


def get_transaction() -> Transaction:
    return Transaction.get_active()


@contextmanager
def transaction(
    key: Optional[str] = None,
    store: Optional[RecordStore] = None,
    commit_mode: CommitMode = CommitMode.LAZY,
) -> Generator[Transaction, None, None]:
    with Transaction(key=key, store=store, commit_mode=commit_mode) as txn:
        yield txn
