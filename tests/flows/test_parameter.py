import pytest

from prefect.core.flow import Flow
from prefect.core.task import Parameter, Task
from prefect.tasks.core.function import FunctionTask


def test_create_parameter():
    x = Parameter("x")
    assert isinstance(x, Task)
    assert x.default is None
    assert x.required


def test_create_parameter_with_default():
    x = Parameter("x", default=2)
    assert x.default == 2
    assert x.run() == 2


def test_parameter_slug_is_its_name():
    x = Parameter("x")
    assert x.name == x.slug == "x"


def test_create_parameter_with_default_is_not_required():
    x = Parameter("x", default=2)
    assert not x.required


def test_create_required_parameter():
    x = Parameter("x", required=True)
    assert x.required


def test_raise_error_if_two_parameters_have_same_name():
    f = Flow(name="test")
    f.add_task(Parameter("x"))
    assert "x" in {p.name for p in f.parameters()}
    with pytest.raises(ValueError):
        f.add_task(Parameter("x"))


def test_flow_parameters():
    f = Flow(name="test")
    x = Parameter("x")
    y = Parameter("y", default=1)
    f.add_task(x)
    f.add_task(y)

    assert f.parameters() == {x, y}
