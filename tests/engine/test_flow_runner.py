import datetime

import pytest

import prefect
from prefect.core import Flow, Task
from prefect.engine import FlowRunner, signals
from prefect.engine.state import (
    Failed,
    Finished,
    Pending,
    Retrying,
    Running,
    Scheduled,
    Skipped,
    State,
    Success,
    TriggerFailed,
)


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


def test_flow_runner_runs_basic_flow_with_1_task():
    flow = prefect.Flow()
    task = SuccessTask()
    flow.add_task(task)
    flow_runner = FlowRunner(flow=flow)
    state = flow_runner.run(return_tasks=[task])
    assert state == Success(data={task: Success(data=1)})


def test_flow_runner_with_no_return_tasks():
    """
    Make sure FlowRunner accepts return_tasks=None and doesn't raise early error
    """
    flow = prefect.Flow()
    task = SuccessTask()
    flow.add_task(task)
    flow_runner = FlowRunner(flow=flow)
    assert flow_runner.run(return_tasks=None)


def test_flow_runner_with_invalid_return_tasks():
    flow = prefect.Flow()
    task = SuccessTask()
    flow.add_task(task)
    flow_runner = FlowRunner(flow=flow)
    with pytest.raises(ValueError):
        flow_runner.run(return_tasks=[1])


def test_flow_runner_runs_basic_flow_with_2_independent_tasks():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = SuccessTask()

    flow.add_task(task1)
    flow.add_task(task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Success)
    assert flow_state.data[task1] == Success(data=1)
    assert flow_state.data[task2] == Success(data=1)


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = SuccessTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Success)
    assert flow_state.data[task1] == Success(data=1)
    assert flow_state.data[task2] == Success(data=1)


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks_and_first_task_fails():
    flow = prefect.Flow()
    task1 = ErrorTask()
    task2 = SuccessTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.data[task1], Failed)
    assert isinstance(flow_state.data[task2], TriggerFailed)


def test_flow_runner_runs_flow_with_2_dependent_tasks_and_first_task_fails_and_second_has_trigger():
    flow = prefect.Flow()
    task1 = ErrorTask()
    task2 = SuccessTask(trigger=prefect.triggers.all_failed)

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(
        flow_state, Success
    )  # flow state is determined by terminal states
    assert isinstance(flow_state.data[task1], Failed)
    assert isinstance(flow_state.data[task2], Success)


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks_and_first_task_fails_with_FAIL():
    flow = prefect.Flow()
    task1 = RaiseFailTask()
    task2 = SuccessTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.data[task1], Failed)
    assert not isinstance(flow_state.data[task1], TriggerFailed)
    assert isinstance(flow_state.data[task2], TriggerFailed)


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks_and_second_task_fails():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = ErrorTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.data[task1], Success)
    assert isinstance(flow_state.data[task2], Failed)


def test_flow_runner_does_not_return_task_states_when_it_doesnt_run():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = ErrorTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(
        state=Success(data=5), return_tasks=[task1, task2]
    )
    assert isinstance(flow_state, Success)
    assert flow_state.data == 5


def test_flow_run_method_returns_task_states_even_if_it_doesnt_run():
    # https://github.com/PrefectHQ/prefect/issues/19
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = ErrorTask()

    flow.add_edge(task1, task2)

    flow_state = flow.run(state=Success(), return_tasks=[task1, task2])
    assert isinstance(flow_state, Success)
    assert isinstance(flow_state.data[task1], Pending)
    assert isinstance(flow_state.data[task2], Pending)


def test_flow_runner_remains_pending_if_tasks_are_retrying():
    # https://github.com/PrefectHQ/prefect/issues/19
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = ErrorTask(max_retries=1)

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Pending)
    assert isinstance(flow_state.data[task1], Success)
    assert isinstance(flow_state.data[task2], Retrying)


