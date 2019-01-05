import collections
import datetime
import pendulum
import queue
import random
import sys
import time

import pytest

from distutils.version import LooseVersion

import prefect
from prefect.core import Flow, Parameter, Task
from prefect.engine import signals
from prefect.engine.flow_runner import ENDRUN, FlowRunner
from prefect.engine.cache_validators import duration_only
from prefect.engine.executors import Executor, LocalExecutor
from prefect.engine.state import (
    CachedState,
    Failed,
    Finished,
    Pending,
    Retrying,
    Running,
    Scheduled,
    Skipped,
    State,
    Success,
    TimedOut,
    TriggerFailed,
)
from prefect.triggers import manual_only, any_failed
from prefect.utilities.tests import raise_on_exception
from unittest.mock import MagicMock


class SuccessTask(Task):
    def run(self):
        return 1


class AddTask(Task):
    def run(self, x, y):  # pylint: disable=W0221
        return x + y


class CountTask(Task):
    call_count = 0

    def run(self):
        self.call_count += 1
        return self.call_count


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


class ReturnTask(Task):
    def run(self, x):
        return 1 / (x - 1)


class SlowTask(Task):
    def run(self, secs):
        time.sleep(secs)


def test_flow_runner_has_logger():
    r = FlowRunner(Flow())
    assert r.logger.name == "prefect.FlowRunner"


def test_flow_runner_runs_basic_flow_with_1_task():
    flow = prefect.Flow()
    task = SuccessTask()
    flow.add_task(task)
    flow_runner = FlowRunner(flow=flow)
    state = flow_runner.run(return_tasks=[task])
    assert state == Success(result={task: Success(result=1)})


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
    assert flow_state.result[task1] == Success(result=1)
    assert flow_state.result[task2] == Success(result=1)


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = SuccessTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Success)
    assert flow_state.result[task1] == Success(result=1)
    assert flow_state.result[task2] == Success(result=1)


def test_flow_runner_runs_base_task_class():
    flow = prefect.Flow()
    task1 = Task()
    task2 = Task()
    flow.add_edge(task1, task2)
    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Success)
    assert isinstance(flow_state.result[task1], Success)
    assert isinstance(flow_state.result[task2], Success)


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks_and_first_task_fails():
    flow = prefect.Flow()
    task1 = ErrorTask()
    task2 = SuccessTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.result[task1], Failed)
    assert isinstance(flow_state.result[task2], TriggerFailed)


def test_flow_runner_runs_flow_with_2_dependent_tasks_and_first_task_fails_and_second_has_trigger():
    flow = prefect.Flow()
    task1 = ErrorTask()
    task2 = SuccessTask(trigger=prefect.triggers.all_failed)

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(
        flow_state, Success
    )  # flow state is determined by terminal states
    assert isinstance(flow_state.result[task1], Failed)
    assert isinstance(flow_state.result[task2], Success)


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks_and_first_task_fails_with_FAIL():
    flow = prefect.Flow()
    task1 = RaiseFailTask()
    task2 = SuccessTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.result[task1], Failed)
    assert not isinstance(flow_state.result[task1], TriggerFailed)
    assert isinstance(flow_state.result[task2], TriggerFailed)


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks_and_second_task_fails():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = ErrorTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.result[task1], Success)
    assert isinstance(flow_state.result[task2], Failed)


def test_flow_runner_does_not_return_task_states_when_it_doesnt_run():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = ErrorTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(
        state=Success(result=5), return_tasks=[task1, task2]
    )
    assert isinstance(flow_state, Success)
    assert flow_state.result == 5


def test_flow_run_method_returns_task_states_even_if_it_doesnt_run():
    # https://github.com/PrefectHQ/prefect/issues/19
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = ErrorTask()

    flow.add_edge(task1, task2)

    flow_state = flow.run(state=Success(), return_tasks=[task1, task2])
    assert flow_state.is_successful()
    assert flow_state.result[task1].is_pending()
    assert flow_state.result[task2].is_pending()


def test_flow_runner_remains_running_if_tasks_are_retrying():
    # https://github.com/PrefectHQ/prefect/issues/19
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = ErrorTask(max_retries=1, retry_delay=datetime.timedelta(0))

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert flow_state.is_running()
    assert flow_state.result[task1].is_successful()
    assert isinstance(flow_state.result[task2], Retrying)


