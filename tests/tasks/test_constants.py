import pytest

import prefect
from prefect.flow import Flow
from prefect.tasks.core.function_task import FunctionTask
from prefect.tasks.core.constants import Constant, ContextTask


def test_constant_task():
    with Flow('test') as flow:
        t1 = Constant(5, name='constant')
        t2 = Constant(5, name='constant')

    assert t2.name == 'constant-2'
    assert flow.run().result['constant'].result == 5


def test_context_task():
    with Flow('test') as flow:
        t = ContextTask('some_var', name='context')

    assert flow.run().result['context'].result is None

    with prefect.context.Context(some_var=17):
        assert flow.run().result['context'].result == 17
