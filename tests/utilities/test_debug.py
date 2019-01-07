from datetime import timedelta
import os
import pytest
import subprocess
import tempfile
import textwrap

import prefect
from prefect.core import Flow, Task
from prefect.engine import FlowRunner, TaskRunner, state
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.debug import (
    is_serializable,
    raise_on_exception,
    make_return_failed_handler,
)


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
    flow = Flow()
    flow.add_task(MathTask())
    try:
        assert "raise_on_exception" not in prefect.context
        with raise_on_exception():
            assert "raise_on_exception" in prefect.context
            flow.run()
    except ZeroDivisionError:
        assert "raise_on_exception" not in prefect.context
        pass


@pytest.mark.parametrize("obj", [5, "string", lambda x, y, z: None, bool])
def test_is_serializable_returns_true_for_basic_objects(obj):
    assert is_serializable(obj) is True


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


class TestReturnFailedStateHandler:
    @pytest.fixture(autouse=True)
    def use_local_executor(self):
        with set_temporary_config(
            {"engine.executor.default_class": prefect.engine.executors.LocalExecutor}
        ):
            yield

    def test_return_failed_works_when_all_fail(self):
        with Flow() as f:
            e = ErrorTask()
            s1 = Task()
            s2 = Task()
            s1.set_upstream(e)
            s2.set_upstream(s1)
        return_tasks = set()
        state = FlowRunner(flow=f).run(
            return_tasks=return_tasks,
            task_runner_state_handlers=[make_return_failed_handler(return_tasks)],
        )
        assert state.is_failed()
        assert e in state.result
        assert s1 in state.result
        assert s2 in state.result
        assert return_tasks == set([e, s1, s2])

    def test_return_failed_works_when_all_fail_from_flow_run_method(self):
        with Flow() as f:
            e = ErrorTask()
            s1 = Task()
            s2 = Task()
            s1.set_upstream(e)
            s2.set_upstream(s1)
        return_tasks = set()
        state = f.run(
            return_tasks=return_tasks,
            task_runner_state_handlers=[make_return_failed_handler(return_tasks)],
        )
        assert state.is_failed()
        assert e in state.result
        assert s1 in state.result
        assert s2 in state.result
        assert return_tasks == set([e, s1, s2])

    def test_return_failed_works_when_non_terminal_fails(self):
        with Flow() as f:
            e = ErrorTask()
            t = Task(trigger=prefect.triggers.always_run)
            t.set_upstream(e)
        return_tasks = set()
        state = FlowRunner(flow=f).run(
            return_tasks=return_tasks,
            task_runner_state_handlers=[make_return_failed_handler(return_tasks)],
        )
        assert state.is_successful()
        assert e in state.result
        assert t not in state.result
        assert return_tasks == set([e])

    def test_return_failed_works_with_mapping(self):
        @prefect.task
        def div(x):
            return 1 / x

        @prefect.task
        def gimme(x):
            return x

        with Flow() as f:
            d = div.map(x=[1, 0, 42])
            res = gimme.map(d)

        return_tasks = set()
        state = FlowRunner(flow=f).run(
            return_tasks=return_tasks,
            task_runner_state_handlers=[make_return_failed_handler(return_tasks)],
        )
        assert state.is_failed()
        assert res in state.result
        assert d in state.result

        # we return the full mapped task
        assert state.result[d].is_mapped()
        assert any(s.is_failed() for s in state.result[d].map_states)
        assert state.result[res].is_mapped()
        assert any(s.is_failed() for s in state.result[res].map_states)

    def test_return_failed_works_for_retries(self):

        with Flow() as f:
            e = ErrorTask(max_retries=1, retry_delay=timedelta(0))
            s1 = Task(max_retries=1, retry_delay=timedelta(0))
            s1.set_upstream(e)
        return_tasks = set()
        state = FlowRunner(flow=f).run(
            return_tasks=return_tasks,
            task_runner_state_handlers=[make_return_failed_handler(return_tasks)],
        )
        assert state.is_running()
        assert e in state.result
        assert s1 not in state.result
