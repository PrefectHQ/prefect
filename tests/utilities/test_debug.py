import os
import subprocess
import sys
import tempfile
import textwrap

import pytest

import prefect
from prefect.core import Flow, Task
from prefect.engine import FlowRunner, TaskRunner, state
from prefect.tasks.control_flow import switch
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.debug import is_serializable, raise_on_exception


class SuccessTask(Task):
    def run(self):
        return 1


class ErrorTask(Task):
    def run(self):
        raise ValueError("I had a problem.")


class BusinessTask(Task):
    def run(self):
        raise prefect.engine.signals.FAIL("needs more blockchain!")


class MathTask(Task):
    def run(self):
        1 / 0


def assert_script_runs(script):
    sd, script_file = tempfile.mkstemp()
    os.close(sd)
    try:
        with open(script_file, "w") as sf:
            sf.write(script)
        subprocess.check_output(
            "python {}".format(script_file), shell=True, stderr=subprocess.STDOUT
        )
    except Exception as exc:
        raise exc
    finally:
        os.unlink(script_file)


def test_raise_on_exception_raises_basic_error():
    flow = Flow(name="test")
    flow.add_task(MathTask())
    with pytest.raises(ZeroDivisionError):
        with raise_on_exception():
            flow.run()


@pytest.mark.parametrize(
    "signal", prefect.engine.signals.PrefectStateSignal.__subclasses__()
)
def test_raise_on_exception_ignores_all_prefect_signals(signal):
    flow = Flow(name="test")

    @prefect.task
    def raise_signal():
        if (
            prefect.context.get("task_loop_count", 1) < 2
            and prefect.context.get("task_run_count", 1) < 2
            and signal.__name__ != "PAUSE"
        ):
            raise signal("my message")

    flow.add_task(raise_signal)
    with raise_on_exception():
        flow_state = flow.run()


def test_raise_on_exception_works_at_the_task_level_with_error():
    taskrunner = TaskRunner(task=MathTask())
    with pytest.raises(ZeroDivisionError):
        with raise_on_exception():
            taskrunner.run()


def test_that_bad_code_in_flow_runner_is_caught():
    """
    Test that an error in the actual FlowRunner code itself (not the execution of user code)
    is caught
    """

    class BadFlowRunner(FlowRunner):
        def get_flow_run_state(self, *args, **kwargs):
            raise RuntimeError("I represent bad code in the flow runner.")

    flow = Flow(name="test")
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

    flow = Flow(name="test")
    math_task = MathTask()
    flow.add_task(math_task)
    flow_state = FlowRunner(flow=flow, task_runner_cls=BadTaskRunner).run(
        return_tasks=[math_task]
    )
    assert isinstance(flow_state, state.Failed)
    assert flow_state.result[math_task].is_failed()
    caught_exc = flow_state.result[math_task].result
    assert isinstance(caught_exc, RuntimeError)
    assert "I represent bad code in the task runner." == str(caught_exc)


def test_raise_on_exception_plays_well_with_context():
    flow = Flow(name="test")
    flow.add_task(MathTask())
    try:
        assert "raise_on_exception" not in prefect.context
        with raise_on_exception():
            assert "raise_on_exception" in prefect.context
            flow.run()
    except ZeroDivisionError:
        assert "raise_on_exception" not in prefect.context
        pass


def test_switch_works_with_raise_on_exception():
    @prefect.task
    def return_b():
        return "b"

    tasks = {let: prefect.Task(name=let) for let in "abcde"}

    with Flow(name="test") as flow:
        res = switch(return_b, tasks)

    with raise_on_exception():
        flow_state = flow.run()


@pytest.mark.skipif(
    sys.platform == "win32", reason="is_serializable is not supported on Windows"
)
@pytest.mark.parametrize("obj", [5, "string", lambda x, y, z: None, bool])
def test_is_serializable_returns_true_for_basic_objects(obj):
    assert is_serializable(obj) is True


@pytest.mark.skipif(
    sys.platform == "win32", reason="is_serializable is not supported on Windows"
)
def test_is_serializable_returns_false_for_curried_functions_defined_in_main():
    script = textwrap.dedent(
        """
        from toolz import curry
        from prefect.utilities.debug import is_serializable

        @curry
        def f(x, y):
            pass

        g = f(y=5)
        assert is_serializable(g) is False
        """
    )
    assert_script_runs(script)


@pytest.mark.skipif(
    sys.platform == "win32", reason="is_serializable is not supported on Windows"
)
def test_is_serializable_with_raise_is_informative():
    script = textwrap.dedent(
        """
        import subprocess
        from toolz import curry
        from prefect.utilities.debug import is_serializable

        @curry
        def f(x, y):
            pass

        g = f(y=5)
        try:
            is_serializable(g, raise_on_error=True)
        except subprocess.CalledProcessError as exc:
            assert "has no attribute \'f\'" in exc.output.decode()
        """
    )
    assert_script_runs(script)


def test_is_serializable_raises_on_windows(monkeypatch):
    monkeypatch.setattr("prefect.utilities.debug.sys.platform", "win32")
    with pytest.raises(OSError):
        is_serializable(5)
