import pytest

import prefect
from prefect.flow import Flow
from prefect.tasks.core.constant_task import ConstantTask, ContextTask


def test_context_task():
    with Flow('test') as flow:
        t = ContextTask('some_var', name='context')


    assert flow.run().result['context'].result is None

    with prefect.context.Context(some_var=17):
        assert flow.run().result['context'].result == 17

