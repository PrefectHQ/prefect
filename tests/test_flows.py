from typing import List
import anyio
from packaging.version import parse as parse_version

import mypy.version
import pydantic
from pydantic.decorator import validate_arguments
import pytest
import time

from prefect import flow, get_result, task, tags
from prefect.client import OrionClient
from prefect.engine import raise_failed_state
from prefect.exceptions import FlowParameterError
from prefect.flows import Flow
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import State, StateType
from prefect.utilities.hashing import file_hash
from prefect.utilities.testing import exceptions_equal
from prefect.utilities.collections import quote


class TestFlow:
    def test_initializes(self):
        f = Flow(name="test", fn=lambda **kwargs: 42, version="A", description="B")
        assert f.name == "test"
        assert f.fn() == 42
        assert f.version == "A"
        assert f.description == "B"

    def test_initializes_with_default_version(self):
        f = Flow(name="test", fn=lambda **kwargs: 42)
        assert isinstance(f.version, str)

    def test_version_none_if_interactively_defined(self):
        "Defining functions interactively does not set __file__ global"

        def ipython_function():
            pass

        del ipython_function.__globals__["__file__"]

        f = Flow(name="test", fn=ipython_function)
        assert f.version is None

    def test_raises_on_bad_funcs(self):
        with pytest.raises(TypeError):
            Flow(name="test", fn={})

    def test_default_description_is_from_docstring(self):
        def my_fn():
            """
            Hello
            """
            pass

        f = Flow(
            name="test",
            fn=my_fn,
        )
        assert f.description == "Hello"

    def test_default_name_is_from_function(self):
        def my_fn():
            pass

        f = Flow(
            fn=my_fn,
        )
        assert f.name == "my-fn"

    def test_raises_clear_error_when_not_compatible_with_validator(self):
        def my_fn(v__args):
            pass

        with pytest.raises(
            ValueError,
            match="Flow function is not compatible with `validate_parameters`",
        ):
            Flow(fn=my_fn)


class TestDecorator:
    def test_flow_decorator_initializes(self):
        # TODO: We should cover initialization with an executor once introduced
        @flow(name="foo", version="B")
        def my_flow():
            return "bar"

        assert isinstance(my_flow, Flow)
        assert my_flow.name == "foo"
        assert my_flow.version == "B"
        assert my_flow.fn() == "bar"

    def test_flow_decorator_sets_default_version(self):
        my_flow = flow(file_hash)

        assert my_flow.version == file_hash(file_hash.__globals__["__file__"])


