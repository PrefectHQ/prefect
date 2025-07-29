from __future__ import annotations

import asyncio
import datetime
import threading
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from prefect.exceptions import ConfigurationError
from prefect.filesystems import LocalFileSystem, NullFileSystem
from prefect.flows import flow
from prefect.locking.memory import MemoryLockManager
from prefect.results import (
    ResultRecord,
    ResultStore,
    aget_default_result_storage,
    get_default_result_storage,
)
from prefect.settings import (
    PREFECT_DEFAULT_RESULT_STORAGE_BLOCK,
    PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK,
    temporary_settings,
)
from prefect.tasks import task
from prefect.transactions import (
    AsyncTransaction,
    BaseTransaction,
    CommitMode,
    IsolationLevel,
    Transaction,
    TransactionState,
    atransaction,
    get_transaction,
    transaction,
)


def test_basic_init():
    txn = Transaction()
    assert txn.store is None
    assert txn.state == TransactionState.PENDING
    assert txn.is_pending()
    assert txn.commit_mode is None


def test_async_basic_init():
    txn = AsyncTransaction()
    assert txn.store is None
    assert txn.state == TransactionState.PENDING
    assert txn.is_pending()
    assert txn.commit_mode is None


def test_equality():
    txn1 = Transaction()
    txn2 = Transaction()
    txn3 = Transaction(key="test")
    assert txn1 == txn2
    assert txn1 != txn3


def test_async_equality():
    txn1 = AsyncTransaction()
    txn2 = AsyncTransaction()
    txn3 = AsyncTransaction(key="test")
    assert txn1 == txn2
    assert txn1 != txn3


class TestGetTxn:
    class TestTransaction:
        def test_get_transaction(self):
            assert get_transaction() is None
            with Transaction() as txn:
                assert get_transaction() == txn
            assert get_transaction() is None

        def test_nested_get_transaction(self):
            assert get_transaction() is None
            with Transaction(key="outer") as outer:
                assert get_transaction() == outer
                with Transaction(key="inner") as inner:
                    assert get_transaction() == inner
                assert get_transaction() == outer
            assert get_transaction() is None

        def test_txn_resets_even_with_error(self):
            assert get_transaction() is None

            with pytest.raises(ValueError, match="foo"):
                with Transaction() as txn:
                    assert get_transaction() == txn
                    raise ValueError("foo")

            assert get_transaction() is None

    class TestAsyncTransaction:
        async def test_get_transaction_async(self):
            assert get_transaction() is None
            async with AsyncTransaction() as txn:
                assert get_transaction() == txn
            assert get_transaction() is None

        async def test_nested_get_transaction_async(self):
            assert get_transaction() is None
            async with AsyncTransaction(key="outer") as outer:
                assert get_transaction() == outer
                async with AsyncTransaction(key="inner") as inner:
                    assert get_transaction() == inner
                assert get_transaction() == outer
            assert get_transaction() is None

        async def test_txn_resets_even_with_error_async(self):
            assert get_transaction() is None

            with pytest.raises(ValueError, match="foo"):
                async with AsyncTransaction() as txn:
                    assert get_transaction() == txn
                    raise ValueError("foo")


class TestGetParent:
    class TestTransaction:
        def test_get_parent(self):
            with Transaction() as txn:
                assert txn.get_parent() is None

        def test_get_parent_with_parent(self):
            with Transaction(key="outer") as outer:
                assert outer.get_parent() is None
                with Transaction(key="inner") as inner:
                    assert inner.get_parent() == outer
                assert outer.get_parent() is None

        def test_get_parent_works_in_rollback_hook_after_success(self):
            """
            This is a regression test for https://github.com/PrefectHQ/prefect/issues/15593
            """
            spy = MagicMock()

            def hook(txn: Transaction):
                spy(txn.get_parent())

            outer = None
            try:
                with Transaction() as outer:
                    with Transaction(key="inner_with_rollback") as inner_with_rollback:
                        inner_with_rollback.stage("foo", on_rollback_hooks=[hook])
                    with Transaction(key="inner_trouble_maker"):
                        raise ValueError("I'm acting out because I'm misunderstood.")
            except ValueError:
                pass

            assert outer is not None
            spy.assert_called_once_with(outer)

    class TestAsyncTransaction:
        async def test_get_parent(self):
            async with AsyncTransaction() as txn:
                assert txn.get_parent() is None

        async def test_get_parent_with_parent(self):
            async with AsyncTransaction(key="outer") as outer:
                assert outer.get_parent() is None
                async with AsyncTransaction(key="inner") as inner:
                    assert inner.get_parent() == outer
                assert outer.get_parent() is None

        async def test_get_parent_works_in_rollback_hook_after_success(
            self,
        ):
            spy = MagicMock()

            def hook(txn: AsyncTransaction):
                spy(txn.get_parent())

            outer = None
            try:
                async with AsyncTransaction() as outer:
                    async with AsyncTransaction(
                        key="inner_with_rollback"
                    ) as inner_with_rollback:
                        inner_with_rollback.stage("foo", on_rollback_hooks=[hook])
                    async with AsyncTransaction(key="inner_trouble_maker"):
                        raise ValueError(
                            "I'm acting out because I like being the center of attention."
                        )
            except ValueError:
                pass

            assert outer is not None
            spy.assert_called_once_with(outer)


