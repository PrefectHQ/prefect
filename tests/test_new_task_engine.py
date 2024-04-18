import logging
import pytest
from uuid import UUID

from prefect import task, Task, get_run_logger
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import StateType
from prefect.context import FlowRunContext, TaskRunContext
from prefect.new_task_engine import run_task, TaskRunEngine
from prefect.results import ResultFactory
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

        @task(task_run_name="test-run")
        async def my_log_task():
            get_run_logger().critical("hey yall")

        result = await run_task(my_log_task)

        assert result is None
        record = caplog.records[0]

        assert record.task_name == "my_log_task"
        # assert record.task_run_name == "test-run"
        assert UUID(record.task_run_id)
        assert record.message == "hey yall"
        assert record.levelname == "CRITICAL"

    async def test_flow_run_id_is_set(self, flow_run, prefect_client):
        @task
        async def foo():
            return TaskRunContext.get().task_run.flow_run_id

        factory = await ResultFactory.from_autonomous_task(foo)
        with FlowRunContext(
            flow_run=flow_run, client=prefect_client, result_factory=factory
        ):
            result = await run_task(foo)

        assert result == flow_run.id

    async def test_task_ends_in_completed(self, prefect_client):
        @task
        async def foo():
            return TaskRunContext.get().task_run.id

        result = await run_task(foo)
        run = await prefect_client.read_task_run(result)

        assert run.state_type == StateType.COMPLETED
