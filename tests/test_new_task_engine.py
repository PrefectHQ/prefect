import pytest

from prefect import task, Task
from prefect.client.orchestration import PrefectClient
from prefect.new_task_engine import run_task, TaskRunEngine


@task
async def foo():
    return 42


class TestTaskRunEngine:
    async def test_basic_init(self):
        engine = TaskRunEngine(task=foo)
        assert isinstance(engine.task, Task)
        assert engine.task.name == "foo"

    async def test_get_client_raises_informative_error(self):
        engine = TaskRunEngine(task=foo)
        with pytest.raises(RuntimeError, match="not started"):
            await engine.get_client()

    async def test_get_client_returns_client_after_starting(self):
        engine = TaskRunEngine(task=foo)
        async with engine.start():
            client = await engine.get_client()
            assert isinstance(client, PrefectClient)

        with pytest.raises(RuntimeError, match="not started"):
            await engine.get_client()


async def test_basic():
    @task
    async def foo():
        return 42

    result = await run_task(foo)

    assert result == 42