class TestFlowCall:
    async def test_call_creates_flow_run_and_runs(self):
        @flow(version="test")
        def foo(x, y=3, z=3):
            return x + y + z

        state = foo(1, 2)
        assert isinstance(state, State)
        assert await get_result(state) == 6
        assert state.state_details.flow_run_id is not None

        async with OrionClient() as client:
            flow_run = await client.read_flow_run(state.state_details.flow_run_id)
        assert flow_run.id == state.state_details.flow_run_id
        assert flow_run.parameters == {"x": 1, "y": 2, "z": 3}
        assert flow_run.flow_version == foo.version

    async def test_async_call_creates_flow_run_and_runs(self):
        @flow(version="test")
        async def foo(x, y=3, z=3):
            return x + y + z

        state = await foo(1, 2)
        assert isinstance(state, State)
        assert await get_result(state) == 6
        assert state.state_details.flow_run_id is not None

        async with OrionClient() as client:
            flow_run = await client.read_flow_run(state.state_details.flow_run_id)
        assert flow_run.id == state.state_details.flow_run_id
        assert flow_run.parameters == {"x": 1, "y": 2, "z": 3}
        assert flow_run.flow_version == foo.version

    def test_call_coerces_parameter_types(self):
        class CustomType(pydantic.BaseModel):
            z: int

        @flow(version="test")
        def foo(x: int, y: List[int], zt: CustomType):
            return x + sum(y) + zt.z

        state = foo(x="1", y=["2", "3"], zt=CustomType(z=4).dict())
        assert get_result(state) == 10

    def test_call_with_variadic_args(self):
        @flow
        def test_flow(*foo, bar):
            return foo, bar

        assert get_result(test_flow(1, 2, 3, bar=4)) == ((1, 2, 3), 4)

    def test_call_with_variadic_keyword_args(self):
        @flow
        def test_flow(foo, bar, **foobar):
            return foo, bar, foobar

        assert get_result(test_flow(1, 2, x=3, y=4, z=5)) == (1, 2, dict(x=3, y=4, z=5))

    def test_call_raises_on_incompatible_parameter_types(self):
        @flow(version="test")
        def foo(x: int):
            pass

        # No error until the state is unpacked
        state = foo(x="foo")

        assert state.is_failed()
        with pytest.raises(
            FlowParameterError,
            match="value is not a valid integer",
        ):
            raise_failed_state(state)

    def test_call_ignores_incompatible_parameter_types_if_asked(self):
        @flow(version="test", validate_parameters=False)
        def foo(x: int):
            return x

        assert get_result(foo(x="foo")) == "foo"

    @pytest.mark.parametrize("error", [ValueError("Hello"), None])
    def test_final_state_reflects_exceptions_during_run(self, error):
        @flow(version="test")
        def foo():
            if error:
                raise error

        state = foo()

        # Assert the final state is correct
        assert state.is_failed() if error else state.is_completed()
        result = get_result(state, raise_failures=False)
        assert exceptions_equal(result, error)

    def test_final_state_respects_returned_state(sel):
        @flow(version="test")
        def foo():
            return State(
                type=StateType.FAILED,
                message="Test returned state",
                data=DataDocument.encode("json", "hello!"),
            )

        state = foo()

        # Assert the final state is correct
        assert state.is_failed()
        assert get_result(state, raise_failures=False) == "hello!"
        assert state.message == "Test returned state"

    def test_flow_state_reflects_returned_task_run_state(self):
        @task
        def fail():
            raise ValueError("Test")

        @flow(version="test")
        def foo():
            return fail()

        flow_state = foo()

        assert flow_state.is_failed()

        # The task run state is returned as the data of the flow state
        task_run_state = get_result(flow_state, raise_failures=False)
        assert isinstance(task_run_state, State)
        assert task_run_state.is_failed()
        with pytest.raises(ValueError, match="Test"):
            raise_failed_state(task_run_state)

    def test_flow_state_reflects_returned_multiple_task_run_states(self):
        @task
        def fail1():
            raise ValueError("Test 1")

        @task
        def fail2():
            raise ValueError("Test 2")

        @task
        def succeed():
            return True

        @flow(version="test")
        def foo():
            return fail1(), fail2(), succeed()

        flow_state = foo()
        assert flow_state.is_failed()
        assert flow_state.message == "2/3 states failed."

        # The task run states are attached as a tuple
        first, second, third = get_result(flow_state, raise_failures=False)
        assert first.is_failed()
        assert second.is_failed()
        assert third.is_completed()

        with pytest.raises(ValueError, match="Test 1"):
            raise_failed_state(first)

        with pytest.raises(ValueError, match="Test 2"):
            raise_failed_state(second)

    async def test_subflow_call_with_no_tasks(self):
        @flow(version="foo")
        def child(x, y, z):
            return x + y + z

        @flow(version="bar")
        def parent(x, y=2, z=3):
            state = child(x, y, z)
            return state.state_details.flow_run_id, state

        parent_state = parent(1, 2)
        assert isinstance(parent_state, State)

        child_run_id, child_state = await get_result(parent_state)
        assert await get_result(child_state) == 6

        async with OrionClient() as client:
            child_flow_run = await client.read_flow_run(child_run_id)
        assert child_flow_run.id == child_run_id
        assert child_flow_run.parameters == {"x": 1, "y": 2, "z": 3}
        assert child_flow_run.parent_task_run_id is not None
        assert child_flow_run.flow_version == child.version

    def test_subflow_call_with_returned_task(self):
        @task
        def compute(x, y, z):
            return x + y + z

        @flow(version="foo")
        def child(x, y, z):
            return compute(x, y, z)

        @flow(version="bar")
        def parent(x, y=2, z=3):
            return child(x, y, z)

        parent_state = parent(1, 2)
        assert isinstance(parent_state, State)
        child_state = get_result(parent_state)
        assert get_result(child_state) == 6

    async def test_async_flow_with_async_subflow_and_async_task(self):
        @task
        async def compute_async(x, y, z):
            return x + y + z

        @flow(version="foo")
        async def child(x, y, z):
            return await compute_async(x, y, z)

        @flow(version="bar")
        async def parent(x, y=2, z=3):
            return await child(x, y, z)

        parent_state = await parent(1, 2)
        assert isinstance(parent_state, State)
        child_state = await get_result(parent_state)
        assert await get_result(child_state) == 6

    async def test_async_flow_with_async_subflow_and_sync_task(self):
        @task
        def compute(x, y, z):
            return x + y + z

        @flow(version="foo")
        async def child(x, y, z):
            return compute(x, y, z)

        @flow(version="bar")
        async def parent(x, y=2, z=3):
            return await child(x, y, z)

        parent_state = await parent(1, 2)
        assert isinstance(parent_state, State)
        child_state = await get_result(parent_state)
        assert await get_result(child_state) == 6

    async def test_async_flow_with_sync_subflow_and_sync_task(self):
        @task
        def compute(x, y, z):
            return x + y + z

        @flow(version="foo")
        def child(x, y, z):
            return compute(x, y, z)

        @flow(version="bar")
        async def parent(x, y=2, z=3):
            return child(x, y, z)

        parent_state = await parent(1, 2)
        assert isinstance(parent_state, State)
        child_state = await get_result(parent_state)
        assert await get_result(child_state) == 6


class TestFlowRunTags:
    async def test_flow_run_tags_added_at_call(self, orion_client):
        @flow
        def my_flow():
            pass

        with tags("a", "b"):
            state = my_flow()

        flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)
        assert set(flow_run.tags) == {"a", "b"}

    async def test_flow_run_tags_added_to_subflows(self, orion_client):
        @flow
        def my_flow():
            with tags("c", "d"):
                return quote(my_subflow())

        @flow
        def my_subflow():
            pass

        with tags("a", "b"):
            subflow_state = (await get_result(my_flow())).unquote()

        flow_run = await orion_client.read_flow_run(
            subflow_state.state_details.flow_run_id
        )
        assert set(flow_run.tags) == {"a", "b", "c", "d"}


