import collections
import datetime
import logging
import queue
import random
import time
from contextlib import contextmanager
from unittest.mock import MagicMock

import pendulum
import pytest

import prefect
from prefect.core import Flow, Parameter, Task
from prefect.engine import signals
from prefect.engine.cache_validators import duration_only
from prefect.executors import Executor, LocalExecutor
from prefect.engine.flow_runner import ENDRUN, FlowRunner, FlowRunnerInitializeResult
from prefect.engine.result import Result
from prefect.engine.state import (
    Cached,
    Failed,
    Finished,
    Mapped,
    Paused,
    Pending,
    Resume,
    Retrying,
    Running,
    Scheduled,
    Skipped,
    State,
    Success,
    TimedOut,
    TriggerFailed,
)
from prefect.tasks.secrets import PrefectSecret
from prefect.triggers import manual_only
from prefect.utilities.debug import raise_on_exception
from prefect.exceptions import TaskTimeoutSignal


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
    r = FlowRunner(Flow(name="test"))
    assert r.logger.name == "prefect.FlowRunner"


def test_flow_runner_runs_basic_flow_with_1_task():
    flow = Flow(name="test")
    task = SuccessTask()
    flow.add_task(task)
    flow_runner = FlowRunner(flow=flow)
    state = flow_runner.run(return_tasks=[task])
    assert state == Success(result={task: Success(result=1)})


def test_flow_runner_with_no_return_tasks():
    """
    Make sure FlowRunner accepts return_tasks=None and doesn't raise early error
    """
    flow = Flow(name="test")
    task = SuccessTask()
    flow.add_task(task)
    flow_runner = FlowRunner(flow=flow)
    assert flow_runner.run(return_tasks=None)


def test_flow_runner_with_invalid_return_tasks():
    flow = Flow(name="test")
    task = SuccessTask()
    flow.add_task(task)
    flow_runner = FlowRunner(flow=flow)
    state = flow_runner.run(return_tasks=[1])
    assert state.is_failed()


def test_flow_runner_runs_basic_flow_with_2_independent_tasks():
    flow = Flow(name="test")
    task1 = SuccessTask()
    task2 = SuccessTask()

    flow.add_task(task1)
    flow.add_task(task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Success)
    assert flow_state.result[task1] == Success(result=1)
    assert flow_state.result[task2] == Success(result=1)


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks():
    flow = Flow(name="test")
    task1 = SuccessTask()
    task2 = SuccessTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Success)
    assert flow_state.result[task1] == Success(result=1)
    assert flow_state.result[task2] == Success(result=1)


def test_flow_runner_runs_base_task_class():
    flow = Flow(name="test")
    task1 = Task()
    task2 = Task()
    flow.add_edge(task1, task2)
    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Success)
    assert isinstance(flow_state.result[task1], Success)
    assert isinstance(flow_state.result[task2], Success)


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks_and_first_task_fails():
    flow = Flow(name="test")
    task1 = ErrorTask()
    task2 = SuccessTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.result[task1], Failed)
    assert isinstance(flow_state.result[task2], TriggerFailed)


def test_flow_runner_runs_flow_with_2_dependent_tasks_and_first_task_fails_and_second_has_trigger():
    flow = Flow(name="test")
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
    flow = Flow(name="test")
    task1 = RaiseFailTask()
    task2 = SuccessTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.result[task1], Failed)
    assert not isinstance(flow_state.result[task1], TriggerFailed)
    assert isinstance(flow_state.result[task2], TriggerFailed)


def test_flow_runner_runs_basic_flow_with_2_dependent_tasks_and_second_task_fails():
    flow = Flow(name="test")
    task1 = SuccessTask()
    task2 = ErrorTask()

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.result[task1], Success)
    assert isinstance(flow_state.result[task2], Failed)


def test_flow_runner_does_not_return_task_states_when_it_doesnt_run():
    flow = Flow(name="test")
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
    flow = Flow(name="test")
    task1 = SuccessTask()
    task2 = ErrorTask()

    flow.add_edge(task1, task2)

    flow_state = flow.run(state=Success())
    assert flow_state.is_successful()
    assert flow_state.result[task1].is_pending()
    assert flow_state.result[task2].is_pending()


def test_flow_runner_remains_running_if_tasks_are_retrying():
    # https://github.com/PrefectHQ/prefect/issues/19
    flow = Flow(name="test")
    task1 = SuccessTask()
    task2 = ErrorTask(max_retries=1, retry_delay=datetime.timedelta(0))

    flow.add_edge(task1, task2)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1, task2])
    assert flow_state.is_running()
    assert flow_state.result[task1].is_successful()
    assert flow_state.result[task2].is_retrying()


def test_secrets_dynamically_pull_from_context():
    flow = Flow(name="test")
    task1 = PrefectSecret("foo", max_retries=1, retry_delay=datetime.timedelta(0))

    flow.add_task(task1)

    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1])
    assert flow_state.is_running()
    assert flow_state.result[task1].is_retrying()

    with prefect.context(secrets=dict(foo=42)):
        time.sleep(1)
        flow_state = FlowRunner(flow=flow).run(task_states=flow_state.result)

    assert flow_state.is_successful()


