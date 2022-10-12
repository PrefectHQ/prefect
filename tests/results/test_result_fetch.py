import pytest

from prefect import flow, task
from prefect.results import LiteralResult
from prefect.settings import PREFECT_ASYNC_FETCH_STATE_RESULT, temporary_settings
from prefect.states import Completed


@pytest.fixture(autouse=True)
def disable_fetch_by_default():
    """
    The test suite defaults to the future behavior.

    For these tests, we enable the default user behavior.
    """
    with temporary_settings({PREFECT_ASYNC_FETCH_STATE_RESULT: False}):
        yield


async def test_async_result_raises_deprecation_warning():
    # This test creates a state directly because a flows do not yet return the new
    # result types
    state = Completed(data=await LiteralResult.create(True))
    result = state.result(fetch=False)

    with pytest.warns(
        DeprecationWarning,
        match=r"State.result\(\) was called from an async context but not awaited.",
    ):
        result = state.result()

    # A result type is returned
    assert isinstance(result, LiteralResult)
    assert await result.get() is True


async def test_async_result_warnings_are_not_raised_by_engine():
    # Since most of our tests are run with the opt-in globally enabled, this test
    # covers a bunch of features to cover remaining cases where we may internally
    # call `State.result` incorrectly.

    task_run_count = flow_run_count = subflow_run_count = 0

    @task(retries=3)
    async def my_task():
        nonlocal task_run_count
        task_run_count += 1
        if task_run_count < 3:
            raise ValueError()
        return 1

    @task(cache_key_fn=lambda *_: "test")
    def foo():
        return 1

    @task(cache_key_fn=lambda *_: "test")
    def bar():
        return 2

    @flow
    def subflow():
        return 1

    @flow
    async def async_subflow():
        return 1

    @flow(retries=3)
    async def retry_subflow():
        nonlocal subflow_run_count
        subflow_run_count += 1
        if subflow_run_count < 3:
            raise ValueError()
        return 1

    @flow(retries=3)
    async def my_flow():
        a = await my_task()

        b = foo()
        c = bar()
        d = subflow()
        e = await async_subflow()
        f = await retry_subflow()

        nonlocal flow_run_count
        flow_run_count += 1

        if flow_run_count < 3:
            raise ValueError()

        return a + b + c + d + e + f

    assert await my_flow() == 6


async def test_async_result_does_not_raise_warning_with_opt_out():
    # This test creates a state directly because a flows do not yet return the new
    # result types
    state = Completed(data=await LiteralResult.create(True))
    result = state.result(fetch=False)

    # A result type is returned
    assert isinstance(result, LiteralResult)
    assert await result.get() is True


async def test_async_result_returns_coroutine_with_opt_in():
    @flow
    async def foo():
        return 1

    state = await foo(return_state=True)
    coro = state.result(fetch=True)
    assert await coro == 1


async def test_async_result_returns_coroutine_with_setting():
    @flow
    async def foo():
        return 1

    state = await foo(return_state=True)
    with temporary_settings({PREFECT_ASYNC_FETCH_STATE_RESULT: True}):
        coro = state.result(fetch=True)

    assert await coro == 1


def test_sync_result_does_not_raise_warning():
    @flow
    def foo():
        return 1

    state = foo(return_state=True)
    result = state.result()
    assert result == 1