class TestFlowTimeouts:
    def test_flows_fail_with_timeout(self):
        @flow(timeout_seconds=0.1)
        def my_flow():
            time.sleep(1)

        state = my_flow()
        assert state.is_failed()
        assert "timed out after 0.1 seconds" in state.message

    async def test_async_flows_fail_with_timeout(self):
        @flow(timeout_seconds=0.1)
        async def my_flow():
            await anyio.sleep(1)

        state = await my_flow()
        assert state.is_failed()
        assert "timed out after 0.1 seconds" in state.message

    def test_timeout_only_applies_if_exceeded(self):
        @flow(timeout_seconds=0.5)
        def my_flow():
            time.sleep(0.1)

        state = my_flow()
        assert state.is_completed()

    def test_timeout_does_not_wait_for_completion_for_sync_flows(self, tmp_path):
        """
        Sync flows are not cancellable, we can stop waiting for the worker thread but
        it will continue running the flow code in the background. This test ensures
        that the engine continues without waiting for the sleeping flow to finish.
        """
        canary_file = tmp_path / "canary"

        @flow(timeout_seconds=0.1)
        def my_flow():
            time.sleep(0.25)
            canary_file.touch()

        t0 = time.time()
        state = my_flow()
        t1 = time.time()

        assert state.is_failed()
        assert "timed out after 0.1 seconds" in state.message
        assert t1 - t0 < 0.2, f"The engine returns without waiting; took {t1-t0}s"

        # Unfortunately, the worker thread continues running and we cannot stop it from
        # doing so. The canary file _will_ be created.
        time.sleep(0.25)
        assert canary_file.exists()

    def test_timeout_stops_execution_at_next_task_for_sync_flows(self, tmp_path):
        """
        Sync flow runs tasks will fail after a timeout which will cause the flow to exit
        """
        canary_file = tmp_path / "canary"
        task_canary_file = tmp_path / "task_canary"

        @task
        def my_task():
            task_canary_file.touch()

        @flow(timeout_seconds=0.1)
        def my_flow():
            time.sleep(0.25)
            my_task()
            canary_file.touch()  # Should not run

        state = my_flow()

        assert state.is_failed()
        assert "timed out after 0.1 seconds" in state.message

        # Wait in case the flow is just sleeping
        time.sleep(0.5)
        assert not canary_file.exists()
        assert not task_canary_file.exists()

    async def test_timeout_stops_execution_after_await_for_async_flows(self, tmp_path):
        """
        Async flow runs can be cancelled after a timeout
        """
        canary_file = tmp_path / "canary"

        @flow(timeout_seconds=0.1)
        async def my_flow():
            await anyio.sleep(0.5)
            canary_file.touch()  # Should not run

        t0 = time.time()
        state = await my_flow()
        t1 = time.time()

        assert state.is_failed()
        assert "timed out after 0.1 seconds" in state.message
        assert t1 - t0 < 0.25, f"The engine returns without waiting; took {t1-t0}s"

        # Wait in case the flow is just sleeping
        await anyio.sleep(0.5)
        assert not canary_file.exists()

    async def test_timeout_stops_execution_in_async_subflows(self, tmp_path):
        """
        Async flow runs can be cancelled after a timeout
        """
        canary_file = tmp_path / "canary"

        @flow(timeout_seconds=0.1)
        async def my_subflow():
            await anyio.sleep(0.5)
            canary_file.touch()  # Should not run

        @flow
        async def my_flow():
            t0 = time.time()
            subflow_state = await my_subflow()
            t1 = time.time()
            return t1 - t0, subflow_state

        state = await my_flow()

        runtime, subflow_state = await get_result(state)
        assert "timed out after 0.1 seconds" in subflow_state.message
        assert runtime < 0.3, "The engine returns without waiting"

        # Wait in case the flow is just sleeping
        await anyio.sleep(0.5)
        assert not canary_file.exists()

    async def test_timeout_stops_execution_in_sync_subflows(self, tmp_path):
        """
        Async flow runs can be cancelled after a timeout
        """
        canary_file = tmp_path / "canary"

        @task
        def timeout_noticing_task():
            pass

        @flow(timeout_seconds=0.1)
        def my_subflow():
            time.sleep(0.5)
            timeout_noticing_task()
            canary_file.touch()  # Should not run

        @flow
        def my_flow():
            t0 = time.time()
            subflow_state = my_subflow()
            t1 = time.time()
            return t1 - t0, subflow_state

        state = my_flow()

        runtime, subflow_state = await get_result(state)
        assert "timed out after 0.1 seconds" in subflow_state.message
        assert runtime < 0.25, "The engine returns without waiting"

        # Wait in case the flow is just sleeping
        time.sleep(0.5)
        assert not canary_file.exists()
