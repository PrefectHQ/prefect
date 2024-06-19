from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import (
    Any,
    Callable,
    Generator,
    List,
    Optional,
    Type,
)

from pydantic import Field
from typing_extensions import Self

from prefect.context import ContextModel, FlowRunContext, TaskRunContext
from prefect.records import RecordStore
from prefect.records.result_store import ResultFactoryStore
from prefect.results import (
    BaseResult,
    ResultFactory,
    get_or_create_default_result_storage,
)
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.collections import AutoEnum


class IsolationLevel(AutoEnum):
    READ_COMMITTED = AutoEnum.auto()
    SERIALIZABLE = AutoEnum.auto()


class CommitMode(AutoEnum):
    EAGER = AutoEnum.auto()
    LAZY = AutoEnum.auto()
    OFF = AutoEnum.auto()


class TransactionState(AutoEnum):
    PENDING = AutoEnum.auto()
    ACTIVE = AutoEnum.auto()
    STAGED = AutoEnum.auto()
    COMMITTED = AutoEnum.auto()
    ROLLED_BACK = AutoEnum.auto()


class Transaction(ContextModel):
    """
    A base model for transaction state.
    """

    store: Optional[RecordStore] = None
    key: Optional[str] = None
    children: List["Transaction"] = Field(default_factory=list)
    commit_mode: Optional[CommitMode] = None
    state: TransactionState = TransactionState.PENDING
    on_commit_hooks: List[Callable[["Transaction"], None]] = Field(default_factory=list)
    on_rollback_hooks: List[Callable[["Transaction"], None]] = Field(
        default_factory=list
    )
    overwrite: bool = False
    _staged_value: Any = None
    __var__: ContextVar = ContextVar("transaction")

    def is_committed(self) -> bool:
        return self.state == TransactionState.COMMITTED

    def is_rolled_back(self) -> bool:
        return self.state == TransactionState.ROLLED_BACK

    def is_staged(self) -> bool:
        return self.state == TransactionState.STAGED

    def is_pending(self) -> bool:
        return self.state == TransactionState.PENDING

    def is_active(self) -> bool:
        return self.state == TransactionState.ACTIVE

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
                self.commit_mode = CommitMode.LAZY

        # this needs to go before begin, which could set the state to committed
        self.state = TransactionState.ACTIVE
        self.begin()
        self._token = self.__var__.set(self)
        return self

    def __exit__(self, *exc_info):
        exc_type, exc_val, _ = exc_info
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
        if (
            not self.overwrite
            and self.store
            and self.key
            and self.store.exists(key=self.key)
        ):
            self.state = TransactionState.COMMITTED

    def read(self) -> BaseResult:
        if self.store and self.key:
            return self.store.read(key=self.key)
        else:
            return {}  # TODO: Determine what this should be

    def reset(self) -> None:
        parent = self.get_parent()

        if parent:
            # parent takes responsibility
            parent.add_child(self)

        if self._token:
            self.__var__.reset(self._token)
            self._token = None

        # do this below reset so that get_transaction() returns the relevant txn
        if parent and self.state == TransactionState.ROLLED_BACK:
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
        if self.state in [TransactionState.ROLLED_BACK, TransactionState.COMMITTED]:
            return False

        try:
            for child in self.children:
                child.commit()

            for hook in self.on_commit_hooks:
                hook(self)

            if self.store and self.key:
                self.store.write(key=self.key, value=self._staged_value)
            self.state = TransactionState.COMMITTED
            return True
        except Exception:
            self.rollback()
            return False

    def stage(
        self,
        value: BaseResult,
        on_rollback_hooks: Optional[List] = None,
        on_commit_hooks: Optional[List] = None,
    ) -> None:
        """
        Stage a value to be committed later.
        """
        on_commit_hooks = on_commit_hooks or []
        on_rollback_hooks = on_rollback_hooks or []

        if self.state != TransactionState.COMMITTED:
            self._staged_value = value
            self.on_rollback_hooks += on_rollback_hooks
            self.on_commit_hooks += on_commit_hooks
            self.state = TransactionState.STAGED

    def rollback(self) -> bool:
        if self.state in [TransactionState.ROLLED_BACK, TransactionState.COMMITTED]:
            return False

        try:
            for hook in reversed(self.on_rollback_hooks):
                hook(self)

            self.state = TransactionState.ROLLED_BACK

            for child in reversed(self.children):
                child.rollback()

            return True
        except Exception:
            return False

    @classmethod
    def get_active(cls: Type[Self]) -> Optional[Self]:
        return cls.__var__.get(None)


def get_transaction() -> Optional[Transaction]:
    return Transaction.get_active()


@contextmanager
def transaction(
    key: Optional[str] = None,
    store: Optional[RecordStore] = None,
    commit_mode: Optional[CommitMode] = None,
    overwrite: bool = False,
) -> Generator[Transaction, None, None]:
    """
    A context manager for opening and managing a transaction.

    Args:
        - key: An identifier to use for the transaction
        - store: The store to use for persisting the transaction result. If not provided,
            a default store will be used based on the current run context.
        - commit_mode: The commit mode controlling when the transaction and
            child transactions are committed
        - overwrite: Whether to overwrite an existing transaction record in the store

    Yields:
        - Transaction: An object representing the transaction state
    """
    # if there is no key, we won't persist a record
    if key and not store:
        flow_run_context = FlowRunContext.get()
        task_run_context = TaskRunContext.get()
        existing_factory = getattr(task_run_context, "result_factory", None) or getattr(
            flow_run_context, "result_factory", None
        )

        if existing_factory and existing_factory.storage_block_id:
            new_factory = existing_factory.model_copy(
                update={
                    "persist_result": True,
                }
            )
        else:
            default_storage = get_or_create_default_result_storage(_sync=True)
            if existing_factory:
                new_factory = existing_factory.model_copy(
                    update={
                        "persist_result": True,
                        "storage_block": default_storage,
                        "storage_block_id": default_storage._block_document_id,
                    }
                )
            else:
                new_factory = run_coro_as_sync(
                    ResultFactory.default_factory(
                        persist_result=True,
                        result_storage=default_storage,
                    )
                )
        store = ResultFactoryStore(
            result_factory=new_factory,
        )

    with Transaction(
        key=key, store=store, commit_mode=commit_mode, overwrite=overwrite
    ) as txn:
        yield txn
