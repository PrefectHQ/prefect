import datetime

import pytest

import prefect
from prefect.core.task import Task
from prefect.engine import TaskRunner
from prefect.engine.state import (
    Failed,
    Pending,
    Retrying,
    Running,
    Skipped,
    State,
    Success,
    TriggerFailed,
)
from prefect.utilities.tests import raise_on_fail


class SuccessTask(Task):
    def run(self):
        return 1


class ErrorTask(Task):
    def run(self):
        raise ValueError("custom-error-message")


class RaiseFailTask(Task):
    def run(self):
        raise prefect.engine.signals.FAIL("custom-fail-message")
        raise ValueError("custom-error-message")  # pylint: disable=W0101


class RaiseSkipTask(Task):
    def run(self):
        raise prefect.engine.signals.SKIP()
        raise ValueError()  # pylint: disable=W0101


class RaiseSuccessTask(Task):
    def run(self):
        raise prefect.engine.signals.SUCCESS()
        raise ValueError()  # pylint: disable=W0101


class RaiseRetryTask(Task):
    def run(self):
        raise prefect.engine.signals.RETRY()
        raise ValueError()  # pylint: disable=W0101


class RaiseDontRunTask(Task):
    """
    This task is just for testing -- raising DONTRUN inside a task is considered bad
    """

    def run(self):
        raise prefect.engine.signals.DONTRUN()


def test_task_that_succeeds_is_marked_success():
    """
    Test running a task that finishes successfully and returns a result
    """
    task_runner = TaskRunner(task=SuccessTask())
    assert isinstance(task_runner.run(), Success)


def test_task_that_raises_success_is_marked_success():
    task_runner = TaskRunner(task=RaiseSuccessTask())
    assert isinstance(task_runner.run(), Success)


def test_task_that_has_an_error_is_marked_fail():
    task_runner = TaskRunner(task=ErrorTask())
    assert isinstance(task_runner.run(), Failed)


def test_task_that_raises_fail_is_marked_fail():
    task_runner = TaskRunner(task=RaiseFailTask())
    assert isinstance(task_runner.run(), Failed)
    assert not isinstance(task_runner.run(), TriggerFailed)


def test_task_that_fails_gets_retried_up_to_1_time():
    """
    Test that failed tasks are marked for retry if run_number is available
    """
    err_task = ErrorTask(max_retries=1)
    task_runner = TaskRunner(task=err_task)

    # first run should be retrying
    with prefect.context(_task_run_number=1):
        state = task_runner.run()
    assert isinstance(state, Retrying)
    assert isinstance(state.data["retry_time"], datetime.datetime)
    assert state.data["last_run_number"] == 1

    # second run should
    with prefect.context(_task_run_number=2):
        state = task_runner.run(state=state)
    assert isinstance(state, Failed)


def test_task_that_raises_retry_gets_retried_even_if_max_retries_is_set():
    """
    Test that tasks that raise a retry signal get retried even if they exceed max_retries
    """
    retry_task = RaiseRetryTask(max_retries=1)
    task_runner = TaskRunner(task=retry_task)

    # first run should be retrying
    with prefect.context(_task_run_number=1):
        state = task_runner.run()
    assert isinstance(state, Retrying)
    assert isinstance(state.data["retry_time"], datetime.datetime)
    assert state.data["last_run_number"] == 1

    # second run should also be retry because the task raises it explicitly

    with prefect.context(_task_run_number=2):
        state = task_runner.run(state=state)
    assert isinstance(state, Retrying)
    assert state.data["last_run_number"] == 2


def test_task_that_raises_skip_gets_skipped():
    task_runner = TaskRunner(task=RaiseSkipTask())
    assert isinstance(task_runner.run(), Skipped)


def test_task_that_is_running_doesnt_run():
    task_runner = TaskRunner(task=SuccessTask())
    initial_state = Running()
    assert task_runner.run(state=initial_state) is initial_state


def test_running_task_that_already_has_finished_state_doesnt_run():
    task_runner = TaskRunner(task=ErrorTask())

    # pending tasks get run (and fail)
    assert isinstance(task_runner.run(state=Pending()), Failed)

    # finished tasks don't run (just return same state)
    assert isinstance(task_runner.run(state=Success()), Success)
    assert isinstance(task_runner.run(state=Failed()), Failed)
    assert isinstance(task_runner.run(state=Skipped()), Skipped)


def test_task_runner_preserves_error_type():
    task_runner = TaskRunner(ErrorTask())
    state = task_runner.run()
    msg = state.message
    if isinstance(msg, Exception):
        assert type(msg).__name__ == "ValueError"
    else:
        assert "ValueError" in msg


def test_task_runner_raise_on_fail_when_task_errors():
    with raise_on_fail():
        with pytest.raises(ValueError):
            TaskRunner(ErrorTask()).run()


def test_task_runner_raise_on_fail_when_task_signals():
    with raise_on_fail():
        with pytest.raises(prefect.engine.signals.FAIL):
            TaskRunner(RaiseFailTask()).run()


def test_tasks_that_raise_DONTRUN_are_treated_as_skipped():
    assert isinstance(TaskRunner(task=RaiseDontRunTask()).run(), Skipped)
