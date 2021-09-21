from typing import List
from packaging.version import parse as parse_version

import mypy.version
import pydantic
from pydantic.decorator import validate_arguments
import pytest

from prefect import flow, get_result, task
from prefect.client import OrionClient
from prefect.engine import raise_failed_state
from prefect.exceptions import FlowParameterError
from prefect.flows import Flow
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import State, StateType
from prefect.utilities.hashing import file_hash
from prefect.utilities.testing import exceptions_equal, check_for_type_errors


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

    @pytest.mark.skipif(
        parse_version(mypy.version.__version__) < parse_version("1.0"),
        reason="mypy does not support PEP-612 https://github.com/python/mypy/issues/8645",
    )
    def test_decorator_return_type_with_correct_params(self):
        check_for_type_errors(
            """
            from prefect import flow, State
            from typing import Dict, Callable

            @flow
            def foo(x: int, y: str) -> Dict[int, str]:
                return {x: y}

            check: Callable[[int, str], State] = foo
            """
        )

    def test_decorator_return_type_coerced_to_state_sync(self):
        check_for_type_errors(
            """
            from prefect import flow, State
            from typing import Dict, Callable

            @flow
            def foo(x: int, y: str) -> Dict[int, str]:
                return {x: y}
            
            # Note, mypy does not support `ParamSpec` yet so it is coerced into `...`
            check: Callable[..., State] = foo
            """
        )

    def test_decorator_return_type_coerced_to_state_async(self):
        check_for_type_errors(
            """
            from prefect import flow, State
            from typing import Dict, Callable, Awaitable

            @flow
            def foo(x: int, y: str) -> Dict[int, str]:
                return {x: y}
            
            check: Callable[..., Awaitable[State]] = foo
            """
        )


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
