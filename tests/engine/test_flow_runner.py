import pytest
import prefect
from prefect.flow import Flow
from prefect import Parameter, Task
from prefect.tasks.core.function_task import FunctionTask
from prefect.engine import FlowRunner
from prefect.engine.state import FlowState, TaskState
from prefect.utilities.tests import run_flow_runner_test


def test_flow_runner_success():
    """
    Test that a simple two-task Flow runs
    """
    with Flow() as f:
        t1 = FunctionTask(fn=lambda: 1)
        t2 = FunctionTask(fn=lambda: 2)
        t2.set_dependencies(upstream_tasks=[t1])

    run_flow_runner_test(
        flow=f,
        expected_state=FlowState.SUCCESS,
        expected_task_states={
            t1: TaskState(TaskState.SUCCESS, result=1),
            t2: TaskState(TaskState.SUCCESS, result=2),
        },
    )


def test_return_all_task_states():
    """
    Test that the flag to return all tasks (not just terminal tasks) works
    """
    with Flow() as f:
        t1 = FunctionTask(fn=lambda: 1)
        t2 = FunctionTask(fn=lambda: 2)
        t2.set_dependencies(upstream_tasks=[t1])

    state = FlowRunner(flow=f).run(return_all_task_states=False)
    assert len(state.result) == 1

    state = FlowRunner(flow=f).run(return_all_task_states=True)
    assert len(state.result) == 2


def test_fail():
    """
    Test that a Flow with a successful task followed by an unsuccessful task
    runs
    """
    with Flow() as f:
        t1 = FunctionTask(fn=lambda: 1)
        t2 = FunctionTask(fn=lambda: 1 / 0)
        t2.set_dependencies(upstream_tasks=[t1])

    run_flow_runner_test(
        flow=f,
        expected_state=FlowState.FAILED,
        expected_task_states={
            t1: TaskState(TaskState.SUCCESS, result=1),
            t2: TaskState.FAILED,
        },
    )


def test_fail_early_and_cleanup():
    """
    Test that a flow with an early failed task flows appropriate through
    the rest of the tasks
    """
    with Flow() as f:
        t1 = FunctionTask(fn=lambda: 1 / 0)
        t2 = FunctionTask(fn=lambda: 2)
        t3 = FunctionTask(fn=lambda: 3, trigger=prefect.tasks.triggers.AllFailed)
        t2.set_dependencies(upstream_tasks=[t1])
        t3.set_dependencies(upstream_tasks=[t2])

    # t1 fails by design
    # t2 fails because it can't run if t1 fails
    # t3 succeeds
    run_flow_runner_test(
        flow=f,
        expected_state=FlowState.SUCCESS,
        expected_task_states={
            t1: TaskState.FAILED,
            t2: TaskState.FAILED,
            t3: TaskState(TaskState.SUCCESS, result=3),
        },
    )


def test_dataflow():
    """
    Test that tasks appropriately pass data among each other
    """
    with Flow() as f:
        x = FunctionTask(fn=lambda: 1)
        y = FunctionTask(fn=lambda: 2)
        z = FunctionTask(fn=lambda x, y: x + 2 * y)
        z(x=x, y=y)

    run_flow_runner_test(
        flow=f,
        expected_state=FlowState.SUCCESS,
        expected_task_states={z: TaskState(TaskState.SUCCESS, result=5)},
    )


def test_indexed_task():
    with Flow() as f:
        t1 = FunctionTask(fn=lambda: {"a": 1})
        t2 = FunctionTask(fn=lambda x: x + 1)
        t2(x=t1["a"])

    # the index should have added a third task
    assert len(f.tasks) == 3

    run_flow_runner_test(
        flow=f,
        expected_state=FlowState.SUCCESS,
        expected_task_states={t2: TaskState(TaskState.SUCCESS, result=2)},
    )


def test_override_inputs():
    with Flow() as f:
        x = FunctionTask(fn=lambda: 1, name="x")
        y = FunctionTask(fn=lambda: 2, name="y")
        z = FunctionTask(fn=lambda x, y: x + y, name="z")
        z(x=x, y=y)

    run_flow_runner_test(
        flow=f, expected_task_states={z: TaskState(TaskState.SUCCESS, result=3)}
    )

    run_flow_runner_test(
        flow=f,
        override_task_inputs={z.id: dict(x=10)},
        expected_task_states={z: TaskState(TaskState.SUCCESS, result=12)},
    )


def test_parameters():
    with Flow() as f:
        x = Parameter("x")
        y = Parameter("y", default=10)
        z = FunctionTask(fn=lambda x, y: x + y)

        z(x=x, y=y)

    # if no parameters are provided, the flow will fail
    run_flow_runner_test(flow=f, expected_state=FlowState.FAILED)

    # if a required parameter isn't provided, the flow will fail
    run_flow_runner_test(
        flow=f, parameters=dict(y=2), expected_state=FlowState.FAILED
    )

    # if the required parameter is provided, the flow will succeed
    run_flow_runner_test(
        flow=f,
        parameters=dict(x=1),
        expected_state=FlowState.SUCCESS,
        expected_task_states={z: TaskState(TaskState.SUCCESS, result=11)},
    )

    # test both parameters
    run_flow_runner_test(
        flow=f,
        parameters=dict(x=1, y=100),
        expected_state=FlowState.SUCCESS,
        expected_task_states={z: TaskState(TaskState.SUCCESS, result=101)},
    )
