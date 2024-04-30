import asyncio
import logging
import time
from typing import List
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from prefect import Task, flow, get_run_logger, task
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import StateType
from prefect.context import TaskRunContext, get_run_context
from prefect.exceptions import CrashedRun, MissingResult
from prefect.filesystems import LocalFileSystem
from prefect.new_task_engine import TaskRunEngine, run_task, run_task_sync
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_NEW_ENGINE,
    PREFECT_TASK_DEFAULT_RETRIES,
    temporary_settings,
)
from prefect.testing.utilities import exceptions_equal
from prefect.utilities.callables import get_call_parameters


@pytest.fixture(autouse=True)
def set_new_engine_setting():
    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_NEW_ENGINE: True}):
        yield


@task
async def foo():
    return 42


async def test_setting_is_set():
    assert PREFECT_EXPERIMENTAL_ENABLE_NEW_ENGINE.value() is True


class TestTaskRunEngine:
    async def test_basic_init(self):
        engine = TaskRunEngine(task=foo)
        assert isinstance(engine.task, Task)
        assert engine.task.name == "foo"
        assert engine.parameters == {}

    async def test_client_attribute_raises_informative_error(self):
        engine = TaskRunEngine(task=foo)
        with pytest.raises(RuntimeError, match="not started"):
            engine.client

    async def test_client_attr_returns_client_after_starting(self):
        engine = TaskRunEngine(task=foo)
        async with engine.start():
            client = engine.client
            assert isinstance(client, PrefectClient)

        with pytest.raises(RuntimeError, match="not started"):
            engine.client


class TestTaskRunsAsync:
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

    async def test_with_args(self):
        @task
        async def f(*args):
            return args

        args = (42, "nate")
        result = await f(*args)
        assert result == args

    async def test_with_kwargs(self):
        @task
        async def f(**kwargs):
            return kwargs

        kwargs = dict(x=42, y="nate")
        result = await f(**kwargs)
        assert result == kwargs

    async def test_with_args_kwargs(self):
        @task
        async def f(*args, x, **kwargs):
            return args, x, kwargs

        result = await f(1, 2, x=5, y=6, z=7)
        assert result == ((1, 2), 5, dict(y=6, z=7))

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

    async def test_flow_run_id_is_set(self, prefect_client):
        flow_run_id = None

        @task
        async def foo():
            return TaskRunContext.get().task_run.flow_run_id

        @flow
        async def workflow():
            nonlocal flow_run_id
            flow_run_id = get_run_context().flow_run.id
            return await run_task(foo)

        assert await workflow() == flow_run_id

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

    async def test_task_tracks_nested_parent_as_dependency(self, prefect_client):
        @task
        async def inner():
            return TaskRunContext.get().task_run.id

        @task
        async def outer():
            id1 = await inner()
            return (id1, TaskRunContext.get().task_run.id)

        a, b = await run_task(outer)
        assert a != b

        # assertions on outer
        outer_run = await prefect_client.read_task_run(b)
        assert outer_run.task_inputs == {}

        # assertions on inner
        inner_run = await prefect_client.read_task_run(a)
        assert "wait_for" in inner_run.task_inputs
        assert inner_run.task_inputs["wait_for"][0].id == b

    async def test_task_runs_respect_result_persistence(self, prefect_client):
        @task(persist_result=False)
        async def no_persist():
            return TaskRunContext.get().task_run.id

        @task(persist_result=True)
        async def persist():
            return TaskRunContext.get().task_run.id

        # assert no persistence
        run_id = await run_task(no_persist)
        task_run = await prefect_client.read_task_run(run_id)
        api_state = task_run.state

        with pytest.raises(MissingResult):
            await api_state.result()

        # assert persistence
        run_id = await run_task(persist)
        task_run = await prefect_client.read_task_run(run_id)
        api_state = task_run.state

        assert await api_state.result() == str(run_id)

    async def test_task_runs_respect_cache_key(self):
        @task(cache_key_fn=lambda *args, **kwargs: "key")
        async def first():
            return 42

        @task(cache_key_fn=lambda *args, **kwargs: "key")
        async def second():
            return 500

        fs = LocalFileSystem(base_url="/tmp/prefect")

        one = await run_task(first.with_options(result_storage=fs))
        two = await run_task(second.with_options(result_storage=fs))

        assert one == 42
        assert two == 42


