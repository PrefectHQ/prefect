import pytest

from prefect import flow
from prefect.core import Flow
from prefect.core.futures import PrefectFuture
from prefect.core.utilities import file_hash, sync


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
    def test_call(self, user_client):
        @flow
        def foo(x, y=2, z=3):
            return x + y + z

        future = foo(1, 2)
        assert isinstance(future, PrefectFuture)
        assert future.result == 6
        assert future.run_id is not None

        flow_run = sync(user_client.read_flow_run, future.run_id)
        assert str(flow_run.id) == future.run_id
        assert flow_run.parameters == {"x": 1, "y": 2}
