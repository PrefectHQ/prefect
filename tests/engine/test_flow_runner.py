import datetime

import prefect
from prefect.core import Flow, Task
from prefect.engine import FlowRunner
from prefect.engine.state import State
from prefect.utilities.tests import run_flow_runner_test


class SuccessTask(Task):
    def run(self):
        return 1


class AddTask(Task):
    def run(self, x, y):  # pylint: disable=W0221
        return x + y


class ErrorTask(Task):
    def run(self):
        raise ValueError("custom-error-message")


class RaiseFailTask(Task):
    def run(self):
        raise prefect.signals.FAIL("custom-fail-message")
        raise ValueError("custom-error-message")  # pylint: disable=W0101


class RaiseSkipTask(Task):
    def run(self):
        raise prefect.signals.SKIP()
        raise ValueError()  # pylint: disable=W0101


class RaiseSuccessTask(Task):
    def run(self):
        raise prefect.signals.SUCCESS()
        raise ValueError()  # pylint: disable=W0101


class RaiseRetryTask(Task):
    def run(self):
        raise prefect.signals.RETRY()
        raise ValueError()  # pylint: disable=W0101


def test_flow_runner_runs_basic_flow_with_1_task():
    flow = prefect.Flow()
    task = SuccessTask()
    flow.add_task(task)
    flow_runner = FlowRunner(flow=flow)
    state = flow_runner.run(return_tasks=[task])
    # assert state.state == State.SUCCESS
    assert state == State(State.SUCCESS, {task: State(State.SUCCESS, data=1)})


def test_flow_runner_runs_basic_flow_with_2_independent_tasks():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = SuccessTask()

    flow.add_task(task1)
    flow.add_task(task2)

    run_flow_runner_test(
        flow,
        expected_state=State.SUCCESS,
        expected_task_states={
            task1: State(State.SUCCESS, data=1),
            task2: State(State.SUCCESS, data=1),
        },
    )


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = SuccessTask()

    flow.add_edge(task1, task2)

    run_flow_runner_test(
        flow,
        expected_state=State.SUCCESS,
        expected_task_states={
            task1: State(State.SUCCESS, data=1),
            task2: State(State.SUCCESS, data=1),
        },
    )


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks_and_first_task_fails():
    flow = prefect.Flow()
    task1 = ErrorTask()
    task2 = SuccessTask()

    flow.add_edge(task1, task2)

    run_flow_runner_test(
        flow,
        expected_state=State.FAILED,
        expected_task_states={task1: State.FAILED, task2: State.FAILED},
    )


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks_and_second_task_fails():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = ErrorTask()

    flow.add_edge(task1, task2)

    run_flow_runner_test(
        flow,
        expected_state=State.FAILED,
        expected_task_states={task1: State.SUCCESS, task2: State.FAILED},
    )


def test_flow_runner_returns_task_states_even_if_it_doesnt_run():
    # https://gitlab.com/prefect/prefect/issues/15
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = ErrorTask()

    flow.add_edge(task1, task2)

    run_flow_runner_test(
        flow,
        state=State(State.SUCCESS),
        expected_state=State.SUCCESS,
        expected_task_states={task1: State.PENDING, task2: State.PENDING},
    )


def test_flow_runner_remains_pending_if_tasks_are_retrying():
    # https://gitlab.com/prefect/prefect/issues/15
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = ErrorTask(max_retries=1)

    flow.add_edge(task1, task2)

    run_flow_runner_test(
        flow,
        expected_state=State.PENDING,
        expected_task_states={task1: State.SUCCESS, task2: State.RETRYING},
    )


def test_flow_runner_doesnt_return_by_default():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = SuccessTask()
    flow.add_edge(task1, task2)
    res = flow.run()
    assert res.data == {}


def test_flow_runner_does_return_when_requested():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = SuccessTask()
    flow.add_edge(task1, task2)
    run_flow_runner_test(
        flow, expected_state=State.SUCCESS, expected_task_states={task1: State.SUCCESS}
    )


def test_missing_parameter_creates_pending_task():
    flow = prefect.Flow()
    task = AddTask()
    y = prefect.Parameter("y")
    task.set_dependencies(flow, keyword_tasks=dict(x=1, y=y))
    run_flow_runner_test(
        flow, expected_state=State.FAILED, expected_task_states={task: State.PENDING}
    )


def test_missing_parameter_error_is_surfaced():
    flow = prefect.Flow()
    task = AddTask()
    y = prefect.Parameter("y")
    task.set_dependencies(flow, keyword_tasks=dict(x=1, y=y))
    msg = flow.run().data["message"]
    assert isinstance(msg, ValueError)
    assert "required parameter" in str(msg).lower()
