import asyncio
import logging
import time
import warnings
from textwrap import dedent
from unittest.mock import MagicMock
from uuid import UUID

import anyio
import pytest

from prefect import Flow, flow, task
from prefect._internal.compatibility.experimental import ExperimentalFeature
from prefect.client.orchestration import PrefectClient, SyncPrefectClient
from prefect.client.schemas.filters import FlowFilter, FlowRunFilter
from prefect.client.schemas.objects import StateType
from prefect.client.schemas.sorting import FlowRunSort
from prefect.context import FlowRunContext, TaskRunContext, get_run_context
from prefect.exceptions import CrashedRun, FailedRun, ParameterTypeError, Pause
from prefect.flow_engine import (
    FlowRunEngine,
    load_flow_and_flow_run,
    run_flow,
    run_flow_async,
    run_flow_sync,
)
from prefect.flow_runs import pause_flow_run, resume_flow_run, suspend_flow_run
from prefect.input.actions import read_flow_run_input
from prefect.input.run_input import RunInput
from prefect.logging import get_run_logger
from prefect.server.schemas.core import FlowRun as ServerFlowRun
from prefect.utilities.callables import get_call_parameters


@flow
async def foo():
    return 42


class TestFlowRunEngine:
    async def test_basic_init(self):
        engine = FlowRunEngine(flow=foo)
        assert isinstance(engine.flow, Flow)
        assert engine.flow.name == "foo"
        assert engine.parameters == {}

    async def test_empty_init(self):
        with pytest.raises(
            TypeError, match="missing 1 required positional argument: 'flow'"
        ):
            FlowRunEngine()

    async def test_client_attr_raises_informative_error(self):
        engine = FlowRunEngine(flow=foo)
        with pytest.raises(RuntimeError, match="not started"):
            engine.client

    async def test_client_attr_returns_client_after_starting(self):
        engine = FlowRunEngine(flow=foo)
        with engine.start():
            client = engine.client
            assert isinstance(client, SyncPrefectClient)

        with pytest.raises(RuntimeError, match="not started"):
            engine.client

    async def test_load_flow_from_entrypoint(self, monkeypatch, tmp_path, flow_run):
        flow_code = """
        from prefect import flow

        @flow
        def dog():
            return "woof!"
        """
        fpath = tmp_path / "f.py"
        fpath.write_text(dedent(flow_code))

        monkeypatch.setenv("PREFECT__FLOW_ENTRYPOINT", f"{fpath}:dog")
        loaded_flow_run, flow = load_flow_and_flow_run(flow_run.id)
        assert loaded_flow_run.id == flow_run.id
        assert flow.fn() == "woof!"