def test_flow_runner_doesnt_return_by_default():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = SuccessTask()
    flow.add_edge(task1, task2)
    res = flow.run()
    assert res.result == {}


def test_flow_runner_does_return_tasks_when_requested():
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = SuccessTask()
    flow.add_edge(task1, task2)
    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1])
    assert isinstance(flow_state, Success)
    assert isinstance(flow_state.result[task1], Success)


def test_required_parameters_must_be_provided():
    flow = prefect.Flow()
    y = prefect.Parameter("y")
    flow.add_task(y)
    flow_state = FlowRunner(flow=flow).run(return_tasks=[y])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.result[y], Failed)
    assert "required but not provided" in str(flow_state.result[y]).lower()


def test_parameters_are_placed_into_context():
    flow = prefect.Flow()
    y = prefect.Parameter("y", default=99)
    flow.add_task(y)
    flow_state = FlowRunner(flow=flow).run(return_tasks=[y], parameters=dict(y=42))
    assert isinstance(flow_state, Success)
    assert flow_state.result[y].result == 42


def test_parameters_are_placed_into_context_and_override_current_context():
    flow = prefect.Flow()
    y = prefect.Parameter("y", default=99)
    flow.add_task(y)
    with prefect.context(parameters=dict(y=88, z=55)):
        flow_state = FlowRunner(flow=flow).run(return_tasks=[y], parameters=dict(y=42))
    assert isinstance(flow_state, Success)
    assert flow_state.result[y].result == 42


def test_flow_run_state_determined_by_reference_tasks():
    flow = prefect.Flow()
    t1 = ErrorTask()
    t2 = SuccessTask(trigger=prefect.triggers.all_finished)
    flow.add_edge(t1, t2)

    flow.set_reference_tasks([t1])
    flow_state = flow.run(return_tasks=[t1, t2])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.result[t1], Failed)
    assert isinstance(flow_state.result[t2], Success)


def test_flow_run_state_not_determined_by_reference_tasks_if_terminal_tasks_are_not_finished():
    flow = prefect.Flow()
    t1 = ErrorTask()
    t2 = RaiseRetryTask(trigger=prefect.triggers.all_finished)
    flow.add_edge(t1, t2)

    flow.set_reference_tasks([t1])
    flow_state = flow.run(return_tasks=[t1, t2])
    assert flow_state.is_running()
    assert flow_state.result[t1].is_failed()
    assert isinstance(flow_state.result[t2], Retrying)


def test_flow_with_multiple_retry_tasks_doesnt_run_them_early():
    """
    t1 -> t2
    t1 -> t3

    Both t2 and t3 fail on initial run and request a retry. Starting the flow at t1 should
    only run t3, which requests an immediate retry, and not t2, which requests a retry in
    10 minutes.

    This tests a check on the TaskRunner, but which matters in Flows like this.
    """
    flow = prefect.Flow()
    t1 = Task()
    t2 = ErrorTask(retry_delay=datetime.timedelta(minutes=10), max_retries=1)
    t3 = ErrorTask(retry_delay=datetime.timedelta(minutes=0), max_retries=1)
    flow.add_edge(t1, t2)
    flow.add_edge(t1, t3)

    state1 = flow.run(return_tasks=flow.tasks)

    assert isinstance(state1.result[t2], Retrying)
    assert isinstance(state1.result[t3], Retrying)

    state2 = flow.run(return_tasks=flow.tasks, task_states=state1.result)

    assert isinstance(state2.result[t2], Retrying)
    assert state2.result[t2] == state1.result[t2]  # state is not modified at all
    assert isinstance(state2.result[t3], Failed)  # this task ran


def test_flow_runner_makes_copy_of_task_results_dict():
    """
    Ensure the flow runner copies the task_results dict rather than modifying it inplace
    """
    flow = prefect.Flow()
    t1, t2 = prefect.Task(), prefect.Task()
    flow.add_edge(t1, t2)

    task_states = {t1: Pending()}
    state = flow.run(task_states=task_states, return_tasks=[t1])
    assert state.result[t1] == Success()
    assert task_states == {t1: Pending()}


class TestCheckFlowPendingOrRunning:
    @pytest.mark.parametrize("state", [Pending(), Running(), Retrying(), Scheduled()])
    def test_pending_or_running_are_ok(self, state):
        flow = prefect.Flow(tasks=[prefect.Task()])
        new_state = FlowRunner(flow=flow).check_flow_is_pending_or_running(state=state)
        assert new_state is state

    @pytest.mark.parametrize("state", [Finished(), Success(), Failed(), Skipped()])
    def test_not_pending_or_running_raise_endrun(self, state):
        flow = prefect.Flow(tasks=[prefect.Task()])
        with pytest.raises(ENDRUN):
            FlowRunner(flow=flow).check_flow_is_pending_or_running(state=state)


