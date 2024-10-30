import asyncio
import logging
import os
import random
import time
from datetime import timedelta
from pathlib import Path
from typing import List, Optional
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, call
from uuid import UUID, uuid4

import anyio
import pytest

from prefect import Task, flow, tags, task
from prefect.cache_policies import FLOW_PARAMETERS, INPUTS, TASK_SOURCE
from prefect.client.orchestration import PrefectClient, SyncPrefectClient
from prefect.client.schemas.objects import StateType
from prefect.concurrency.asyncio import concurrency as aconcurrency
from prefect.concurrency.sync import concurrency
from prefect.concurrency.v1.asyncio import (
    _acquire_concurrency_slots,
    _release_concurrency_slots,
)
from prefect.context import (
    EngineContext,
    FlowRunContext,
    TaskRunContext,
    get_run_context,
)
from prefect.exceptions import CrashedRun, MissingResult
from prefect.filesystems import LocalFileSystem
from prefect.logging import get_run_logger
from prefect.results import ResultRecord, ResultStore
from prefect.server.schemas.core import ConcurrencyLimitV2
from prefect.settings import (
    PREFECT_TASK_DEFAULT_RETRIES,
    temporary_settings,
)
from prefect.states import Running, State
from prefect.task_engine import (
    AsyncTaskRunEngine,
    SyncTaskRunEngine,
    run_task_async,
    run_task_sync,
)
from prefect.task_runners import ThreadPoolTaskRunner
from prefect.testing.utilities import exceptions_equal
from prefect.transactions import transaction
from prefect.utilities.callables import get_call_parameters
from prefect.utilities.engine import propose_state


@task
async def foo():
    return 42


class TestSyncTaskRunEngine:
    async def test_basic_init(self):
        engine = SyncTaskRunEngine(task=foo)
        assert isinstance(engine.task, Task)
        assert engine.task.name == "foo"
        assert engine.parameters == {}

    async def test_client_attribute_raises_informative_error(self):
        engine = SyncTaskRunEngine(task=foo)
        with pytest.raises(RuntimeError, match="not started"):
            engine.client

    async def test_client_attr_returns_client_after_starting(self):
        engine = SyncTaskRunEngine(task=foo)
        with engine.initialize_run():
            client = engine.client
            assert isinstance(client, SyncPrefectClient)

        with pytest.raises(RuntimeError, match="not started"):
            engine.client


class TestAsyncTaskRunEngine:
    async def test_basic_init(self):
        engine = AsyncTaskRunEngine(task=foo)
        assert isinstance(engine.task, Task)
        assert engine.task.name == "foo"
        assert engine.parameters == {}

    async def test_client_attribute_raises_informative_error(self):
        engine = AsyncTaskRunEngine(task=foo)
        with pytest.raises(RuntimeError, match="not started"):
            engine.client

    async def test_client_attr_returns_client_after_starting(self):
        engine = AsyncTaskRunEngine(task=foo)
        async with engine.initialize_run():
            client = engine.client
            assert isinstance(client, PrefectClient)

        with pytest.raises(RuntimeError, match="not started"):
            engine.client


