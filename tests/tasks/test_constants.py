import pytest

from prefect.core import Flow
from prefect.tasks.core.constants import Constant
from prefect.tasks.core.function_task import FunctionTask


def test_test_create_constant_task():
    x = Constant("x")
    assert x.run() == "x"


def test_automatic_create_constant_task():
    with Flow() as flow:
        t = FunctionTask(fn=lambda x: x)
        t.set_dependencies(upstream_tasks=[4])
        assert len(flow.tasks) == 2
        assert any(isinstance(t, Constant) for t in flow.tasks)
