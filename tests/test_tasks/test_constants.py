import pytest

import prefect
from prefect.flow import Flow
from prefect.tasks.core.function_task import FunctionTask
from prefect.tasks.core.constant_task import ConstantTask, ContextTask, Parameter


def test_constant_task():
    with Flow('test') as flow:
        t1 = ConstantTask(5, name='constant')
        t2 = ConstantTask(5, name='constant')

    assert t2.name == 'constant-2'
    assert flow.run().result['constant'].result == 5


def test_context_task():
    with Flow('test') as flow:
        t = ContextTask('some_var', name='context')

    assert flow.run().result['context'].result is None

    with prefect.context.Context(some_var=17):
        assert flow.run().result['context'].result == 17

def test_parameter():
    with Flow('test') as flow:
        x = Parameter('x')
        y = Parameter('y', default=1)
        z = FunctionTask(fn=lambda a: a + 1)

        z.set(x=x, y=y)

    assert len(flow.parameters()) == 2
    assert 'x' in flow.parameters()
    assert flow.parameters()['x']['required']
    assert not flow.parameters()['y']['required']
