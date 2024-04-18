import logging
import pytest

from prefect import task, Task, get_run_logger
from prefect.client.orchestration import PrefectClient
from prefect.new_task_engine import run_task, TaskRunEngine
from prefect.utilities.callables import get_call_parameters


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


class TestTaskRuns:
    async def test_basic(self):
        @task
        async def foo():
            return 42

        result = await run_task(foo)

        assert result == 42

    async def test_with_params(self):
        @task
        async def bar(x: int, y: str = None):
            return x, y

        parameters = get_call_parameters(bar.fn, (42,), dict(y="nate"))
        result = await run_task(bar, parameters=parameters)

        assert result == (42, "nate")

    async def test_get_run_logger(self, caplog):
        caplog.set_level(logging.CRITICAL)

        @task
        async def my_log_task():
            get_run_logger().critical("hey yall")

        result = await run_task(foo)

        assert result is None
