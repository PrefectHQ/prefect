import datetime

import prefect
from prefect.core.task import Task
from prefect.engine import TaskRunner
from prefect.engine.state import State


class SuccessTask(Task):
    def run(self):
        return 1


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


def test_task_that_succeeds_is_marked_success():
    """
    Test running a task that finishes successfully and returns a result
    """
    task_runner = TaskRunner(task=SuccessTask())
    assert task_runner.run().state == State.SUCCESS


def test_task_that_raises_success_is_marked_success():
    task_runner = TaskRunner(task=RaiseSuccessTask())
    assert task_runner.run().state == State.SUCCESS


def test_task_that_has_an_error_is_marked_fail():
    task_runner = TaskRunner(task=ErrorTask())
    assert task_runner.run().state == State.FAILED


def test_task_that_raises_fail_is_marked_fail():
    task_runner = TaskRunner(task=RaiseFailTask())
    assert task_runner.run().state == State.FAILED


def test_task_that_fails_gets_retried_up_to_1_time():
    """
    Test that failed tasks are marked for retry if run_number is available
    """
    err_task = ErrorTask(max_retries=1)
    task_runner = TaskRunner(task=err_task)

    # first run should be retrying
    state = task_runner.run(context={"_task_run_number": 1})
    assert state.state == State.RETRYING
    assert isinstance(state.data, datetime.datetime)

    # second run should
    state = task_runner.run(state=state, context={"_task_run_number": 2})
    assert state.state == State.FAILED


def test_task_that_raises_retry_gets_retried_even_if_max_retries_is_set():
    """
    Test that tasks that raise a retry signal get retried even if they exceed max_retries
    """
    retry_task = RaiseRetryTask(max_retries=1)
    task_runner = TaskRunner(task=retry_task)

    # first run should be retrying
    state = task_runner.run(context={"_task_run_number": 1})
    assert state.state == State.RETRYING
    assert isinstance(state.data, datetime.datetime)

    # second run should also be retry because the task raises it explicitly
    state = task_runner.run(state=state, context={"_task_run_number": 2})
    assert state.state == State.RETRYING
    assert isinstance(state.data, datetime.datetime)


def test_task_that_raises_skip_gets_skipped():
    task_runner = TaskRunner(task=RaiseSkipTask())
    assert task_runner.run().state == State.SKIPPED


def test_running_task_that_already_has_finished_state_doesnt_run():
    task_runner = TaskRunner(task=ErrorTask())

    # pending tasks get run (and fail)
    assert task_runner.run(state=State(State.PENDING)).state == State.FAILED

    # finished tasks don't run (just return same state)
    assert task_runner.run(state=State(State.SUCCESS)).state == State.SUCCESS
    assert task_runner.run(state=State(State.FAILED)).state == State.FAILED
    assert task_runner.run(state=State(State.SKIPPED)).state == State.SKIPPED


def test_task_runner_preserves_error_type():
    task_runner = TaskRunner(ErrorTask())
    state = task_runner.run()
    data = state.data["message"]
    if isinstance(data, Exception):
        assert type(data).__name__ == "ValueError"
    else:
        assert "ValueError" in data
