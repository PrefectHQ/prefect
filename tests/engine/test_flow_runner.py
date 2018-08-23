import datetime
import random
import sys
import time

import pytest

import prefect
from prefect.core import Flow, Parameter, Task
from prefect.engine import FlowRunner, signals
from prefect.engine.cache_validators import duration_only
from prefect.engine.executors import DaskExecutor, Executor, LocalExecutor
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


@pytest.fixture(
    params=[
        DaskExecutor(scheduler="synchronous"),
        DaskExecutor(scheduler="threads"),
        DaskExecutor(scheduler="processes"),
        LocalExecutor(),
    ],
    ids=["dask-sync", "dask-threads", "dask-process", "local"],
)
def executor(request):
    return request.param


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
    assert flow_state.result is None


def test_missing_parameter_returns_failed_with_pending_tasks_if_called_from_flow():
    flow = prefect.Flow()
    task = AddTask()
    y = prefect.Parameter("y")
    task.set_dependencies(flow, keyword_tasks=dict(x=1, y=y))
    flow_state = flow.run(return_tasks=[task])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.result[task], Pending)


def test_missing_parameter_error_is_surfaced():
    flow = prefect.Flow()
    task = AddTask()
    y = prefect.Parameter("y")
    task.set_dependencies(flow, keyword_tasks=dict(x=1, y=y))
    msg = flow.run().message
    assert isinstance(msg, prefect.engine.signals.FAIL)
    assert "required parameter" in str(msg).lower()


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


class TestStartTasks:
    def test_start_tasks_ignores_triggers(self):
        f = Flow()
        t1, t2 = SuccessTask(), SuccessTask()
        f.add_edge(t1, t2)
        with raise_on_exception():
            state = FlowRunner(flow=f).run(task_states={t1: Failed()}, start_tasks=[t2])
        assert isinstance(state, Success)


class TestInputCaching:
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


class TestTagThrottling:
    @pytest.mark.parametrize("num", [1, 2])
    @pytest.mark.parametrize("scheduler", ["threads", "processes"])
    def test_throttle_via_order(self, scheduler, num):
        global_exec = DaskExecutor(scheduler=scheduler)
        executor = DaskExecutor(scheduler=scheduler)

        with global_exec.start():
            global_q = global_exec.queue(0)
            ticket_q = global_exec.queue(0)

            @prefect.task(tags=["connection"])
            def record_size(q, t):
                t.put(0)  # each task records its connection
                time.sleep(random.random() / 10)
                q.put(t.qsize())  # and records the number of active connections
                t.get()

            with Flow() as f:
                for _ in range(20):
                    record_size(global_q, ticket_q)

            f.run(throttle=dict(connection=num), executor=executor)
            res = max([global_q.get() for _ in range(global_q.qsize())])

        assert res == num

    @pytest.mark.parametrize("num", [1, 2])
    @pytest.mark.parametrize("scheduler", ["threads", "processes"])
    def test_throttle_multiple_tags(self, scheduler, num):
        global_exec = DaskExecutor(scheduler=scheduler)
        executor = DaskExecutor(scheduler=scheduler)

        with global_exec.start():
            global_q = global_exec.queue(0)
            a_ticket_q = global_exec.queue(0)
            b_ticket_q = global_exec.queue(0)

            @prefect.task
            def record_size(q, **kwargs):
                for name, val in kwargs.items():
                    val.put(0)  # each task records its connection
                time.sleep(random.random() / 100)
                for name, val in kwargs.items():
                    q.put(
                        (name, val.qsize())
                    )  # and records the number of active connections
                    val.get()

            with Flow() as f:
                for _ in range(10):
                    a = record_size(global_q, a=a_ticket_q)
                    a.tags = ["a"]
                for _ in range(10):
                    b = record_size(global_q, b=b_ticket_q)
                    b.tags = ["b"]
                for _ in range(10):
                    c = record_size(global_q, a=a_ticket_q, b=b_ticket_q)
                    c.tags = ["a", "b"]

            f.run(throttle=dict(a=num, b=num + 1), executor=executor)
            res = [global_q.get() for _ in range(global_q.qsize())]

        a_res = [val for tag, val in res if tag == "a"]
        b_res = [val for tag, val in res if tag == "b"]
        assert max(a_res) <= num
        assert max(b_res) <= num + 1

    @pytest.mark.parametrize("scheduler", ["threads", "processes"])
    def test_extreme_throttling_prevents_parallelism(self, scheduler):
        executor = DaskExecutor(scheduler=scheduler)

        @prefect.task(tags=["there-can-be-only-one"])
        def timed():
            time.sleep(0.05)
            return time.time()

        with prefect.Flow() as f:
            a, b = timed(), timed()

        res = f.run(
            executor=executor,
            return_tasks=f.tasks,
            throttle={"there-can-be-only-one": 1},
        )
        times = [s.result for t, s in res.result.items()]
        assert abs(times[0] - times[1]) > 0.05


def test_flow_runner_uses_user_provided_executor():
    t = SuccessTask()
    with Flow() as f:
        result = t()
    with raise_on_exception():
        with pytest.raises(NotImplementedError):
            FlowRunner(flow=f).run(executor=Executor())