class TestCommitMode:
    class TestTransaction:
        def test_txns_dont_auto_commit(self):
            with Transaction(key="outer") as outer:
                assert not outer.is_committed()

                with Transaction(key="inner") as inner:
                    pass

                assert not inner.is_committed()

            assert outer.is_committed()
            assert inner.is_committed()

        def test_txns_auto_commit_in_eager(self):
            with Transaction(commit_mode=CommitMode.EAGER) as txn:
                assert txn.is_active()
                assert not txn.is_committed()
            assert txn.is_committed()

            with Transaction(key="outer", commit_mode=CommitMode.EAGER) as outer:
                assert not outer.is_committed()
                with Transaction(key="inner") as inner:
                    pass
                assert inner.is_committed()
            assert outer.is_committed()

        def test_txns_dont_commit_on_exception(self):
            txn = None
            with pytest.raises(ValueError, match="foo"):
                with Transaction() as txn:
                    raise ValueError("foo")

            assert txn is not None
            assert not txn.is_committed()
            assert txn.is_rolled_back()

        def test_txns_dont_commit_on_rollback(self):
            with Transaction() as txn:
                txn.rollback()

            assert not txn.is_committed()
            assert txn.is_rolled_back()

        def test_txns_commit_with_lazy_parent_if_eager(self):
            with Transaction(key="outer", commit_mode=CommitMode.LAZY) as outer:
                assert not outer.is_committed()

                with Transaction(key="inner", commit_mode=CommitMode.EAGER) as inner:
                    pass

                assert inner.is_committed()

            assert outer.is_committed()

        def test_txns_commit_off_rolls_back_on_exit(self):
            with Transaction(commit_mode=CommitMode.OFF) as txn:
                assert not txn.is_committed()
            assert not txn.is_committed()
            assert txn.is_rolled_back()

        def test_txns_commit_off_doesnt_roll_back_if_committed(self):
            with Transaction(commit_mode=CommitMode.OFF) as txn:
                txn.commit()
            assert txn.is_committed()
            assert not txn.is_rolled_back()

        def test_error_in_commit_triggers_rollback(self):
            class BadTxn(Transaction):
                def commit(self, **kwargs: Any) -> bool:
                    raise ValueError("foo")

            with Transaction() as txn:
                txn.add_child(BadTxn())

            assert not txn.is_committed()
            assert txn.is_rolled_back()

    class TestAsyncTransaction:
        async def test_txns_dont_auto_commit(self):
            async with AsyncTransaction(key="outer") as outer:
                assert not outer.is_committed()

                async with AsyncTransaction(key="inner") as inner:
                    pass

                assert not inner.is_committed()

            assert outer.is_committed()
            assert inner.is_committed()

        async def test_txns_auto_commit_in_eager(self):
            async with AsyncTransaction(commit_mode=CommitMode.EAGER) as txn:
                assert txn.is_active()
                assert not txn.is_committed()
            assert txn.is_committed()

            with Transaction(key="outer", commit_mode=CommitMode.EAGER) as outer:
                assert not outer.is_committed()
                with Transaction(key="inner") as inner:
                    pass
                assert inner.is_committed()
            assert outer.is_committed()

        async def test_txns_dont_commit_on_exception(self):
            txn = None
            with pytest.raises(ValueError, match="foo"):
                async with AsyncTransaction() as txn:
                    raise ValueError("foo")

            assert txn is not None
            assert not txn.is_committed()
            assert txn.is_rolled_back()

        async def test_txns_dont_commit_on_rollback(self):
            async with AsyncTransaction() as txn:
                await txn.rollback()

            assert not txn.is_committed()
            assert txn.is_rolled_back()

        async def test_txns_commit_with_lazy_parent_if_eager(self):
            async with AsyncTransaction(
                key="outer", commit_mode=CommitMode.LAZY
            ) as outer:
                assert not outer.is_committed()

                async with AsyncTransaction(
                    key="inner", commit_mode=CommitMode.EAGER
                ) as inner:
                    pass

                assert inner.is_committed()

            assert outer.is_committed()

        async def test_txns_commit_off_rolls_back_on_exit(self):
            async with AsyncTransaction(commit_mode=CommitMode.OFF) as txn:
                assert not txn.is_committed()
            assert not txn.is_committed()
            assert txn.is_rolled_back()

        async def test_txns_commit_off_doesnt_roll_back_if_committed(self):
            async with AsyncTransaction(commit_mode=CommitMode.OFF) as txn:
                await txn.commit()
            assert txn.is_committed()
            assert not txn.is_rolled_back()

        async def test_error_in_commit_triggers_rollback(self):
            class BadTxn(AsyncTransaction):
                async def commit(self, **kwargs: Any) -> bool:
                    raise ValueError("foo")

            async with AsyncTransaction() as txn:
                txn.add_child(BadTxn())

            assert not txn.is_committed()
            assert txn.is_rolled_back()


