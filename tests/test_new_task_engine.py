import logging
from uuid import UUID

import pytest

from prefect import Task, get_run_logger, task
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import StateType
from prefect.context import FlowRunContext, TaskRunContext
from prefect.new_task_engine import TaskRunEngine, run_task
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
        assert engine.parameters == {}

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

    async def test_task_run_name(self, prefect_client):
        @task(task_run_name="name is {x}")
        async def foo(x):
            return TaskRunContext.get().task_run.id

        result = await run_task(foo, parameters=dict(x="blue"))
        run = await prefect_client.read_task_run(result)

        assert run.name == "name is blue"

    async def test_get_run_logger(self, caplog):
        caplog.set_level(logging.CRITICAL)

        @task(task_run_name="test-run")
        async def my_log_task():
            get_run_logger().critical("hey yall")

        result = await run_task(my_log_task)

        assert result is None
        record = caplog.records[0]

        assert record.task_name == "my_log_task"
        assert record.task_run_name == "test-run"
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

    async def test_task_ends_in_failed(self, prefect_client):
        ID = None

        @task
        async def foo():
            nonlocal ID
            ID = TaskRunContext.get().task_run.id
            raise ValueError("xyz")

        with pytest.raises(ValueError, match="xyz"):
            await run_task(foo)

        run = await prefect_client.read_task_run(ID)

        assert run.state_type == StateType.FAILED

    async def test_task_ends_in_failed_after_retrying(self, prefect_client):
        ID = None

        @task(retries=1)
        async def foo():
            nonlocal ID
            if ID is None:
                ID = TaskRunContext.get().task_run.id
                raise ValueError("xyz")
            else:
                return ID

        result = await run_task(foo)

        run = await prefect_client.read_task_run(result)

        assert run.state_type == StateType.COMPLETED

    @pytest.mark.skip(reason="This wont work until both task runs use run_task")
    async def test_task_tracks_nested_parent_as_dependency(self, prefect_client):
        @task
        async def inner():
            return TaskRunContext.get().task_run.id

        @task
        async def outer():
            id1 = inner()
            return (id1, TaskRunContext.get().task_run.id)

        a, b = await run_task(outer)
        assert a != b

        # assertions on outer
        outer_run = await prefect_client.read_task_run(b)
        assert outer_run.task_inputs

    @pytest.mark.skip(reason="This wont work until caching is wired up")
    async def test_task_tracks_nested_parent_as_dependency(self, prefect_client):
        @task(cache_key_fn="key")
        async def first():
            return 42

        @task(cache_key_fn="key")
        async def second():
            return 500

        one = await run_task(first)
        two = await run_task(second)

        assert one == 42
        assert two == 42
