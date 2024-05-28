import pytest

from prefect.exceptions import RollBack
from prefect.tasks import task
from prefect.transactions import CommitMode, Transaction, get_transaction


def test_basic_init():
    txn = Transaction()
    assert txn.store is None
    assert txn.rolled_back is False
    assert txn.committed is False
    assert txn.commit_mode is None


def test_equality():
    txn1 = Transaction()
    txn2 = Transaction()
    txn3 = Transaction(key="test")
    assert txn1 == txn2
    assert txn1 != txn3


class TestGetTxn:
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


class TestGetParent:
    def test_get_parent(self):
        with Transaction() as txn:
            assert txn.get_parent() is None

    def test_get_parent_with_parent(self):
        with Transaction(key="outer") as outer:
            assert outer.get_parent() is None
            with Transaction(key="inner") as inner:
                assert inner.get_parent() == outer
            assert outer.get_parent() is None


class TestCommitMode:
    def test_txns_auto_commit(self):
        with Transaction() as txn:
            assert txn.committed is False
        assert txn.committed is True

        with Transaction(key="outer") as outer:
            assert outer.committed is False
            with Transaction(key="inner") as inner:
                pass
            assert inner.committed is True
        assert outer.committed is True

    def test_txns_dont_commit_on_exception(self):
        with pytest.raises(ValueError, match="foo"):
            with Transaction() as txn:
                raise ValueError("foo")

        assert txn.committed is False

    def test_txns_dont_commit_on_rollback(self):
        with Transaction() as txn:
            txn.rollback()

        assert txn.committed is False

    def test_txns_dont_auto_commit_with_lazy_parent(self):
        with Transaction(key="outer", commit_mode=CommitMode.LAZY) as outer:
            assert outer.committed is False

            with Transaction(key="inner") as inner:
                pass

            assert inner.committed is False

        assert outer.committed is True
        assert inner.committed is True

    def test_txns_commit_with_lazy_parent_if_eager(self):
        with Transaction(key="outer", commit_mode=CommitMode.LAZY) as outer:
            assert outer.committed is False

            with Transaction(key="inner", commit_mode=CommitMode.EAGER) as inner:
                pass

            assert inner.committed is True

        assert outer.committed is True

    def test_txns_commit_off_rolls_back(self):
        with Transaction(commit_mode=CommitMode.OFF) as txn:
            assert txn.committed is False
        assert txn.committed is False
        assert txn.rolled_back is True

    def test_txns_commit_off_doesnt_roll_back_if_committed(self):
        with Transaction(commit_mode=CommitMode.OFF) as txn:
            txn.commit()
        assert txn.committed is True
        assert txn.rolled_back is False

    def test_error_in_commit_triggers_rollback(self):
        class BadTxn(Transaction):
            def commit(self, **kwargs):
                raise ValueError("foo")

        with Transaction() as txn:
            txn.add_child(BadTxn())

        assert txn.committed is False
        assert txn.rolled_back is True


class TestRollBacks:
    def test_rollback_flag_is_set(self):
        with Transaction() as txn:
            assert txn.rolled_back is False
            txn.rollback()
            assert txn.rolled_back is True

    def test_txns_rollback_on_rollback_exception(self):
        with pytest.raises(ValueError, match="foo"):
            with Transaction() as txn:
                raise ValueError("foo")

        assert txn.rolled_back is False

        with pytest.raises(RollBack, match="foo"):
            with Transaction() as txn:
                raise RollBack("foo")

        assert txn.rolled_back is True

    def test_rollback_flag_gates_rollback(self):
        data = {}

        @task
        def my_task():
            pass

        @my_task.on_rollback
        def rollback(txn):
            data["called"] = True

        with Transaction() as txn:
            txn.add_task(my_task)
            txn.rolled_back = True
            txn.rollback()

        assert data.get("called") is None

    def test_rollback_flag_propagates_up(self):
        with Transaction(key="outer") as outer:
            assert outer.rolled_back is False
            with Transaction(key="inner") as inner:
                assert inner.rolled_back is False
                with Transaction(key="nested") as nested:
                    assert nested.rolled_back is False
                    nested.rollback()
                    assert nested.rolled_back is True
                assert inner.rolled_back is True
            assert outer.rolled_back is True

    def test_nested_rollbacks_have_accurate_active_txn(self):
        data = {}

        @task
        def outer_task():
            pass

        @outer_task.on_rollback
        def rollback(txn):
            data["outer"] = txn.key

        @task
        def inner_task():
            pass

        @inner_task.on_rollback
        def inner_rollback(txn):
            data["inner"] = txn.key

        with Transaction(key="outer") as txn:
            txn.add_task(outer_task)
            with Transaction(key="inner") as inner:
                inner.add_task(inner_task)
                inner.rollback()

        assert data["inner"] == "inner"
        assert data["outer"] == "outer"

    def test_failed_rollback_resets_txn(self):
        class BadTxn(Transaction):
            def rollback(self, **kwargs):
                raise ValueError("foo")

        assert get_transaction() is None

        with Transaction(key="outer") as txn:
            txn.add_child(BadTxn())
            assert txn.rollback() is False  # rollback failed

        assert get_transaction() is None
