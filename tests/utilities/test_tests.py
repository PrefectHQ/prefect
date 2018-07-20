from contextlib import contextmanager
import pytest

import prefect

from prefect.utilities.tests import raise_on_fail
from prefect.core import Flow, Task
from prefect.engine import TaskRunner, FlowRunner
from prefect.engine import state


class SuccessTask(Task):
    def run(self):
        return 1


class BusinessTask(Task):
    def run(self):
        raise prefect.signals.FAIL("needs more blockchain!")


class MathTask(Task):
    def run(self):
        1 / 0


def test_raise_on_fail_raises_basic_error():
    flow = Flow()
    flow.add_task(MathTask())
    with pytest.raises(ZeroDivisionError):
        with raise_on_fail():
            flow.run()


def test_raise_on_fail_raises_basic_prefect_signal():
    flow = Flow()
    flow.add_task(BusinessTask())
    with pytest.raises(prefect.signals.FAIL) as error:
        with raise_on_fail():
            flow.run()
    assert "needs more blockchain!" in str(error)


def test_raise_on_fail_works_at_the_task_level_with_error():
    taskrunner = TaskRunner(task=MathTask())
    with pytest.raises(ZeroDivisionError):
        with raise_on_fail():
            taskrunner.run()


def test_raise_on_fail_works_at_the_task_level_with_signal():
    taskrunner = TaskRunner(task=BusinessTask())
    with pytest.raises(prefect.signals.FAIL) as error:
        with raise_on_fail():
            taskrunner.run()
    assert "needs more blockchain!" in str(error)


def test_that_bad_code_in_flow_runner_is_caught(monkeypatch):
    """
    Test that an error in the actual FlowRunner code itself (not the execution of user code)
    is caught
    """
    flow = Flow()
    flow.add_task(MathTask())

    class BadTaskRunner(TaskRunner):
        def retry_or_fail(self, *args, **kwargs):
            raise RuntimeError("I represent bad code in the task runner.")

    class BadFlowRunner(FlowRunner):
        @contextmanager
        def flow_context(self, *args, **kwargs):
            raise RuntimeError("I represent bad code in the flow runner.")

    monkeypatch.setattr(prefect.engine, "FlowRunner", BadFlowRunner)
    monkeypatch.setattr(prefect.engine, "TaskRunner", BadTaskRunner)

    flow_state = BadFlowRunner(flow=flow).run()
    assert isinstance(flow_state, state.Failed)
    assert isinstance(flow_state.message, RuntimeError)
    assert "I represent bad code in the flow runner." == str(flow_state.message)


def test_that_bad_code_in_task_runner_is_caught(monkeypatch):
    """
    Test that an error in the actual TaskRunner code itself (not the execution of user code)
    is caught
    """
    flow = Flow()
    flow.add_task(MathTask())

    class BadTaskRunner(TaskRunner):
        def retry_or_fail(self, *args, **kwargs):
            raise RuntimeError("I represent bad code in the task runner.")

    monkeypatch.setattr(prefect.engine, "TaskRunner", BadTaskRunner)

    flow_state = FlowRunner(flow=flow).run()
    assert isinstance(flow_state, state.Failed)
    assert isinstance(flow_state.message, RuntimeError)
    assert "I represent bad code in the task runner." == str(flow_state.message)


def test_raise_on_fail_raises_basic_error():
    flow = Flow()
    flow.add_task(MathTask())
    try:
        assert "_raise_on_fail" not in prefect.context
        with raise_on_fail():
            assert "_raise_on_fail" in prefect.context
            flow.run()
        assert "_raise_on_fail" not in prefect.context
    except ZeroDivisionError:
        pass
