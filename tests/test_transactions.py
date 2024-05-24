from unittest.mock import MagicMock

from prefect.transactions import Transaction, transaction, get_transaction


def test_basic_init():
    txn = Transaction()
    assert txn.key is None
    assert txn.rolled_back is False


def test_equality():
    txn1 = Transaction()
    txn2 = Transaction()
    txn3 = Transaction(key="test")
    assert txn1 == txn2
    assert txn1 != txn3


def test_get_transaction():
    assert get_transaction() is None
    with Transaction() as txn:
        assert get_transaction() == txn
    assert get_transaction() is None


def test_nested_get_transaction():
    assert get_transaction() is None
    with Transaction(key="outer") as outer:
        assert get_transaction() == outer
        with Transaction(key="inner") as inner:
            assert get_transaction() == inner
        assert get_transaction() == outer
    assert get_transaction() is None


class TestRollBacks:
    def test_rollback_flag_is_set(self):
        with Transaction() as txn:
            assert txn.rolled_back is False
            txn.rollback()
            assert txn.rolled_back is True

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
