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


def test_parameter_name_cant_be_changed():
    x = Parameter("x")
    assert x.name == "x"
    with pytest.raises(AttributeError):
        x.name = "hi"


def test_parameter_slug_cant_be_changed():
    x = Parameter("x")
    assert x.slug == "x"
    with pytest.raises(AttributeError):
        x.slug = "hi"


def test_create_parameter_with_default_is_not_required():
    x = Parameter("x", default=2)
    assert not x.required


def test_create_required_parameter():
    x = Parameter("x", required=True)
    assert x.required


def test_raise_error_if_two_parameters_have_same_name():
    f = Flow()
    f.add_task(Parameter("x"))
    assert "x" in f.parameters()
    with pytest.raises(ValueError):
        f.add_task(Parameter("x"))


def test_flow_parameters():
    f = Flow()
    f.add_task(Parameter("x"))
    f.add_task(Parameter("y", default=1))

    params = dict(
        x=dict(required=True, default=None), y=dict(required=False, default=1)
    )
    required_params = params.copy()
    required_params.pop("y")
    assert f.parameters() == params
    assert f.parameters(only_required=True) == required_params