class TestRollBacks:
    class TestTransaction:
        def test_rollback_flag_is_set(self):
            with Transaction() as txn:
                assert not txn.is_rolled_back()
                txn.rollback()
                assert txn.is_rolled_back()

        def test_txns_rollback_on_exception(self):
            txn = None
            with pytest.raises(ValueError, match="foo"):
                with Transaction() as txn:
                    raise ValueError("foo")

            assert txn is not None
            assert txn.is_rolled_back()

        def test_rollback_flag_propagates_up(self):
            with Transaction(key="outer") as outer:
                assert not outer.is_rolled_back()
                with Transaction(key="inner") as inner:
                    assert not inner.is_rolled_back()
                    with Transaction(key="nested") as nested:
                        assert not nested.is_rolled_back()
                        nested.rollback()
                        assert nested.is_rolled_back()
                    assert inner.is_rolled_back()
            assert outer.is_rolled_back()

    class TestAsyncTransaction:
        async def test_rollback_flag_is_set(self):
            async with AsyncTransaction() as txn:
                assert not txn.is_rolled_back()
                await txn.rollback()
                assert txn.is_rolled_back()

        async def test_txns_rollback_on_exception(self):
            txn = None
            with pytest.raises(ValueError, match="foo"):
                async with AsyncTransaction() as txn:
                    raise ValueError("foo")

            assert txn is not None
            assert txn.is_rolled_back()

        async def test_rollback_flag_propagates_up(self):
            async with AsyncTransaction(key="outer") as outer:
                assert not outer.is_rolled_back()
                async with AsyncTransaction(key="inner") as inner:
                    assert not inner.is_rolled_back()
                    async with AsyncTransaction(key="nested") as nested:
                        assert not nested.is_rolled_back()
                        await nested.rollback()
                        assert nested.is_rolled_back()
                    assert inner.is_rolled_back()
            assert outer.is_rolled_back()


class TestTransactionState:
    @pytest.mark.parametrize("txn_class", [Transaction, AsyncTransaction])
    @pytest.mark.parametrize("state", TransactionState.__members__.values())
    def test_state_and_methods_are_consistent(
        self, txn_class: type[BaseTransaction], state: TransactionState
    ):
        "Not the best test, but it does the job"
        txn = txn_class(state=state)
        assert txn.is_active() == (txn.state.name == "ACTIVE")
        assert txn.is_pending() == (txn.state.name == "PENDING")
        assert txn.is_committed() == (txn.state.name == "COMMITTED")
        assert txn.is_staged() == (txn.state.name == "STAGED")
        assert txn.is_rolled_back() == (txn.state.name == "ROLLED_BACK")

    class TestTransaction:
        def test_happy_state_lifecycle(self):
            txn = Transaction()
            assert txn.is_pending()

            with txn:
                assert txn.is_active()

            assert txn.is_committed()

        def test_unhappy_state_lifecycle(self):
            txn = Transaction()
            assert txn.is_pending()

            with pytest.raises(ValueError, match="foo"):
                with txn:
                    assert txn.is_active()
                    raise ValueError("foo")

            assert txn.is_rolled_back()

    class TestAsyncTransaction:
        async def test_happy_state_lifecycle(self):
            txn = AsyncTransaction()
            assert txn.is_pending()

            async with txn:
                assert txn.is_active()

            assert txn.is_committed()

            async with txn:
                assert txn.is_active()

            assert txn.is_committed()

        async def test_unhappy_state_lifecycle(self):
            txn = AsyncTransaction()
            assert txn.is_pending()

            with pytest.raises(ValueError, match="foo"):
                async with txn:
                    assert txn.is_active()
                    raise ValueError("foo")

            assert txn.is_rolled_back()