def test_secrets_are_rerun_on_restart():
    @prefect.task
    def identity(x):
        return x

    with Flow("test") as flow:
        secret = PrefectSecret("key")
        val = identity(secret)

    with prefect.context(secrets={"key": "val"}):
        state = FlowRunner(flow=flow).run(
            task_states={secret: Success()}, return_tasks=[val]
        )
    assert state.is_successful()
    assert state.result[val].result == "val"


def test_flow_runner_doesnt_return_by_default():
    flow = Flow(name="test")
    task1 = SuccessTask()
    task2 = SuccessTask()
    flow.add_edge(task1, task2)
    res = FlowRunner(flow=flow).run()
    assert res.result == {}


def test_flow_runner_does_return_tasks_when_requested():
    flow = Flow(name="test")
    task1 = SuccessTask()
    task2 = SuccessTask()
    flow.add_edge(task1, task2)
    flow_state = FlowRunner(flow=flow).run(return_tasks=[task1])
    assert isinstance(flow_state, Success)
    assert isinstance(flow_state.result[task1], Success)


def test_required_parameters_must_be_provided():
    flow = Flow(name="test")
    y = prefect.Parameter("y")
    flow.add_task(y)
    flow_state = FlowRunner(flow=flow).run(return_tasks=[y])
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.result[y], Failed)
    assert "required but not provided" in str(flow_state.result[y]).lower()


def test_parameters_are_placed_into_context():
    flow = Flow(name="test")
    y = prefect.Parameter("y", default=99)
    flow.add_task(y)
    flow_state = FlowRunner(flow=flow).run(return_tasks=[y], parameters=dict(y=42))
    assert isinstance(flow_state, Success)
    assert flow_state.result[y].result == 42


def test_parameters_are_placed_into_context_including_defaults():
    @prefect.task
    def whats_in_ctx():
        return prefect.context.parameters

    y = prefect.Parameter("y", default=99)
    z = prefect.Parameter("z", default=19)
    flow = Flow(name="test", tasks=[y, z, whats_in_ctx])
    flow_state = FlowRunner(flow=flow).run(
        return_tasks=[whats_in_ctx], parameters=dict(y=42)
    )
    assert isinstance(flow_state, Success)
    assert flow_state.result[whats_in_ctx].result == dict(y=42, z=19)


def test_parameters_are_placed_into_context_and_override_current_context():
    flow = Flow(name="test")
    y = prefect.Parameter("y", default=99)
    flow.add_task(y)
    with prefect.context(parameters=dict(y=88, z=55)):
        flow_state = FlowRunner(flow=flow).run(return_tasks=[y], parameters=dict(y=42))
    assert isinstance(flow_state, Success)
    assert flow_state.result[y].result == 42


def test_flow_run_state_determined_by_reference_tasks():
    flow = Flow(name="test")
    t1 = ErrorTask()
    t2 = SuccessTask(trigger=prefect.triggers.all_finished)
    flow.add_edge(t1, t2)

    flow.set_reference_tasks([t1])
    flow_state = flow.run()
    assert isinstance(flow_state, Failed)
    assert isinstance(flow_state.result[t1], Failed)
    assert isinstance(flow_state.result[t2], Success)


def test_flow_run_state_not_determined_by_reference_tasks_if_terminal_tasks_are_not_finished():
    flow = Flow(name="test")
    t1 = ErrorTask()
    t2 = RaiseRetryTask(trigger=prefect.triggers.all_finished)
    flow.add_edge(t1, t2)

    flow.set_reference_tasks([t1])
    flow_state = FlowRunner(flow=flow).run(return_tasks=flow.tasks)
    assert flow_state.is_running()
    assert flow_state.result[t1].is_failed()
    assert flow_state.result[t2].is_retrying()


def test_flow_with_multiple_retry_tasks_doesnt_run_them_early():
    """
    t1 -> t2
    t1 -> t3

    Both t2 and t3 fail on initial run and request a retry. Starting the flow at t1 should
    only run t3, which requests an immediate retry, and not t2, which requests a retry in
    10 minutes.

    This tests a check on the TaskRunner, but which matters in Flows like this.
    """
    flow = Flow(name="test")
    t1 = Task()
    t2 = ErrorTask(retry_delay=datetime.timedelta(minutes=10), max_retries=1)
    t3 = ErrorTask(retry_delay=datetime.timedelta(minutes=0), max_retries=1)
    flow.add_edge(t1, t2)
    flow.add_edge(t1, t3)

    state1 = FlowRunner(flow=flow).run(return_tasks=flow.tasks)

    assert state1.result[t2].is_retrying()
    assert state1.result[t3].is_retrying()

    state2 = FlowRunner(flow=flow).run(
        return_tasks=flow.tasks, task_states=state1.result
    )

    assert state2.result[t2].is_retrying()
    assert state2.result[t2] == state1.result[t2]  # state is not modified at all
    assert isinstance(state2.result[t3], Failed)  # this task ran


def test_flow_runner_makes_copy_of_task_results_dict():
    """
    Ensure the flow runner copies the task_results dict rather than modifying it inplace
    """
    flow = Flow(name="test")
    t1, t2 = Task(), Task()
    flow.add_edge(t1, t2)

    task_states = {t1: Pending()}
    state = flow.run(task_states=task_states)
    assert state.result[t1] == Success(result=None)
    assert task_states == {t1: Pending()}