class TestSetFlowToRunning:
    @pytest.mark.parametrize("state", [Pending(), Retrying()])
    def test_pending_becomes_running(self, state):
        flow = prefect.Flow(tasks=[prefect.Task()])
        new_state = FlowRunner(flow=flow).set_flow_to_running(state=state)
        assert new_state.is_running()

    def test_running_stays_running(self):
        state = Running()
        flow = prefect.Flow(tasks=[prefect.Task()])
        new_state = FlowRunner(flow=flow).set_flow_to_running(state=state)
        assert new_state.is_running()

    @pytest.mark.parametrize("state", [Finished(), Success(), Failed(), Skipped()])
    def test_other_states_raise_endrun(self, state):
        flow = prefect.Flow(tasks=[prefect.Task()])
        with pytest.raises(ENDRUN):
            FlowRunner(flow=flow).set_flow_to_running(state=state)


class TestRunFlowStep:
    def test_running_state_finishes(self):
        flow = prefect.Flow(tasks=[prefect.Task()])
        new_state = FlowRunner(flow=flow).get_flow_run_state(
            state=Running(),
            task_states={},
            start_tasks=[],
            return_tasks=set(),
            executor=LocalExecutor(),
        )
        assert new_state.is_successful()

    @pytest.mark.parametrize(
        "state", [Pending(), Retrying(), Finished(), Success(), Failed(), Skipped()]
    )
    def test_other_states_raise_endrun(self, state):
        flow = prefect.Flow(tasks=[prefect.Task()])
        with pytest.raises(ENDRUN):
            FlowRunner(flow=flow).get_flow_run_state(
                state=state,
                task_states={},
                start_tasks=[],
                return_tasks=set(),
                executor=Executor(),
            )

    def test_determine_final_state_has_final_say(self):
        class MyFlowRunner(FlowRunner):
            def determine_final_state(self, *args, **kwargs):
                return Failed("Very specific error message")

        flow = prefect.Flow(tasks=[prefect.Task()])
        new_state = MyFlowRunner(flow=flow).get_flow_run_state(
            state=Running(),
            task_states={},
            start_tasks=[],
            return_tasks=set(),
            executor=LocalExecutor(),
        )
        assert new_state.is_failed()
        assert new_state.message == "Very specific error message"


class TestStartTasks:
    def test_start_tasks_ignores_triggers(self):
        f = Flow()
        t1, t2 = SuccessTask(), SuccessTask()
        f.add_edge(t1, t2)
        with raise_on_exception():
            state = FlowRunner(flow=f).run(task_states={t1: Failed()}, start_tasks=[t2])
        assert isinstance(state, Success)

    def test_can_start_from_mapped_tasks(self):
        @prefect.task
        def my_list():
            return [1, 2, 3]

        @prefect.task
        def add(x):
            return x + 1

        with Flow() as f:
            res = my_list()

        state = FlowRunner(flow=f).run(return_tasks=[res])

        with f:
            final = add.map(res)

        final_state = FlowRunner(flow=f).run(
            return_tasks=[final], start_tasks=[final], task_states=state.result
        )
        assert [s.result for s in final_state.result[final]] == [2, 3, 4]


