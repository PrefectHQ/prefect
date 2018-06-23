import pytest

from prefect.tasks.core.constants import Constant
from prefect.tasks.core.function_task import FunctionTask


def test_test_create_constant_task():
    x = Constant("x")
    assert x.run() == "x"


def test_automatic_create_constant_task():
    t = FunctionTask(fn=lambda x: x)
    result = t.set_dependencies(upstream_tasks=[4])
    assert len(result.flow.tasks) == 2
    assert any(isinstance(t, Constant) for t in result.flow.tasks)
