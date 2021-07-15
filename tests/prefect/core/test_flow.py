import pytest

from prefect import flow
from prefect.core import Flow


class TestFlow:
    def test_initializes(self):
        f = Flow(name="test", fn=lambda **kwargs: 42, version="A")
        assert f.name == "test"
        assert f.fn() == 42
        assert f.version == "A"

    def test_raises_on_bad_funcs(self):
        with pytest.raises(TypeError):
            Flow(name="test", fn={})


class TestDecorator:
    def test_flow_decorator_initializes(self):
        @flow(name="foo", version="B")
        def my_flow():
            return "bar"

        assert isinstance(my_flow, Flow)
        assert my_flow.name == "foo"
        assert my_flow.version == "B"
        assert my_flow.fn() == "bar"