class TestRunTask:
    def test_run_task_with_client_provided_uuid(
        self, sync_prefect_client, events_pipeline
    ):
        @task
        def foo():
            return 42

        task_run_id = uuid4()

        run_task_sync(foo, task_run_id=task_run_id)

        events_pipeline.process_events(_sync=True)

        task_run = sync_prefect_client.read_task_run(task_run_id)
        assert task_run.id == task_run_id

    async def test_with_provided_context(self, prefect_client):
        @flow
        def f():
            pass

        test_task_runner = ThreadPoolTaskRunner()
        flow_run = await prefect_client.create_flow_run(f)
        await propose_state(prefect_client, Running(), flow_run_id=flow_run.id)
        result_store = await ResultStore().update_for_flow(f)
        flow_run_context = EngineContext(
            flow=f,
            flow_run=flow_run,
            client=prefect_client,
            task_runner=test_task_runner,
            result_store=result_store,
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
        self,
        prefect_client: PrefectClient,
        events_pipeline,
    ):
        @task
        async def foo():
            return 42

        task_run_id = uuid4()

        await run_task_async(foo, task_run_id=task_run_id)

        await events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(task_run_id)
        assert task_run.id == task_run_id

    async def test_with_provided_context(self, prefect_client):
        @flow
        def f():
            pass

        test_task_runner = ThreadPoolTaskRunner()
        flow_run = await prefect_client.create_flow_run(f)
        await propose_state(prefect_client, Running(), flow_run_id=flow_run.id)
        result_store = await ResultStore().update_for_flow(f)
        flow_run_context = EngineContext(
            flow=f,
            flow_run=flow_run,
            client=prefect_client,
            task_runner=test_task_runner,
            result_store=result_store,
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

    async def test_task_run_name(self, prefect_client, events_pipeline):
        @task(task_run_name="name is {x}")
        async def foo(x):
            return TaskRunContext.get().task_run.id

        result = await run_task_async(foo, parameters=dict(x="blue"))
        await events_pipeline.process_events()

        run = await prefect_client.read_task_run(result)

        assert run.name == "name is blue"

    async def test_get_run_logger(self, caplog):
        caplog.set_level(logging.CRITICAL)

        @task(task_run_name="test-run")
        async def my_log_task():
            get_run_logger().critical("hey yall")

        result = await run_task_async(my_log_task)

        assert result is None
        record = next((r for r in caplog.records if r.message == "hey yall"), None)
        assert record is not None, "Couldn't find expected log record"

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

    async def test_task_ends_in_completed(self, prefect_client, events_pipeline):
        @task
        async def foo():
            return TaskRunContext.get().task_run.id

        result = await run_task_async(foo)
        await events_pipeline.process_events()

        run = await prefect_client.read_task_run(result)

        assert run.state_type == StateType.COMPLETED

    async def test_task_ends_in_failed(self, prefect_client, events_pipeline):
        ID = None

        @task
        async def foo():
            nonlocal ID
            ID = TaskRunContext.get().task_run.id
            raise ValueError("xyz")

        with pytest.raises(ValueError, match="xyz"):
            await run_task_async(foo)

        await events_pipeline.process_events()

        run = await prefect_client.read_task_run(ID)

        assert run.state_type == StateType.FAILED

    async def test_task_ends_in_failed_after_retrying(
        self, prefect_client, events_pipeline
    ):
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

        await events_pipeline.process_events()

        run = await prefect_client.read_task_run(result)

        assert run.state_type == StateType.COMPLETED

    async def test_task_tracks_nested_parent_as_dependency(
        self, prefect_client, events_pipeline
    ):
        @task
        async def inner():
            return TaskRunContext.get().task_run.id

        @task
        async def outer():
            id1 = await inner()
            return (id1, TaskRunContext.get().task_run.id)

        a, b = await run_task_async(outer)
        assert a != b

        await events_pipeline.process_events()

        # assertions on outer
        outer_run = await prefect_client.read_task_run(b)
        assert outer_run.task_inputs == {}

        # assertions on inner
        inner_run = await prefect_client.read_task_run(a)
        assert "__parents__" in inner_run.task_inputs
        assert inner_run.task_inputs["__parents__"][0].id == b

    async def test_multiple_nested_tasks_track_parent(
        self, prefect_client, events_pipeline
    ):
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

        await events_pipeline.process_events()

        for id_, parent_id in [(id3, id2), (id2, id1)]:
            run = await prefect_client.read_task_run(id_)
            assert "__parents__" in run.task_inputs
            assert run.task_inputs["__parents__"][0].id == parent_id

        run = await prefect_client.read_task_run(id1)
        assert "__parents__" not in run.task_inputs

    async def test_tasks_in_subflow_do_not_track_subflow_dummy_task_as_parent(
        self, prefect_client, events_pipeline
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

        await events_pipeline.process_events()

        tr = await prefect_client.read_task_run(level_3_id)
        assert "__parents__" not in tr.task_inputs

    async def test_tasks_in_subflow_do_not_track_subflow_dummy_task_parent_as_parent(
        self, prefect_client, events_pipeline
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

        await events_pipeline.process_events()

        tr = await prefect_client.read_task_run(level_4_id)

        assert "__parents__" not in tr.task_inputs

    async def test_task_runs_respect_result_persistence(
        self, prefect_client, events_pipeline
    ):
        @task(persist_result=False)
        async def no_persist():
            return TaskRunContext.get().task_run.id

        @task(persist_result=True)
        async def persist():
            return TaskRunContext.get().task_run.id

        # assert no persistence
        run_id = await run_task_async(no_persist)
        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(run_id)
        api_state = task_run.state

        with pytest.raises(MissingResult):
            await api_state.result()

        # assert persistence
        run_id = await run_task_async(persist)
        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(run_id)
        api_state = task_run.state

        assert await api_state.result() == run_id

    async def test_task_runs_respect_cache_key(self):
        @task(cache_key_fn=lambda *args, **kwargs: "key", persist_result=True)
        async def first():
            return 42

        @task(cache_key_fn=lambda *args, **kwargs: "key", persist_result=True)
        async def second():
            return 500

        one = await run_task_async(first)
        two = await run_task_async(second)

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

    async def test_task_run_name(self, prefect_client, events_pipeline):
        @task(task_run_name="name is {x}")
        def foo(x):
            return TaskRunContext.get().task_run.id

        result = run_task_sync(foo, parameters=dict(x="blue"))
        await events_pipeline.process_events()
        run = await prefect_client.read_task_run(result)
        assert run.name == "name is blue"

    def test_get_run_logger(self, caplog):
        caplog.set_level(logging.CRITICAL)

        @task(task_run_name="test-run")
        def my_log_task():
            get_run_logger().critical("hey yall")

        result = run_task_sync(my_log_task)

        assert result is None
        record = next((r for r in caplog.records if r.message == "hey yall"), None)
        assert record is not None, "Couldn't find expected log record"

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

    async def test_task_ends_in_completed(self, prefect_client, events_pipeline):
        @task
        def foo():
            return TaskRunContext.get().task_run.id

        result = run_task_sync(foo)
        await events_pipeline.process_events()
        run = await prefect_client.read_task_run(result)

        assert run.state_type == StateType.COMPLETED

    async def test_task_ends_in_failed(self, prefect_client, events_pipeline):
        ID = None

        @task
        def foo():
            nonlocal ID
            ID = TaskRunContext.get().task_run.id
            raise ValueError("xyz")

        with pytest.raises(ValueError, match="xyz"):
            run_task_sync(foo)

        await events_pipeline.process_events()
        run = await prefect_client.read_task_run(ID)

        assert run.state_type == StateType.FAILED

    async def test_task_ends_in_failed_after_retrying(
        self, prefect_client, events_pipeline
    ):
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

        await events_pipeline.process_events()
        run = await prefect_client.read_task_run(result)

        assert run.state_type == StateType.COMPLETED

    async def test_task_tracks_nested_parent_as_dependency(
        self, prefect_client, events_pipeline
    ):
        @task
        def inner():
            return TaskRunContext.get().task_run.id

        @task
        def outer():
            id1 = inner()
            return (id1, TaskRunContext.get().task_run.id)

        a, b = run_task_sync(outer)
        assert a != b
        await events_pipeline.process_events()

        # assertions on outer
        outer_run = await prefect_client.read_task_run(b)
        assert outer_run.task_inputs == {}

        # assertions on inner
        inner_run = await prefect_client.read_task_run(a)
        assert "__parents__" in inner_run.task_inputs
        assert inner_run.task_inputs["__parents__"][0].id == b

    async def test_task_runs_respect_result_persistence(
        self, prefect_client, events_pipeline
    ):
        @task(persist_result=False)
        def no_persist():
            ctx = TaskRunContext.get()
            assert ctx
            return ctx.task_run.id

        @task(persist_result=True)
        def persist():
            ctx = TaskRunContext.get()
            assert ctx
            return ctx.task_run.id

        # assert no persistence
        run_id = run_task_sync(no_persist)
        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(run_id)
        api_state = task_run.state

        with pytest.raises(MissingResult):
            await api_state.result()

        # assert persistence
        run_id = run_task_sync(persist)
        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(run_id)
        api_state = task_run.state

        assert await api_state.result() == run_id

    async def test_task_runs_respect_cache_key(self):
        @task(cache_key_fn=lambda *args, **kwargs: "key", persist_result=True)
        def first():
            return 42

        @task(cache_key_fn=lambda *args, **kwargs: "key", persist_result=True)
        def second():
            return 500

        one = run_task_sync(first)
        two = run_task_sync(second)

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
    async def test_task_respects_retry_count(
        self, always_fail, prefect_client, events_pipeline
    ):
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

        await events_pipeline.process_events()
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
    async def test_task_respects_retry_count_sync(
        self, always_fail, prefect_client, events_pipeline
    ):
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

        await events_pipeline.process_events()
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

    async def test_task_only_uses_necessary_retries(
        self, prefect_client, events_pipeline
    ):
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

        await events_pipeline.process_events()
        states = await prefect_client.read_task_run_states(task_run_id)

        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Retrying",
            "Completed",
        ]

    async def test_task_passes_failed_state_to_retry_fn(
        self, prefect_client, events_pipeline
    ):
        mock = MagicMock()
        exc = SyntaxError("oops")
        handler_mock = MagicMock()

        async def handler(task, task_run, state):
            handler_mock()
            assert state.is_failed()
            try:
                await state.result()
            except SyntaxError:
                return True
            return False

        @task(retries=3, retry_condition_fn=handler)
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
        assert handler_mock.call_count == 1

        await events_pipeline.process_events()
        states = await prefect_client.read_task_run_states(task_run_id)

        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Retrying",
            "Completed",
        ]

    async def test_task_passes_failed_state_to_retry_fn_sync(
        self, prefect_client, events_pipeline
    ):
        mock = MagicMock()
        exc = SyntaxError("oops")
        handler_mock = MagicMock()

        def handler(task, task_run, state):
            handler_mock()
            assert state.is_failed()
            try:
                state.result()
            except SyntaxError:
                return True
            return False

        @task(retries=3, retry_condition_fn=handler)
        def flaky_function():
            mock()
            if mock.call_count == 2:
                return True
            raise exc

        @flow
        def test_flow():
            return flaky_function(return_state=True)

        task_run_state = test_flow()
        task_run_id = task_run_state.state_details.task_run_id

        assert task_run_state.is_completed()
        assert await task_run_state.result() is True
        assert mock.call_count == 2
        assert handler_mock.call_count == 1

        await events_pipeline.process_events()
        states = await prefect_client.read_task_run_states(task_run_id)

        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Retrying",
            "Completed",
        ]

    async def test_task_retries_receive_latest_task_run_in_context(self):
        state_names: List[str] = []
        run_counts = []
        start_times = []

        @task(retries=3)
        async def flaky_function():
            ctx = TaskRunContext.get()
            state_names.append(ctx.task_run.state_name)
            run_counts.append(ctx.task_run.run_count)
            start_times.append(ctx.start_time)
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
        assert len(state_names) == len(expected_state_names) == len(run_counts)
        for i in range(len(state_names)):
            assert run_counts[i] == i + 1
            assert state_names[i] == expected_state_names[i]

            if i > 0:
                last_start_time = start_times[i - 1]
                assert (
                    last_start_time < start_times[i]
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
        self,
        retry_delay_seconds,
        expected_delay_sequence,
        prefect_client,
        events_pipeline,
        monkeypatch,
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
            call(pytest.approx(delay, abs=1)) for delay in expected_delay_sequence
        ]

        await events_pipeline.process_events()
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
        self,
        retry_delay_seconds,
        expected_delay_sequence,
        prefect_client,
        events_pipeline,
        monkeypatch,
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
        await events_pipeline.process_events()
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
        self, prefect_client, interrupt_type, events_pipeline
    ):
        @task
        async def my_task():
            raise interrupt_type()

        with pytest.raises(interrupt_type):
            await my_task()

        await events_pipeline.process_events()
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
        self, prefect_client, events_pipeline, interrupt_type
    ):
        @task
        def my_task():
            raise interrupt_type()

        with pytest.raises(interrupt_type):
            my_task()

        await events_pipeline.process_events()
        task_runs = await prefect_client.read_task_runs()
        assert len(task_runs) == 1
        task_run = task_runs[0]
        assert task_run.state.is_crashed()
        assert task_run.state.type == StateType.CRASHED
        assert "Execution was aborted" in task_run.state.message
        with pytest.raises(CrashedRun, match="Execution was aborted"):
            await task_run.state.result()

    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_task_orchestration_crashes_task_and_flow_sync(
        self, prefect_client, events_pipeline, interrupt_type, monkeypatch
    ):
        monkeypatch.setattr(
            SyncTaskRunEngine, "begin_run", MagicMock(side_effect=interrupt_type)
        )

        @task
        def my_task():
            pass

        with pytest.raises(interrupt_type):
            my_task()

        await events_pipeline.process_events()
        task_runs = await prefect_client.read_task_runs()
        assert len(task_runs) == 1
        task_run = task_runs[0]
        assert task_run.state.is_crashed()
        assert task_run.state.type == StateType.CRASHED
        assert "Execution was aborted" in task_run.state.message
        with pytest.raises(CrashedRun, match="Execution was aborted"):
            await task_run.state.result()

    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_task_orchestration_crashes_task_and_flow_async(
        self, prefect_client, events_pipeline, interrupt_type, monkeypatch
    ):
        monkeypatch.setattr(
            AsyncTaskRunEngine, "begin_run", MagicMock(side_effect=interrupt_type)
        )

        @task
        async def my_task():
            pass

        with pytest.raises(interrupt_type):
            await my_task()

        await events_pipeline.process_events()
        task_runs = await prefect_client.read_task_runs()
        assert len(task_runs) == 1
        task_run = task_runs[0]
        assert task_run.state.is_crashed()
        assert task_run.state.type == StateType.CRASHED
        assert "Execution was aborted" in task_run.state.message
        with pytest.raises(CrashedRun, match="Execution was aborted"):
            await task_run.state.result()


