import pytest

import prefect
from prefect.core import Flow, Task
from prefect.engine import FlowRunner, TaskRunner, state
from prefect.utilities.tests import raise_on_exception, set_temporary_config


class SuccessTask(Task):
    def run(self):
        return 1


class BusinessTask(Task):
    def run(self):
        raise prefect.engine.signals.FAIL("needs more blockchain!")


class MathTask(Task):
    def run(self):
        1 / 0


def test_raise_on_exception_raises_basic_error():
    flow = Flow()
    flow.add_task(MathTask())
    with pytest.raises(ZeroDivisionError):
        with raise_on_exception():
            flow.run()


def test_raise_on_exception_raises_basic_prefect_signal():
    flow = Flow()
    flow.add_task(BusinessTask())
    with pytest.raises(prefect.engine.signals.FAIL) as error:
        with raise_on_exception():
            flow.run()
    assert "needs more blockchain!" in str(error)


def test_raise_on_exception_works_at_the_task_level_with_error():
    taskrunner = TaskRunner(task=MathTask())
    with pytest.raises(ZeroDivisionError):
        with raise_on_exception():
            taskrunner.run()


def test_raise_on_exception_works_at_the_task_level_with_signal():
    taskrunner = TaskRunner(task=BusinessTask())
    with pytest.raises(prefect.engine.signals.FAIL) as error:
        with raise_on_exception():
            taskrunner.run()
    assert "needs more blockchain!" in str(error)


def test_that_bad_code_in_flow_runner_is_caught():
    """
    Test that an error in the actual FlowRunner code itself (not the execution of user code)
    is caught
    """

    class BadFlowRunner(FlowRunner):
        def get_flow_run_state(self, *args, **kwargs):
            raise RuntimeError("I represent bad code in the flow runner.")

    flow = Flow()
    flow.add_task(MathTask())
    flow_state = BadFlowRunner(flow=flow).run()
    assert isinstance(flow_state, state.Failed)
    assert isinstance(flow_state.result, RuntimeError)
    assert "I represent bad code in the flow runner." == str(flow_state.result)


def test_that_bad_code_in_task_runner_is_caught():
    """
    Test that an error in the actual TaskRunner code itself (not the execution of user code)
    is caught
    """

    class BadTaskRunner(TaskRunner):
        def get_task_run_state(self, *args, **kwargs):
            raise RuntimeError("I represent bad code in the task runner.")

    flow = Flow()
    flow.add_task(MathTask())
    flow_state = FlowRunner(flow=flow, task_runner_cls=BadTaskRunner).run()
    assert isinstance(flow_state, state.Failed)
    assert isinstance(flow_state.result, RuntimeError)
    assert "I represent bad code in the task runner." == str(flow_state.result)


def test_raise_on_exception_plays_well_with_context():
    flow = Flow()
    flow.add_task(MathTask())
    try:
        assert "_raise_on_exception" not in prefect.context
        with raise_on_exception():
            assert "_raise_on_exception" in prefect.context
            flow.run()
    except ZeroDivisionError:
        assert "_raise_on_exception" not in prefect.context
        pass


def test_set_temporary_config_is_temporary():
    with set_temporary_config({"tasks.defaults.max_retries": 5}):
        with set_temporary_config({"tasks.defaults.max_retries": 1}):
            t1 = Task()
            assert t1.max_retries == 1
        t2 = Task()
        assert t2.max_retries == 5
    t3 = Task()
    assert t3.max_retries == 0


def test_set_temporary_config_can_invent_new_settings():
    with set_temporary_config({"flows.nested.nested_again.val": "5"}):
        assert prefect.config.flows.nested.nested_again.val == "5"

    with pytest.raises(AttributeError):
        assert prefect.config.flows.nested.nested_again.val == "5"


def test_set_temporary_config_with_multiple_keys():
    with set_temporary_config({"x.y.z": 1, "a.b.c": 2}):
        assert prefect.config.x.y.z == 1
        assert prefect.config.a.b.c == 2