class TestCheckFlowPendingOrRunning:
    @pytest.mark.parametrize("state", [Pending(), Running(), Retrying(), Scheduled()])
    def test_pending_or_running_are_ok(self, state):
        flow = Flow(name="test", tasks=[Task()])
        new_state = FlowRunner(flow=flow).check_flow_is_pending_or_running(state=state)
        assert new_state is state

    @pytest.mark.parametrize(
        "state", [Finished(), Success(), Failed(), Skipped(), State()]
    )
    def test_not_pending_or_running_raise_endrun(self, state):
        flow = Flow(name="test", tasks=[Task()])
        with pytest.raises(ENDRUN):
            FlowRunner(flow=flow).check_flow_is_pending_or_running(state=state)


class TestCheckScheduledStep:
    @pytest.mark.parametrize("state", [Failed(), Pending(), Running(), Success()])
    def test_non_scheduled_states(self, state):
        assert (
            FlowRunner(flow=Flow(name="test")).check_flow_reached_start_time(
                state=state
            )
            is state
        )

    def test_scheduled_states_without_start_time(self):
        state = Scheduled(start_time=None)
        assert (
            FlowRunner(flow=Flow(name="test")).check_flow_reached_start_time(
                state=state
            )
            is state
        )

    def test_scheduled_states_with_future_start_time(self):
        state = Scheduled(
            start_time=pendulum.now("utc") + datetime.timedelta(minutes=10)
        )
        with pytest.raises(ENDRUN) as exc:
            FlowRunner(flow=Flow(name="test")).check_flow_reached_start_time(
                state=state
            )
        assert exc.value.state is state

    def test_scheduled_states_with_past_start_time(self):
        state = Scheduled(
            start_time=pendulum.now("utc") - datetime.timedelta(minutes=1)
        )
        assert (
            FlowRunner(flow=Flow(name="test")).check_flow_reached_start_time(
                state=state
            )
            is state
        )


class TestSetFlowToRunning:
    @pytest.mark.parametrize("state", [Pending(), Retrying()])
    def test_pending_becomes_running(self, state):
        flow = Flow(name="test", tasks=[Task()])
        new_state = FlowRunner(flow=flow).set_flow_to_running(state=state)
        assert new_state.is_running()

    def test_running_stays_running(self):
        state = Running()
        flow = Flow(name="test", tasks=[Task()])
        new_state = FlowRunner(flow=flow).set_flow_to_running(state=state)
        assert new_state.is_running()

    @pytest.mark.parametrize("state", [Finished(), Success(), Failed(), Skipped()])
    def test_other_states_raise_endrun(self, state):
        flow = Flow(name="test", tasks=[Task()])
        with pytest.raises(ENDRUN):
            FlowRunner(flow=flow).set_flow_to_running(state=state)


class TestRunFlowStep:
    def test_running_state_finishes(self):
        flow = Flow(name="test", tasks=[Task()])
        new_state = FlowRunner(flow=flow).get_flow_run_state(
            state=Running(),
            task_states={},
            task_contexts={},
            return_tasks=set(),
            task_runner_state_handlers=[],
            executor=LocalExecutor(),
        )
        assert new_state.is_successful()

    @pytest.mark.parametrize(
        "state", [Pending(), Retrying(), Finished(), Success(), Failed(), Skipped()]
    )
    def test_other_states_raise_endrun(self, state):
        flow = Flow(name="test", tasks=[Task()])
        with pytest.raises(ENDRUN):
            FlowRunner(flow=flow).get_flow_run_state(
                state=state,
                task_states={},
                task_contexts={},
                return_tasks=set(),
                task_runner_state_handlers=[],
                executor=Executor(),
            )

    def test_determine_final_state_has_final_say(self):
        class MyFlowRunner(FlowRunner):
            def determine_final_state(self, *args, **kwargs):
                return Failed("Very specific error message")

        flow = Flow(name="test", tasks=[Task()])
        new_state = MyFlowRunner(flow=flow).get_flow_run_state(
            state=Running(),
            task_states={},
            task_contexts={},
            return_tasks=set(),
            task_runner_state_handlers=[],
            executor=LocalExecutor(),
        )
        assert new_state.is_failed()
        assert new_state.message == "Very specific error message"

    def test_determine_final_state_preserves_running_states_when_tasks_still_running(
        self,
    ):
        task = Task()
        flow = Flow(name="test", tasks=[task])
        old_state = Running()
        new_state = FlowRunner(flow=flow).get_flow_run_state(
            state=old_state,
            task_states={task: Retrying(start_time=pendulum.now("utc").add(days=1))},
            task_contexts={},
            return_tasks=set(),
            task_runner_state_handlers=[],
            executor=LocalExecutor(),
        )
        assert new_state is old_state


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

        with Flow(name="test") as f:
            y = TestTask(
                cache_validator=duration_only, cache_for=datetime.timedelta(days=1)
            )
            x = Parameter("x")
            s = SuccessTask()
            f.add_edge(x, y, key="x")
            f.add_edge(s, y, key="s")

        state = Cached(
            cached_result_expiration=pendulum.now("utc") + datetime.timedelta(days=1),
            result=100,
        )
        flow_state = FlowRunner(flow=f).run(
            executor=executor,
            parameters=dict(x=1),
            return_tasks=[y],
            task_states={y: state},
        )
        assert isinstance(flow_state, Success)
        assert flow_state.result[y].result == 100


