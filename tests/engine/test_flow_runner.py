import datetime
import queue
import random
import sys
import time

import pytest

from distutils.version import LooseVersion

import prefect
from prefect.core import Flow, Parameter, Task
from prefect.engine import FlowRunner, signals
from prefect.engine.cache_validators import duration_only
from prefect.engine.executors import Executor
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
    TriggerFailed,
)
from prefect.triggers import manual_only
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


def test_flow_runner_prevents_bad_throttle_values():
    runner = FlowRunner(flow=prefect.Flow())
    with pytest.raises(ValueError):
        runner.run(throttle=dict(x=5, y=0))

    with pytest.raises(ValueError):
        runner.run(throttle=dict(x=-5, y=6))

    with pytest.raises(ValueError) as exc:
        runner.run(throttle=dict(x=-5, y=0))

    base_msg= 'Cannot throttle tags "{0}", "{1}" - an invalid value less than 1 was provided.'
    assert str(exc.value) in [base_msg.format("x", "y"), base_msg.format("y", "x")] # for py34


@pytest.mark.skipif(
    sys.version_info < (3, 6), reason="Depends on ordered dictionaries of Python 3.6+"
)
def test_return_tasks_are_sorted():
    flow = prefect.Flow()
    a, b, c = SuccessTask(), SuccessTask(), SuccessTask()
    flow.add_edge(a, b)
    flow.add_edge(b, c)
    flow_runner = FlowRunner(flow=flow)
    result = flow_runner.run(return_tasks=[c, b, a])
    assert list(result.result.keys()) == [a, b, c]


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
    assert isinstance(flow_state, Success)
    assert isinstance(flow_state.result[task1], Pending)
    assert isinstance(flow_state.result[task2], Pending)


def test_flow_runner_remains_pending_if_tasks_are_retrying():
    # https://github.com/PrefectHQ/prefect/issues/19
    flow = prefect.Flow()
    task1 = SuccessTask()
    task2 = ErrorTask(max_retries=1)

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Pending)
    assert isinstance(flow_state.result[task1], Success)
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
    assert isinstance(flow_state, Pending)
    assert isinstance(flow_state.result[t1], Failed)
    assert isinstance(flow_state.result[t2], Retrying)


class TestFlowRunner_get_pre_run_state:
    def test_runs_as_expected(self):
        flow = prefect.Flow()
        task1 = SuccessTask()
        task2 = SuccessTask()
        flow.add_edge(task1, task2)

        state = FlowRunner(flow=flow).get_pre_run_state(state=Pending())
        assert isinstance(state, Running)

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
            FlowRunner(flow=flow).get_run_state(
                state=state,
                task_states={},
                start_tasks=[],
                return_tasks=[],
                task_contexts={},
                executor=None,
            )
        assert "not in a running state" in str(exc.value).lower()


class TestStartTasks:
    def test_start_tasks_ignores_triggers(self):
        f = Flow()
        t1, t2 = SuccessTask(), SuccessTask()
        f.add_edge(t1, t2)
        with raise_on_exception():
            state = FlowRunner(flow=f).run(task_states={t1: Failed()}, start_tasks=[t2])
        assert isinstance(state, Success)


class TestInputCaching:
    @pytest.mark.parametrize(
        "executor", ["local", "sync", "multi", "threaded"], indirect=True
    )
    def test_retries_use_cached_inputs(self, executor):
        with Flow() as f:
            a = CountTask()
            b = ReturnTask(max_retries=1)
            res = b(a())

        first_state = FlowRunner(flow=f).run(executor=executor, return_tasks=[res])
        assert isinstance(first_state, Pending)
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
        "executor", ["local", "sync", "multi", "threaded"], indirect=True
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
        "executor", ["local", "sync", "multi", "threaded"], indirect=True
    )
    def test_retries_caches_parameters_as_well(self, executor):
        with Flow() as f:
            x = Parameter("x")
            a = ReturnTask(max_retries=1)
            res = a(x)

        first_state = FlowRunner(flow=f).run(
            executor=executor, parameters=dict(x=1), return_tasks=[res]
        )
        assert isinstance(first_state, Pending)

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
        "executor", ["local", "sync", "multi", "threaded"], indirect=True
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
        assert isinstance(first_state, Pending)
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
        "executor", ["local", "sync", "multi", "threaded"], indirect=True
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
            cached_result_expiration=datetime.datetime.utcnow()
            + datetime.timedelta(days=1),
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


@pytest.mark.skipif(
    sys.version_info < (3, 5), reason="dask.distributed does not support Python 3.4"
)
class TestTagThrottling:
    @pytest.mark.parametrize("executor", ["multi", "threaded"], indirect=True)
    def test_throttle_via_time(self, executor):
        import distributed

        if executor.processes is False and LooseVersion(
            distributed.__version__
        ) < LooseVersion("1.23.0"):
            pytest.skip("https://github.com/dask/distributed/issues/2220")

        @prefect.task(tags=["io"])
        def record_times():
            res = []
            pause = random.randint(0, 75)
            for i in range(75):
                if i == pause:
                    time.sleep(0.1)
                res.append(time.time())
            return res

        with Flow() as flow:
            a, b = record_times(), record_times()

        state = flow.run(throttle=dict(io=1), executor=executor, return_tasks=[a, b])
        assert state.is_successful()

        times = [("alice", t) for t in state.result[a].result] + [
            ("bob", t) for t in state.result[b].result
        ]
        names = [name for name, time in sorted(times, key=lambda x: x[1])]

        alice_first = ["alice"] * 75 + ["bob"] * 75
        bob_first = ["bob"] * 75 + ["alice"] * 75

        assert (names == alice_first) or (names == bob_first)


def test_flow_runner_uses_user_provided_executor():
    t = SuccessTask()
    with Flow() as f:
        result = t()
    with raise_on_exception():
        with pytest.raises(NotImplementedError):
            FlowRunner(flow=f).run(executor=Executor())


@pytest.mark.parametrize("executor", ["multi", "threaded"], indirect=True)
def test_flow_runner_captures_and_exposes_dask_errors(executor):
    q = queue.Queue()

    @prefect.task
    def put():
        q.put(55)

    f = Flow(tasks=[put])
    state = f.run(executor=executor)

    assert state.is_failed()
    assert isinstance(state.message, TypeError)
    assert str(state.message) == "can't pickle _thread.lock objects"


@pytest.mark.parametrize("executor", ["multi", "threaded"], indirect=True)
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


@pytest.mark.parametrize("executor", ["multi", "threaded"], indirect=True)
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
