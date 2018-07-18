import pytest

import prefect

from prefect.utilities.tests import raise_on_fail
from prefect.core import Flow, Task
from prefect.engine import TaskRunner


class BusinessTask(Task):
    def run(self):
        raise prefect.signals.FAIL("needs more blockchain!")


class MathTask(Task):
    def run(self):
        1 / 0


def test_raise_on_fail_raises_basic_error():
    flow = Flow()
    task = MathTask()
    flow.add_task(task)
    with pytest.raises(ZeroDivisionError):
        with raise_on_fail():
            flow.run()


def test_raise_on_fail_raises_basic_prefect_signal():
    flow = Flow()
    task = BusinessTask()
    flow.add_task(task)
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


def test_core_code_errors_bubble_up(monkeypatch):
    flow = Flow()
    flow.add_task(MathTask())
    class BadTaskRunner(TaskRunner):
        def handle_fail(self, *args, **kwargs):
            raise RuntimeError("I'm not cool with this.")
    monkeypatch.setattr(prefect.engine, "TaskRunner", BadTaskRunner)
    with pytest.raises(RuntimeError) as error:
        with raise_on_fail():
            flow.run()
    assert "I'm not cool with this." in str(error)