class TestCachingFromContext:
    def test_caches_do_not_persist_across_flow_runner_runs(self):
        @prefect.task(cache_for=datetime.timedelta(seconds=10))
        def test_task():
            return random.random()

        with Flow("test_cache") as flow:
            t = test_task()

        flow_state = FlowRunner(flow=flow).run(return_tasks=[t])
        first_result = flow_state.result[t].result

        flow_state = FlowRunner(flow=flow).run(return_tasks=[t])
        second_result = flow_state.result[t].result

        assert first_result != second_result


class TestInitializeRun:
    def test_initialize_sets_none_to_pending(self):
        result = FlowRunner(Flow(name="test")).initialize_run(
            state=None, task_states={}, context={}, task_contexts={}, parameters={}
        )
        assert result.state.is_pending()

    @pytest.mark.parametrize("state", [Pending(), Running()])
    def test_initialize_returns_state_if_provided(self, state):
        result = FlowRunner(Flow(name="test")).initialize_run(
            state=state, task_states={}, context={}, task_contexts={}, parameters={}
        )
        assert result.state is state

    def test_initialize_sets_task_contexts(self):
        t1 = Task(name="t1")
        t2 = Parameter(name="x")
        flow = Flow(name="test", tasks=[t1, t2])

        result = FlowRunner(flow).initialize_run(
            state=Pending(), task_states={}, context={}, task_contexts={}, parameters={}
        )
        assert result.task_contexts == {
            t: dict(task_name=t.name, task_slug=flow.slugs[t]) for t in flow.tasks
        }

    def test_initialize_puts_parameters_in_context(self):
        x = Parameter(name="x")
        flow = Flow(name="test", tasks=[x])

        result = FlowRunner(flow).initialize_run(
            state=Pending(),
            task_states={},
            context={},
            task_contexts={},
            parameters={"x": 1},
        )
        assert result.context["parameters"] == {"x": 1}

    def test_parameter_precedance(self):
        x = Parameter(name="x")
        flow = Flow(name="test", tasks=[x])

        result = FlowRunner(flow).initialize_run(
            state=Pending(),
            task_states={},
            context={"parameters": {"x": 2, "y": 1}},
            task_contexts={},
            parameters={"x": 1},
        )
        assert result.context["parameters"] == {"x": 1, "y": 1}


class TestRunCount:
    def test_run_count_updates_after_each_retry(self):
        flow = Flow(name="test")
        t1 = ErrorTask(max_retries=2, retry_delay=datetime.timedelta(0))
        flow.add_task(t1)

        state1 = FlowRunner(flow=flow).run(return_tasks=[t1])
        assert state1.result[t1].is_retrying()
        assert state1.result[t1].run_count == 1

        state2 = FlowRunner(flow=flow).run(return_tasks=[t1], task_states=state1.result)
        assert state2.result[t1].is_retrying()
        assert state2.result[t1].run_count == 2

    def test_run_count_tracked_via_retry_states(self):
        flow = Flow(name="test")
        t1 = ErrorTask(max_retries=1, retry_delay=datetime.timedelta(0))
        t2 = ErrorTask(max_retries=2, retry_delay=datetime.timedelta(0))
        flow.add_task(t1)
        flow.add_task(t2)

        # first run
        state1 = FlowRunner(flow=flow).run(return_tasks=[t1, t2])
        assert state1.is_running()
        assert state1.result[t1].is_retrying()
        assert state1.result[t1].run_count == 1
        assert state1.result[t2].is_retrying()
        assert state1.result[t2].run_count == 1

        # second run
        state2 = FlowRunner(flow=flow).run(
            task_states=state1.result, return_tasks=[t1, t2]
        )
        assert state2.is_running()
        assert isinstance(state2.result[t1], Failed)
        assert state2.result[t2].is_retrying()
        assert state2.result[t2].run_count == 2

        # third run
        state3 = FlowRunner(flow=flow).run(
            task_states=state2.result, return_tasks=[t1, t2]
        )
        assert state3.is_failed()
        assert isinstance(state3.result[t1], Failed)
        assert isinstance(state3.result[t2], Failed)


def test_flow_runner_uses_default_executor_on_flow_if_present():
    t = SuccessTask()
    with Flow(name="test", executor=Executor()) as flow:
        result = t()

    with raise_on_exception():
        with pytest.raises(NotImplementedError):
            FlowRunner(flow=flow).run()


def test_flow_runner_uses_user_provided_executor():
    t = SuccessTask()
    with Flow(name="test") as f:
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

    f = Flow(name="test", tasks=[put])
    state = f.run(executor=executor)

    assert state.is_failed()
    assert isinstance(state.result, TypeError)

    # assert two possible result outputs for different Python versions
    assert str(state.result) in [
        "can't pickle _thread.lock objects",
        "cannot pickle '_thread.lock' object",
    ]