def test_overwrite_ignores_existing_record():
    class Store(ResultStore):
        def exists(self, key: str) -> bool:
            return True

        def read(self, key: str, holder: str | None = None) -> Any:
            return "done"

        def write(
            self,
            obj: Any,
            key: str | None = None,
            expiration: datetime.datetime | None = None,
            holder: str | None = None,
        ) -> None:
            pass

        def supports_isolation_level(self, level: IsolationLevel) -> bool:
            return True

    with Transaction(
        key="test_overwrite_ignores_existing_record", store=Store()
    ) as txn:
        assert txn.is_committed()

    with Transaction(
        key="test_overwrite_ignores_existing_record", store=Store(), overwrite=True
    ) as txn:
        assert not txn.is_committed()


async def test_overwrite_ignores_existing_record_async():
    class Store(ResultStore):
        async def aexists(self, key: str) -> bool:
            return True

        async def aread(self, key: str, holder: str | None = None) -> Any:
            return "done"

        async def awrite(
            self,
            obj: Any,
            key: str | None = None,
            expiration: datetime.datetime | None = None,
            holder: str | None = None,
        ) -> None:
            pass

        def supports_isolation_level(self, level: IsolationLevel) -> bool:
            return True

    async with AsyncTransaction(
        key="test_overwrite_ignores_existing_record", store=Store()
    ) as txn:
        assert txn.is_committed()

    async with AsyncTransaction(
        key="test_overwrite_ignores_existing_record", store=Store(), overwrite=True
    ) as txn:
        assert not txn.is_committed()


class TestDefaultTransactionStorage:
    @pytest.fixture(autouse=True)
    def default_storage_setting(self, tmp_path: Path):
        name = str(uuid.uuid4())
        LocalFileSystem(basepath=str(tmp_path)).save(name)
        with temporary_settings(
            {
                PREFECT_DEFAULT_RESULT_STORAGE_BLOCK: f"local-file-system/{name}",
                PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK: f"local-file-system/{name}",
            }
        ):
            yield

    class TestTransaction:
        def test_transaction_outside_of_run(self):
            with transaction(
                key="test_transaction_outside_of_run", write_on_commit=True
            ) as txn:
                assert isinstance(txn.store, ResultStore)
                txn.stage({"foo": "bar"})

            record = txn.read()
            assert isinstance(record, ResultRecord)
            assert record.result == {"foo": "bar"}

        def test_transaction_inside_flow_default_storage(self):
            @flow(persist_result=True)
            def test_flow():
                with transaction(
                    key="test_transaction_inside_flow_default_storage"
                ) as txn:
                    assert isinstance(txn.store, ResultStore)
                    txn.stage({"foo": "bar"})

                record = txn.read()
                assert isinstance(record, ResultRecord)
                # make sure we aren't using an anonymous block
                assert (
                    record.metadata.storage_block_id
                    == get_default_result_storage()._block_document_id
                )
                return record.result

            assert test_flow() == {"foo": "bar"}

        def test_transaction_inside_task_default_storage(self):
            @task(persist_result=True)
            def test_task():
                with transaction(
                    key="test_transaction_inside_task_default_storage",
                    commit_mode=CommitMode.EAGER,
                ) as txn:
                    assert isinstance(txn.store, ResultStore)
                    txn.stage({"foo": "bar"})

                record = txn.read()
                assert isinstance(record, ResultRecord)
                # make sure we aren't using an anonymous block
                assert (
                    record.metadata.storage_block_id
                    == get_default_result_storage()._block_document_id
                )
                return record.result

            assert test_task() == {"foo": "bar"}

    class TestAsyncTransaction:
        async def test_transaction_outside_of_run(self):
            async with atransaction(
                key="test_transaction_outside_of_run", write_on_commit=True
            ) as txn:
                assert isinstance(txn.store, ResultStore)
                txn.stage({"foo": "bar"})

            record = await txn.read()
            assert isinstance(record, ResultRecord)
            assert record.result == {"foo": "bar"}

        async def test_transaction_inside_flow_default_storage(self):
            @flow(persist_result=True)
            async def test_flow():
                async with atransaction(
                    key="test_transaction_inside_flow_default_storage"
                ) as txn:
                    assert isinstance(txn.store, ResultStore)
                    txn.stage({"foo": "bar"})

                record = await txn.read()
                assert isinstance(record, ResultRecord)
                # make sure we aren't using an anonymous block
                assert (
                    record.metadata.storage_block_id
                    == (await aget_default_result_storage())._block_document_id
                )
                return record.result

            assert await test_flow() == {"foo": "bar"}

        async def test_transaction_inside_task_default_storage(self):
            @task(persist_result=True)
            async def test_task():
                async with atransaction(
                    key="test_transaction_inside_task_default_storage",
                    commit_mode=CommitMode.EAGER,
                ) as txn:
                    assert isinstance(txn.store, ResultStore)
                    txn.stage({"foo": "bar"})

                record = await txn.read()
                assert isinstance(record, ResultRecord)
                # make sure we aren't using an anonymous block
                assert (
                    record.metadata.storage_block_id
                    == (await aget_default_result_storage())._block_document_id
                )
                return record.result

            assert await test_task() == {"foo": "bar"}


