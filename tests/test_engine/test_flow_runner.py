import distributed
import pytest

import prefect
from prefect.tasks import FunctionTask
from prefect.engine import FlowRunner
from prefect.state import FlowRunState, TaskRunState
from prefect.utilities.test import run_flow_runner_test


def test_flow_runner_success():
    """
    Test that a simple two-task Flow runs
    """
    with prefect.Flow('flow') as f:
        t1 = FunctionTask(fn=lambda: 1, name='t1')
        t2 = FunctionTask(fn=lambda: 2, name='t2')
        t1.set(run_before=t2)

    run_flow_runner_test(
        flow=f,
        expected_state=FlowRunState.SUCCESS,
        expected_task_states=dict(
            t1=TaskRunState(TaskRunState.SUCCESS, result=1),
            t2=TaskRunState(TaskRunState.SUCCESS, result=2)))


def test_return_all_task_states():
    """
    Test that the flag to return all tasks (not just terminal tasks) works
    """
    with prefect.Flow('flow') as f:
        t1 = FunctionTask(fn=lambda: 1, name='t1')
        t2 = FunctionTask(fn=lambda: 2, name='t2')
        t1.set(run_before=t2)
    state = FlowRunner(flow=f).run(return_all_task_states=False)
    assert len(state.result) == 1
    state = FlowRunner(flow=f).run(return_all_task_states=True)
    assert len(state.result) == 2


def test_fail():
    """
    Test that a Flow with a successful task followed by an unsuccessful task
    runs
    """
    with prefect.Flow('flow') as f:
        t1 = FunctionTask(fn=lambda: 1, name='t1')
        t2 = FunctionTask(fn=lambda: 1 / 0, name='t2')
        t1.set(run_before=t2)

    run_flow_runner_test(
        flow=f,
        expected_state=FlowRunState.FAILED,
        expected_task_states=dict(
            t1=TaskRunState(TaskRunState.SUCCESS, result=1),
            t2=TaskRunState.FAILED))


def test_fail_early_and_cleanup():
    """
    Test that a flow with an early failed task flows appropriate through
    the rest of the tasks
    """
    with prefect.Flow('flow') as f:
        t1 = FunctionTask(fn=lambda: 1 / 0, name='t1')
        t2 = FunctionTask(fn=lambda: 2, name='t2')
        t3 = FunctionTask(fn=lambda: 3, name='t3', trigger='all_failed')
        t1.set(run_before=t2).set(run_before=t3)

    run_flow_runner_test(
        flow=f,
        expected_state=FlowRunState.SUCCESS,
        expected_task_states=dict(
            t1=TaskRunState.FAILED,
            t2=TaskRunState.FAILED,
            t3=TaskRunState(TaskRunState.SUCCESS, result=3)))


def test_dataflow():
    """
    Test that tasks appropriately pass data among each other
    """
    with prefect.Flow('flow') as f:
        x = FunctionTask(fn=lambda: 1, name='x')
        y = FunctionTask(fn=lambda: 2, name='y')
        z = FunctionTask(fn=lambda x, y: x + 2 * y, name='z')
        z.set(x=x, y=y)

    run_flow_runner_test(
        flow=f,
        expected_state=FlowRunState.SUCCESS,
        expected_task_states=dict(
            z=TaskRunState(TaskRunState.SUCCESS, result=5)))


def test_indexed_task():
    with prefect.Flow('flow') as f:
        t1 = FunctionTask(fn=lambda: {'a': 1}, name='t1')
        t2 = FunctionTask(fn=lambda x: x + 1, name='t2')
        t2.set(x=t1['a'])

    # the index should have added a third task
    assert len(f.tasks) == 3

    run_flow_runner_test(
        flow=f,
        expected_state=FlowRunState.SUCCESS,
        expected_task_states=dict(
            t2=TaskRunState(TaskRunState.SUCCESS, result=2)))


def test_provided_inputs():
    with prefect.Flow('flow') as f:
        x = FunctionTask(fn=lambda: 1, name='x')
        y = FunctionTask(fn=lambda: 2, name='y')
        z = FunctionTask(fn=lambda x, y: x + y, name='z')
        z.set(x=x, y=y)

    # test FlowRunner directly
    fr = FlowRunner(flow=f)
    fr_state = fr.run(return_all_task_states=True)
    assert fr_state.result['x'].result == 1
    assert fr_state.result['z'].result == 3

    # test FlowRunner with inputs
    fr_state_inputs = fr.run(
        inputs=dict(z=dict(x=10)),
        return_all_task_states=True,
    )
    assert fr_state_inputs.result['x'].result == 1
    assert fr_state_inputs.result['z'].result == 12

    # test utility
    run_flow_runner_test(
        flow=f,
        inputs=dict(z=dict(x=10)),
        expected_state=FlowRunState.SUCCESS,
        expected_task_states=dict(
            z=TaskRunState(TaskRunState.SUCCESS, result=12)))


# def test_approval
