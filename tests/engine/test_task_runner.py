import datetime
import pytest
import prefect
from prefect.task import Task
from prefect.utilities.tasks import task
from prefect.engine import TaskRunner
from prefect.engine.state import TaskRunState
from prefect.utilities.tests import run_task_runner_test


@pytest.fixture()
def task():
    return prefect.tasks.FunctionTask(fn=lambda: 1)


@pytest.fixture()
def err_task():
    return prefect.tasks.FunctionTask(fn=lambda: 1 / 0, max_retries=1)


@pytest.fixture()
def inputs_task():

    def fn(x, y=10):
        return 2 * x + y

    return prefect.tasks.FunctionTask(fn=fn, max_retries=1)


@pytest.fixture
def cleanup_task():
    return prefect.tasks.FunctionTask(
        fn=lambda: 'Clean!', trigger=prefect.triggers.any_failed)


def test_success(task):
    """
    Test running a task that finishes successfully and returns a result
    """
    state = run_task_runner_test(
        task=task, expected_state=TaskRunState(TaskRunState.SUCCESS, result=1))
    assert state.is_finished()


def test_error(err_task):
    """
    Test running a task that has an error
    """
    state = run_task_runner_test(
        task=err_task, expected_state=TaskRunState.FAILED)
    assert state.is_finished()


def test_retry(err_task):
    """
    Test that failed tasks are marked for retry if run_number is available
    """
    state = run_task_runner_test(
        task=err_task,
        expected_state=TaskRunState.PENDING_RETRY,
        context={'run_number': 1})
    assert isinstance(state.result, datetime.datetime)


def test_signal():
    """
    Test running a task that raises a Prefect signal
    """

    class FailTask(Task):

        def run(self):
            raise prefect.signals.FAIL(3)

    class SkipTask(Task):

        def run(self):
            raise prefect.signals.SKIP(3)

    class SuccessTask(Task):

        def run(self):
            raise prefect.signals.SUCCESS(3)

    # fail task
    run_task_runner_test(
        task=FailTask(),
        expected_state=TaskRunState(TaskRunState.FAILED, result=3))

    state = run_task_runner_test(
        task=FailTask(max_retries=1),
        expected_state=TaskRunState.PENDING_RETRY,
        context={'run_number': 1})

    assert isinstance(state.result, datetime.datetime)


    # skip task
    run_task_runner_test(
        task=SkipTask(),
        expected_state=TaskRunState(TaskRunState.SKIPPED, result=3))

    # success task
    run_task_runner_test(
        task=SuccessTask(),
        expected_state=TaskRunState(TaskRunState.SUCCESS, result=3))


def test_run_finished_task(task, err_task):
    """
    Tests what happens when we run tasks that are already finished.

    They shouldn't run and the provided state should be returned.
    """
    # a successful task initialized as failed should fail
    state = TaskRunState(TaskRunState.FAILED, result=-1)
    run_task_runner_test(task=task, state=state, expected_state=state)

    # a failing task initialized as successful should be successful
    state = TaskRunState(TaskRunState.SUCCESS, result=1)
    run_task_runner_test(task=err_task, state=state, expected_state=state)

    state = TaskRunState(TaskRunState.SKIPPED, result=-1)
    run_task_runner_test(task=err_task, state=state, expected_state=state)