class TestInputCaching:
    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_retries_use_cached_inputs(self, executor):
        with Flow() as f:
            a = CountTask()
            b = ReturnTask(max_retries=1, retry_delay=datetime.timedelta(0))
            res = b(a())

        first_state = FlowRunner(flow=f).run(executor=executor, return_tasks=[res])
        assert first_state.is_running()
        b_state = first_state.result[res]
        b_state.cached_inputs = dict(x=2)  # artificially alter state
        with raise_on_exception():  # without caching we'd expect a KeyError
            second_state = FlowRunner(flow=f).run(
                executor=executor,
                return_tasks=[res],
                start_tasks=[res],
                task_states={res: b_state},
            )
        assert isinstance(second_state, Success)
        assert second_state.result[res].result == 1

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_retries_only_uses_cache_data(self, executor):
        with Flow() as f:
            t1 = Task()
            t2 = AddTask()
            f.add_edge(t1, t2)

        state = FlowRunner(flow=f).run(
            executor=executor,
            task_states={t2: Retrying(cached_inputs=dict(x=4, y=1))},
            start_tasks=[t2],
            return_tasks=[t2],
        )
        assert isinstance(state, Success)
        assert state.result[t2].result == 5

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_retries_caches_parameters_as_well(self, executor):
        with Flow() as f:
            x = Parameter("x")
            a = ReturnTask(max_retries=1, retry_delay=datetime.timedelta(0))
            res = a(x)

        first_state = FlowRunner(flow=f).run(
            executor=executor, parameters=dict(x=1), return_tasks=[res]
        )
        assert first_state.is_running()

        res_state = first_state.result[res]
        res_state.cached_inputs = dict(x=2)  # artificially alter state

        second_state = FlowRunner(flow=f).run(
            executor=executor,
            parameters=dict(x=1),
            return_tasks=[res],
            start_tasks=[res],
            task_states={res: first_state.result[res]},
        )
        assert isinstance(second_state, Success)
        assert second_state.result[res].result == 1

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_manual_only_trigger_caches_inputs(self, executor):
        with Flow() as f:
            x = Parameter("x")
            inp = SuccessTask()
            t = AddTask(trigger=manual_only)
            res = t(x, inp)

        first_state = FlowRunner(flow=f).run(
            executor=executor, parameters=dict(x=11), return_tasks=[res]
        )
        assert first_state.is_running()
        second_state = FlowRunner(flow=f).run(
            executor=executor,
            parameters=dict(x=1),
            return_tasks=[res],
            start_tasks=[res],
            task_states={res: first_state.result[res]},
        )
        assert isinstance(second_state, Success)
        assert second_state.result[res].result == 12


class TestOutputCaching:
    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_providing_cachedstate_with_simple_example(self, executor):
        class TestTask(Task):
            call_count = 0

            def run(self, x, s):
                self.call_count += 1
                return self.call_count

        with Flow() as f:
            y = TestTask(
                cache_validator=duration_only, cache_for=datetime.timedelta(days=1)
            )
            x = Parameter("x")
            s = SuccessTask()
            f.add_edge(x, y, key="x")
            f.add_edge(s, y, key="s")

        state = CachedState(
            cached_result_expiration=pendulum.now("utc") + datetime.timedelta(days=1),
            cached_result=100,
        )
        flow_state = FlowRunner(flow=f).run(
            executor=executor,
            parameters=dict(x=1),
            return_tasks=[y],
            task_states={y: state},
        )
        assert isinstance(flow_state, Success)
        assert flow_state.result[y].result == 100


class TestReturnFailed:
    def test_return_failed_works_when_all_fail(self):
        with Flow() as f:
            s = SuccessTask()
            e = ErrorTask()
            s.set_upstream(e)
        state = FlowRunner(flow=f).run(return_failed=True)
        assert state.is_failed()
        assert e in state.result
        assert s in state.result

    def test_return_failed_works_when_non_terminal_fails(self):
        with Flow() as f:
            s = SuccessTask(trigger=any_failed)
            e = ErrorTask()
            s.set_upstream(e)
        state = FlowRunner(flow=f).run(return_failed=True)
        assert state.is_successful()
        assert e in state.result
        assert s not in state.result

    def test_return_failed_works_with_mapping(self):
        @prefect.task
        def div(x):
            return 1 / x

        @prefect.task
        def gimme(x):
            return x

        with Flow() as f:
            res = gimme.map(div.map(x=[1, 0, 42]))

        state = FlowRunner(flow=f).run(return_failed=True)
        assert state.is_failed()
        assert len(state.result) == 2
        assert all([len(v) == 3 for v in state.result.values()])

    def test_return_failed_doesnt_duplicate(self):
        with Flow() as f:
            s = SuccessTask()
            e = ErrorTask()
            s.set_upstream(e)
        state = FlowRunner(flow=f).run(return_tasks=f.tasks, return_failed=True)
        assert state.is_failed()
        assert len(state.result) == 2

    def test_return_failed_includes_retries(self):
        with Flow() as f:
            s = SuccessTask()
            e = ErrorTask(max_retries=1, retry_delay=datetime.timedelta(0))
            s.set_upstream(e)
        state = FlowRunner(flow=f).run(return_failed=True)
        assert state.is_running()
        assert e in state.result
        assert isinstance(state.result[e], Retrying)