class TestWithResultStore:
    @pytest.fixture(autouse=True)
    def default_storage_setting(self, tmp_path: Path):
        name = str(uuid.uuid4())
        LocalFileSystem(basepath=str(tmp_path)).save(name)
        with temporary_settings(
            {
                PREFECT_DEFAULT_RESULT_STORAGE_BLOCK: f"local-file-system/{name}",
                PREFECT_TASK_SCHEDULING_DEFAULT_STORAGE_BLOCK: f"local-file-system/{name}",
            }
        ):
            yield

    @pytest.fixture
    async def result_store(self):
        result_store = ResultStore(lock_manager=MemoryLockManager())
        return result_store

    class TestTransaction:
        def test_basic_transaction(self, result_store: ResultStore):
            with transaction(
                key="test_basic_transaction", store=result_store, write_on_commit=True
            ) as txn:
                assert isinstance(txn.store, ResultStore)
                txn.stage({"foo": "bar"})

            record_1 = txn.read()
            assert record_1
            assert record_1.result == {"foo": "bar"}

            record_2 = result_store.read("test_basic_transaction")
            assert record_2
            assert record_2 == record_1
            assert record_2.metadata.storage_key == "test_basic_transaction"

        def test_transaction_with_nullfilesystem_metadata(self, tmp_path: Path):
            """Test transactions correctly handle NullFileSystem for metadata storage.

            This tests for the bug where a file would exist at the expected path, but
            the transaction would not recognize it as committed because the exists check
            used metadata_storage (which is a NullFileSystem).

            The fix ensures that when a transaction is created with a ResultStore that has
            NullFileSystem for metadata_storage, it replaces it with None to enable
            metadata persistence and proper idempotency detection.
            """
            # Create a result store with explicit NullFileSystem for metadata_storage
            local_storage = LocalFileSystem(basepath=str(tmp_path))
            result_store = ResultStore(
                result_storage=local_storage,
                metadata_storage=NullFileSystem(),
            )

            # Verify it's using NullFileSystem
            assert isinstance(result_store.metadata_storage, NullFileSystem)

            # First transaction - creates a file
            transaction_key = "test-null-metadata-transaction"
            with transaction(
                key=transaction_key, store=result_store, write_on_commit=True
            ) as txn:
                # Verify transaction has replaced NullFileSystem with None
                assert txn.store.metadata_storage is None
                txn.stage({"foo": "bar"})

            # Verify the file was created
            assert (tmp_path / transaction_key).exists()

            # Second transaction - should recognize the file as already committed
            with transaction(key=transaction_key, store=result_store) as txn:
                assert txn.is_committed(), (
                    "Transaction should correctly identify existing file after replacing NullFileSystem"
                )

        def test_competing_read_transaction(self, result_store: ResultStore):
            write_transaction_open = threading.Event()

            def writing_transaction():
                # isolation level is SERIALIZABLE, so a lock will be taken
                with transaction(
                    key="test_competing_read_transaction",
                    store=result_store,
                    isolation_level=IsolationLevel.SERIALIZABLE,
                    write_on_commit=True,
                ) as txn:
                    write_transaction_open.set()
                    txn.stage({"foo": "bar"})

            thread = threading.Thread(target=writing_transaction)
            thread.start()
            write_transaction_open.wait()
            with transaction(
                key="test_competing_read_transaction", store=result_store
            ) as txn:
                read_result = txn.read()

            assert read_result.result == {"foo": "bar"}
            thread.join()

        async def test_competing_write_transaction(self, result_store: ResultStore):
            transaction_1_open = threading.Event()

            def winning_transaction():
                with transaction(
                    key="test_competing_write_transaction",
                    store=result_store,
                    isolation_level=IsolationLevel.SERIALIZABLE,
                    write_on_commit=True,
                ) as txn:
                    transaction_1_open.set()
                    txn.stage({"foo": "bar"})

            thread = threading.Thread(target=winning_transaction)
            thread.start()
            transaction_1_open.wait()
            with transaction(
                key="test_competing_write_transaction",
                store=result_store,
                isolation_level=IsolationLevel.SERIALIZABLE,
                write_on_commit=True,
            ) as txn:
                txn.stage({"fizz": "buzz"})

            thread.join()
            record = result_store.read("test_competing_write_transaction")
            assert record
            # the first transaction should have written its result
            # and the second transaction should not have written on exit
            assert record.result == {"foo": "bar"}

    class TestAsyncTransaction:
        async def test_basic_transaction(self, result_store: ResultStore):
            async with atransaction(
                key="test_basic_transaction", store=result_store, write_on_commit=True
            ) as txn:
                assert isinstance(txn.store, ResultStore)
                txn.stage({"foo": "bar"})

            record_1 = await txn.read()
            assert record_1
            assert record_1.result == {"foo": "bar"}

            record_2 = await result_store.aread("test_basic_transaction")
            assert record_2
            assert record_2 == record_1
            assert record_2.metadata.storage_key == "test_basic_transaction"

        async def test_transaction_with_nullfilesystem_metadata(self, tmp_path: Path):
            # Create a result store with explicit NullFileSystem for metadata_storage
            local_storage = LocalFileSystem(basepath=str(tmp_path))
            result_store = ResultStore(
                result_storage=local_storage,
                metadata_storage=NullFileSystem(),
            )

            # Verify it's using NullFileSystem
            assert isinstance(result_store.metadata_storage, NullFileSystem)

            # First transaction - creates a file
            transaction_key = "test-null-metadata-transaction"
            async with atransaction(
                key=transaction_key, store=result_store, write_on_commit=True
            ) as txn:
                # Verify transaction has replaced NullFileSystem with None
                assert txn.store.metadata_storage is None
                txn.stage({"foo": "bar"})

            # Verify the file was created
            assert (tmp_path / transaction_key).exists()

            # Second transaction - should recognize the file as already committed
            async with atransaction(key=transaction_key, store=result_store) as txn:
                assert txn.is_committed(), (
                    "Transaction should correctly identify existing file after replacing NullFileSystem"
                )

        async def test_competing_read_transaction(self, result_store: ResultStore):
            write_transaction_open = asyncio.Event()

            async def writing_transaction():
                # isolation level is SERIALIZABLE, so a lock will be taken
                async with atransaction(
                    key="test_competing_read_transaction",
                    store=result_store,
                    isolation_level=IsolationLevel.SERIALIZABLE,
                    write_on_commit=True,
                ) as txn:
                    write_transaction_open.set()
                    txn.stage({"foo": "bar"})

            task = asyncio.create_task(writing_transaction())
            await write_transaction_open.wait()
            async with atransaction(
                key="test_competing_read_transaction", store=result_store
            ) as txn:
                read_result = await txn.read()

            assert read_result.result == {"foo": "bar"}
            await task

        async def test_competing_write_transaction_async(
            self, result_store: ResultStore
        ):
            transaction_1_open = asyncio.Event()

            async def winning_transaction():
                async with atransaction(
                    key="test_competing_write_transaction",
                    store=result_store,
                    isolation_level=IsolationLevel.SERIALIZABLE,
                    write_on_commit=True,
                ) as txn:
                    transaction_1_open.set()
                    txn.stage({"foo": "bar"})

            task = asyncio.create_task(winning_transaction())
            await transaction_1_open.wait()
            async with atransaction(
                key="test_competing_write_transaction",
                store=result_store,
                isolation_level=IsolationLevel.SERIALIZABLE,
                write_on_commit=True,
            ) as txn:
                txn.stage({"fizz": "buzz"})

            await task
            record = await result_store.aread("test_competing_write_transaction")
            assert record
            # the first transaction should have written its result
            # and the second transaction should not have written on exit
            assert record.result == {"foo": "bar"}


