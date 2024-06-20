import asyncio
import logging
import time
from datetime import timedelta
from pathlib import Path
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, call
from uuid import UUID, uuid4

import anyio
import pytest

from prefect import Task, flow, task
from prefect.cache_policies import FLOW_PARAMETERS
from prefect.client.orchestration import PrefectClient, SyncPrefectClient
from prefect.client.schemas.objects import StateType
from prefect.context import (
    EngineContext,
    FlowRunContext,
    TaskRunContext,
    get_run_context,
)
from prefect.exceptions import CrashedRun, MissingResult
from prefect.filesystems import LocalFileSystem
from prefect.logging import get_run_logger
from prefect.results import PersistedResult, ResultFactory, UnpersistedResult
from prefect.settings import (
    PREFECT_TASK_DEFAULT_RETRIES,
    temporary_settings,
)
from prefect.states import Running, State
from prefect.task_engine import TaskRunEngine, run_task_async, run_task_sync
from prefect.task_runners import ThreadPoolTaskRunner
from prefect.testing.utilities import exceptions_equal
from prefect.utilities.callables import get_call_parameters
from prefect.utilities.engine import propose_state


@task
async def foo():
    return 42


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
        with engine.initialize_run():
            client = engine.client
            assert isinstance(client, SyncPrefectClient)

        with pytest.raises(RuntimeError, match="not started"):
            engine.client


class TestRunTask:
    def test_run_task_with_client_provided_uuid(
        self, sync_prefect_client: SyncPrefectClient
    ):
        @task
        def foo():
            return 42

        task_run_id = uuid4()

        run_task_sync(foo, task_run_id=task_run_id)

        task_run = sync_prefect_client.read_task_run(task_run_id)
        assert task_run.id == task_run_id

    async def test_with_provided_context(self, prefect_client):
        @flow
        def f():
            pass

        test_task_runner = ThreadPoolTaskRunner()
        flow_run = await prefect_client.create_flow_run(f)
        await propose_state(prefect_client, Running(), flow_run_id=flow_run.id)
        result_factory = await ResultFactory.from_flow(f)
        flow_run_context = EngineContext(
            flow=f,
            flow_run=flow_run,
            client=prefect_client,
            task_runner=test_task_runner,
            result_factory=result_factory,
            parameters={"x": "y"},
        )

        @task
        def foo():
            return FlowRunContext.get().flow_run.id

        context = {"flow_run_context": flow_run_context.serialize()}

        result = run_task_sync(foo, context=context)

        assert result == flow_run.id


