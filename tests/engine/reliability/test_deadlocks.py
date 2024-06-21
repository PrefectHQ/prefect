import pytest
from tests.generic_tasks import (
    add_one,
    async_multiply_by_two,
    noop,
    sleep,
    subtract_ten,
)

from prefect import flow


@pytest.mark.skip(reason="This test takes multiple minutes")
def test_map_wait_for_many_tasks():
    @flow
    def run(n):
        added = add_one.map(range(n))
        result = [subtract_ten(x, wait_for=added) for x in range(n)]

        return result

    run(500)


@pytest.mark.skip(reason="This test takes multiple minutes")
def test_loop_wait_for_many_tasks():
    @flow
    def run(n):
        added = add_one.map(range(n))
        for x in range(n):
            subtract_ten.submit(x, wait_for=added)

    run(500)


@pytest.mark.usefixtures("use_hosted_api_server")
def test_sleep_wait_for():
    @flow
    def run(sleep_time: float, n: int):
        add_one.map(range(n), wait_for=[sleep.submit(sleep_time)])

    run(5, 50)


async def test_async_task_as_dependency():
    @flow
    async def run():
        multiplied = await async_multiply_by_two(42)
        add_one(multiplied)

    await run()


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_sync_task_after_async_in_async_flow():
    @flow
    async def run():
        await async_multiply_by_two(42)
        noop.submit()

    await run()