class TestFlowRunsAsync:
    async def test_basic(self):
        @flow
        async def foo():
            return 42

        result = await run_flow(foo)

        assert result == 42

    async def test_with_params(self):
        @flow
        async def bar(x: int, y: str = None):
            return x, y

        parameters = get_call_parameters(bar.fn, (42,), dict(y="nate"))
        result = await run_flow(bar, parameters=parameters)

        assert result == (42, "nate")

    async def test_with_param_validation(self):
        @flow
        async def bar(x: int):
            return x

        parameters = get_call_parameters(bar.fn, tuple(), dict(x="42"))
        result = await run_flow(bar, parameters=parameters)

        assert result == 42

    async def test_with_param_validation_failure(self):
        @flow
        async def bar(x: int):
            return x

        parameters = get_call_parameters(bar.fn, tuple(), dict(x="FAIL!"))
        state = await run_flow(bar, parameters=parameters, return_type="state")

        assert state.is_failed()
        with pytest.raises(
            ParameterTypeError, match="Flow run received invalid parameters"
        ):
            await state.result()

    async def test_flow_run_name(self, sync_prefect_client):
        @flow(flow_run_name="name is {x}")
        async def foo(x):
            return FlowRunContext.get().flow_run.id

        result = await run_flow(foo, parameters=dict(x="blue"))
        run = sync_prefect_client.read_flow_run(result)

        assert run.name == "name is blue"

    async def test_with_args(self):
        @flow
        async def f(*args):
            return args

        args = (42, "nate")
        result = await f(*args)
        assert result == args

    async def test_with_kwargs(self):
        @flow
        async def f(**kwargs):
            return kwargs

        kwargs = dict(x=42, y="nate")
        result = await f(**kwargs)
        assert result == kwargs

    async def test_with_args_kwargs(self):
        @flow
        async def f(*args, x, **kwargs):
            return args, x, kwargs

        result = await f(1, 2, x=5, y=6, z=7)
        assert result == ((1, 2), 5, dict(y=6, z=7))

    async def test_get_run_logger(self, caplog):
        caplog.set_level(logging.CRITICAL)

        @flow(flow_run_name="test-run")
        async def my_log_flow():
            get_run_logger().critical("hey yall")

        result = await run_flow(my_log_flow)

        assert result is None
        record = caplog.records[0]

        assert record.flow_name == "my-log-flow"
        assert record.flow_run_name == "test-run"
        assert UUID(record.flow_run_id)
        assert record.message == "hey yall"
        assert record.levelname == "CRITICAL"

    async def test_flow_ends_in_completed(self, sync_prefect_client):
        @flow
        async def foo():
            return FlowRunContext.get().flow_run.id

        result = await run_flow(foo)
        run = sync_prefect_client.read_flow_run(result)

        assert run.state_type == StateType.COMPLETED

    async def test_flow_ends_in_failed(self, sync_prefect_client):
        ID = None

        @flow
        async def foo():
            nonlocal ID
            ID = FlowRunContext.get().flow_run.id
            raise ValueError("xyz")

        with pytest.raises(ValueError, match="xyz"):
            await run_flow(foo)

        run = sync_prefect_client.read_flow_run(ID)

        assert run.state_type == StateType.FAILED

    def test_subflow_inside_task_tracks_all_parents(
        self, sync_prefect_client: SyncPrefectClient
    ):
        tracker = {}

        @flow
        def flow_3():
            tracker["flow_3"] = FlowRunContext.get().flow_run.id

        @task
        def task_2():
            tracker["task_2"] = TaskRunContext.get().task_run.id
            flow_3()

        @flow
        def flow_1():
            task_2()

        flow_1()

        # retrieve the flow 3 subflow run
        l3 = sync_prefect_client.read_flow_run(tracker["flow_3"])
        # retrieve the dummy task for the flow 3 subflow run
        l3_dummy = sync_prefect_client.read_task_run(l3.parent_task_run_id)

        # assert the parent of the dummy task is task 2
        assert l3_dummy.task_inputs["__parents__"][0].id == tracker["task_2"]


class TestFlowRunsSync:
    async def test_basic(self):
        @flow
        def foo():
            return 42

        result = run_flow_sync(foo)

        assert result == 42

    async def test_with_params(self):
        @flow
        def bar(x: int, y: str = None):
            return x, y

        parameters = get_call_parameters(bar.fn, (42,), dict(y="nate"))
        result = run_flow_sync(bar, parameters=parameters)

        assert result == (42, "nate")

    async def test_with_param_validation(self):
        @flow
        def bar(x: int):
            return x

        parameters = get_call_parameters(bar.fn, tuple(), dict(x="42"))
        result = run_flow_sync(bar, parameters=parameters)

        assert result == 42

    async def test_with_param_validation_failure(self):
        @flow
        def bar(x: int):
            return x

        parameters = get_call_parameters(bar.fn, tuple(), dict(x="FAIL!"))
        state = run_flow_sync(bar, parameters=parameters, return_type="state")

        assert state.is_failed()
        with pytest.raises(
            ParameterTypeError, match="Flow run received invalid parameters"
        ):
            await state.result()

    async def test_flow_run_name(self, sync_prefect_client):
        @flow(flow_run_name="name is {x}")
        def foo(x):
            return FlowRunContext.get().flow_run.id

        result = run_flow_sync(foo, parameters=dict(x="blue"))
        run = sync_prefect_client.read_flow_run(result)

        assert run.name == "name is blue"

    def test_with_args(self):
        @flow
        def f(*args):
            return args

        args = (42, "nate")
        result = f(*args)
        assert result == args

    def test_with_kwargs(self):
        @flow
        def f(**kwargs):
            return kwargs

        kwargs = dict(x=42, y="nate")
        result = f(**kwargs)
        assert result == kwargs

    def test_with_args_kwargs(self):
        @flow
        def f(*args, x, **kwargs):
            return args, x, kwargs

        result = f(1, 2, x=5, y=6, z=7)
        assert result == ((1, 2), 5, dict(y=6, z=7))

    async def test_get_run_logger(self, caplog):
        caplog.set_level(logging.CRITICAL)

        @flow(flow_run_name="test-run")
        def my_log_flow():
            get_run_logger().critical("hey yall")

        result = run_flow_sync(my_log_flow)

        assert result is None
        record = caplog.records[0]

        assert record.flow_name == "my-log-flow"
        assert record.flow_run_name == "test-run"
        assert UUID(record.flow_run_id)
        assert record.message == "hey yall"
        assert record.levelname == "CRITICAL"

    async def test_flow_ends_in_completed(self, sync_prefect_client):
        @flow
        def foo():
            return FlowRunContext.get().flow_run.id

        result = run_flow_sync(foo)
        run = sync_prefect_client.read_flow_run(result)

        assert run.state_type == StateType.COMPLETED

    async def test_flow_ends_in_failed(self, sync_prefect_client):
        ID = None

        @flow
        def foo():
            nonlocal ID
            ID = FlowRunContext.get().flow_run.id
            raise ValueError("xyz")

        with pytest.raises(ValueError, match="xyz"):
            run_flow_sync(foo)

        run = sync_prefect_client.read_flow_run(ID)

        assert run.state_type == StateType.FAILED