@pytest.mark.xfail(
    reason="This test fails on CircleCI for Python 3.5+ if not enough cores/workers are available."
)
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

    with Flow(name="test") as flow:
        a, b = record_times(), record_times()

    state = flow.run(executor=executor)
    assert state.is_successful()

    times = [("alice", t) for t in state.result[a].result] + [
        ("bob", t) for t in state.result[b].result
    ]
    names = [name for name, time in sorted(times, key=lambda x: x[1])]

    alice_first = ["alice"] * 75 + ["bob"] * 75
    bob_first = ["bob"] * 75 + ["alice"] * 75

    assert names != alice_first
    assert names != bob_first


@pytest.mark.parametrize(
    "executor", ["local", "mproc", "mthread", "sync"], indirect=True
)
def test_flow_runner_properly_provides_context_to_task_runners(executor):
    @prefect.task
    def my_name():
        return prefect.context.get("my_name")

    @prefect.task
    def flow_name():
        return prefect.context.get("flow_name")

    flow = Flow(name="test-dummy", tasks=[flow_name, my_name])
    with prefect.context(my_name="marvin"):
        res = flow.run(executor=executor)

    assert res.result[flow_name].result == "test-dummy"
    assert res.result[my_name].result == "marvin"

    with Flow("test-map") as f:
        tt = flow_name.map(upstream_tasks=[my_name])

    with prefect.context(my_name="mapped-marvin"):
        res = f.run(executor=executor)

    assert res.result[my_name].result == "mapped-marvin"
    assert res.result[tt].result[0] == "test-map"


@pytest.mark.parametrize(
    "executor", ["local", "mthread", "sync", "mproc", "threaded_local"], indirect=True
)
def test_flow_runner_handles_timeouts(executor):
    sleeper = SlowTask(timeout=1)

    with Flow(name="test") as flow:
        res = sleeper(3)

    state = FlowRunner(flow=flow).run(return_tasks=[res], executor=executor)
    assert state.is_failed()
    assert isinstance(state.result[res], TimedOut)
    assert "timed out" in state.result[res].message
    assert isinstance(state.result[res].result, TaskTimeoutSignal)


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
        flow = Flow(name="test", state_handlers=[flow_handler])
        FlowRunner(flow=flow).run()
        # the flow changed state twice: Pending -> Running -> Success
        assert handler_results["Flow"] == 2

    def test_flow_handlers_are_called_even_when_initialize_run_fails(self):
        class BadRunner(FlowRunner):
            def initialize_run(self, *args, **kwargs):
                raise SyntaxError("bad")

        def handler(runner, old, new):
            handler_results["Flow"] += 1
            return new

        flow = Flow(name="test", state_handlers=[handler])
        BadRunner(flow=flow).run()
        # the flow changed state twice: Pending -> Failed
        assert handler_results["Flow"] == 1

    def test_flow_handlers_can_return_none(self):
        flow_handler = MagicMock(side_effect=lambda t, o, n: None)
        flow = Flow(name="test", state_handlers=[flow_handler])
        flow_state = FlowRunner(flow=flow).run()
        assert flow_state.is_successful()

        # the flow changed state twice: Pending -> Running -> Success
        assert flow_handler.call_count == 2

    def test_flow_on_failure_is_not_called(self):
        on_failure = MagicMock()
        flow = Flow(name="test", on_failure=on_failure, tasks=[Task()])
        FlowRunner(flow=flow).run()
        assert not on_failure.called

    def test_task_on_failure_is_called(self):
        on_failure = MagicMock()
        flow = Flow(name="test", tasks=[ErrorTask()], on_failure=on_failure)
        FlowRunner(flow=flow).run()
        assert on_failure.call_count == 1
        assert on_failure.call_args[0][0] is flow
        assert on_failure.call_args[0][1].is_failed()

    def test_multiple_flow_handlers_are_called(self):
        flow = Flow(name="test", state_handlers=[flow_handler, flow_handler])
        FlowRunner(flow=flow).run()
        # each flow changed state twice: Pending -> Running -> Success
        assert handler_results["Flow"] == 4

    def test_multiple_flow_handlers_are_called_in_sequence(self):
        # the second flow handler will assert the result of the first flow handler is a state
        # and raise an error, as long as the flow_handlers are called in sequence on the
        # previous result
        flow = Flow(name="test", state_handlers=[lambda *a: True, flow_handler])
        with pytest.raises(AssertionError):
            with prefect.utilities.debug.raise_on_exception():
                FlowRunner(flow=flow).run()

    def test_task_handler_that_doesnt_return_state_or_none(self):
        flow = Flow(name="test", state_handlers=[lambda *a: True])
        # raises an attribute error because it tries to access a property of the state that
        # doesn't exist on None
        with pytest.raises(AttributeError):
            with prefect.utilities.debug.raise_on_exception():
                FlowRunner(flow=flow).run()