class TestTaskTimeTracking:
    async def test_sync_task_sets_start_time_on_running(
        self, prefect_client, events_pipeline
    ):
        @task
        def foo():
            return TaskRunContext.get().task_run.id

        task_run_id = run_task_sync(foo)
        await events_pipeline.process_events()

        run = await prefect_client.read_task_run(task_run_id)

        states = await prefect_client.read_task_run_states(task_run_id)
        running = [state for state in states if state.type == StateType.RUNNING][0]
        assert run.start_time
        assert run.start_time == running.timestamp

    async def test_async_task_sets_start_time_on_running(
        self, prefect_client, events_pipeline
    ):
        @task
        async def foo():
            return TaskRunContext.get().task_run.id

        task_run_id = await run_task_async(foo)
        await events_pipeline.process_events()
        run = await prefect_client.read_task_run(task_run_id)

        states = await prefect_client.read_task_run_states(task_run_id)
        running = [state for state in states if state.type == StateType.RUNNING][0]
        assert run.start_time
        assert run.start_time == running.timestamp

    async def test_sync_task_sets_end_time_on_completed(
        self, prefect_client, events_pipeline
    ):
        @task
        def foo():
            return TaskRunContext.get().task_run.id

        task_run_id = run_task_sync(foo)
        await events_pipeline.process_events()
        run = await prefect_client.read_task_run(task_run_id)

        states = await prefect_client.read_task_run_states(task_run_id)
        running = [state for state in states if state.type == StateType.RUNNING][0]
        completed = [state for state in states if state.type == StateType.COMPLETED][0]

        assert run.end_time
        assert run.end_time == completed.timestamp
        assert run.total_run_time == completed.timestamp - running.timestamp

    async def test_async_task_sets_end_time_on_completed(
        self, prefect_client, events_pipeline
    ):
        @task
        async def foo():
            return TaskRunContext.get().task_run.id

        task_run_id = await run_task_async(foo)
        await events_pipeline.process_events()
        run = await prefect_client.read_task_run(task_run_id)
        states = await prefect_client.read_task_run_states(task_run_id)
        running = [state for state in states if state.type == StateType.RUNNING][0]
        completed = [state for state in states if state.type == StateType.COMPLETED][0]

        assert run.end_time
        assert run.end_time == completed.timestamp
        assert run.total_run_time == completed.timestamp - running.timestamp

    async def test_sync_task_sets_end_time_on_failed(
        self, prefect_client, events_pipeline
    ):
        ID = None

        @task
        def foo():
            nonlocal ID
            ID = TaskRunContext.get().task_run.id
            raise ValueError("failure!!!")

        with pytest.raises(ValueError):
            run_task_sync(foo)

        await events_pipeline.process_events()

        run = await prefect_client.read_task_run(ID)

        states = await prefect_client.read_task_run_states(ID)
        running = [state for state in states if state.type == StateType.RUNNING][0]
        failed = [state for state in states if state.type == StateType.FAILED][0]

        assert run.end_time
        assert run.end_time == failed.timestamp
        assert run.total_run_time == failed.timestamp - running.timestamp

    async def test_async_task_sets_end_time_on_failed(
        self, prefect_client, events_pipeline
    ):
        ID = None

        @task
        async def foo():
            nonlocal ID
            ID = TaskRunContext.get().task_run.id
            raise ValueError("failure!!!")

        with pytest.raises(ValueError):
            await run_task_async(foo)

        await events_pipeline.process_events()
        run = await prefect_client.read_task_run(ID)
        states = await prefect_client.read_task_run_states(ID)
        running = [state for state in states if state.type == StateType.RUNNING][0]
        failed = [state for state in states if state.type == StateType.FAILED][0]

        assert run.end_time
        assert run.end_time == failed.timestamp
        assert run.total_run_time == failed.timestamp - running.timestamp

    async def test_sync_task_sets_end_time_on_crashed(
        self, prefect_client, events_pipeline
    ):
        ID = None

        @task
        def foo():
            nonlocal ID
            ID = TaskRunContext.get().task_run.id
            raise SystemExit

        with pytest.raises(SystemExit):
            run_task_sync(foo)
        await events_pipeline.process_events()

        run = await prefect_client.read_task_run(ID)
        states = await prefect_client.read_task_run_states(ID)
        running = [state for state in states if state.type == StateType.RUNNING][0]
        crashed = [state for state in states if state.type == StateType.CRASHED][0]

        assert run.end_time
        assert run.end_time == crashed.timestamp
        assert run.total_run_time == crashed.timestamp - running.timestamp

    async def test_async_task_sets_end_time_on_crashed(
        self, prefect_client, events_pipeline
    ):
        ID = None

        @task
        async def foo():
            nonlocal ID
            ID = TaskRunContext.get().task_run.id
            raise SystemExit

        with pytest.raises(SystemExit):
            await run_task_async(foo)

        await events_pipeline.process_events()
        run = await prefect_client.read_task_run(ID)
        states = await prefect_client.read_task_run_states(ID)
        running = [state for state in states if state.type == StateType.RUNNING][0]
        crashed = [state for state in states if state.type == StateType.CRASHED][0]

        assert run.end_time
        assert run.end_time == crashed.timestamp
        assert run.total_run_time == crashed.timestamp - running.timestamp

    async def test_sync_task_does_not_set_end_time_on_crash_pre_runnning(
        self, monkeypatch, prefect_client, events_pipeline
    ):
        monkeypatch.setattr(
            SyncTaskRunEngine, "begin_run", MagicMock(side_effect=SystemExit)
        )

        @task
        def my_task():
            pass

        with pytest.raises(SystemExit):
            my_task()

        await events_pipeline.process_events()
        task_runs = await prefect_client.read_task_runs()
        assert len(task_runs) == 1
        run = task_runs[0]

        assert run.end_time is None

    async def test_async_task_does_not_set_end_time_on_crash_pre_running(
        self, monkeypatch, prefect_client, events_pipeline
    ):
        monkeypatch.setattr(
            AsyncTaskRunEngine, "begin_run", MagicMock(side_effect=SystemExit)
        )

        @task
        async def my_task():
            pass

        with pytest.raises(SystemExit):
            await my_task()

        await events_pipeline.process_events()

        task_runs = await prefect_client.read_task_runs()
        assert len(task_runs) == 1
        run = task_runs[0]

        assert run.end_time is None

    async def test_sync_task_sets_expected_start_time_on_pending(
        self, prefect_client, events_pipeline
    ):
        @task
        def foo():
            return TaskRunContext.get().task_run.id

        task_run_id = run_task_sync(foo)
        await events_pipeline.process_events()
        run = await prefect_client.read_task_run(task_run_id)

        states = await prefect_client.read_task_run_states(task_run_id)
        pending = [state for state in states if state.type == StateType.PENDING][0]

        assert run.expected_start_time
        assert run.expected_start_time == pending.timestamp

    async def test_async_task_sets_expected_start_time_on_pending(
        self, prefect_client, events_pipeline
    ):
        @task
        async def foo():
            return TaskRunContext.get().task_run.id

        task_run_id = await run_task_async(foo)
        await events_pipeline.process_events()
        run = await prefect_client.read_task_run(task_run_id)
        states = await prefect_client.read_task_run_states(task_run_id)
        pending = [state for state in states if state.type == StateType.PENDING][0]
        assert run.expected_start_time
        assert run.expected_start_time == pending.timestamp


