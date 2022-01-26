import pendulum
import pytest

import prefect
from prefect.core.flow import Flow
from prefect.core.parameter import DateTimeParameter, Parameter
from prefect.core.task import Task
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


def test_create_parameter_with_default_none():
    x = Parameter("x", default=None)
    assert x.default is None
    assert not x.required
    assert x.run() is None


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


def test_calling_parameter_is_ok():
    with Flow("test") as f:
        Parameter("x")()

    assert len(f.tasks) == 1


def test_call_accepts_flow():
    f = Flow("test")
    Parameter("x")(flow=f)

    assert len(f.tasks) == 1


def test_call_must_have_a_flow_out_of_context():
    with pytest.raises(ValueError, match="infer an active Flow"):
        Parameter("x")()


@pytest.mark.parametrize("attr", ["mapped", "task_args", "upstream_tasks"])
def test_call_does_not_accept_most_args(attr):
    x = Parameter("x")
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        x(**{attr: None})


def test_copy_with_new_name():
    x = Parameter("x")
    y = x.copy("y")

    assert x.name == x.slug == "x"
    assert y.name == y.slug == "y"


def test_copy_requires_name():
    x = Parameter("x")
    with pytest.raises(TypeError, match="required positional argument"):
        x.copy()


class TestDateTimeParameter:
    @prefect.task
    def return_value(x):
        return x

    with Flow("test") as dt_flow:
        dt = DateTimeParameter("dt", required=False)
        x = return_value(dt)

    def test_datetime_parameter_returns_datetimes_if_passed_datetimes(self):
        now = pendulum.now()
        state = self.dt_flow.run(dt=now)
        assert state.result[self.dt].result == now
        assert state.result[self.x].result == now

    def test_datetime_parameter_returns_datetimes_if_passed_string(self):
        now = pendulum.now()
        state = self.dt_flow.run(dt=str(now))
        assert state.result[self.dt].result == now
        assert state.result[self.x].result == now

    def test_datetime_parameter_returns_none_if_passed_none(self):
        state = self.dt_flow.run(dt=None)
        assert state.result[self.dt].result is None
        assert state.result[self.x].result is None

    def test_datetime_parameter_with_none_default(self):
        state = self.dt_flow.run()
        assert state.result[self.dt].result is None
        assert state.result[self.x].result is None