class TestFlowRunnerStateHandlers:
    def test_task_runner_handlers_are_called(self):
        FlowRunner(flow=Flow(name="test"), state_handlers=[flow_runner_handler]).run()
        # the flow changed state twice: Pending -> Running -> Success
        assert handler_results["FlowRunner"] == 2

    def test_multiple_task_runner_handlers_are_called(self):
        FlowRunner(
            flow=Flow(name="test"),
            state_handlers=[flow_runner_handler, flow_runner_handler],
        ).run()
        # each flow changed state twice: Pending -> Running -> Success
        assert handler_results["FlowRunner"] == 4

    def test_multiple_task_runner_handlers_are_called_in_sequence(self):
        # the second flow handler will assert the result of the first flow handler is a state
        # and raise an error, as long as the flow_handlers are called in sequence on the
        # previous result
        with pytest.raises(AssertionError):
            with prefect.utilities.debug.raise_on_exception():
                FlowRunner(
                    flow=Flow(name="test"),
                    state_handlers=[lambda *a: True, flow_runner_handler],
                ).run()

    def test_task_runner_handler_that_doesnt_return_state_or_none(self):
        # raises an attribute error because it tries to access a property of the state that
        # doesn't exist on None
        with pytest.raises(AttributeError):
            with prefect.utilities.debug.raise_on_exception():
                FlowRunner(
                    flow=Flow(name="test"), state_handlers=[lambda *a: True]
                ).run()

    def test_task_handler_that_raises_signal_is_trapped(self):
        def handler(flow, old, new):
            raise signals.FAIL()

        flow = Flow(name="test", state_handlers=[handler])
        state = FlowRunner(flow=flow).run()
        assert state.is_failed()

    def test_task_handler_that_has_error_is_trapped(self):
        def handler(flow, old, new):
            1 / 0

        flow = Flow(name="test", state_handlers=[handler])
        state = FlowRunner(flow=flow).run()
        assert state.is_failed()