class TestRunCountTracking:
    @pytest.fixture
    async def flow_run_context(self, prefect_client: PrefectClient):
        @flow
        def f():
            pass

        test_task_runner = ThreadPoolTaskRunner()
        flow_run = await prefect_client.create_flow_run(f)
        await propose_state(prefect_client, Running(), flow_run_id=flow_run.id)

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.run_count == 1

        result_store = await ResultStore().update_for_flow(f)
        return EngineContext(
            flow=f,
            flow_run=flow_run,
            client=prefect_client,
            task_runner=test_task_runner,
            result_store=result_store,
            parameters={"x": "y"},
        )

    def test_sync_task_run_counts(
        self, flow_run_context: EngineContext, sync_prefect_client, events_pipeline
    ):
        ID = None
        proof_that_i_ran = uuid4()

        @task
        def foo():
            task_run = TaskRunContext.get().task_run

            nonlocal ID
            ID = task_run.id

            assert task_run
            assert task_run.state
            assert task_run.state.type == StateType.RUNNING

            assert task_run.run_count == 1
            assert task_run.flow_run_run_count == flow_run_context.flow_run.run_count

            return proof_that_i_ran

        with flow_run_context:
            assert run_task_sync(foo) == proof_that_i_ran

        events_pipeline.process_events(_sync=True)
        task_run = sync_prefect_client.read_task_run(ID)
        assert task_run
        assert task_run.run_count == 1
        assert task_run.flow_run_run_count == flow_run_context.flow_run.run_count

    async def test_async_task_run_counts(
        self, flow_run_context: EngineContext, prefect_client, events_pipeline
    ):
        ID = None
        proof_that_i_ran = uuid4()

        @task
        async def foo():
            task_run = TaskRunContext.get().task_run

            nonlocal ID
            ID = task_run.id

            assert task_run
            assert task_run.state
            assert task_run.state.type == StateType.RUNNING

            assert task_run.run_count == 1
            assert task_run.flow_run_run_count == flow_run_context.flow_run.run_count

            return proof_that_i_ran

        with flow_run_context:
            assert await run_task_async(foo) == proof_that_i_ran

        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(ID)
        assert task_run
        assert task_run.run_count == 1
        assert task_run.flow_run_run_count == flow_run_context.flow_run.run_count


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

    async def test_timeout_concurrency_slot_released_sync(
        self, concurrency_limit_v2: ConcurrencyLimitV2, prefect_client: PrefectClient
    ):
        @task(timeout_seconds=0.5)
        def expensive_task():
            with concurrency(concurrency_limit_v2.name):
                time.sleep(1)

        with pytest.raises(TimeoutError):
            expensive_task()

        response = await prefect_client.read_global_concurrency_limit_by_name(
            concurrency_limit_v2.name
        )
        assert response.active_slots == 0

    async def test_timeout_concurrency_slot_released_async(
        self, concurrency_limit_v2: ConcurrencyLimitV2, prefect_client: PrefectClient
    ):
        @task(timeout_seconds=0.5)
        async def expensive_task():
            async with aconcurrency(concurrency_limit_v2.name):
                await asyncio.sleep(1)

        with pytest.raises(TimeoutError):
            await expensive_task()

        response = await prefect_client.read_global_concurrency_limit_by_name(
            concurrency_limit_v2.name
        )
        assert response.active_slots == 0


