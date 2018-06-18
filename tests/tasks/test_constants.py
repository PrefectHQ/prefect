import pytest

import prefect
from prefect.core.flow import Flow
from prefect.tasks.core.function_task import FunctionTask
from prefect.tasks.core.constants import Constant


def test_constant_task():
    with Flow("test") as flow:
        t1 = Constant(5, name="constant")
        t2 = Constant(5, name="constant")

    assert t2.name == "constant-2"
    assert flow.run().result["constant"].result == 5
