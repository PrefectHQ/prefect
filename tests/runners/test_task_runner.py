import pytest
import prefect
from prefect.state import TaskRunState

def test_simple_taskrunner():
    t1 = prefect.task.FunctionTask(fn=lambda: 1)
    tr = prefect.runners.TaskRunner(task=t1)
    result = tr.run()
    assert result['state'].is_successful()
    assert result['result'] == 1

def test_simple_taskrunner_error():
    t1 = prefect.task.FunctionTask(fn=lambda: 1/0)
    tr = prefect.runners.TaskRunner(task=t1)
    result = tr.run()
    assert result['state'].is_failed()
    assert result['result'] is None


def test_run_finished_task():
    """
    Test running tasks that are given finished states.

    They shouldn't run and the state should be returned.
    """
    t1 = prefect.task.FunctionTask(fn=lambda: 1)
    tr1 = prefect.runners.TaskRunner(task=t1)
    result1 = tr1.run(state=TaskRunState.FAILED, success_result=99)
    assert result1['state'].is_failed()
    assert result1['result'] is None

    t2 = prefect.task.FunctionTask(fn=lambda: 1/0)
    tr2 = prefect.runners.TaskRunner(task=t2)
    result2 = tr2.run(state=TaskRunState.SUCCESS, success_result=99)
    assert result2['state'].is_successful()
    assert result2['result'] == 99

    t2 = prefect.task.FunctionTask(fn=lambda: 1/0)
    tr2 = prefect.runners.TaskRunner(task=t2)
    result2 = tr2.run(state=TaskRunState.SUCCESS)
    assert result2['state'].is_successful()
    assert result2['result'] is None