class TestTaskRunsAsync:
    async def test_run_task_async_with_client_provided_uuid(
        self, prefect_client: PrefectClient
    ):
        @task
        async def foo():
            return 42

        task_run_id = uuid4()

        await run_task_async(foo, task_run_id=task_run_id)

        task_run = await prefect_client.read_task_run(task_run_id)
        assert task_run.id == task_run_id

    async def test_with_provided_context(self, prefect_client):
        @flow
        def f():
            pass

        test_task_runner = ThreadPoolTaskRunner()
        flow_run = await prefect_client.create_flow_run(f)
        await propose_state(prefect_client, Running(), flow_run_id=flow_run.id)
        result_factory = await ResultFactory.from_flow(f)
        flow_run_context = EngineContext(
            flow=f,
            flow_run=flow_run,
            client=prefect_client,
            task_runner=test_task_runner,
            result_factory=result_factory,
            parameters={"x": "y"},
        )

        @task
        async def foo():
            return FlowRunContext.get().flow_run.id

        context = {"flow_run_context": flow_run_context.serialize()}

        result = await run_task_async(foo, context=context)

        assert result == flow_run.id

    async def test_basic(self):
        @task
        async def foo():
            return 42

        result = await run_task_async(foo)

        assert result == 42

    async def test_with_params(self):
        @task
        async def bar(x: int, y: Optional[str] = None):
            return x, y

        parameters = get_call_parameters(bar.fn, (42,), dict(y="nate"))
        result = await run_task_async(bar, parameters=parameters)

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

        result = await run_task_async(foo, parameters=dict(x="blue"))
        run = await prefect_client.read_task_run(result)

        assert run.name == "name is blue"

    async def test_get_run_logger(self, caplog):
        caplog.set_level(logging.CRITICAL)

        @task(task_run_name="test-run")
        async def my_log_task():
            get_run_logger().critical("hey yall")

        result = await run_task_async(my_log_task)

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
            return await run_task_async(foo)

        assert await workflow() == flow_run_id

    async def test_task_ends_in_completed(self, prefect_client):
        @task
        async def foo():
            return TaskRunContext.get().task_run.id

        result = await run_task_async(foo)
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
            await run_task_async(foo)

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

        result = await run_task_async(foo)

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

        a, b = await run_task_async(outer)
        assert a != b

        # assertions on outer
        outer_run = await prefect_client.read_task_run(b)
        assert outer_run.task_inputs == {}

        # assertions on inner
        inner_run = await prefect_client.read_task_run(a)
        assert "__parents__" in inner_run.task_inputs
        assert inner_run.task_inputs["__parents__"][0].id == b

    async def test_multiple_nested_tasks_track_parent(self, prefect_client):
        @task
        def level_3():
            return TaskRunContext.get().task_run.id

        @task
        def level_2():
            id_3 = level_3()
            return TaskRunContext.get().task_run.id, id_3

        @task
        def level_1():
            id_2, id_3 = level_2()
            return TaskRunContext.get().task_run.id, id_2, id_3

        @flow
        def f():
            return level_1()

        id1, id2, id3 = f()
        assert id1 != id2 != id3

        for id_, parent_id in [(id3, id2), (id2, id1)]:
            run = await prefect_client.read_task_run(id_)
            assert "__parents__" in run.task_inputs
            assert run.task_inputs["__parents__"][0].id == parent_id

        run = await prefect_client.read_task_run(id1)
        assert "__parents__" not in run.task_inputs

    async def test_tasks_in_subflow_do_not_track_subflow_dummy_task_as_parent(
        self, sync_prefect_client: SyncPrefectClient
    ):
        """
        Ensures that tasks in a subflow do not track the subflow's dummy task as
        a parent.


        Setup:
            Flow (level_1)
            -> calls a subflow (level_2)
            -> which calls a task (level_3)

        We want to make sure that level_3 does not track level_2's dummy task as
        a parent.

        This shouldn't happen in the current engine because no context is
        actually opened for the dummy task.
        """

        @task
        def level_3():
            return TaskRunContext.get().task_run.id

        @flow
        def level_2():
            return level_3()

        @flow
        def level_1():
            return level_2()

        level_3_id = level_1()

        tr = sync_prefect_client.read_task_run(level_3_id)
        assert "__parents__" not in tr.task_inputs

    async def test_tasks_in_subflow_do_not_track_subflow_dummy_task_parent_as_parent(
        self, sync_prefect_client: SyncPrefectClient
    ):
        """
        Ensures that tasks in a subflow do not track the subflow's dummy task as
        a parent.

        Setup:
            Flow (level_1)
            -> calls a task (level_2)
            -> which calls a subflow (level_3)
            -> which calls a task (level_4)

        We want to make sure that level_4 does not track level_2 as a parent.
        """

        @task
        def level_4():
            return TaskRunContext.get().task_run.id

        @flow
        def level_3():
            return level_4()

        @task
        def level_2():
            return level_3()

        @flow
        def level_1():
            return level_2()

        level_4_id = level_1()

        tr = sync_prefect_client.read_task_run(level_4_id)

        assert "__parents__" not in tr.task_inputs

    async def test_task_runs_respect_result_persistence(self, prefect_client, tmp_path):
        fs = LocalFileSystem(basepath=tmp_path)

        @task(persist_result=False, result_storage=fs)
        async def no_persist():
            return TaskRunContext.get().task_run.id

        @task(persist_result=True, result_storage=fs)
        async def persist():
            return TaskRunContext.get().task_run.id

        # assert no persistence
        run_id = await run_task_async(no_persist)
        task_run = await prefect_client.read_task_run(run_id)
        api_state = task_run.state

        with pytest.raises(MissingResult):
            await api_state.result()

        # assert persistence
        run_id = await run_task_async(persist)
        task_run = await prefect_client.read_task_run(run_id)
        api_state = task_run.state

        assert await api_state.result() == run_id

    async def test_task_runs_respect_cache_key(self, tmp_path: Path):
        @task(cache_key_fn=lambda *args, **kwargs: "key")
        async def first():
            return 42

        @task(cache_key_fn=lambda *args, **kwargs: "key")
        async def second():
            return 500

        fs = LocalFileSystem(basepath=tmp_path)

        one = await run_task_async(first.with_options(result_storage=fs))
        two = await run_task_async(second.with_options(result_storage=fs))

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
        def bar(x: int, y: Optional[str] = None):
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
        assert "__parents__" in inner_run.task_inputs
        assert inner_run.task_inputs["__parents__"][0].id == b

    async def test_task_runs_respect_result_persistence(self, prefect_client, tmp_path):
        fs = LocalFileSystem(basepath=tmp_path)

        @task(persist_result=False, result_storage=fs)
        def no_persist():
            ctx = TaskRunContext.get()
            assert ctx
            return ctx.task_run.id

        @task(persist_result=True, result_storage=fs)
        def persist():
            ctx = TaskRunContext.get()
            assert ctx
            return ctx.task_run.id

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

        assert await api_state.result() == run_id

    async def test_task_runs_respect_cache_key(self, tmp_path: Path):
        @task(cache_key_fn=lambda *args, **kwargs: "key")
        def first():
            return 42

        @task(cache_key_fn=lambda *args, **kwargs: "key")
        def second():
            return 500

        fs = LocalFileSystem(basepath=tmp_path)

        one = run_task_sync(first.with_options(result_storage=fs))
        two = run_task_sync(second.with_options(result_storage=fs))

        assert one == 42
        assert two == 42