class TestFlowRetries:
    async def test_flow_retry_with_error_in_flow(self):
        run_count = 0

        @flow(retries=1)
        async def foo():
            nonlocal run_count
            run_count += 1
            if run_count == 1:
                raise ValueError()
            return "hello"

        assert await foo() == "hello"
        assert run_count == 2

    async def test_flow_retry_with_error_in_flow_sync(self):
        run_count = 0

        @flow(retries=1)
        def foo():
            nonlocal run_count
            run_count += 1
            if run_count == 1:
                raise ValueError()
            return "hello"

        assert foo() == "hello"
        assert run_count == 2

    async def test_flow_retry_with_error_in_flow_and_successful_task(self):
        task_run_count = 0
        flow_run_count = 0

        @task
        async def my_task():
            nonlocal task_run_count
            task_run_count += 1
            return "hello"

        @flow(retries=1)
        async def foo():
            nonlocal flow_run_count
            flow_run_count += 1

            state = await my_task(return_state=True)

            if flow_run_count == 1:
                raise ValueError()

            return await state.result()

        assert await foo() == "hello"
        assert flow_run_count == 2
        assert task_run_count == 1

    def test_flow_retry_with_no_error_in_flow_and_one_failed_task(self):
        task_run_count = 0
        flow_run_count = 0

        @task
        def my_task():
            nonlocal task_run_count
            task_run_count += 1

            # Fail on the first flow run but not the retry
            if flow_run_count == 1:
                raise ValueError()

            return "hello"

        @flow(retries=1)
        def foo():
            nonlocal flow_run_count
            flow_run_count += 1
            return my_task()

        assert foo() == "hello"
        assert flow_run_count == 2
        assert task_run_count == 2, "Task should be reset and run again"

    def test_flow_retry_with_error_in_flow_and_one_failed_task(self):
        task_run_count = 0
        flow_run_count = 0

        @task
        def my_task():
            nonlocal task_run_count
            task_run_count += 1

            # Fail on the first flow run but not the retry
            if flow_run_count == 1:
                raise ValueError()

            return "hello"

        @flow(retries=1)
        def my_flow():
            nonlocal flow_run_count
            flow_run_count += 1

            fut = my_task()

            # It is important that the flow run fails after the task run is created
            if flow_run_count == 1:
                raise ValueError()

            return fut

        assert my_flow() == "hello"
        assert flow_run_count == 2
        assert task_run_count == 2, "Task should be reset and run again"

    @pytest.mark.xfail
    async def test_flow_retry_with_branched_tasks(self, sync_prefect_client):
        flow_run_count = 0

        @task
        def identity(value):
            return value

        @flow(retries=1)
        def my_flow():
            nonlocal flow_run_count
            flow_run_count += 1

            # Raise on the first run but use 'foo'
            if flow_run_count == 1:
                identity("foo")
                raise ValueError()
            else:
                # On the second run, switch to 'bar'
                result = identity("bar")

            return result

        my_flow()

        assert flow_run_count == 2

        # The state is pulled from the API and needs to be decoded
        document = await (await my_flow().result()).result()
        result = sync_prefect_client.retrieve_data(document)

        assert result == "bar"
        # AssertionError: assert 'foo' == 'bar'
        # Wait, what? Because tasks are identified by dynamic key which is a simple
        # increment each time the task is called, if there branching is different
        # after a flow run retry, the stale value will be pulled from the cache.

    async def test_flow_retry_with_no_error_in_flow_and_one_failed_child_flow(
        self, sync_prefect_client: SyncPrefectClient
    ):
        child_run_count = 0
        flow_run_count = 0

        @flow
        async def child_flow():
            nonlocal child_run_count
            child_run_count += 1

            # Fail on the first flow run but not the retry
            if flow_run_count == 1:
                raise ValueError()

            return "hello"

        @flow(retries=1)
        async def parent_flow():
            nonlocal flow_run_count
            flow_run_count += 1
            return await child_flow()

        state = await parent_flow(return_state=True)
        assert await state.result() == "hello"
        assert flow_run_count == 2
        assert child_run_count == 2, "Child flow should be reset and run again"

        # Ensure that the tracking task run for the subflow is reset and tracked
        task_runs = sync_prefect_client.read_task_runs(
            flow_run_filter=FlowRunFilter(
                id={"any_": [state.state_details.flow_run_id]}
            )
        )
        state_types = {task_run.state_type for task_run in task_runs}
        assert state_types == {StateType.COMPLETED}

        # There should only be the child flow run's task
        assert len(task_runs) == 1

    async def test_flow_retry_with_error_in_flow_and_one_successful_child_flow(self):
        child_run_count = 0
        flow_run_count = 0

        @flow
        async def child_flow():
            nonlocal child_run_count
            child_run_count += 1
            return "hello"

        @flow(retries=1)
        async def parent_flow():
            nonlocal flow_run_count
            flow_run_count += 1
            child_result = await child_flow()

            # Fail on the first flow run but not the retry
            if flow_run_count == 1:
                raise ValueError()

            return child_result

        assert await parent_flow() == "hello"
        assert flow_run_count == 2
        assert child_run_count == 1, "Child flow should not run again"

    async def test_flow_retry_with_error_in_flow_and_one_failed_child_flow(
        self, sync_prefect_client: SyncPrefectClient
    ):
        child_flow_run_count = 0
        flow_run_count = 0

        @flow
        def child_flow():
            nonlocal child_flow_run_count
            child_flow_run_count += 1

            # Fail on the first flow run but not the retry
            if flow_run_count == 1:
                raise ValueError()

            return "hello"

        @flow(retries=1)
        def parent_flow():
            nonlocal flow_run_count
            flow_run_count += 1

            state = child_flow(return_state=True)

            # It is important that the flow run fails after the child flow run is created
            if flow_run_count == 1:
                raise ValueError()

            return state

        parent_state = parent_flow(return_state=True)
        child_state = await parent_state.result()
        assert await child_state.result() == "hello"
        assert flow_run_count == 2
        assert child_flow_run_count == 2, "Child flow should run again"

        child_flow_run = sync_prefect_client.read_flow_run(
            child_state.state_details.flow_run_id
        )
        child_flow_runs = sync_prefect_client.read_flow_runs(
            flow_filter=FlowFilter(id={"any_": [child_flow_run.flow_id]}),
            sort=FlowRunSort.EXPECTED_START_TIME_ASC,
        )

        assert len(child_flow_runs) == 2

        # The original flow run has its failed state preserved
        assert child_flow_runs[0].state.is_failed()

        # The final flow run is the one returned by the parent flow
        assert child_flow_runs[-1] == child_flow_run

    async def test_flow_retry_with_failed_child_flow_with_failed_task(self):
        child_task_run_count = 0
        child_flow_run_count = 0
        flow_run_count = 0

        @task
        async def child_task():
            nonlocal child_task_run_count
            child_task_run_count += 1

            # Fail on the first task run but not the retry
            if child_task_run_count == 1:
                raise ValueError()

            return "hello"

        @flow
        async def child_flow():
            nonlocal child_flow_run_count
            child_flow_run_count += 1
            return await child_task()

        @flow(retries=1)
        async def parent_flow():
            nonlocal flow_run_count
            flow_run_count += 1

            state = await child_flow()

            return state

        assert await parent_flow() == "hello"
        assert flow_run_count == 2
        assert child_flow_run_count == 2, "Child flow should run again"
        assert child_task_run_count == 2, "Child tasks should run again with child flow"

    def test_flow_retry_with_error_in_flow_and_one_failed_task_with_retries(self):
        task_run_retry_count = 0
        task_run_count = 0
        flow_run_count = 0

        @task(retries=1)
        def my_task():
            nonlocal task_run_count, task_run_retry_count
            task_run_count += 1
            task_run_retry_count += 1

            # Always fail on the first flow run
            if flow_run_count == 1:
                raise ValueError("Fail on first flow run")

            # Only fail the first time this task is called within a given flow run
            # This ensures that we will always retry this task so we can ensure
            # retry logic is preserved
            if task_run_retry_count == 1:
                raise ValueError("Fail on first task run")

            return "hello"

        @flow(retries=1)
        def foo():
            nonlocal flow_run_count, task_run_retry_count
            task_run_retry_count = 0
            flow_run_count += 1

            fut = my_task()

            # It is important that the flow run fails after the task run is created
            if flow_run_count == 1:
                raise ValueError()

            return fut

        assert foo() == "hello"
        assert flow_run_count == 2
        assert task_run_count == 4, "Task should use all of its retries every time"

    async def test_flow_retry_with_error_in_flow_and_one_failed_task_with_retries_cannot_exceed_retries(
        self,
    ):
        task_run_count = 0
        flow_run_count = 0

        @task(retries=2)
        async def my_task():
            nonlocal task_run_count
            task_run_count += 1
            raise ValueError("This task always fails")

        @flow(retries=1)
        async def my_flow():
            nonlocal flow_run_count
            flow_run_count += 1

            fut = await my_task()

            # It is important that the flow run fails after the task run is created
            if flow_run_count == 1:
                raise ValueError()

            return fut

        with pytest.raises(ValueError, match="This task always fails"):
            fut = await my_flow()
            flow_result = await fut.result()
            await flow_result.result()

        assert flow_run_count == 2
        assert task_run_count == 6, "Task should use all of its retries every time"

    async def test_flow_with_failed_child_flow_with_retries(self):
        child_flow_run_count = 0
        flow_run_count = 0

        @flow(retries=1)
        def child_flow():
            nonlocal child_flow_run_count
            child_flow_run_count += 1

            # Fail on first try.
            if child_flow_run_count == 1:
                raise ValueError()

            return "hello"

        @flow
        def parent_flow():
            nonlocal flow_run_count
            flow_run_count += 1

            state = child_flow()

            return state

        assert parent_flow() == "hello"
        assert flow_run_count == 1, "Parent flow should only run once"
        assert child_flow_run_count == 2, "Child flow should run again"

    async def test_parent_flow_retries_failed_child_flow_with_retries(self):
        child_flow_retry_count = 0
        child_flow_run_count = 0
        flow_run_count = 0

        @flow(retries=1)
        def child_flow():
            nonlocal child_flow_run_count, child_flow_retry_count
            child_flow_run_count += 1
            child_flow_retry_count += 1

            # Fail during first parent flow run, but not on parent retry.
            if flow_run_count == 1:
                raise ValueError()

            # Fail on first try after parent retry.
            if child_flow_retry_count == 1:
                raise ValueError()

            return "hello"

        @flow(retries=1)
        def parent_flow():
            nonlocal flow_run_count, child_flow_retry_count
            child_flow_retry_count = 0
            flow_run_count += 1

            state = child_flow()

            return state

        assert parent_flow() == "hello"
        assert flow_run_count == 2, "Parent flow should exhaust retries"
        assert (
            child_flow_run_count == 4
        ), "Child flow should run 2 times for each parent run"