class TestRunCount:
    def test_run_count_updates_after_each_retry(self):
        flow = Flow()
        t1 = ErrorTask(max_retries=2, retry_delay=datetime.timedelta(0))
        flow.add_task(t1)

        state1 = FlowRunner(flow=flow).run(return_tasks=[t1])
        assert isinstance(state1.result[t1], Retrying)
        assert state1.result[t1].run_count == 1

        state2 = FlowRunner(flow=flow).run(return_tasks=[t1], task_states=state1.result)
        assert isinstance(state2.result[t1], Retrying)
        assert state2.result[t1].run_count == 2

    def test_run_count_tracked_via_retry_states(self):
        flow = Flow()
        t1 = ErrorTask(max_retries=1, retry_delay=datetime.timedelta(0))
        t2 = ErrorTask(max_retries=2, retry_delay=datetime.timedelta(0))
        flow.add_task(t1)
        flow.add_task(t2)

        # first run
        state1 = FlowRunner(flow=flow).run(return_tasks=[t1, t2])
        assert state1.is_running()
        assert isinstance(state1.result[t1], Retrying)
        assert state1.result[t1].run_count == 1
        assert isinstance(state1.result[t2], Retrying)
        assert state1.result[t2].run_count == 1

        # second run
        state2 = FlowRunner(flow=flow).run(
            task_states=state1.result, return_tasks=[t1, t2]
        )
        assert state2.is_running()
        assert isinstance(state2.result[t1], Failed)
        assert isinstance(state2.result[t2], Retrying)
        assert state2.result[t2].run_count == 2

        # third run
        state3 = FlowRunner(flow=flow).run(
            task_states=state2.result, return_tasks=[t1, t2]
        )
        assert state3.is_failed()
        assert isinstance(state3.result[t1], Failed)
        assert isinstance(state3.result[t2], Failed)


def test_flow_runner_uses_user_provided_executor():
    t = SuccessTask()
    with Flow() as f:
        result = t()
    with raise_on_exception():
        with pytest.raises(NotImplementedError):
            FlowRunner(flow=f).run(executor=Executor())


@pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
def test_flow_runner_captures_and_exposes_dask_errors(executor):
    q = queue.Queue()

    @prefect.task
    def put():
        q.put(55)

    f = Flow(tasks=[put])
    state = f.run(executor=executor)

    assert state.is_failed()
    assert isinstance(state.result, TypeError)
    assert str(state.result) == "can't pickle _thread.lock objects"


@pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
def test_flow_runner_allows_for_parallelism_with_prints(capsys, executor):

    # related:
    # "https://stackoverflow.com/questions/52121686/why-is-dask-distributed-not-parallelizing-the-first-run-of-my-workflow"

    @prefect.task
    def alice():
        for _ in range(75):
            print("alice")

    @prefect.task
    def bob():
        for _ in range(75):
            print("bob")

    with Flow() as flow:
        alice(), bob()

    state = flow.run(executor=executor)
    assert state.is_successful()
    captured = capsys.readouterr()

    alice_first = ["alice"] * 75 + ["bob"] * 75
    bob_first = ["bob"] * 75 + ["alice"] * 75
    assert captured.out != alice_first
    assert captured.out != bob_first


@pytest.mark.xfail(reason="This test fails on CircleCI for Python 3.5+")
@pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
def test_flow_runner_allows_for_parallelism_with_times(executor):

    # related:
    # "https://stackoverflow.com/questions/52121686/why-is-dask-distributed-not-parallelizing-the-first-run-of-my-workflow"

    @prefect.task
    def record_times():
        res = []
        pause = random.randint(0, 75)
        for i in range(75):
            if i == pause:
                time.sleep(0.1)  # add a little noise
            res.append(time.time())
        return res

    with Flow() as flow:
        a, b = record_times(), record_times()

    state = flow.run(executor=executor, return_tasks=[a, b])
    assert state.is_successful()

    times = [("alice", t) for t in state.result[a].result] + [
        ("bob", t) for t in state.result[b].result
    ]
    names = [name for name, time in sorted(times, key=lambda x: x[1])]

    alice_first = ["alice"] * 75 + ["bob"] * 75
    bob_first = ["bob"] * 75 + ["alice"] * 75

    assert names != alice_first
    assert names != bob_first


