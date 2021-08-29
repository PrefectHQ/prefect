from typing import List

import pydantic
import pytest

from prefect import flow, task
from prefect.client import OrionClient
from prefect.flows import Flow
from prefect.futures import PrefectFuture
from prefect.orion.schemas.states import State, StateType
from prefect.utilities.hashing import file_hash


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
        assert f.name == "my_fn"


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

        future = foo(1, 2)
        assert isinstance(future, PrefectFuture)
        assert future.result().is_completed()
        assert future.result().data == 6
        assert future.run_id is not None

        async with OrionClient() as client:
            flow_run = await client.read_flow_run(future.run_id)
        assert flow_run.id == future.run_id
        assert flow_run.parameters == {"x": 1, "y": 2, "z": 3}
        assert flow_run.flow_version == foo.version

    async def test_async_call_creates_flow_run_and_runs(self):
        @flow(version="test")
        async def foo(x, y=3, z=3):
            return x + y + z

        future = await foo(1, 2)
        assert isinstance(future, PrefectFuture)
        assert future.result().is_completed()
        assert future.result().data == 6
        assert future.run_id is not None

        async with OrionClient() as client:
            flow_run = await client.read_flow_run(future.run_id)
        assert flow_run.id == future.run_id
        assert flow_run.parameters == {"x": 1, "y": 2, "z": 3}
        assert flow_run.flow_version == foo.version

    def test_call_coerces_parameter_types(self):
        class CustomType(pydantic.BaseModel):
            z: int

        @flow(version="test")
        def foo(x: int, y: List[int], zt: CustomType):
            return x + sum(y) + zt.z

        future = foo(x="1", y=["2", "3"], zt=CustomType(z=4).dict())
        assert future.result().is_completed()
        assert future.result().data == 10

    def test_call_raises_on_incompatible_parameter_types(self):
        @flow(version="test")
        def foo(x: int):
            pass

        # No error until the future is unpacked
        future = foo(x="foo")

        assert future.result().is_failed()
        with pytest.raises(
            pydantic.error_wrappers.ValidationError,
            match="value is not a valid integer",
        ):
            raise future.result().data

    @pytest.mark.parametrize("error", [ValueError("Hello"), None])
    def test_final_state_reflects_exceptions_during_run(self, error):
        @flow(version="test")
        def foo():
            if error:
                raise error

        future = foo()
        state = future.result()

        # Assert the final state is correct
        assert state.is_failed() if error else state.is_completed()
        assert state.data is error

    def test_final_state_respects_returned_state(sel):
        @flow(version="test")
        def foo():
            return State(
                type=StateType.FAILED, message="Test returned state", data=True
            )

        future = foo()
        state = future.result()

        # Assert the final state is correct
        assert state.is_failed()
        assert state.data is True
        assert state.message == "Test returned state"

    def test_flow_state_reflects_returned_task_run_state(self):
        exc = ValueError("Test")

        @task
        def fail():
            raise exc

        @flow(version="test")
        def foo():
            return fail()

        flow_state = foo().result()

        assert flow_state.is_failed()
        assert flow_state.message == "1/1 states failed."

        # The task run state is returned as the data of the flow state
        task_run_state = flow_state.data
        assert isinstance(task_run_state, State)
        assert task_run_state.is_failed()
        assert task_run_state.data is exc

    def test_flow_state_reflects_returned_multiple_task_run_states(self):
        exc = ValueError("Test")

        @task
        def fail():
            raise exc

        @task
        def fail():
            raise exc

        @task
        def succeed():
            return True

        @flow(version="test")
        def foo():
            return fail(), fail(), succeed()

        flow_state = foo().result()
        assert flow_state.is_failed()
        assert flow_state.message == "2/3 states failed."

        # The task run states are attached as a tuple
        first, second, third = flow_state.data
        assert first.is_failed()
        assert second.is_failed()
        assert third.is_completed()

    async def test_subflow_call_with_no_tasks(self):
        @flow(version="foo")
        def child(x, y, z):
            return x + y + z

        @flow(version="bar")
        def parent(x, y=2, z=3):
            future = child(x, y, z)
            return future.run_id, future.result()

        parent_future = parent(1, 2)
        assert isinstance(parent_future, PrefectFuture)
        assert parent_future.result().is_completed()

        child_run_id, child_state = parent_future.result().data
        assert child_state.is_completed()
        assert child_state.data == 6

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

        parent_future = parent(1, 2)
        assert isinstance(parent_future, PrefectFuture)
        assert parent_future.result().is_completed()

        child_state = parent_future.result().data
        assert child_state.is_completed()
        child_task_state = child_state.data
        assert child_task_state.data == 6

    async def test_async_subflow_call(self):
        @task
        async def compute_async(x, y, z):
            return x + y + z

        @task
        def compute_sync(x, y, z):
            return x + y + z

        @flow(version="foo")
        async def child(x, y, z):
            return compute_sync(x, y, z), await compute_async(x, y, z)

        @flow(version="bar")
        async def parent(x, y=2, z=3):
            return await child(x, y, z)

        parent_future = await parent(1, 2)
        assert isinstance(parent_future, PrefectFuture)
        assert parent_future.result().is_completed()

        child_state = parent_future.result().data
        assert child_state.is_completed()
        sync_state, async_state = child_state.data
        assert sync_state.data == 6
        assert sync_state.data == async_state.data