class TestFlowCrashDetection:
    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_flow_function_crashes_flow(
        self, prefect_client, interrupt_type
    ):
        @flow
        async def my_flow():
            raise interrupt_type()

        with pytest.raises(interrupt_type):
            await my_flow()

        flow_runs = await prefect_client.read_flow_runs()
        assert len(flow_runs) == 1
        flow_run = flow_runs[0]
        assert flow_run.state.is_crashed()
        assert flow_run.state.type == StateType.CRASHED
        assert "Execution was aborted" in flow_run.state.message
        with pytest.raises(CrashedRun, match="Execution was aborted"):
            await flow_run.state.result()

    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_flow_function_crashes_flow_sync(
        self, prefect_client, interrupt_type
    ):
        @flow
        def my_flow():
            raise interrupt_type()

        with pytest.raises(interrupt_type):
            my_flow()

        flow_runs = await prefect_client.read_flow_runs()
        assert len(flow_runs) == 1
        flow_run = flow_runs[0]
        assert flow_run.state.is_crashed()
        assert flow_run.state.type == StateType.CRASHED
        assert "Execution was aborted" in flow_run.state.message
        with pytest.raises(CrashedRun, match="Execution was aborted"):
            await flow_run.state.result()

    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_flow_orchestration_crashes_flow(
        self, prefect_client, interrupt_type, monkeypatch
    ):
        monkeypatch.setattr(
            FlowRunEngine, "begin_run", MagicMock(side_effect=interrupt_type)
        )

        @flow
        async def my_flow():
            pass

        with pytest.raises(interrupt_type):
            await my_flow()

        flow_runs = await prefect_client.read_flow_runs()
        assert len(flow_runs) == 1
        flow_run = flow_runs[0]
        assert flow_run.state.is_crashed()
        assert flow_run.state.type == StateType.CRASHED
        assert "Execution was aborted" in flow_run.state.message
        with pytest.raises(CrashedRun, match="Execution was aborted"):
            await flow_run.state.result()