@pytest.mark.parametrize("executor", ["mproc", "mthread", "sync"], indirect=True)
def test_flow_runner_properly_provides_context_to_task_runners(executor):
    @prefect.task
    def my_name():
        return prefect.context.get("my_name")

    @prefect.task
    def flow_name():
        return prefect.context.get("flow_name")

    flow = Flow(name="test-dummy", tasks=[flow_name, my_name])
    with prefect.context(my_name="marvin"):
        res = flow.run(executor=executor, return_tasks=flow.tasks)

    assert res.result[flow_name].result == "test-dummy"
    assert res.result[my_name].result == "marvin"

    with Flow("test-map") as f:
        tt = flow_name.map(upstream_tasks=[my_name])

    with prefect.context(my_name="mapped-marvin"):
        res = f.run(executor=executor, return_tasks=f.tasks)

    assert res.result[my_name].result == "mapped-marvin"
    assert res.result[tt][0].result == "test-map"


@pytest.mark.parametrize("executor", ["local", "mthread", "sync"], indirect=True)
def test_flow_runner_handles_timeouts(executor):
    sleeper = SlowTask(timeout=datetime.timedelta(seconds=1))

    with Flow() as flow:
        res = sleeper(3)

    state = FlowRunner(flow=flow).run(return_tasks=[res], executor=executor)
    assert state.is_failed()
    assert isinstance(state.result[res], TimedOut)
    assert "timed out" in state.result[res].message
    assert isinstance(state.result[res].result, TimeoutError)


@pytest.mark.skipif(
    sys.version_info < (3, 5), reason="dask.distributed does not support Python 3.4"
)
def test_flow_runner_handles_timeout_error_with_mproc(mproc):
    sleeper = SlowTask(timeout=datetime.timedelta(seconds=1))

    with Flow() as flow:
        res = sleeper(3)

    state = FlowRunner(flow=flow).run(return_tasks=[res], executor=mproc)
    assert state.is_failed()
    assert isinstance(state.result[res].result, AssertionError)


@pytest.mark.parametrize("executor", ["local", "mthread", "sync"], indirect=True)
def test_flow_runner_handles_mapped_timeouts(executor):
    sleeper = SlowTask(timeout=datetime.timedelta(seconds=1))

    with Flow() as flow:
        res = sleeper.map([0, 2, 3])

    state = FlowRunner(flow=flow).run(return_tasks=[res], executor=executor)
    assert state.is_failed()

    mapped_states = state.result[res]
    assert mapped_states[0].is_successful()
    for fstate in mapped_states[1:]:
        assert fstate.is_failed()
        assert isinstance(fstate.result, TimeoutError)


handler_results = collections.defaultdict(lambda: 0)


@pytest.fixture(autouse=True)
def clear_handler_results():
    handler_results.clear()


def flow_handler(flow, old_state, new_state):
    """state change handler for flows that increments a value by 1"""
    assert isinstance(flow, Flow)
    assert isinstance(old_state, State)
    assert isinstance(new_state, State)
    handler_results["Flow"] += 1
    return new_state


def flow_runner_handler(flow_runner, old_state, new_state):
    """state change handler for flow runners that increments a value by 1"""
    assert isinstance(flow_runner, FlowRunner)
    assert isinstance(old_state, State)
    assert isinstance(new_state, State)
    handler_results["FlowRunner"] += 1
    return new_state


class TestFlowStateHandlers:
    def test_flow_handlers_are_called(self):
        flow = Flow(state_handlers=[flow_handler])
        FlowRunner(flow=flow).run()
        # the flow changed state twice: Pending -> Running -> Success
        assert handler_results["Flow"] == 2

    def test_multiple_flow_handlers_are_called(self):
        flow = Flow(state_handlers=[flow_handler, flow_handler])
        FlowRunner(flow=flow).run()
        # each flow changed state twice: Pending -> Running -> Success
        assert handler_results["Flow"] == 4

    def test_multiple_flow_handlers_are_called_in_sequence(self):
        # the second flow handler will assert the result of the first flow handler is a state
        # and raise an error, as long as the flow_handlers are called in sequence on the
        # previous result
        flow = Flow(state_handlers=[lambda *a: None, flow_handler])
        with pytest.raises(AssertionError):
            with prefect.utilities.tests.raise_on_exception():
                FlowRunner(flow=flow).run()

    def test_task_handler_that_doesnt_return_state(self):
        flow = Flow(state_handlers=[lambda *a: None])
        # raises an attribute error because it tries to access a property of the state that
        # doesn't exist on None
        with pytest.raises(AttributeError):
            with prefect.utilities.tests.raise_on_exception():
                FlowRunner(flow=flow).run()