class TestTaskRunsSync:
    def test_basic(self):
        @task
        def foo():
            return 42

        result = run_task_sync(foo)
        assert result == 42

    def test_with_params(self):
        @task
        def bar(x: int, y: str = None):
            return x, y

        parameters = get_call_parameters(bar.fn, (42,), dict(y="nate"))
        result = run_task_sync(bar, parameters=parameters)
        assert result == (42, "nate")

    def test_with_args(self):
        @task
        def f(*args):
            return args

        args = (42, "nate")
        result = f(*args)
        assert result == args

    def test_with_kwargs(self):
        @task
        def f(**kwargs):
            return kwargs

        kwargs = dict(x=42, y="nate")
        result = f(**kwargs)
        assert result == kwargs

    def test_with_args_kwargs(self):
        @task
        def f(*args, x, **kwargs):
            return args, x, kwargs

        result = f(1, 2, x=5, y=6, z=7)
        assert result == ((1, 2), 5, dict(y=6, z=7))

    async def test_task_run_name(self, prefect_client):
        @task(task_run_name="name is {x}")
        def foo(x):
            return TaskRunContext.get().task_run.id

        result = run_task_sync(foo, parameters=dict(x="blue"))
        run = await prefect_client.read_task_run(result)
        assert run.name == "name is blue"

    def test_get_run_logger(self, caplog):
        caplog.set_level(logging.CRITICAL)

        @task(task_run_name="test-run")
        def my_log_task():
            get_run_logger().critical("hey yall")

        result = run_task_sync(my_log_task)

        assert result is None
        record = caplog.records[0]

        assert record.task_name == "my_log_task"
        assert record.task_run_name == "test-run"
        assert UUID(record.task_run_id)
        assert record.message == "hey yall"
        assert record.levelname == "CRITICAL"

    def test_flow_run_id_is_set(self, prefect_client):
        flow_run_id = None

        @task
        def foo():
            return TaskRunContext.get().task_run.flow_run_id

        @flow
        def workflow():
            nonlocal flow_run_id
            flow_run_id = get_run_context().flow_run.id
            return run_task_sync(foo)

        assert workflow() == flow_run_id

    async def test_task_ends_in_completed(self, prefect_client):
        @task
        def foo():
            return TaskRunContext.get().task_run.id

        result = run_task_sync(foo)
        run = await prefect_client.read_task_run(result)

        assert run.state_type == StateType.COMPLETED

    async def test_task_ends_in_failed(self, prefect_client):
        ID = None

        @task
        def foo():
            nonlocal ID
            ID = TaskRunContext.get().task_run.id
            raise ValueError("xyz")

        with pytest.raises(ValueError, match="xyz"):
            run_task_sync(foo)

        run = await prefect_client.read_task_run(ID)

        assert run.state_type == StateType.FAILED

    async def test_task_ends_in_failed_after_retrying(self, prefect_client):
        ID = None

        @task(retries=1)
        def foo():
            nonlocal ID
            if ID is None:
                ID = TaskRunContext.get().task_run.id
                raise ValueError("xyz")
            else:
                return ID

        result = run_task_sync(foo)

        run = await prefect_client.read_task_run(result)

        assert run.state_type == StateType.COMPLETED

    async def test_task_tracks_nested_parent_as_dependency(self, prefect_client):
        @task
        def inner():
            return TaskRunContext.get().task_run.id

        @task
        def outer():
            id1 = inner()
            return (id1, TaskRunContext.get().task_run.id)

        a, b = run_task_sync(outer)
        assert a != b

        # assertions on outer
        outer_run = await prefect_client.read_task_run(b)
        assert outer_run.task_inputs == {}

        # assertions on inner
        inner_run = await prefect_client.read_task_run(a)
        assert "wait_for" in inner_run.task_inputs

    async def test_task_runs_respect_result_persistence(self, prefect_client):
        @task(persist_result=False)
        def no_persist():
            return TaskRunContext.get().task_run.id

        @task(persist_result=True)
        def persist():
            return TaskRunContext.get().task_run.id

        # assert no persistence
        run_id = run_task_sync(no_persist)
        task_run = await prefect_client.read_task_run(run_id)
        api_state = task_run.state

        with pytest.raises(MissingResult):
            await api_state.result()

        # assert persistence
        run_id = run_task_sync(persist)
        task_run = await prefect_client.read_task_run(run_id)
        api_state = task_run.state

        assert await api_state.result() == str(run_id)

    async def test_task_runs_respect_cache_key(self):
        @task(cache_key_fn=lambda *args, **kwargs: "key")
        def first():
            return 42

        @task(cache_key_fn=lambda *args, **kwargs: "key")
        def second():
            return 500

        fs = LocalFileSystem(base_url="/tmp/prefect")

        one = run_task_sync(first.with_options(result_storage=fs))
        two = run_task_sync(second.with_options(result_storage=fs))

        assert one == 42
        assert two == 42


