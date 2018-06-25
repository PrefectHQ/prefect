import datetime

import pytest

import prefect
from prefect.core.task import Task
from prefect.tasks.core.function_task import FunctionTask
from prefect.engine import TaskRunner
from prefect.engine.state import State
from prefect.utilities.tasks import task
from prefect.utilities.tests import run_task_runner_test


class SuccessTask(Task):
    def run(self):
        return 1


class ErrorTask(Task):
    def run(self):
        raise ValueError("custom-error-message")


class RaiseFailTask(Task):
    def run(self):
        raise prefect.signals.FAIL("custom-fail-message")
        raise ValueError("custom-error-message")


class RaiseSkipTask(Task):
    def run(self):
        raise prefect.signals.SKIP()
        raise ValueError()


class RaiseSuccessTask(Task):
    def run(self):
        raise prefect.signals.SUCCESS()
        raise ValueError()


class RaiseRetryTask(Task):
    def run(self):
        raise prefect.signals.RETRY()
        raise ValueError()


def test_task_that_succeeds_is_marked_success():
    """
    Test running a task that finishes successfully and returns a result
    """
    run_task_runner_test(task=SuccessTask(), expected_state=State.SUCCESS)


def test_task_that_raises_success_is_marked_success():
    run_task_runner_test(task=RaiseSuccessTask(), expected_state=State.SUCCESS)


def test_task_that_has_an_error_is_marked_fail():
    run_task_runner_test(task=ErrorTask(), expected_state=State.FAILED)


def test_task_that_raises_fail_is_marked_fail():
    run_task_runner_test(task=RaiseFailTask(), expected_state=State.FAILED)


def test_task_that_fails_gets_retried_up_to_1_time():
    """
    Test that failed tasks are marked for retry if run_number is available
    """
    err_task = ErrorTask(max_retries=1)
    state = run_task_runner_test(
        task=err_task, expected_state=State.RETRYING, context={"run_number": 1}
    )
    assert isinstance(state.data, datetime.datetime)

    state = run_task_runner_test(
        task=err_task,
        state=state,
        expected_state=State.FAILED,
        context={"run_number": 2},
    )


def test_task_that_raises_retry_gets_retried_even_if_max_retries_is_set():
    """
    Test that failed tasks are marked for retry if run_number is available
    """
    err_task = RaiseRetryTask(max_retries=1)
    state = run_task_runner_test(
        task=err_task, expected_state=State.RETRYING, context={"run_number": 1}
    )

    state = run_task_runner_test(
        task=err_task,
        state=state,
        expected_state=State.RETRYING,
        context={"run_number": 2},
    )


def test_task_that_raises_skip_gets_skipped():
    run_task_runner_test(task=RaiseSkipTask(), expected_state=State.SKIPPED)


def test_running_task_that_already_finished_doesnt_run():
    run_task_runner_test(
        task=ErrorTask(), state=State(State.SUCCESS), expected_state=State.SUCCESS
    )
    run_task_runner_test(
        task=ErrorTask(), state=State(State.FAILED), expected_state=State.FAILED
    )


def test_task_runner_preserves_error_type():
    task_runner = TaskRunner(ErrorTask())
    result = task_runner.run()
    data = result.data["message"]
    if isinstance(data, Exception):
        assert type(data).__name__ == "ValueError"
    else:
        assert "ValueError" in data
