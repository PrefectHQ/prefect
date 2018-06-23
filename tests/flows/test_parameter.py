from prefect.core.flow import Flow
from prefect.core.task import Parameter, Task
from prefect.tasks.core.function_task import FunctionTask


def test_create_parameter():
    x = Parameter("x")
    assert isinstance(x, Task)
    assert x.default is None
    assert x.required


def test_create_parameter_with_default():
    x = Parameter("x", default=2)
    assert x.default == 2
    assert x.run() == 2


def test_create_parameter_with_default_is_not_required():
    x = Parameter("x", default=2)
    assert not x.required


def test_create_required_parameter():
    x = Parameter("x", required=True)
    assert x.required


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