class TestPersistence:
    async def test_task_can_return_result_record(self):
        @task
        async def async_task():
            store = ResultStore()
            record = store.create_result_record(42)
            store.persist_result_record(record)
            return record

        assert await async_task() == 42
        state = await async_task(return_state=True)
        assert await state.result() == 42

    async def test_task_loads_result_if_exists_using_result_storage_key(self):
        store = ResultStore()
        store.write(obj=-92, key="foo-bar")

        @task(result_storage_key="foo-bar", persist_result=True)
        async def async_task():
            return 42

        state = await run_task_async(async_task, return_type="state")
        assert state.is_completed()
        assert await state.result() == -92
        assert isinstance(state.data, ResultRecord)
        key_path = Path(state.data.metadata.storage_key)
        assert key_path.name == "foo-bar"

    async def test_task_result_persistence_references_absolute_path(self):
        @task(result_storage_key="test-absolute-path", persist_result=True)
        async def async_task():
            return 42

        state = await run_task_async(async_task, return_type="state")
        assert state.is_completed()
        assert await state.result() == 42
        assert isinstance(state.data, ResultRecord)

        key_path = Path(state.data.metadata.storage_key)
        assert key_path.is_absolute()
        assert key_path.name == "test-absolute-path"


class TestCachePolicy:
    async def test_result_stored_with_storage_key_if_no_policy_set(
        self, prefect_client
    ):
        # avoid conflicts
        key = f"foo-bar-{random.randint(0, 10000)}"

        @task(persist_result=True, result_storage_key=key)
        async def async_task():
            return 1800

        state = await async_task(return_state=True)

        assert state.is_completed()
        assert await state.result() == 1800
        assert Path(state.data.metadata.storage_key).name == key

    async def test_cache_expiration_is_respected(self, advance_time, tmp_path):
        fs = LocalFileSystem(basepath=tmp_path)
        await fs.save("local-fs")

        @task(
            persist_result=True,
            result_storage_key="expiring-foo-bar",
            cache_expiration=timedelta(seconds=1.0),
            result_storage=fs,
        )
        async def async_task():
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
        await fs.save("test-once")

        @task(
            persist_result=True,
            result_storage_key="expiring-foo-bar",
            cache_expiration=timedelta(seconds=0.0),
            result_storage=fs,
        )
        async def async_task():
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
        assert isinstance(state.data, ResultRecord)
        assert not Path(state.data.metadata.storage_key).exists()

    async def test_none_return_value_does_persist(self, prefect_client, tmp_path):
        fs = LocalFileSystem(basepath=tmp_path)
        await fs.save("none-test")

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

    async def test_error_handling_on_cache_policies(self, prefect_client, tmp_path):
        fs = LocalFileSystem(basepath=tmp_path)
        await fs.save("error-handling-test")

        @task(
            cache_policy=TASK_SOURCE + INPUTS,
            result_storage=fs,
        )
        def my_random_task(x: int, cmplx_input):
            return random.randint(0, x)

        @flow
        def my_param_flow(x: int):
            import threading

            thread = threading.Thread()

            first_val = my_random_task(x, cmplx_input=thread, return_state=True)
            second_val = my_random_task(x, cmplx_input=thread, return_state=True)
            return first_val, second_val

        first, second = my_param_flow(4200)
        assert first.name == "Completed"
        assert second.name == "Completed"

        first_result = await first.result()
        second_result = await second.result()
        assert first_result != second_result

    async def test_flow_parameter_caching(self, prefect_client, tmp_path):
        fs = LocalFileSystem(basepath=tmp_path)
        await fs.save("param-test")

        @task(
            cache_policy=FLOW_PARAMETERS,
            result_storage=fs,
            persist_result=True,
        )
        def my_random_task(x: int):
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

    async def test_bad_api_result_references_cause_reruns(self, tmp_path: Path):
        fs = LocalFileSystem(basepath=tmp_path)
        await fs.save("badapi")

        PAYLOAD = {"return": 42}

        @task(result_storage=fs, result_storage_key="tmp-first", persist_result=True)
        async def first():
            return PAYLOAD["return"], get_run_context().task_run

        result, task_run = await run_task_async(first)

        assert result == 42
        assert await fs.read_path("tmp-first")

        # delete record
        path = fs._resolve_path("tmp-first")
        os.unlink(path)
        with pytest.raises(ValueError, match="does not exist"):
            assert await fs.read_path("tmp-first")

        # rerun with same task run ID
        PAYLOAD["return"] = "bar"
        result, task_run = await run_task_async(first, task_run=task_run)

        assert result == "bar"
        assert await fs.read_path("tmp-first")


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

    async def test_generator_task_states(
        self, prefect_client: PrefectClient, events_pipeline
    ):
        """
        Test for generator behavior including StopIteration
        """

        @task
        def g():
            yield TaskRunContext.get().task_run.id
            yield 2

        gen = g()
        tr_id = next(gen)
        events_pipeline.process_events(_sync=True)
        tr = await prefect_client.read_task_run(tr_id)
        assert tr.state.is_running()

        # exhaust the generator
        for _ in gen:
            pass

        events_pipeline.process_events(_sync=True)
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
        self, prefect_client: PrefectClient, events_pipeline
    ):
        @task
        def g():
            yield TaskRunContext.get().task_run.id
            raise ValueError("xyz")

        gen = g()
        tr_id = next(gen)
        with pytest.raises(ValueError, match="xyz"):
            next(gen)
        await events_pipeline.process_events()
        tr = await prefect_client.read_task_run(tr_id)
        assert tr.state.is_failed()

    async def test_generator_parent_tracking(
        self, prefect_client: PrefectClient, events_pipeline
    ):
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
        await events_pipeline.process_events()
        tr = await prefect_client.read_task_run(tr_id)
        assert "x" in tr.task_inputs
        assert "__parents__" in tr.task_inputs
        # the parent run and upstream 'x' run are the same
        assert tr.task_inputs["__parents__"][0].id == tr.task_inputs["x"][0].id
        # the parent run is "gen-1000"
        gen_id = tr.task_inputs["__parents__"][0].id
        await events_pipeline.process_events()
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

    async def test_generator_task_states(
        self, prefect_client: PrefectClient, events_pipeline
    ):
        """
        Test for generator behavior including StopIteration
        """

        @task
        async def g():
            yield TaskRunContext.get().task_run.id

        async for val in g():
            tr_id = val
            await events_pipeline.process_events()
            tr = await prefect_client.read_task_run(tr_id)
            assert tr.state.is_running()

        await events_pipeline.process_events()
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
        self, prefect_client: PrefectClient, events_pipeline
    ):
        @task
        async def g():
            yield TaskRunContext.get().task_run.id
            raise ValueError("xyz")

        with pytest.raises(ValueError, match="xyz"):
            async for val in g():
                tr_id = val
        await events_pipeline.process_events()
        tr = await prefect_client.read_task_run(tr_id)
        assert tr.state.is_failed()

    async def test_generator_parent_tracking(
        self, prefect_client: PrefectClient, events_pipeline
    ):
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
        await events_pipeline.process_events()
        tr = await prefect_client.read_task_run(tr_id)
        assert "x" in tr.task_inputs
        assert "__parents__" in tr.task_inputs
        # the parent run and upstream 'x' run are the same
        assert tr.task_inputs["__parents__"][0].id == tr.task_inputs["x"][0].id
        # the parent run is "gen-1000"
        gen_id = tr.task_inputs["__parents__"][0].id
        await events_pipeline.process_events()
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