def test_flow_runner_doesnt_return_by_default():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = SuccessTask()
    flow.add_edge(task1, task2)
    res = flow.run()
    assert res.data == {}


def test_flow_runner_does_return_tasks_when_requested():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = SuccessTask()
    flow.add_edge(task1, task2)
    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1])
    assert isinstance(flow_state, Success)
    assert isinstance(flow_state.data[task1], Success)


def test_required_parameters_must_be_provided():
    flow = prefect.Flow()
    y = prefect.Parameter("y")
    flow.add_task(y)
    flow_state = FlowRunner(flow=flow).run()
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.message, prefect.engine.signals.FAIL)
    assert "required parameter" in str(flow_state.message).lower()


def test_missing_parameter_returns_failed_with_no_data():
    flow = prefect.Flow()
    task = AddTask()
    y = prefect.Parameter("y")
    task.set_dependencies(flow, keyword_tasks=dict(x=1, y=y))
    flow_state = FlowRunner(flow=flow).run(return_tasks=[task])
    assert isinstance(flow_state, Failed)
    assert flow_state.data is None


def test_missing_parameter_returns_failed_with_pending_tasks_if_called_from_flow():
    flow = prefect.Flow()
    task = AddTask()
    y = prefect.Parameter("y")
    task.set_dependencies(flow, keyword_tasks=dict(x=1, y=y))
    flow_state = flow.run(return_tasks=[task])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.data[task], Pending)


def test_missing_parameter_error_is_surfaced():
    flow = prefect.Flow()
    task = AddTask()
    y = prefect.Parameter("y")
    task.set_dependencies(flow, keyword_tasks=dict(x=1, y=y))
    msg = flow.run().message
    assert isinstance(msg, prefect.engine.signals.FAIL)
    assert "required parameter" in str(msg).lower()


class TestFlowRunner_get_pre_run_state:
    def test_runs_as_expected(self):
        flow = prefect.Flow()
        task1 = SuccessTask()
        task2 = SuccessTask()
        flow.add_edge(task1, task2)

        state = FlowRunner(flow=flow).get_pre_run_state(state=Pending())
        assert isinstance(state, Running)

    def test_raises_fail_if_required_parameters_missing(self):
        flow = prefect.Flow()
        y = prefect.Parameter("y")
        flow.add_task(y)
        flow_state = FlowRunner(flow=flow).get_pre_run_state(state=Pending())
        assert isinstance(flow_state, Failed)
        assert isinstance(flow_state.message, prefect.engine.signals.FAIL)
        assert "required parameter" in str(flow_state.message).lower()

    @pytest.mark.parametrize("state", [Success(), Failed()])
    def test_raise_dontrun_if_state_is_finished(self, state):
        flow = prefect.Flow()
        task1 = SuccessTask()
        task2 = SuccessTask()
        flow.add_edge(task1, task2)

        with pytest.raises(signals.DONTRUN) as exc:
            FlowRunner(flow=flow).get_pre_run_state(state=state)
        assert "already finished" in str(exc.value).lower()

    def test_raise_dontrun_for_unknown_state(self):
        class MyState(State):
            pass

        flow = prefect.Flow()
        task1 = SuccessTask()
        task2 = SuccessTask()
        flow.add_edge(task1, task2)

        with pytest.raises(signals.DONTRUN) as exc:
            FlowRunner(flow=flow).get_pre_run_state(state=MyState())
        assert "not ready to run" in str(exc.value).lower()


class TestFlowRunner_get_run_state:
    @pytest.mark.parametrize("state", [Pending(), Failed(), Success()])
    def test_raises_dontrun_if_not_running(self, state):
        flow = prefect.Flow()
        task1 = SuccessTask()
        task2 = SuccessTask()
        flow.add_edge(task1, task2)

        with pytest.raises(signals.DONTRUN) as exc:
            FlowRunner(flow=flow).get_run_state(state=state)
        assert "not in a running state" in str(exc.value).lower()