class TestReturnState:
    async def test_return_state(self, prefect_client):
        @task
        async def foo():
            return 42

        state = await run_task_async(foo, return_type="state")

        assert isinstance(state, State)

        assert state.is_completed()

        assert await state.result() == 42

    async def test_return_state_even_on_failure(self, prefect_client):
        @task
        async def foo():
            raise ValueError("xyz")

        state = await run_task_async(foo, return_type="state")

        assert isinstance(state, State)

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
                await task_run_state.result(raise_on_failure=False),  # type: ignore
                exc,
            )
            assert mock.call_count == 4
        else:
            assert task_run_state.is_completed()
            assert await task_run_state.result() is True  # type: ignore
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

    @pytest.mark.parametrize(
        "retry_delay_seconds,expected_delay_sequence",
        [
            (1, [1, 1, 1]),
            ([1, 2, 3], [1, 2, 3]),
            (
                [1, 2],
                [1, 2, 2],
            ),  # repeat last value if len(retry_delay_seconds) < retries
        ],
    )
    async def test_async_task_respects_retry_delay_seconds(
        self, retry_delay_seconds, expected_delay_sequence, prefect_client, monkeypatch
    ):
        mock_sleep = AsyncMock()
        monkeypatch.setattr(anyio, "sleep", mock_sleep)

        @task(retries=3, retry_delay_seconds=retry_delay_seconds)
        async def flaky_function():
            raise ValueError()

        task_run_state = await flaky_function(return_state=True)
        task_run_id = task_run_state.state_details.task_run_id

        assert task_run_state.is_failed()
        assert mock_sleep.call_count == 3
        assert mock_sleep.call_args_list == [
            call(pytest.approx(delay, abs=0.2)) for delay in expected_delay_sequence
        ]

        states = await prefect_client.read_task_run_states(task_run_id)
        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "AwaitingRetry",
            "Retrying",
            "AwaitingRetry",
            "Retrying",
            "AwaitingRetry",
            "Retrying",
            "Failed",
        ]

    @pytest.mark.parametrize(
        "retry_delay_seconds,expected_delay_sequence",
        [
            (1, [1, 1, 1]),
            ([1, 2, 3], [1, 2, 3]),
            (
                [1, 2],
                [1, 2, 2],
            ),  # repeat last value if len(retry_delay_seconds) < retries
        ],
    )
    async def test_sync_task_respects_retry_delay_seconds(
        self, retry_delay_seconds, expected_delay_sequence, prefect_client, monkeypatch
    ):
        mock_sleep = AsyncMock()
        monkeypatch.setattr(anyio, "sleep", mock_sleep)

        @task(retries=3, retry_delay_seconds=retry_delay_seconds)
        def flaky_function():
            raise ValueError()

        task_run_state = flaky_function(return_state=True)
        task_run_id = task_run_state.state_details.task_run_id

        assert task_run_state.is_failed()
        assert mock_sleep.call_count == 3
        assert mock_sleep.call_args_list == [
            call(pytest.approx(delay, abs=1)) for delay in expected_delay_sequence
        ]

        states = await prefect_client.read_task_run_states(task_run_id)
        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "AwaitingRetry",
            "Retrying",
            "AwaitingRetry",
            "Retrying",
            "AwaitingRetry",
            "Retrying",
            "Failed",
        ]


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
            TaskRunEngine, "begin_run", MagicMock(side_effect=interrupt_type)
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

        result = await run_task_async(async_task)
        assert result == 42