class TestTaskConcurrencyLimits:
    async def test_tag_concurrency(self):
        task_run_id = None

        @task(tags=["limit-tag"])
        async def bar():
            nonlocal task_run_id
            task_run_id = TaskRunContext.get().task_run.id
            return 42

        with mock.patch(
            "prefect.concurrency.v1.asyncio._acquire_concurrency_slots",
            wraps=_acquire_concurrency_slots,
        ) as acquire_spy:
            with mock.patch(
                "prefect.concurrency.v1.asyncio._release_concurrency_slots",
                wraps=_release_concurrency_slots,
            ) as release_spy:
                await bar()

                acquire_spy.assert_called_once_with(
                    ["limit-tag"], task_run_id=task_run_id, timeout_seconds=None
                )

                names, _task_run_id, occupy_seconds = release_spy.call_args[0]
                assert names == ["limit-tag"]
                assert _task_run_id == task_run_id
                assert occupy_seconds > 0

    def test_tag_concurrency_sync(self):
        task_run_id = None

        @task(tags=["limit-tag"])
        def bar():
            nonlocal task_run_id
            task_run_id = TaskRunContext.get().task_run.id
            return 42

        with mock.patch(
            "prefect.concurrency.v1.sync._acquire_concurrency_slots",
            wraps=_acquire_concurrency_slots,
        ) as acquire_spy:
            with mock.patch(
                "prefect.concurrency.v1.sync._release_concurrency_slots",
                wraps=_release_concurrency_slots,
            ) as release_spy:
                bar()

                acquire_spy.assert_called_once_with(
                    ["limit-tag"],
                    task_run_id=task_run_id,
                    timeout_seconds=None,
                    _sync=True,
                )

                names, _task_run_id, occupy_seconds = release_spy.call_args[0]
                assert names == ["limit-tag"]
                assert _task_run_id == task_run_id
                assert occupy_seconds > 0

    def test_tag_concurrency_sync_with_tags_context(self):
        task_run_id = None

        @task
        def bar():
            nonlocal task_run_id
            task_run_id = TaskRunContext.get().task_run.id
            return 42

        with mock.patch(
            "prefect.concurrency.v1.sync._acquire_concurrency_slots",
            wraps=_acquire_concurrency_slots,
        ) as acquire_spy:
            with mock.patch(
                "prefect.concurrency.v1.sync._release_concurrency_slots",
                wraps=_release_concurrency_slots,
            ) as release_spy:
                with tags("limit-tag"):
                    bar()

                acquire_spy.assert_called_once_with(
                    ["limit-tag"],
                    task_run_id=task_run_id,
                    timeout_seconds=None,
                    _sync=True,
                )

                names, _task_run_id, occupy_seconds = release_spy.call_args[0]
                assert names == ["limit-tag"]
                assert _task_run_id == task_run_id
                assert occupy_seconds > 0

    async def test_tag_concurrency_with_tags_context(self):
        task_run_id = None

        @task
        async def bar():
            nonlocal task_run_id
            task_run_id = TaskRunContext.get().task_run.id
            return 42

        with mock.patch(
            "prefect.concurrency.v1.asyncio._acquire_concurrency_slots",
            wraps=_acquire_concurrency_slots,
        ) as acquire_spy:
            with mock.patch(
                "prefect.concurrency.v1.asyncio._release_concurrency_slots",
                wraps=_release_concurrency_slots,
            ) as release_spy:
                with tags("limit-tag"):
                    await bar()

                acquire_spy.assert_called_once_with(
                    ["limit-tag"], task_run_id=task_run_id, timeout_seconds=None
                )

                names, _task_run_id, occupy_seconds = release_spy.call_args[0]
                assert names == ["limit-tag"]
                assert _task_run_id == task_run_id
                assert occupy_seconds > 0

    async def test_no_tags_no_concurrency(self):
        @task
        async def bar():
            return 42

        with mock.patch(
            "prefect.concurrency.v1.asyncio._acquire_concurrency_slots",
            wraps=_acquire_concurrency_slots,
        ) as acquire_spy:
            with mock.patch(
                "prefect.concurrency.v1.asyncio._release_concurrency_slots",
                wraps=_release_concurrency_slots,
            ) as release_spy:
                await bar()

                assert acquire_spy.call_count == 0
                assert release_spy.call_count == 0

    def test_no_tags_no_concurrency_sync(self):
        @task
        def bar():
            return 42

        with mock.patch(
            "prefect.concurrency.v1.sync._acquire_concurrency_slots",
            wraps=_acquire_concurrency_slots,
        ) as acquire_spy:
            with mock.patch(
                "prefect.concurrency.v1.sync._release_concurrency_slots",
                wraps=_release_concurrency_slots,
            ) as release_spy:
                bar()

                assert acquire_spy.call_count == 0
                assert release_spy.call_count == 0

    async def test_tag_concurrency_does_not_create_limits(self, prefect_client):
        task_run_id = None

        @task(tags=["limit-tag"])
        async def bar():
            nonlocal task_run_id
            task_run_id = TaskRunContext.get().task_run.id
            return 42

        with mock.patch(
            "prefect.concurrency.v1.asyncio._acquire_concurrency_slots",
            wraps=_acquire_concurrency_slots,
        ) as acquire_spy:
            await bar()

            acquire_spy.assert_called_once_with(
                ["limit-tag"], task_run_id=task_run_id, timeout_seconds=None
            )

            limits = await prefect_client.read_concurrency_limits(10, 0)
            assert len(limits) == 0