class TestGetAndSetData:
    class TestTransaction:
        def test_get_and_set_data(self):
            with transaction(key="test") as txn:
                txn.set("x", 42)
                assert txn.get("x") == 42

        def test_get_and_set_data_in_nested_context(self):
            with transaction(key="test") as top:
                top.set("key", 42)
                with transaction(key="nested") as inner:
                    assert (
                        inner.get("key") == 42
                    )  # children inherit from their parents first
                    inner.set("key", "string")  # and can override
                    assert inner.get("key") == "string"
                    assert top.get("key") == 42
                assert top.get("key") == 42

        def test_get_and_set_data_doesnt_mutate_parent(self):
            with transaction(key="test") as top:
                top.set("key", {"x": [42]})
                with transaction(key="nested") as inner:
                    inner_value = inner.get("key")
                    inner_value["x"].append(43)
                    inner.set("key", inner_value)
                    assert inner.get("key") == {"x": [42, 43]}
                    assert top.get("key") == {"x": [42]}
                assert top.get("key") == {"x": [42]}

        def test_get_raises_on_unknown_but_allows_default(self):
            with transaction(key="test") as txn:
                with pytest.raises(ValueError, match="foobar"):
                    txn.get("foobar")
                assert txn.get("foobar", None) is None
                assert txn.get("foobar", "string") == "string"

        def test_parent_values_set_after_child_open_are_available(self):
            parent_transaction = Transaction()
            child_transaction = Transaction()

            parent_transaction.__enter__()
            child_transaction.__enter__()

            try:
                parent_transaction.set("key", "value")

                # child can access parent's values
                assert child_transaction.get("key") == "value"

                parent_transaction.set("list", [1, 2, 3])
                assert child_transaction.get("list") == [1, 2, 3]

                # Mutating the value doesn't update the stored value
                child_transaction.get("list").append(4)
                assert child_transaction.get("list") == [1, 2, 3]
                child_transaction.set("list", [1, 2, 3, 4])
                assert child_transaction.get("list") == [1, 2, 3, 4]

                # parent transaction isn't affected by child's modifications
                assert parent_transaction.get("list") == [1, 2, 3]

            finally:
                child_transaction.__exit__(None, None, None)
                parent_transaction.__exit__(None, None, None)

    class TestAsyncTransaction:
        async def test_get_and_set_data(self):
            async with atransaction(key="test") as txn:
                txn.set("x", 42)
                assert txn.get("x") == 42

        async def test_get_and_set_data_in_nested_context(self):
            async with atransaction(key="test") as top:
                top.set("key", 42)
                async with atransaction(key="nested") as inner:
                    assert (
                        inner.get("key") == 42
                    )  # children inherit from their parents first
                    inner.set("key", "string")  # and can override
                    assert inner.get("key") == "string"
                    assert top.get("key") == 42
                assert top.get("key") == 42

        async def test_get_and_set_data_doesnt_mutate_parent(self):
            async with atransaction(key="test") as top:
                top.set("key", {"x": [42]})
                async with atransaction(key="nested") as inner:
                    inner_value = inner.get("key")
                    inner_value["x"].append(43)
                    inner.set("key", inner_value)
                    assert inner.get("key") == {"x": [42, 43]}
                    assert top.get("key") == {"x": [42]}
                assert top.get("key") == {"x": [42]}

        async def test_get_raises_on_unknown_but_allows_default(self):
            async with atransaction(key="test") as txn:
                with pytest.raises(ValueError, match="foobar"):
                    txn.get("foobar")
                assert txn.get("foobar", None) is None
                assert txn.get("foobar", "string") == "string"

        async def test_parent_values_set_after_child_open_are_available(self):
            parent_transaction = AsyncTransaction()
            child_transaction = AsyncTransaction()

            await parent_transaction.__aenter__()
            await child_transaction.__aenter__()

            try:
                parent_transaction.set("key", "value")

                # child can access parent's values
                assert child_transaction.get("key") == "value"

                parent_transaction.set("list", [1, 2, 3])
                assert child_transaction.get("list") == [1, 2, 3]

                # Mutating the value doesn't update the stored value
                child_transaction.get("list").append(4)
                assert child_transaction.get("list") == [1, 2, 3]
                child_transaction.set("list", [1, 2, 3, 4])
                assert child_transaction.get("list") == [1, 2, 3, 4]

                # parent transaction isn't affected by child's modifications
                assert parent_transaction.get("list") == [1, 2, 3]

            finally:
                await child_transaction.__aexit__(None, None, None)
                await parent_transaction.__aexit__(None, None, None)