class TestTimeout:
    async def test_timeout_async_task(self):
        @task(timeout_seconds=0.1)
        async def async_task():
            await asyncio.sleep(2)

        with pytest.raises(TimeoutError, match=".*timed out after 0.1 second(s)*"):
            await run_task_async(async_task)

    @pytest.mark.xfail(
        reason="Synchronous sleep in an async task is not interruptible by async timeout"
    )
    async def test_timeout_async_task_with_sync_sleep(self):
        @task(timeout_seconds=0.1)
        async def async_task():
            time.sleep(2)

        with pytest.raises(TimeoutError, match=".*timed out after 0.1 second(s)*"):
            await run_task_async(async_task)

    async def test_timeout_sync_task(self):
        @task(timeout_seconds=0.1)
        def sync_task():
            time.sleep(2)

        with pytest.raises(TimeoutError, match=".*timed out after 0.1 second(s)*"):
            run_task_sync(sync_task)


class TestPersistence:
    async def test_task_can_return_persisted_result(self, prefect_client):
        @task
        async def async_task():
            factory = await ResultFactory.default_factory(
                client=prefect_client, persist_result=True
            )
            result = await factory.create_result(42)
            return result

        assert await async_task() == 42
        state = await async_task(return_state=True)
        assert await state.result() == 42

    async def test_task_loads_result_if_exists_using_result_storage_key(
        self, prefect_client, tmp_path
    ):
        fs = LocalFileSystem(basepath=tmp_path)

        factory = await ResultFactory.default_factory(
            client=prefect_client, persist_result=True, result_storage=fs
        )
        await factory.create_result(-92, key="foo-bar")

        @task(result_storage=fs, result_storage_key="foo-bar")
        async def async_task():
            return 42

        state = await run_task_async(async_task, return_type="state")
        assert state.is_completed()
        assert await state.result() == -92
        assert isinstance(state.data, PersistedResult)
        assert state.data.storage_key == "foo-bar"