class TestFlowRunnerStateHandlers:
    def test_task_runner_handlers_are_called(self):
        FlowRunner(flow=Flow(), state_handlers=[flow_runner_handler]).run()
        # the flow changed state twice: Pending -> Running -> Success
        assert handler_results["FlowRunner"] == 2

    def test_multiple_task_runner_handlers_are_called(self):
        FlowRunner(
            flow=Flow(), state_handlers=[flow_runner_handler, flow_runner_handler]
        ).run()
        # each flow changed state twice: Pending -> Running -> Success
        assert handler_results["FlowRunner"] == 4

    def test_multiple_task_runner_handlers_are_called_in_sequence(self):
        # the second flow handler will assert the result of the first flow handler is a state
        # and raise an error, as long as the flow_handlers are called in sequence on the
        # previous result
        with pytest.raises(AssertionError):
            with prefect.utilities.tests.raise_on_exception():
                FlowRunner(
                    flow=Flow(), state_handlers=[lambda *a: None, flow_runner_handler]
                ).run()

    def test_task_runner_handler_that_doesnt_return_state(self):
        # raises an attribute error because it tries to access a property of the state that
        # doesn't exist on None
        with pytest.raises(AttributeError):
            with prefect.utilities.tests.raise_on_exception():
                FlowRunner(flow=Flow(), state_handlers=[lambda *a: None]).run()

    def test_task_handler_that_raises_signal_is_trapped(self):
        def handler(flow, old, new):
            raise signals.FAIL()

        flow = Flow(state_handlers=[handler])
        state = FlowRunner(flow=flow).run()
        assert state.is_failed()

    def test_task_handler_that_has_error_is_trapped(self):
        def handler(flow, old, new):
            1 / 0

        flow = Flow(state_handlers=[handler])
        state = FlowRunner(flow=flow).run()
        assert state.is_failed()


def test_improper_use_of_unmapped_fails_gracefully():
    add = AddTask()
    x = Parameter("x", default=[1, 2, 3])
    with Flow() as f:
        res = add.map(x, y=8)  # incorrect, should use `unmapped`

    state = FlowRunner(flow=f).run(return_tasks=f.tasks)
    assert state.is_failed()

    # make sure tasks were still returned with the correct states
    x_state = state.result.pop(x)
    res_state = state.result.pop(res)
    y_state = state.result.popitem()[1]
    assert x_state.is_successful()
    assert x_state.result == [1, 2, 3]
    assert y_state.is_successful()
    assert y_state.result == 8
    assert res_state.is_failed()


def test_all_pipeline_method_steps_are_called():

    pipeline = [
        "initialize_run",
        "check_flow_is_pending_or_running",
        "set_flow_to_running",
        "get_flow_run_state",
    ]

    runner = FlowRunner(Flow())

    for method in pipeline:
        setattr(runner, method, MagicMock())

    # initialize run is unpacked, which MagicMocks dont support
    runner.initialize_run = MagicMock(return_value=(MagicMock(), MagicMock()))

    runner.run()

    for method in pipeline:
        assert getattr(runner, method).call_count == 1


def test_endrun_raised_in_initialize_is_caught_correctly():
    class BadInitializeRunner(FlowRunner):
        def initialize_run(self, *args, **kwargs):
            raise ENDRUN(state=Pending())

    res = BadInitializeRunner(Flow()).run()
    assert res.is_pending()


def test_task_runner_cls_uses_default_function_if_none():
    fr = FlowRunner(flow=None, task_runner_cls=None)
    assert fr.task_runner_cls is prefect.engine.get_default_task_runner_class()

    with prefect.utilities.configuration.set_temporary_config(
        {"engine.task_runner.default_class": "prefect.engine.cloud.CloudTaskRunner"}
    ):
        fr = FlowRunner(flow=None, task_runner_cls=None)
        assert fr.task_runner_cls is prefect.engine.get_default_task_runner_class()


def test_flow_run_uses_default_flow_runner(monkeypatch):
    x = MagicMock()
    monkeypatch.setattr("prefect.engine.flow_runner.FlowRunner", x)

    with prefect.utilities.configuration.set_temporary_config(
        {"engine.flow_runner.default_class": "prefect.engine.x"}
    ):
        prefect.Flow().run()

    assert x.call_count == 1