class TestIsolationLevel:
    class TestTransaction:
        def test_default_isolation_level(self):
            with transaction(key="test") as txn:
                assert txn.isolation_level == IsolationLevel.READ_COMMITTED

        def test_inherited_isolation_level(self):
            with transaction(
                key="test",
                store=ResultStore(lock_manager=MemoryLockManager()),
                isolation_level=IsolationLevel.SERIALIZABLE,
            ) as top:
                with transaction(
                    key="nested", store=ResultStore(lock_manager=MemoryLockManager())
                ) as inner:
                    assert (
                        inner.isolation_level
                        == top.isolation_level
                        == IsolationLevel.SERIALIZABLE
                    )

        def test_raises_on_unsupported_isolation_level(self):
            with pytest.raises(
                ConfigurationError,
                match="Isolation level SERIALIZABLE is not supported by provided configuration",
            ):
                with transaction(
                    key="test",
                    store=ResultStore(),
                    isolation_level=IsolationLevel.SERIALIZABLE,
                ):
                    pass

    class TestAsyncTransaction:
        async def test_default_isolation_level(self):
            async with atransaction(key="test") as txn:
                assert txn.isolation_level == IsolationLevel.READ_COMMITTED

        async def test_inherited_isolation_level(self):
            async with atransaction(
                key="test",
                store=ResultStore(lock_manager=MemoryLockManager()),
                isolation_level=IsolationLevel.SERIALIZABLE,
            ) as top:
                async with atransaction(
                    key="nested", store=ResultStore(lock_manager=MemoryLockManager())
                ) as inner:
                    assert (
                        inner.isolation_level
                        == top.isolation_level
                        == IsolationLevel.SERIALIZABLE
                    )

        async def test_raises_on_unsupported_isolation_level(self):
            with pytest.raises(
                ConfigurationError,
                match="Isolation level SERIALIZABLE is not supported by provided configuration",
            ):
                async with atransaction(
                    key="test",
                    store=ResultStore(),
                    isolation_level=IsolationLevel.SERIALIZABLE,
                ):
                    pass

        async def test_serializable_isolation_works_with_multiple_asyncio_tasks(self):
            """
            Regression test for issue https://github.com/PrefectHQ/prefect/issues/18600

            The current task is accounted for in the generated lock holder. Nested transactions
            spanning multiple tasks could previously fail because each task resulted in a different lock holder,
            so the lock could not be released and would raise an error.
            """

            async def child_task():
                async with atransaction(
                    key="child",
                    store=ResultStore(lock_manager=MemoryLockManager()),
                    isolation_level=IsolationLevel.SERIALIZABLE,
                ) as txn:
                    txn.stage({"foo": "bar"})

            async def parent_task():
                async with atransaction(
                    key="parent",
                    store=ResultStore(lock_manager=MemoryLockManager()),
                    isolation_level=IsolationLevel.SERIALIZABLE,
                ):
                    t = asyncio.create_task(child_task())
                    await t

            # Should not raise an error
            await parent_task()

            assert ResultStore().read("child").result == {"foo": "bar"}