class TestCachePolicy:
    async def test_result_stored_with_storage_key_if_no_policy_set(
        self, prefect_client
    ):
        @task(persist_result=True, result_storage_key="foo-bar")
        async def async_task():
            return 1800

        state = await async_task(return_state=True)

        assert state.is_completed()
        assert await state.result() == 1800
        assert state.data.storage_key == "foo-bar"

    async def test_cache_expiration_is_respected(
        self, prefect_client, tmp_path, advance_time
    ):
        fs = LocalFileSystem(basepath=tmp_path)

        @task(
            persist_result=True,
            result_storage_key="expiring-foo-bar",
            cache_expiration=timedelta(seconds=1.0),
            result_storage=fs,
        )
        async def async_task():
            import random

            return random.randint(0, 10000)

        first_state = await async_task(return_state=True)
        assert first_state.is_completed()
        first_result = await first_state.result()

        second_state = await async_task(return_state=True)
        assert second_state.is_completed()
        second_result = await second_state.result()

        assert first_result == second_result, "Cache was not used"

        # let cache expire...
        advance_time(timedelta(seconds=1.1))

        third_state = await async_task(return_state=True)
        assert third_state.is_completed()
        third_result = await third_state.result()

        # cache expired, new result
        assert third_result not in [first_result, second_result], "Cache did not expire"

    async def test_cache_expiration_expires(self, prefect_client, tmp_path):
        fs = LocalFileSystem(basepath=tmp_path)

        @task(
            persist_result=True,
            result_storage_key="expiring-foo-bar",
            cache_expiration=timedelta(seconds=0.0),
            result_storage=fs,
        )
        async def async_task():
            import random

            return random.randint(0, 10000)

        first_state = await async_task(return_state=True)
        assert first_state.is_completed()
        await asyncio.sleep(0.1)

        second_state = await async_task(return_state=True)
        assert second_state.is_completed()

        assert (
            await first_state.result() != await second_state.result()
        ), "Cache did not expire"

    async def test_none_policy_with_persist_result_false(self, prefect_client):
        @task(cache_policy=None, result_storage_key=None, persist_result=False)
        async def async_task():
            return 1800

        assert async_task.cache_policy is None
        state = await async_task(return_state=True)

        assert state.is_completed()
        assert await state.result() == 1800
        assert isinstance(state.data, UnpersistedResult)

    async def test_none_return_value_does_persist(self, prefect_client, tmp_path):
        fs = LocalFileSystem(basepath=tmp_path)
        FIRST_RUN = True

        @task(
            persist_result=True,
            cache_key_fn=lambda *args, **kwargs: "test-none-caches",
            result_storage=fs,
        )
        async def async_task():
            nonlocal FIRST_RUN

            if FIRST_RUN:
                FIRST_RUN = False
                return None
            else:
                return 42

        first_val = await async_task()
        # make sure test is behaving
        assert FIRST_RUN is False

        second_val = await async_task()

        assert first_val is None
        assert second_val is None

    async def test_flow_parameter_caching(self, prefect_client, tmp_path):
        fs = LocalFileSystem(basepath=tmp_path)

        @task(
            cache_policy=FLOW_PARAMETERS,
            result_storage=fs,
        )
        def my_random_task(x: int):
            import random

            return random.randint(0, x)

        @flow
        def my_param_flow(x: int, other_val: str):
            first_val = my_random_task(x, return_state=True)
            second_val = my_random_task(x, return_state=True)
            return first_val, second_val

        first, second = my_param_flow(4200, other_val="foo")
        assert first.name == "Completed"
        assert second.name == "Cached"

        first_result = await first.result()
        second_result = await second.result()
        assert first_result == second_result

        third, fourth = my_param_flow(4200, other_val="bar")
        assert third.name == "Completed"
        assert fourth.name == "Cached"

        third_result = await third.result()
        fourth_result = await fourth.result()

        assert third_result not in [first_result, second_result]
        assert fourth_result not in [first_result, second_result]


