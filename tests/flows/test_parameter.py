from prefect.core.flow import Flow
from prefect.core.task import Parameter
from prefect.tasks.core.function_task import FunctionTask


def test_parameter():
    with Flow("test") as flow:
        x = Parameter("x")
        y = Parameter("y", default=1)
        z = FunctionTask(fn=lambda a: a + 1)

        z.set(x=x, y=y)

    assert len(flow.parameters()) == 2
    assert "x" in flow.parameters()
    assert flow.parameters()["x"]["required"]
    assert not flow.parameters()["y"]["required"]