class TestRunStateIsDenormalized:
    async def test_state_attributes_are_denormalized_async_success(
        self, prefect_client, events_pipeline
    ):
        ID = None

        @task
        async def foo():
            nonlocal ID
            ID = TaskRunContext.get().task_run.id

            task_run = TaskRunContext.get().task_run

            # while we are Running, we should have the state attributes copied onto the
            # current task run instance
            assert task_run.state
            assert task_run.state_id == task_run.state.id
            assert task_run.state_type == task_run.state.type == StateType.RUNNING
            assert task_run.state_name == task_run.state.name == "Running"

        await run_task_async(foo)
        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(ID)

        assert task_run
        assert task_run.state

        assert task_run.state_id == task_run.state.id
        assert task_run.state_type == task_run.state.type == StateType.COMPLETED
        assert task_run.state_name == task_run.state.name == "Completed"

    async def test_state_attributes_are_denormalized_async_failure(
        self, prefect_client, events_pipeline
    ):
        ID = None

        @task
        async def foo():
            nonlocal ID
            ID = TaskRunContext.get().task_run.id

            task_run = TaskRunContext.get().task_run

            # while we are Running, we should have the state attributes copied onto the
            # current task run instance
            assert task_run.state
            assert task_run.state_id == task_run.state.id
            assert task_run.state_type == task_run.state.type == StateType.RUNNING
            assert task_run.state_name == task_run.state.name == "Running"

            raise ValueError("woops!")

        with pytest.raises(ValueError, match="woops!"):
            await run_task_async(foo)

        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(ID)

        assert task_run
        assert task_run.state

        assert task_run.state_id == task_run.state.id
        assert task_run.state_type == task_run.state.type == StateType.FAILED
        assert task_run.state_name == task_run.state.name == "Failed"

    def test_state_attributes_are_denormalized_sync_success(
        self, sync_prefect_client, events_pipeline
    ):
        ID = None

        @task
        def foo():
            nonlocal ID
            ID = TaskRunContext.get().task_run.id

            task_run = TaskRunContext.get().task_run

            # while we are Running, we should have the state attributes copied onto the
            # current task run instance
            assert task_run.state
            assert task_run.state_id == task_run.state.id
            assert task_run.state_type == task_run.state.type == StateType.RUNNING
            assert task_run.state_name == task_run.state.name == "Running"

        run_task_sync(foo)
        events_pipeline.process_events(_sync=True)
        task_run = sync_prefect_client.read_task_run(ID)

        assert task_run
        assert task_run.state

        assert task_run.state_id == task_run.state.id
        assert task_run.state_type == task_run.state.type == StateType.COMPLETED
        assert task_run.state_name == task_run.state.name == "Completed"

    def test_state_attributes_are_denormalized_sync_failure(
        self, sync_prefect_client, events_pipeline
    ):
        ID = None

        @task
        def foo():
            nonlocal ID
            ID = TaskRunContext.get().task_run.id

            task_run = TaskRunContext.get().task_run

            # while we are Running, we should have the state attributes copied onto the
            # current task run instance
            assert task_run.state
            assert task_run.state_id == task_run.state.id
            assert task_run.state_type == task_run.state.type == StateType.RUNNING
            assert task_run.state_name == task_run.state.name == "Running"

            raise ValueError("woops!")

        with pytest.raises(ValueError, match="woops!"):
            run_task_sync(foo)

        events_pipeline.process_events(_sync=True)
        task_run = sync_prefect_client.read_task_run(ID)

        assert task_run
        assert task_run.state

        assert task_run.state_id == task_run.state.id
        assert task_run.state_type == task_run.state.type == StateType.FAILED
        assert task_run.state_name == task_run.state.name == "Failed"

    async def test_state_details_have_denormalized_task_run_id_async(self):
        proof_that_i_ran = uuid4()

        @task
        async def foo():
            task_run = TaskRunContext.get().task_run

            assert task_run
            assert task_run.state
            assert task_run.state.state_details

            assert task_run.state.state_details.flow_run_id is None
            assert task_run.state.state_details.task_run_id == task_run.id

            return proof_that_i_ran

        assert await run_task_async(foo) == proof_that_i_ran

    async def test_state_details_have_denormalized_flow_run_id_async(self):
        proof_that_i_ran = uuid4()

        @flow
        async def the_flow():
            return foo()

        @task
        async def foo():
            task_run = TaskRunContext.get().task_run

            assert task_run
            assert task_run.state
            assert task_run.state.state_details

            assert task_run.state.state_details.flow_run_id == task_run.flow_run_id
            assert task_run.state.state_details.task_run_id == task_run.id

            return proof_that_i_ran

        assert await the_flow() == proof_that_i_ran

    def test_state_details_have_denormalized_task_run_id_sync(self):
        proof_that_i_ran = uuid4()

        @task
        def foo():
            task_run = TaskRunContext.get().task_run

            assert task_run
            assert task_run.state
            assert task_run.state.state_details

            assert task_run.state.state_details.flow_run_id is None
            assert task_run.state.state_details.task_run_id == task_run.id

            return proof_that_i_ran

        assert run_task_sync(foo) == proof_that_i_ran

    def test_state_details_have_denormalized_flow_run_id_sync(self):
        proof_that_i_ran = uuid4()

        @flow
        def the_flow():
            return foo()

        @task
        def foo():
            task_run = TaskRunContext.get().task_run

            assert task_run
            assert task_run.state
            assert task_run.state.state_details

            assert task_run.state.state_details.flow_run_id == task_run.flow_run_id
            assert task_run.state.state_details.task_run_id == task_run.id

            return proof_that_i_ran

        assert the_flow() == proof_that_i_ran