class TestGenerators:
    async def test_generator_task(self):
        """
        Test for generator behavior including StopIteration
        """

        @task
        def g():
            yield 1
            yield 2

        gen = g()
        assert next(gen) == 1
        assert next(gen) == 2
        with pytest.raises(StopIteration):
            next(gen)

    async def test_generator_task_requires_return_type_result(self):
        @task
        def g():
            yield 1

        with pytest.raises(
            ValueError, match="The return_type for a generator task must be 'result'"
        ):
            for i in g(return_state=True):
                pass

    async def test_generator_task_states(self, prefect_client: PrefectClient):
        """
        Test for generator behavior including StopIteration
        """

        @task
        def g():
            yield TaskRunContext.get().task_run.id
            yield 2

        gen = g()
        tr_id = next(gen)
        tr = await prefect_client.read_task_run(tr_id)
        assert tr.state.is_running()

        # exhaust the generator
        for _ in gen:
            pass

        tr = await prefect_client.read_task_run(tr_id)
        assert tr.state.is_completed()

    async def test_generator_task_with_return(self):
        """
        If a generator returns, the return value is trapped
        in its StopIteration error
        """

        @task
        def g():
            yield 1
            return 2

        gen = g()
        assert next(gen) == 1
        with pytest.raises(StopIteration) as exc_info:
            next(gen)
        assert exc_info.value.value == 2

    async def test_generator_task_with_exception(self):
        @task
        def g():
            yield 1
            raise ValueError("xyz")

        gen = g()
        assert next(gen) == 1
        with pytest.raises(ValueError, match="xyz"):
            next(gen)

    async def test_generator_task_with_exception_is_failed(
        self, prefect_client: PrefectClient
    ):
        @task
        def g():
            yield TaskRunContext.get().task_run.id
            raise ValueError("xyz")

        gen = g()
        tr_id = next(gen)
        with pytest.raises(ValueError, match="xyz"):
            next(gen)
        tr = await prefect_client.read_task_run(tr_id)
        assert tr.state.is_failed()

    async def test_generator_parent_tracking(self, prefect_client: PrefectClient):
        """ """

        @task(task_run_name="gen-1000")
        def g():
            yield 1000

        @task
        def f(x):
            return TaskRunContext.get().task_run.id

        @flow
        def parent_tracking():
            for val in g():
                tr_id = f(val)
            return tr_id

        tr_id = parent_tracking()
        tr = await prefect_client.read_task_run(tr_id)
        assert "x" in tr.task_inputs
        assert "__parents__" in tr.task_inputs
        # the parent run and upstream 'x' run are the same
        assert tr.task_inputs["__parents__"][0].id == tr.task_inputs["x"][0].id
        # the parent run is "gen-1000"
        gen_id = tr.task_inputs["__parents__"][0].id
        gen_tr = await prefect_client.read_task_run(gen_id)
        assert gen_tr.name == "gen-1000"

    async def test_generator_retries(self):
        """
        Test that a generator can retry and will re-emit its events
        """

        @task(retries=2)
        def g():
            yield 1
            yield 2
            raise ValueError()

        values = []
        try:
            for v in g():
                values.append(v)
        except ValueError:
            pass
        assert values == [1, 2, 1, 2, 1, 2]

    async def test_generator_timeout(self):
        """
        Test that a generator can timeout
        """

        @task(timeout_seconds=1)
        def g():
            yield 1
            time.sleep(2)
            yield 2

        values = []
        with pytest.raises(TimeoutError):
            for v in g():
                values.append(v)
        assert values == [1]

    async def test_generator_doesnt_retry_on_generator_exception(self):
        """
        Test that a generator doesn't retry for normal generator exceptions like StopIteration
        """

        @task(retries=2)
        def g():
            yield 1
            yield 2

        values = []
        try:
            for v in g():
                values.append(v)
        except ValueError:
            pass
        assert values == [1, 2]

    def test_generators_can_be_yielded_without_being_consumed(self):
        CONSUMED = []

        @task
        def g():
            CONSUMED.append("g")
            yield 1
            yield 2

        @task
        def f_return():
            return g()

        @task
        def f_yield():
            yield g()

        # returning a generator automatically consumes it
        # because it can't be serialized
        f_return()
        assert CONSUMED == ["g"]
        CONSUMED.clear()

        gen = next(f_yield())
        assert CONSUMED == []
        list(gen)
        assert CONSUMED == ["g"]


