from typing import List

import pydantic
import pytest

from prefect import flow
from prefect.client import OrionClient
from prefect.flows import Flow
from prefect.futures import PrefectFuture
from prefect.utilities.files import file_hash


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
    def test_call_creates_flow_run_and_runs(self):
        @flow(version="test")
        def foo(x, y=2, z=3):
            return x + y + z

        future = foo(1, 2)
        assert isinstance(future, PrefectFuture)
        assert future.result() == 6
        assert future.run_id is not None

        flow_run = OrionClient().read_flow_run(future.run_id)
        assert flow_run.id == future.run_id
        assert flow_run.parameters == {"x": 1, "y": 2}
        assert flow_run.flow_version == foo.version

    def test_call_creates_ephemeral_instance(self):
        @flow(version="test")
        def foo(x, y=2, z=3):
            return x + y + z

        future = foo(1, 2)
        assert isinstance(future, PrefectFuture)
        assert future.result() == 6
        assert future.run_id is not None

        flow_run = OrionClient().read_flow_run(future.run_id)
        assert flow_run.id == future.run_id
        assert flow_run.parameters == {"x": 1, "y": 2}
        assert flow_run.flow_version == foo.version

    def test_call_coerces_parameter_types(self):
        class CustomType(pydantic.BaseModel):
            z: int

        @flow(version="test")
        def foo(x: int, y: List[int], zt: CustomType):
            return x + sum(y) + zt.z

        future = foo(x="1", y=["2", "3"], zt=CustomType(z=4).dict())
        assert future.result() == 10

    def test_call_raises_on_incompatible_parameter_types(self):
        @flow(version="test")
        def foo(x: int):
            pass

        # No error until the future is unpacked
        future = foo(x="foo")

        with pytest.raises(
            pydantic.error_wrappers.ValidationError,
            match="value is not a valid integer",
        ):
            future.result()

    @pytest.mark.parametrize("error", [ValueError("Hello"), None])
    def test_state_reflects_result_of_run(self, error):
        @flow(version="test")
        def foo():
            if error:
                raise error

        future = foo()

        raised = None
        try:
            future.result()
        except Exception as exc:
            raised = exc

        # Assert the exception was raised correctly
        assert raised is error

        # Assert the final state is correct
        states = OrionClient().read_flow_run_states(future.run_id)
        final_state = states[-1]
        assert final_state.is_failed() if error else final_state.is_completed()
