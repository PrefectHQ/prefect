import pytest

from prefect import flow, task
from prefect.settings import PREFECT_ASYNC_FETCH_STATE_RESULT, temporary_settings


@pytest.fixture(autouse=True)
def disable_fetch_by_default():
    """
    The test suite defaults to the future behavior.

    For these tests, we enable the default user behavior.
    """
    with temporary_settings({PREFECT_ASYNC_FETCH_STATE_RESULT: False}):
        yield


@pytest.mark.skip(reason="This test is flaky and needs to be fixed")
async def test_async_result_warnings_are_not_raised_by_engine():
    # Since most of our tests are run with the opt-in globally enabled, this test
    # covers a bunch of features to cover remaining cases where we may internally
    # call `State.result` incorrectly.

    task_run_count = flow_run_count = subflow_run_count = 0

    @task(persist_result=True, retries=3)
    async def my_task():
        nonlocal task_run_count
        task_run_count += 1
        if task_run_count < 3:
            raise ValueError()
        return 1

    @task(persist_result=True, cache_key_fn=lambda *_: "test")
    def foo():
        return 1

    @task(persist_result=True, cache_key_fn=lambda *_: "test")
    def bar():
        return 2

    @flow(persist_result=True)
    def subflow():
        return 1

    @flow(persist_result=True)
    async def async_subflow():
        return 1

    @flow(retries=3, persist_result=True)
    async def retry_subflow():
        nonlocal subflow_run_count
        subflow_run_count += 1
        if subflow_run_count < 3:
            raise ValueError()
        return 1

    @flow(retries=3, persist_result=True)
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

    @flow
    def sync():
        state = foo(return_state=True)
        return state.result()

    assert sync() == 1