class TestReturnState:
    async def test_return_state(self, prefect_client):
        @task
        async def foo():
            return 42

        state = await run_task(foo, return_type="state")

        assert state.is_completed()

        assert await state.result() == 42

    async def test_return_state_even_on_failure(self, prefect_client):
        @task
        async def foo():
            raise ValueError("xyz")

        state = await run_task(foo, return_type="state")

        assert state.is_failed()

        with pytest.raises(ValueError, match="xyz"):
            await state.result()


class TestTaskRetries:
    @pytest.mark.parametrize("always_fail", [True, False])
    async def test_task_respects_retry_count(self, always_fail, prefect_client):
        mock = MagicMock()
        exc = ValueError()

        @task(retries=3)
        async def flaky_function():
            mock()

            # 3 retries means 4 attempts
            # Succeed on the final retry unless we're ending in a failure
            if not always_fail and mock.call_count == 4:
                return True

            raise exc

        @flow
        async def test_flow():
            # return a tuple to avoid unpacking the state which would raise
            return await flaky_function(return_state=True), ...

        task_run_state, _ = await test_flow()
        task_run_id = task_run_state.state_details.task_run_id

        if always_fail:
            assert task_run_state.is_failed()
            assert exceptions_equal(
                await task_run_state.result(raise_on_failure=False), exc
            )
            assert mock.call_count == 4
        else:
            assert task_run_state.is_completed()
            assert await task_run_state.result() is True
            assert mock.call_count == 4

        states = await prefect_client.read_task_run_states(task_run_id)

        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Retrying",
            "Retrying",
            "Retrying",
            "Failed" if always_fail else "Completed",
        ]

    @pytest.mark.parametrize("always_fail", [True, False])
    async def test_task_respects_retry_count_sync(self, always_fail, prefect_client):
        mock = MagicMock()
        exc = ValueError()

        @task(retries=3)
        def flaky_function():
            mock()

            # 3 retries means 4 attempts
            # Succeed on the final retry unless we're ending in a failure
            if not always_fail and mock.call_count == 4:
                return True

            raise exc

        @flow
        def test_flow():
            # return a tuple to avoid unpacking the state which would raise
            return flaky_function(return_state=True), ...

        task_run_state, _ = test_flow()
        task_run_id = task_run_state.state_details.task_run_id

        if always_fail:
            assert task_run_state.is_failed()
            assert exceptions_equal(
                await task_run_state.result(raise_on_failure=False), exc
            )
            assert mock.call_count == 4
        else:
            assert task_run_state.is_completed()
            assert await task_run_state.result() is True
            assert mock.call_count == 4

        states = await prefect_client.read_task_run_states(task_run_id)

        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Retrying",
            "Retrying",
            "Retrying",
            "Failed" if always_fail else "Completed",
        ]

    async def test_task_only_uses_necessary_retries(self, prefect_client):
        mock = MagicMock()
        exc = ValueError()

        @task(retries=3)
        async def flaky_function():
            mock()
            if mock.call_count == 2:
                return True
            raise exc

        @flow
        async def test_flow():
            return await flaky_function(return_state=True)

        task_run_state = await test_flow()
        task_run_id = task_run_state.state_details.task_run_id

        assert task_run_state.is_completed()
        assert await task_run_state.result() is True
        assert mock.call_count == 2

        states = await prefect_client.read_task_run_states(task_run_id)
        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Retrying",
            "Completed",
        ]

    async def test_task_retries_receive_latest_task_run_in_context(self):
        contexts: List[TaskRunContext] = []

        @task(retries=3)
        async def flaky_function():
            contexts.append(get_run_context())
            raise ValueError()

        @flow
        async def test_flow():
            await flaky_function()

        with pytest.raises(ValueError):
            await test_flow()

        expected_state_names = [
            "Running",
            "Retrying",
            "Retrying",
            "Retrying",
        ]
        assert len(contexts) == len(expected_state_names)
        for i, context in enumerate(contexts):
            assert context.task_run.run_count == i + 1
            assert context.task_run.state_name == expected_state_names[i]

            if i > 0:
                last_context = contexts[i - 1]
                assert (
                    last_context.start_time < context.start_time
                ), "Timestamps should be increasing"

    async def test_global_task_retry_config(self):
        with temporary_settings(updates={PREFECT_TASK_DEFAULT_RETRIES: "1"}):
            mock = MagicMock()
            exc = ValueError()

            @task()
            async def flaky_function():
                mock()
                if mock.call_count == 2:
                    return True
                raise exc

            @flow
            async def test_flow():
                return await flaky_function()

            await test_flow()
            assert mock.call_count == 2