def test_improper_use_of_unmapped_fails_gracefully():
    add = AddTask()
    x = Parameter("x", default=[1, 2, 3])
    with Flow(name="test") as f:
        res = add.map(
            x, y=prefect.tasks.core.constants.Constant(8)
        )  # incorrect, should use `unmapped`

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

    runner = FlowRunner(Flow(name="test"))

    for method in pipeline:
        setattr(runner, method, MagicMock())

    # initialize run is unpacked, which MagicMocks dont support
    runner.initialize_run = MagicMock(
        return_value=FlowRunnerInitializeResult(
            MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
    )

    runner.run()

    for method in pipeline:
        assert getattr(runner, method).call_count == 1


def test_endrun_raised_in_initialize_is_caught_correctly():
    class BadInitializeRunner(FlowRunner):
        def initialize_run(self, *args, **kwargs):
            raise ENDRUN(state=Pending())

    res = BadInitializeRunner(Flow(name="test")).run()
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
        with pytest.warns(UserWarning):
            Flow(name="test").run()

    assert x.call_count == 1


def test_parameters_can_be_set_in_context_if_none_passed():
    x = prefect.Parameter("x")
    f = FlowRunner(Flow(name="test", tasks=[x]))
    state = f.run(parameters={}, context={"parameters": {"x": 5}}, return_tasks=[x])
    assert state.result[x].result == 5


def test_parameters_overwrite_context():
    x = prefect.Parameter("x")
    f = FlowRunner(Flow(name="test", tasks=[x]))
    state = f.run(
        parameters={"x": 2}, context={"parameters": {"x": 5}}, return_tasks=[x]
    )
    assert state.result[x].result == 2


def test_parameters_overwrite_context_only_if_key_matches():
    x = prefect.Parameter("x")
    y = prefect.Parameter("y")
    f = FlowRunner(Flow(name="test", tasks=[x, y]))
    state = f.run(
        parameters={"x": 2},
        context={"parameters": {"x": 5, "y": 6}},
        return_tasks=[x, y],
    )
    assert state.result[x].result == 2
    assert state.result[y].result == 6


class TestMapping:
    @pytest.mark.parametrize(
        "executor", ["local", "mthread", "mproc", "sync"], indirect=True
    )
    def test_terminal_mapped_states_are_used_for_flow_state(self, executor):

        with Flow(name="test") as flow:
            res = ReturnTask().map([0, 1])
        state = FlowRunner(flow=flow).run(return_tasks=[res], executor=executor)
        assert state.is_failed()
        assert state.result[res].map_states[0].is_successful()
        assert state.result[res].map_states[1].is_failed()

    @pytest.mark.parametrize(
        "executor", ["local", "mthread", "mproc", "sync"], indirect=True
    )
    def test_mapped_will_use_existing_map_states_if_available(self, executor):

        with Flow(name="test") as flow:
            res = ReturnTask().map([0, 1])

        state = FlowRunner(flow=flow).run(
            return_tasks=[res],
            executor=executor,
            task_states={res: Mapped(map_states=[Success(), Success(result=100)])},
        )
        assert state.is_successful()
        assert state.result[res].map_states[1].is_successful()
        assert state.result[res].map_states[1].result == 100

    @pytest.mark.parametrize(
        "executor", ["local", "mthread", "mproc", "sync"], indirect=True
    )
    def test_mapped_will_use_partial_existing_map_states_if_available(self, executor):

        with Flow(name="test") as flow:
            res = ReturnTask().map([1, 1])

        state = FlowRunner(flow=flow).run(
            return_tasks=[res],
            executor=executor,
            task_states={res: Mapped(map_states=[None, Success(result=100)])},
        )
        assert state.is_failed()
        assert state.result[res].map_states[0].is_failed()
        assert state.result[res].map_states[1].is_successful()
        assert state.result[res].map_states[1].result == 100

    @pytest.mark.parametrize(
        "executor", ["local", "mthread", "mproc", "sync"], indirect=True
    )
    def test_mapped_tasks_dont_run_if_upstream_pending(self, executor):

        with Flow(name="test") as flow:
            ups = SuccessTask()
            res = ReturnTask().map([ups])

        state = FlowRunner(flow=flow).run(
            return_tasks=flow.tasks,
            executor=executor,
            task_states={ups: Retrying(start_time=pendulum.now().add(hours=1))},
        )
        assert state.is_running()
        assert state.result[ups].is_pending()
        assert state.result[res].is_pending()

    @pytest.mark.parametrize(
        "executor", ["local", "mthread", "mproc", "sync"], indirect=True
    )
    def test_mapped_task_can_be_scheduled(self, executor):

        with Flow(name="test") as flow:
            res = ReturnTask().map([0, 0])

        state = FlowRunner(flow=flow).run(
            return_tasks=[res],
            executor=executor,
            task_states={res: Scheduled(start_time=pendulum.now().subtract(minutes=1))},
        )
        assert state.is_successful()

    @pytest.mark.parametrize(
        "executor", ["local", "mthread", "mproc", "sync"], indirect=True
    )
    def test_mapped_task_can_be_scheduled_for_future(self, executor):

        with Flow(name="test") as flow:
            res = ReturnTask().map([0, 0])

        state = FlowRunner(flow=flow).run(
            return_tasks=[res],
            executor=executor,
            task_states={res: Scheduled(start_time=pendulum.now().add(hours=1))},
        )
        assert state.is_running()
        assert isinstance(state.result[res], Scheduled)


def test_task_contexts_are_provided_to_tasks():
    @prefect.task(name="rc", slug="rc")
    def return_context():
        return prefect.context.to_dict()

    with Flow(name="test") as flow:
        rc = return_context()
    state = FlowRunner(flow=flow).run(return_tasks=[rc])
    ctx = state.result[rc].result

    assert ctx["task_name"] == rc.name
    assert ctx["task_slug"] == rc.slug


def test_paused_tasks_stay_paused_when_run():
    t = Task()
    f = Flow(name="test", tasks=[t])

    state = FlowRunner(flow=f).run(task_states={t: Paused()}, return_tasks=[t])
    assert state.is_running()
    assert isinstance(state.result[t], Paused)


class TestContext:
    def test_flow_runner_passes_along_its_run_context_to_tasks(self):
        @prefect.task
        def grab_key():
            return prefect.context["THE_ANSWER"]

        with prefect.context(THE_ANSWER=42):
            runner = FlowRunner(Flow(name="test", tasks=[grab_key]))
            flow_state = runner.run(return_tasks=[grab_key])

        assert flow_state.is_successful()
        assert flow_state.result[grab_key].result == 42

    def test_flow_runner_provides_scheduled_start_time(self):
        @prefect.task
        def return_scheduled_start_time():
            return prefect.context.get("scheduled_start_time")

        f = Flow(name="test", tasks=[return_scheduled_start_time])
        res = f.run()

        assert res.is_successful()
        assert res.result[return_scheduled_start_time].is_successful()
        assert isinstance(
            res.result[return_scheduled_start_time].result, datetime.datetime
        )

    @pytest.mark.parametrize("run_on_schedule", [True, False])
    def test_flow_runner_doesnt_override_scheduled_start_time_when_running_on_schedule(
        self, run_on_schedule
    ):
        @prefect.task
        def return_scheduled_start_time():
            return prefect.context.get("scheduled_start_time")

        f = Flow(name="test", tasks=[return_scheduled_start_time])
        res = f.run(
            context=dict(scheduled_start_time=42), run_on_schedule=run_on_schedule
        )

        assert res.is_successful()
        assert res.result[return_scheduled_start_time].result != 42

    @pytest.mark.parametrize(
        "date", ["today_nodash", "tomorrow_nodash", "yesterday_nodash"]
    )
    def test_context_contains_nodash_date_formats(self, date):
        @prefect.task
        def return_ctx_key():
            return prefect.context.get(date)

        f = Flow(name="test", tasks=[return_ctx_key])
        res = f.run()

        assert res.is_successful()

        output = res.result[return_ctx_key].result
        assert isinstance(output, str)
        assert len(output) == 8

    @pytest.mark.parametrize("date", ["today", "tomorrow", "yesterday"])
    def test_context_contains_date_formats(self, date):
        @prefect.task
        def return_ctx_key():
            return prefect.context.get(date)

        f = Flow(name="test", tasks=[return_ctx_key])
        res = f.run()

        assert res.is_successful()

        output = res.result[return_ctx_key].result
        assert isinstance(output, str)
        assert len(output) == 10

    def test_context_includes_date(self):
        @prefect.task
        def return_ctx_key():
            return prefect.context.get("date")

        f = Flow(name="test", tasks=[return_ctx_key])
        res = f.run()

        assert res.is_successful()

        output = res.result[return_ctx_key].result
        assert isinstance(output, datetime.datetime)

    @pytest.mark.parametrize("as_string", [True, False])
    def test_context_derives_dates_from_custom_date(self, as_string):
        @prefect.task
        def return_ctx():
            return prefect.context.copy()

        custom_date = pendulum.now().add(months=1)

        f = Flow(name="test", tasks=[return_ctx])
        with prefect.context(
            {"date": custom_date.to_datetime_string() if as_string else custom_date}
        ):
            res = f.run()

        assert res.is_successful()

        context = res.result[return_ctx].result

        # Ensure the string is converted to a datetime object
        assert isinstance(context["date"], pendulum.DateTime)

        # Ensure dependent variables use the custom date
        assert context["yesterday"] == custom_date.add(days=-1).strftime("%Y-%m-%d")
        assert context["tomorrow"] == custom_date.add(days=1).strftime("%Y-%m-%d")
        assert context["today_nodash"] == custom_date.strftime("%Y%m%d")
        assert context["yesterday_nodash"] == custom_date.add(days=-1).strftime(
            "%Y%m%d"
        )
        assert context["tomorrow_nodash"] == custom_date.add(days=1).strftime("%Y%m%d")

    def test_context_warns_on_unparsable_custom_date(self, caplog, monkeypatch):

        now = pendulum.now()
        monkeypatch.setattr("pendulum.now", MagicMock(return_value=now))

        caplog.set_level(logging.WARNING)

        @prefect.task
        def return_ctx_key():
            return prefect.context.get("tomorrow")

        f = Flow(name="test", tasks=[return_ctx_key])
        with prefect.context({"date": "foobar"}):
            res = f.run()

        assert res.is_successful()

        found_log = False
        for record in caplog.records:
            if (
                record.levelno == logging.WARNING
                and "could not be parsed into a pendulum `DateTime` object"
                in record.message
            ):
                found_log = True
        assert found_log

        # Uses `now` to determine tomorrow
        output = res.result[return_ctx_key].result
        assert output == now.add(days=1).strftime("%Y-%m-%d")

    @pytest.mark.parametrize(
        "outer_context, inner_context, sol",
        [
            ({"date": "outer"}, {"date": "inner"}, "inner"),
            ({"date": "outer"}, {}, "outer"),
        ],
    )
    def test_user_provided_context_is_prioritized(
        self, outer_context, inner_context, sol
    ):
        @prefect.task
        def return_ctx_key():
            return prefect.context.get("date")

        f = Flow(name="test", tasks=[return_ctx_key])
        with prefect.context(**outer_context):
            res = f.run(context=inner_context)

        assert res.is_successful()

        output = res.result[return_ctx_key].result
        assert output == sol


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread", "threaded_local"], indirect=True
)
def test_task_logs_survive_if_timeout_is_used(caplog, executor):
    @prefect.task(timeout=2)
    def log_stuff():
        logger = prefect.context.get("logger")
        logger.critical("important log right here")

    f = Flow(name="logs", tasks=[log_stuff])
    res = f.run()

    assert res.is_successful()
    assert len([r for r in caplog.records if r.levelname == "CRITICAL"]) == 1