class TestAsyncGenerators:
    async def test_generator_task(self):
        """
        Test for generator behavior including StopIteration
        """

        @task
        async def g():
            yield 1
            yield 2

        counter = 0
        async for val in g():
            if counter == 0:
                assert val == 1
            if counter == 1:
                assert val == 2
            assert counter <= 1
            counter += 1

    async def test_generator_task_requires_return_type_result(self):
        @task
        async def g():
            yield 1

        with pytest.raises(
            ValueError, match="The return_type for a generator task must be 'result'"
        ):
            async for i in g(return_state=True):
                pass

    async def test_generator_task_states(self, prefect_client: PrefectClient):
        """
        Test for generator behavior including StopIteration
        """

        @task
        async def g():
            yield TaskRunContext.get().task_run.id

        async for val in g():
            tr_id = val
            tr = await prefect_client.read_task_run(tr_id)
            assert tr.state.is_running()

        tr = await prefect_client.read_task_run(tr_id)
        assert tr.state.is_completed()

    async def test_generator_task_with_exception(self):
        @task
        async def g():
            yield 1
            raise ValueError("xyz")

        with pytest.raises(ValueError, match="xyz"):
            async for val in g():
                assert val == 1

    async def test_generator_task_with_exception_is_failed(
        self, prefect_client: PrefectClient
    ):
        @task
        async def g():
            yield TaskRunContext.get().task_run.id
            raise ValueError("xyz")

        with pytest.raises(ValueError, match="xyz"):
            async for val in g():
                tr_id = val

        tr = await prefect_client.read_task_run(tr_id)
        assert tr.state.is_failed()

    async def test_generator_parent_tracking(self, prefect_client: PrefectClient):
        """ """

        @task(task_run_name="gen-1000")
        async def g():
            yield 1000

        @task
        async def f(x):
            return TaskRunContext.get().task_run.id

        @flow
        async def parent_tracking():
            async for val in g():
                tr_id = await f(val)
            return tr_id

        tr_id = await parent_tracking()
        tr = await prefect_client.read_task_run(tr_id)
        assert "x" in tr.task_inputs
        assert "__parents__" in tr.task_inputs
        # the parent run and upstream 'x' run are the same
        assert tr.task_inputs["__parents__"][0].id == tr.task_inputs["x"][0].id
        # the parent run is "gen-1000"
        gen_id = tr.task_inputs["__parents__"][0].id
        gen_tr = await prefect_client.read_task_run(gen_id)
        assert gen_tr.name == "gen-1000"

    async def test_generator_retries(self):
        """
        Test that a generator can retry and will re-emit its events
        """

        @task(retries=2)
        async def g():
            yield 1
            yield 2
            raise ValueError()

        values = []
        try:
            async for v in g():
                values.append(v)
        except ValueError:
            pass
        assert values == [1, 2, 1, 2, 1, 2]

    @pytest.mark.xfail(
        reason="Synchronous sleep in an async task is not interruptible by async timeout"
    )
    async def test_generator_timeout_with_sync_sleep(self):
        """
        Test that a generator can timeout
        """

        @task(timeout_seconds=0.1)
        async def g():
            yield 1
            time.sleep(2)
            yield 2

        values = []
        with pytest.raises(TimeoutError):
            async for v in g():
                values.append(v)
        assert values == [1]

    async def test_generator_timeout_with_async_sleep(self):
        """
        Test that a generator can timeout
        """

        @task(timeout_seconds=0.1)
        async def g():
            yield 1
            await asyncio.sleep(2)
            yield 2

        values = []
        with pytest.raises(TimeoutError):
            async for v in g():
                values.append(v)
        assert values == [1]

    async def test_generator_doesnt_retry_on_generator_exception(self):
        """
        Test that a generator doesn't retry for normal generator exceptions like StopIteration
        """

        @task(retries=2)
        async def g():
            yield 1
            yield 2

        values = []
        try:
            async for v in g():
                values.append(v)
        except ValueError:
            pass
        assert values == [1, 2]