class TestTaskCrashDetection:
    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_task_function_crashes_task(
        self, prefect_client, interrupt_type
    ):
        @task
        async def my_task():
            raise interrupt_type()

        with pytest.raises(interrupt_type):
            await my_task()

        task_runs = await prefect_client.read_task_runs()
        assert len(task_runs) == 1
        task_run = task_runs[0]
        assert task_run.state.is_crashed()
        assert task_run.state.type == StateType.CRASHED
        assert "Execution was aborted" in task_run.state.message
        with pytest.raises(CrashedRun, match="Execution was aborted"):
            await task_run.state.result()

    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_task_function_crashes_task_sync(
        self, prefect_client, interrupt_type
    ):
        @task
        def my_task():
            raise interrupt_type()

        with pytest.raises(interrupt_type):
            my_task()

        task_runs = await prefect_client.read_task_runs()
        assert len(task_runs) == 1
        task_run = task_runs[0]
        assert task_run.state.is_crashed()
        assert task_run.state.type == StateType.CRASHED
        assert "Execution was aborted" in task_run.state.message
        with pytest.raises(CrashedRun, match="Execution was aborted"):
            await task_run.state.result()

    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_task_orchestration_crashes_task_and_flow(
        self, prefect_client, interrupt_type, monkeypatch
    ):
        monkeypatch.setattr(
            TaskRunEngine, "begin_run", AsyncMock(side_effect=interrupt_type)
        )

        @task
        async def my_task():
            pass

        with pytest.raises(interrupt_type):
            await my_task()

        task_runs = await prefect_client.read_task_runs()
        assert len(task_runs) == 1
        task_run = task_runs[0]
        assert task_run.state.is_crashed()
        assert task_run.state.type == StateType.CRASHED
        assert "Execution was aborted" in task_run.state.message
        with pytest.raises(CrashedRun, match="Execution was aborted"):
            await task_run.state.result()


class TestSyncAsyncTasks:
    async def test_sync_task_in_async_task(self):
        @task
        def sync_task():
            return 42

        @task
        async def async_task():
            return sync_task()

        result = await run_task(async_task)
        assert result == 42


class TestTimeout:
    async def test_timeout_async_task(self):
        @task(timeout_seconds=0.1)
        async def async_task():
            await asyncio.sleep(2)

        with pytest.raises(TimeoutError):
            await run_task(async_task)

    async def test_timeout_sync_task(self):
        @task(timeout_seconds=0.1)
        def sync_task():
            time.sleep(2)

        with pytest.raises(TimeoutError):
            run_task_sync(sync_task)