class TestTransactionHooks:
    async def test_task_transitions_to_rolled_back_on_transaction_rollback(
        self,
        events_pipeline,
        prefect_client,
    ):
        task_run_state = None

        @task
        def foo():
            pass

        @foo.on_rollback
        def rollback(txn):
            pass

        @flow
        def txn_flow():
            with transaction():
                nonlocal task_run_state
                task_run_state = foo(return_state=True)
                raise ValueError("txn failed")

        txn_flow(return_state=True)

        task_run_id = task_run_state.state_details.task_run_id

        await events_pipeline.process_events()
        task_run_states = await prefect_client.read_task_run_states(task_run_id)

        state_names = [state.name for state in task_run_states]
        assert state_names == [
            "Pending",
            "Running",
            "Completed",
            "RolledBack",
        ]

    async def test_task_transitions_to_rolled_back_on_transaction_rollback_async(
        self,
        events_pipeline,
        prefect_client,
    ):
        task_run_state = None

        @task
        async def foo():
            pass

        @foo.on_rollback
        def rollback(txn):
            pass

        @flow
        async def txn_flow():
            with transaction():
                nonlocal task_run_state
                task_run_state = await foo(return_state=True)
                raise ValueError("txn failed")

        await txn_flow(return_state=True)

        task_run_id = task_run_state.state_details.task_run_id

        await events_pipeline.process_events()
        task_run_states = await prefect_client.read_task_run_states(task_run_id)

        state_names = [state.name for state in task_run_states]
        assert state_names == [
            "Pending",
            "Running",
            "Completed",
            "RolledBack",
        ]

    def test_rollback_errors_are_logged(self, caplog):
        @task
        def foo():
            pass

        @foo.on_rollback
        def rollback(txn):
            raise RuntimeError("whoops!")

        @flow
        def txn_flow():
            with transaction():
                foo()
                raise ValueError("txn failed")

        txn_flow(return_state=True)
        assert "An error was encountered while running rollback hook" in caplog.text
        assert "RuntimeError" in caplog.text
        assert "whoops!" in caplog.text

    def test_rollback_hook_execution_and_completion_are_logged(self, caplog):
        @task
        def foo():
            pass

        @foo.on_rollback
        def rollback(txn):
            pass

        @flow
        def txn_flow():
            with transaction():
                foo()
                raise ValueError("txn failed")

        txn_flow(return_state=True)
        assert "Running rollback hook 'rollback'" in caplog.text
        assert "Rollback hook 'rollback' finished running successfully" in caplog.text

    def test_commit_errors_are_logged(self, caplog):
        @task
        def foo():
            pass

        @foo.on_commit
        def rollback(txn):
            raise RuntimeError("whoops!")

        @flow
        def txn_flow():
            with transaction():
                foo()

        txn_flow(return_state=True)
        assert "An error was encountered while running commit hook" in caplog.text
        assert "RuntimeError" in caplog.text
        assert "whoops!" in caplog.text

    def test_commit_hook_execution_and_completion_are_logged(self, caplog):
        @task
        def foo():
            pass

        @foo.on_commit
        def commit(txn):
            pass

        @flow
        def txn_flow():
            with transaction():
                foo()

        txn_flow(return_state=True)
        assert "Running commit hook 'commit'" in caplog.text
        assert "Commit hook 'commit' finished running successfully" in caplog.text