class TestHooks:
    class TestTransaction:
        def test_sync_on_commit_hook(self):
            spy = MagicMock()
            with transaction(key="test_sync_on_commit_hook") as txn:
                txn.stage("foo", on_commit_hooks=[spy])

            spy.assert_called_once_with(txn)

        def test_sync_on_rollback_hook(self):
            spy = MagicMock()
            txn = None
            with pytest.raises(RuntimeError):
                with transaction(key="test_sync_on_rollback_hook") as txn:
                    txn.stage("foo", on_rollback_hooks=[spy])
                    raise RuntimeError("I left the stove on!")

            assert txn is not None
            spy.assert_called_once_with(txn)

        def test_async_on_commit_hook(self):
            spy = AsyncMock()

            async def async_on_commit_hook(txn: Transaction):
                await spy(txn)

            with transaction(key="test_async_on_commit_hook") as txn:
                txn.stage("foo", on_commit_hooks=[async_on_commit_hook])

            spy.assert_called_once_with(txn)

        def test_async_on_rollback_hook(self):
            spy = AsyncMock()

            async def async_on_rollback_hook(txn: Transaction):
                await spy(txn)

            txn = None
            with pytest.raises(RuntimeError):
                with transaction(key="test_async_on_rollback_hook") as txn:
                    txn.stage("foo", on_rollback_hooks=[async_on_rollback_hook])
                    raise RuntimeError("I forgot my keys at home!")

            assert txn is not None
            spy.assert_called_once_with(txn)

    class TestAsyncTransaction:
        async def test_sync_on_commit_hook(self):
            spy = MagicMock()
            async with atransaction(key="test_sync_on_commit_hook") as txn:
                txn.stage("foo", on_commit_hooks=[spy])

            spy.assert_called_once_with(txn)

        async def test_sync_on_rollback_hook(self):
            spy = MagicMock()
            txn = None
            with pytest.raises(RuntimeError):
                async with atransaction(key="test_sync_on_rollback_hook") as txn:
                    txn.stage("foo", on_rollback_hooks=[spy])
                    raise RuntimeError("I forgot to pay my internet bill!")

            assert txn is not None
            spy.assert_called_once_with(txn)

        async def test_async_on_commit_hook(self):
            spy = AsyncMock()

            async def async_on_commit_hook(txn: AsyncTransaction):
                await spy(txn)

            async with atransaction(key="test_async_on_commit_hook") as txn:
                txn.stage("foo", on_commit_hooks=[async_on_commit_hook])

            spy.assert_called_once_with(txn)

        async def test_async_on_rollback_hook(self):
            spy = AsyncMock()

            async def async_on_rollback_hook(txn: AsyncTransaction):
                await spy(txn)

            txn = None
            with pytest.raises(RuntimeError):
                async with atransaction(key="test_async_on_rollback_hook") as txn:
                    txn.stage("foo", on_rollback_hooks=[async_on_rollback_hook])
                    raise RuntimeError("The sump pump is unplugged!")

            assert txn is not None
            spy.assert_called_once_with(txn)