def test_constant_tasks_arent_submitted(caplog):
    calls = []

    class TrackSubmissions(LocalExecutor):
        def submit(self, *args, **kwargs):
            calls.append(kwargs)
            return super().submit(*args, **kwargs)

    @prefect.task
    def add(x):
        return x + 1

    with Flow("constants") as flow:
        output = add(5)

    runner = FlowRunner(flow=flow)
    flow_state = runner.run(return_tasks=[output], executor=TrackSubmissions())
    assert flow_state.is_successful()
    assert flow_state.result[output].result == 6

    ## only add was submitted
    assert len(calls) == 1

    ## to be safe, ensure '5' isn't in the logs
    assert len([log.message for log in caplog.records if "5" in log.message]) == 0


def test_constant_tasks_arent_submitted_when_mapped(caplog):
    calls = []

    class TrackSubmissions(LocalExecutor):
        def submit(self, *args, **kwargs):
            calls.append(kwargs)
            return super().submit(*args, **kwargs)

    @prefect.task
    def add(x):
        return x + 1

    with Flow("constants") as flow:
        output = add.map([99] * 10)

    runner = FlowRunner(flow=flow)
    flow_state = runner.run(return_tasks=[output], executor=TrackSubmissions())
    assert flow_state.is_successful()
    assert flow_state.result[output].result == [100] * 10

    ## the add task was submitted 11 times: one for the parent and 10 times for each child
    assert len(calls) == 11

    ## to be safe, ensure '5' isn't in the logs
    assert len([log.message for log in caplog.records if "99" in log.message]) == 0


def test_dask_executor_with_flow_runner_sets_task_keys(mthread):
    """Integration test that ensures the flow runner forwards the proper
    information to the DaskExecutor so that key names are set based on
    the task name"""
    key_names = set()

    class MyExecutor(Executor):
        @contextmanager
        def start(self):
            with mthread.start():
                yield

        def submit(self, *args, **kwargs):
            fut = mthread.submit(*args, **kwargs)
            key_names.add(fut.key.split("-")[0])
            return fut

        def wait(self, x):
            return mthread.wait(x)

    @prefect.task
    def inc(x):
        return x + 1

    @prefect.task
    def do_sum(x):
        return sum(x)

    with Flow("test") as flow:
        a = inc(1)
        b = inc.map(range(3))
        c = do_sum(b)

    flow.run(executor=MyExecutor())

    assert key_names == {"inc", "do_sum"}