class TestPauseFlowRun:
    @pytest.fixture(autouse=True)
    def ignore_experimental_warnings(self):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=ExperimentalFeature)
            yield

    async def test_tasks_cannot_be_paused(self):
        @task
        async def the_little_task_that_pauses():
            await pause_flow_run()
            return True

        @flow
        async def the_mountain():
            return await the_little_task_that_pauses()

        with pytest.raises(RuntimeError, match="Cannot pause task runs.*"):
            await the_mountain()

    async def test_paused_flows_fail_if_not_resumed(self):
        @task
        async def doesnt_pause():
            return 42

        @flow
        async def pausing_flow():
            await doesnt_pause()
            await pause_flow_run(timeout=0.1)
            await doesnt_pause()

        with pytest.raises(FailedRun):
            await pausing_flow()

    def test_paused_flows_block_execution_in_sync_flows(self, prefect_client):
        completed = False

        @flow
        def pausing_flow():
            nonlocal completed
            pause_flow_run(timeout=0.1)
            completed = True

        pausing_flow(return_state=True)
        assert not completed

    async def test_paused_flows_block_execution_in_async_flows(self, prefect_client):
        @task
        async def foo():
            return 42

        @flow
        async def pausing_flow():
            await foo()
            await foo()
            await pause_flow_run(timeout=0.1)
            await foo()

        flow_run_state = await pausing_flow(return_state=True)
        flow_run_id = flow_run_state.state_details.flow_run_id
        task_runs = await prefect_client.read_task_runs(
            flow_run_filter=FlowRunFilter(id={"any_": [flow_run_id]})
        )
        assert len(task_runs) == 2, "only two tasks should have completed"

    async def test_paused_flows_can_be_resumed(self, prefect_client):
        @task
        async def foo():
            return 42

        @flow
        async def pausing_flow():
            await foo()
            await foo()
            await pause_flow_run(timeout=10, poll_interval=2, key="do-not-repeat")
            await foo()
            await pause_flow_run(timeout=10, poll_interval=2, key="do-not-repeat")
            await foo()
            await foo()

        async def flow_resumer():
            await anyio.sleep(3)
            flow_runs = await prefect_client.read_flow_runs(limit=1)
            active_flow_run = flow_runs[0]
            await resume_flow_run(active_flow_run.id)

        flow_run_state, the_answer = await asyncio.gather(
            pausing_flow(return_state=True),
            flow_resumer(),
        )
        flow_run_id = flow_run_state.state_details.flow_run_id
        task_runs = await prefect_client.read_task_runs(
            flow_run_filter=FlowRunFilter(id={"any_": [flow_run_id]})
        )
        assert len(task_runs) == 5, "all tasks should finish running"

    async def test_paused_flows_can_receive_input(self, prefect_client):
        flow_run_id = None

        class FlowInput(RunInput):
            x: int

        @flow
        async def pausing_flow():
            nonlocal flow_run_id
            context = FlowRunContext.get()
            flow_run_id = context.flow_run.id

            flow_input = await pause_flow_run(
                timeout=10, poll_interval=2, wait_for_input=FlowInput
            )
            return flow_input

        async def flow_resumer():
            # Wait on flow run to start
            while not flow_run_id:
                await anyio.sleep(0.1)

            # Wait on flow run to pause
            flow_run = await prefect_client.read_flow_run(flow_run_id)
            while not flow_run.state.is_paused():
                await asyncio.sleep(0.1)
                flow_run = await prefect_client.read_flow_run(flow_run_id)

            keyset = flow_run.state.state_details.run_input_keyset
            assert keyset

            # Wait for the flow run input schema to be saved
            while not (await read_flow_run_input(keyset["schema"], flow_run_id)):
                await asyncio.sleep(0.1)

            await resume_flow_run(flow_run_id, run_input={"x": 42})

        flow_run_state, the_answer = await asyncio.gather(
            pausing_flow(return_state=True),
            flow_resumer(),
        )
        flow_input = await flow_run_state.result()
        assert isinstance(flow_input, FlowInput)
        assert flow_input.x == 42

        # Ensure that the flow run did create the corresponding schema input
        schema = await read_flow_run_input(
            key="paused-1-schema", flow_run_id=flow_run_id
        )
        assert schema is not None

    async def test_paused_flows_can_receive_automatic_input(
        self, prefect_client: PrefectClient
    ):
        flow_run_id = None

        @flow
        async def pausing_flow():
            nonlocal flow_run_id
            context = FlowRunContext.get()
            flow_run_id = context.flow_run.id

            age = await pause_flow_run(int, timeout=10, poll_interval=2)
            return age

        async def flow_resumer():
            # Wait on flow run to start
            while not flow_run_id:
                await anyio.sleep(0.1)

            # Wait on flow run to pause
            flow_run = await prefect_client.read_flow_run(flow_run_id)
            while not flow_run.state.is_paused():
                await asyncio.sleep(0.1)
                flow_run = await prefect_client.read_flow_run(flow_run_id)

            keyset = flow_run.state.state_details.run_input_keyset
            assert keyset

            # Wait for the flow run input schema to be saved
            while not (await read_flow_run_input(keyset["schema"], flow_run_id)):
                await asyncio.sleep(0.1)

            await resume_flow_run(flow_run_id, run_input={"value": 42})

        flow_run_state, the_answer = await asyncio.gather(
            pausing_flow(return_state=True),
            flow_resumer(),
        )
        age = await flow_run_state.result()
        assert isinstance(age, int)
        assert age == 42

        # Ensure that the flow run did create the corresponding schema input
        schema = await read_flow_run_input(
            key="paused-1-schema", flow_run_id=flow_run_id
        )
        assert schema is not None

    async def test_paused_task_polling(self, monkeypatch, prefect_client):
        sleeper = MagicMock(side_effect=[None, None, None, None, None])
        monkeypatch.setattr("prefect.task_engine.time.sleep", sleeper)

        @task
        async def doesnt_pause():
            return 42

        @task
        async def doesnt_run():
            assert False, "This task should not run"

        @flow
        async def pausing_flow():
            await doesnt_pause()
            # don't wait on this to avoid blocking execution
            asyncio.create_task(pause_flow_run(timeout=20, poll_interval=100))

            # wait for the flow run to enter the paused state
            flow_run_id = FlowRunContext.get().flow_run.id
            flow_run = await prefect_client.read_flow_run(flow_run_id)
            while not flow_run.state.is_paused():
                await asyncio.sleep(0.1)
                flow_run = await prefect_client.read_flow_run(flow_run_id)

            # execution isn't blocked, so this task should enter the engine, but not begin
            # execution
            with pytest.raises(RuntimeError):
                # the sleeper mock will exhaust its side effects after 6 calls
                await doesnt_run()

        await pausing_flow()

        sleep_intervals = [c.args[0] for c in sleeper.call_args_list]
        assert len(sleep_intervals) == 6


