import pytest

from prefect.futures import PrefectFuture
from uuid import uuid4


def test_future_init():
    test_id = uuid4()
    future = PrefectFuture(run_id=test_id)
    assert future.run_id == test_id


def test_future_result_before_set_fails():
    with pytest.raises(ValueError, match="result has not been set"):
        PrefectFuture(run_id=uuid4()).result()


def test_future_result_after_set():
    future = PrefectFuture(run_id=uuid4())
    future.set_result("foo")
    assert future.result() == "foo"


def test_future_does_not_reraise_returned_exception():
    future = PrefectFuture(run_id=uuid4())
    exc = Exception()
    future.set_result(exc, user_exception=False)
    assert future.result() is exc


def test_future_raises_user_exceptions_on_retrieval():
    future = PrefectFuture(run_id=uuid4())
    future.set_result(ValueError("test"), user_exception=True)
    with pytest.raises(ValueError, match="test"):
        future.result()
