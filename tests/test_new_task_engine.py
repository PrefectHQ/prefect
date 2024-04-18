from prefect import task
from prefect.new_task_engine import run_task


async def test_basic():
    @task
    async def foo():
        return 42

    result = await run_task(foo)

    assert result == 42