class TestSuspendFlowRun:
    @pytest.fixture(autouse=True)
    def ignore_experimental_warnings(self):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=ExperimentalFeature)
            yield

    async def test_suspended_flow_runs_do_not_block_execution(
        self, prefect_client, deployment, session
    ):
        flow_run_id = None

        @flow()
        async def suspending_flow():
            nonlocal flow_run_id
            context = get_run_context()
            assert context.flow_run
            flow_run_id = context.flow_run.id

            from prefect.server.models.flow_runs import update_flow_run

            await update_flow_run(
                session,
                flow_run_id,
                ServerFlowRun.model_construct(deployment_id=deployment.id),
            )
            await session.commit()

            await suspend_flow_run()
            await asyncio.sleep(20)

        start = time.time()
        with pytest.raises(Pause):
            await suspending_flow()
        end = time.time()
        assert end - start < 20

    async def test_suspended_flow_run_has_correct_state(
        self, prefect_client, deployment, session
    ):
        flow_run_id = None

        @flow()
        async def suspending_flow():
            nonlocal flow_run_id
            context = get_run_context()
            assert context.flow_run
            flow_run_id = context.flow_run.id

            from prefect.server.models.flow_runs import update_flow_run

            await update_flow_run(
                session,
                flow_run_id,
                ServerFlowRun.model_construct(deployment_id=deployment.id),
            )
            await session.commit()

            await suspend_flow_run()

        with pytest.raises(Pause):
            await suspending_flow()

        flow_run = await prefect_client.read_flow_run(flow_run_id)
        state = flow_run.state
        assert state.is_paused()
        assert state.name == "Suspended"

    async def test_suspending_flow_run_without_deployment_fails(self):
        @flow()
        async def suspending_flow():
            await suspend_flow_run()

        with pytest.raises(
            RuntimeError, match="Cannot suspend flows without a deployment."
        ):
            await suspending_flow()

    async def test_suspending_sub_flow_run_fails(self):
        @flow()
        async def suspending_flow():
            await suspend_flow_run()

        @flow
        async def main_flow():
            await suspending_flow()

        with pytest.raises(RuntimeError, match="Cannot suspend subflows."):
            await main_flow()

    @pytest.mark.xfail(reason="Brittle caused by 5xx from API")
    async def test_suspend_flow_run_by_id(self, prefect_client, deployment, session):
        flow_run_id = None
        task_completions = 0

        @task
        async def increment_completions():
            nonlocal task_completions
            task_completions += 1
            await asyncio.sleep(1)

        @flow
        async def suspendable_flow():
            nonlocal flow_run_id
            context = get_run_context()
            assert context.flow_run

            from prefect.server.models.flow_runs import update_flow_run

            await update_flow_run(
                session,
                context.flow_run.id,
                ServerFlowRun.model_construct(deployment_id=deployment.id),
            )
            await session.commit()

            flow_run_id = context.flow_run.id

            for i in range(20):
                await increment_completions()

        async def suspending_func():
            nonlocal flow_run_id

            while flow_run_id is None:
                await asyncio.sleep(0.1)

            # Sleep for a bit to let some of `suspendable_flow`s tasks complete
            await asyncio.sleep(2)

            await suspend_flow_run(flow_run_id=flow_run_id)

        with pytest.raises(Pause):
            await asyncio.gather(suspendable_flow(), suspending_func())

        # When suspending a flow run by id, that flow run must use tasks for
        # the suspension to take place. This setup allows for `suspendable_flow`
        # to complete some tasks before `suspending_flow` suspends the flow run.
        # Here then we check to ensure that some tasks completed but not _all_
        # of the tasks.
        assert task_completions > 0 and task_completions < 20

        flow_run = await prefect_client.read_flow_run(flow_run_id)
        state = flow_run.state
        assert state.is_paused(), state
        assert state.name == "Suspended"

    async def test_suspend_can_receive_input(self, deployment, session, prefect_client):
        flow_run_id = None

        class FlowInput(RunInput):
            x: int

        @flow()
        async def suspending_flow():
            nonlocal flow_run_id
            context = get_run_context()
            assert context.flow_run

            if not context.flow_run.deployment_id:
                # Ensure that the flow run has a deployment id so it's
                # suspendable.
                from prefect.server.models.flow_runs import update_flow_run

                await update_flow_run(
                    session,
                    context.flow_run.id,
                    ServerFlowRun.model_construct(deployment_id=deployment.id),
                )
                await session.commit()

            flow_run_id = context.flow_run.id

            flow_input = await suspend_flow_run(wait_for_input=FlowInput)

            return flow_input

        with pytest.raises(Pause):
            await suspending_flow()

        assert flow_run_id

        flow_run = await prefect_client.read_flow_run(flow_run_id)
        keyset = flow_run.state.state_details.run_input_keyset

        schema = await read_flow_run_input(
            key=keyset["schema"], flow_run_id=flow_run_id
        )
        assert schema is not None

        await resume_flow_run(flow_run_id, run_input={"x": 42})

        flow_input = await run_flow_async(
            flow=suspending_flow,
            flow_run=flow_run,
            parameters={},
        )
        assert flow_input
        assert flow_input.x == 42

    async def test_suspend_can_receive_automatic_input(
        self, deployment, session, prefect_client
    ):
        flow_run_id = None

        @flow()
        async def suspending_flow():
            nonlocal flow_run_id
            context = get_run_context()
            assert context.flow_run

            if not context.flow_run.deployment_id:
                # Ensure that the flow run has a deployment id so it's
                # suspendable.
                from prefect.server.models.flow_runs import update_flow_run

                assert await update_flow_run(
                    session,
                    context.flow_run.id,
                    ServerFlowRun.model_construct(deployment_id=deployment.id),
                )
                await session.commit()

            flow_run_id = context.flow_run.id

            age = await suspend_flow_run(int)

            return age

        with pytest.raises(Pause):
            await suspending_flow()

        assert flow_run_id

        flow_run = await prefect_client.read_flow_run(flow_run_id)
        keyset = flow_run.state.state_details.run_input_keyset

        schema = await read_flow_run_input(
            key=keyset["schema"], flow_run_id=flow_run_id
        )
        assert schema is not None

        await resume_flow_run(flow_run_id, run_input={"value": 42})

        age = await run_flow_async(
            flow=suspending_flow,
            flow_run=flow_run,
            parameters={},
        )

        assert age == 42
