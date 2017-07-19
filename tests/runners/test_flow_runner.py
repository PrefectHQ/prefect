import distributed
import pytest
import prefect
from prefect.state import FlowState, TaskState


def test_flowrunner():
    with prefect.Flow('flow') as f:
        t1 = prefect.tasks.FunctionTask(fn=lambda: 1, name='t1')
        t2 = prefect.tasks.FunctionTask(fn=lambda: 2, name='t2')
        t1.run_before(t2)

    result = prefect.runners.FlowRunner(flow=f).run()

    assert len(result) == 3
    assert result['state'].is_successful()
    assert result['task_states']['t1'].is_successful()
    assert result['task_states']['t2'].is_successful()
    assert result['task_results']['t1'] == 1
    assert result['task_results']['t2'] == 2


def test_flowrunner_fail():
    """
    Test that a Flow with a successful task followed by an unsuccessful task
    runs
    """
    with prefect.Flow('flow') as f:
        t1 = prefect.tasks.FunctionTask(fn=lambda: 1, name='t1')
        t2 = prefect.tasks.FunctionTask(fn=lambda: 1 / 0, name='t2')
        t1.run_before(t2)

    result = prefect.runners.FlowRunner(flow=f).run()

    assert result['state'].is_failed()
    assert result['task_states']['t1'].is_successful()
    assert result['task_states']['t2'].is_failed()
    assert result['task_results']['t1'] == 1
    assert result['task_results']['t2'] is None


def test_flowrunner_fail_early():
    """
    Test that a flow with an early failed task flows appropriate through
    the rest of the tasks
    """
    with prefect.Flow('flow') as f:
        t1 = prefect.tasks.FunctionTask(fn=lambda: 1 / 0, name='t1')
        t2 = prefect.tasks.FunctionTask(fn=lambda: 2, name='t2')
        t3 = prefect.tasks.FunctionTask(fn=lambda: 3, name='t3', trigger='all_failed')
        t1.then(t2).then(t3)

    result = prefect.runners.FlowRunner(flow=f).run()

    assert result['state'].is_successful()
    assert result['task_states']['t1'].is_failed()
    assert result['task_states']['t2'].is_failed()
    assert result['task_states']['t3'].is_successful()
