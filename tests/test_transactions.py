import pytest

from prefect.records import Record
from prefect.tasks import task
from prefect.transactions import CommitMode, Transaction, get_transaction


def test_basic_init():
    txn = Transaction()
    assert txn.record is None
    assert txn.rolled_back is False
    assert txn.committed is False
    assert txn.commit_mode is None


def test_equality():
    txn1 = Transaction()
    txn2 = Transaction()
    txn3 = Transaction(record=Record("test"))
    assert txn1 == txn2
    assert txn1 != txn3


def test_get_transaction():
    assert get_transaction() is None
    with Transaction() as txn:
        assert get_transaction() == txn
    assert get_transaction() is None


def test_nested_get_transaction():
    assert get_transaction() is None
    with Transaction(record=Record("outer")) as outer:
        assert get_transaction() == outer
        with Transaction(record=Record("inner")) as inner:
            assert get_transaction() == inner
        assert get_transaction() == outer
    assert get_transaction() is None


class TestGetParent:
    def test_get_parent(self):
        with Transaction() as txn:
            assert txn.get_parent() is None

    def test_get_parent_with_parent(self):
        with Transaction(record=Record("outer")) as outer:
            assert outer.get_parent() is None
            with Transaction(record=Record("inner")) as inner:
                assert inner.get_parent() == outer
            assert outer.get_parent() is None


class TestCommitMode:
    def test_txns_auto_commit(self):
        with Transaction() as txn:
            assert txn.committed is False
        assert txn.committed is True

        outer_rec, inner_rec = Record("outer"), Record("inner")
        with Transaction(record=outer_rec) as outer:
            assert outer.committed is False
            with Transaction(record=inner_rec) as inner:
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
        outer_rec, inner_rec = Record("outer"), Record("inner")
        with Transaction(record=outer_rec, commit_mode=CommitMode.LAZY) as outer:
            assert outer.committed is False

            with Transaction(record=inner_rec) as inner:
                pass

            assert inner.committed is False

        assert outer.committed is True
        assert inner.committed is True

    def test_txns_commit_with_lazy_parent_if_eager(self):
        outer_rec, inner_rec = Record("outer"), Record("inner")
        with Transaction(record=outer_rec, commit_mode=CommitMode.LAZY) as outer:
            assert outer.committed is False

            with Transaction(record=inner_rec, commit_mode=CommitMode.EAGER) as inner:
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

    def test_txns_rollback_on_exception(self):
        with pytest.raises(ValueError, match="foo"):
            with Transaction() as txn:
                raise ValueError("foo")

        assert txn.rolled_back is True

    def test_rollback_flag_gates_rollback(self):
        data = {}

        @task
        def my_task():
            pass

        @my_task.on_rollback
        def rollback(**kwargs):
            data["called"] = True

        with Transaction() as txn:
            txn.add_task(my_task, None)
            txn.rolled_back = True
            txn.rollback()

        assert data.get("called") is None

    def test_rollback_flag_propagates_up(self):
        with Transaction(record=Record("outer")) as outer:
            assert outer.rolled_back is False
            with Transaction(record=Record("inner")) as inner:
                assert inner.rolled_back is False
                with Transaction(record=Record("nested")) as nested:
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
        def rollback(**kwargs):
            data["outer"] = get_transaction().record.key

        @task
        def inner_task():
            pass

        @inner_task.on_rollback
        def inner_rollback(**kwargs):
            data["inner"] = get_transaction().record.key

        with Transaction(record=Record("outer")) as txn:
            txn.add_task(outer_task, None)
            with Transaction(record=Record("inner")) as inner:
                inner.add_task(inner_task, None)
                inner.rollback()

        assert data["inner"] == "inner"
        assert data["outer"] == "outer"
