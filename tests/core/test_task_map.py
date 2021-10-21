import datetime
import random
import time

import pytest

import prefect
from prefect.exceptions import PrefectSignal
from prefect.core import Edge, Flow, Parameter, Task
from prefect.engine.flow_runner import FlowRunner
from prefect.engine.result import Result, NoResult
from prefect.engine.state import Mapped, Pending, Retrying, Success
from prefect.utilities.debug import raise_on_exception
from prefect.utilities.tasks import task
from prefect.utilities.edges import unmapped, flatten, mapped
from prefect.tasks.core.constants import Constant


class AddTask(Task):
    def run(self, x, y=1):
        return x + y


class DivTask(Task):
    def run(self, x):
        return 1 / x


class IdTask(Task):
    def run(self, x):
        return x


class ListTask(Task):
    def run(self, start=1):
        return [start + 0, start + 1, start + 2]


class NestTask(Task):
    # given x, returns [x]
    def run(self, x):
        return [x]


def test_map_returns_a_task_copy():
    ll = ListTask()
    a = AddTask()

    with Flow(name="test") as flow:
        res = a.map(ll)

    assert res != a
    assert res in flow.tasks


def test_map_returns_a_task_copy_without_context():
    ll = ListTask()
    a = AddTask()

    flow = Flow(name="test")
    res = a.map(ll, flow=flow)

    assert res != a
    assert res in flow.tasks


def test_calling_map_with_bind_returns_self():
    ll = ListTask()
    a = AddTask()

    with Flow(name="test"):
        res = a.bind(ll, mapped=True)

    assert res is a


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_spawns_new_tasks(executor):
    ll = ListTask()
    a = AddTask()

    with Flow(name="test") as f:
        res = a.map(ll)

    s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_successful()
    assert m.is_mapped()
    assert isinstance(m.map_states, list)
    assert len(m.map_states) == 3
    assert all(isinstance(ms, Success) for ms in m.map_states)
    assert m.result == [2, 3, 4]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_over_parameters(executor):
    a = AddTask()

    with Flow(name="test") as f:
        ll = Parameter("list")
        res = a.map(ll)

    s = f.run(executor=executor, parameters=dict(list=[1, 2, 3]))
    m = s.result[res]
    assert s.is_successful()
    assert m.is_mapped()
    assert isinstance(m.map_states, list)
    assert all(s.is_successful() for s in m.map_states)
    assert len(m.map_states) == 3
    assert m.result == [2, 3, 4]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_composition(executor):
    ll = ListTask()
    a = AddTask()

    with Flow(name="test") as f:
        r1 = a.map(ll)
        r2 = a.map(r1)

    with raise_on_exception():
        s = f.run(executor=executor)

    m1 = s.result[r1]
    m2 = s.result[r2]
    assert s.is_successful()
    assert m1.is_mapped()
    assert m2.is_mapped()

    assert isinstance(m1.map_states, list)
    assert all(s.is_successful() for s in m1.map_states)
    assert len(m1.map_states) == 3
    assert m1.result == [2, 3, 4]

    assert isinstance(m2.map_states, list)
    assert all(s.is_successful() for s in m2.map_states)
    assert len(m2.map_states) == 3
    assert m2.result == [3, 4, 5]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_deep_map_composition(executor):
    ll = ListTask()
    a = AddTask()

    with Flow(name="test") as f:
        res = a.map(ll)  # [2, 3, 4]
        for _ in range(10):
            res = a.map(res)  # [2 + 10, 3 + 10, 4 + 10]

    s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_successful()
    assert m.is_mapped()
    assert isinstance(m.map_states, list)
    assert len(m.map_states) == 3
    assert m.result == [12, 13, 14]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_multiple_map_arguments(executor):
    ll = ListTask()
    a = AddTask()

    with Flow(name="test") as f:
        res = a.map(x=ll, y=ll())

    s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_successful()
    assert isinstance(m.map_states, list)
    assert len(m.result) == 3
    assert m.result == [2, 4, 6]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_mapping_over_no_successful_upstreams(executor):
    with Flow(name="test") as f:
        a = AddTask().map(x=DivTask()(0))

    s = f.run(executor=executor)
    assert s.is_failed()
    assert s.result[a].is_failed()
    assert s.result[a].message == "No upstream states can be mapped over."


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_mapping_over_one_unmappable_input(executor):
    with Flow(name="test") as f:
        a = AddTask().map(x=Constant(1), y=Constant([1]))

    s = f.run(executor=executor)
    assert s.is_failed()
    assert s.result[a].is_failed()
    assert (
        s.result[a].message == "At least one upstream state has an unmappable result."
    )


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_failures_dont_leak_out(executor):
    ii = IdTask()
    ll = ListTask()
    a = AddTask()
    div = DivTask()

    with Flow(name="test") as f:
        res = ii.map(div.map(a.map(ll(start=-1))))

    s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_failed()
    assert isinstance(m.map_states, list)
    assert len(m.result) == 3
    assert m.result[1:] == [1, 0.5]
    assert isinstance(m.result[0], prefect.engine.signals.TRIGGERFAIL)
    assert isinstance(m.map_states[0], prefect.engine.state.TriggerFailed)


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_skips_return_exception_as_result(executor):
    ll = ListTask()

    @task
    def add(x):
        if x == 1:
            raise prefect.engine.signals.SKIP("One is no good")
        else:
            return x + 1

    with Flow(name="test") as f:
        res = add.map(ll)

    s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_successful()
    assert isinstance(m.map_states, list)
    assert len(m.result) == 3
    assert m.result[1:] == [3, 4]
    assert isinstance(m.result[0], BaseException)
    assert isinstance(m.result[0], prefect.engine.signals.SKIP)
    assert isinstance(m.map_states[0], prefect.engine.state.Skipped)


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_upstream_skip_signals_are_handled_properly(executor):
    @task
    def skip_task():
        raise prefect.engine.signals.SKIP("Not going to run.")

    @task
    def add(x):
        return x + 1

    with Flow(name="test") as f:
        res = add.map(skip_task)

    s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_successful()
    assert m.is_skipped()


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_upstream_skipped_states_are_handled_properly(executor):
    @task
    def skip_task():
        pass

    @task
    def add(x):
        return x + 1

    with Flow(name="test") as f:
        res = add.map(skip_task)

    s = f.run(
        executor=executor, task_states={skip_task: prefect.engine.state.Skipped()}
    )
    m = s.result[res]
    assert s.is_successful()
    assert m.is_skipped()


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_skips_dont_leak_out(executor):
    ll = ListTask()

    @task
    def add(x):
        if x == 1:
            raise prefect.engine.signals.SKIP("One is no good")
        else:
            return x + 1

    with Flow(name="test") as f:
        res = add.map(add.map(ll))

    s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_successful()
    assert isinstance(m.map_states, list)
    assert len(m.result) == 3
    assert m.result == [None, 4, 5]
    assert m.map_states[0].result is None
    assert m.map_states[0]._result == NoResult
    assert isinstance(m.map_states[0], prefect.engine.state.Skipped)


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_handles_upstream_empty(executor):
    @task
    def make_list():
        return []

    a = AddTask()

    with Flow(name="test") as f:
        res = a.map(make_list)
        terminal = a.map(res)

    s = f.run(executor=executor)
    res_state = s.result[res]
    terminal_state = s.result[terminal]
    assert s.is_successful()
    assert res_state.is_mapped()
    assert res_state.result == []
    assert terminal_state.is_mapped()
    assert terminal_state.result == []


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_handles_non_keyed_upstream_empty(executor):
    @task
    def make_list():
        return []

    @task
    def return_1():
        return 1

    with Flow(name="test") as f:
        res = return_1.map(upstream_tasks=[make_list])

    s = f.run(executor=executor)
    res_state = s.result[res]
    assert s.is_successful()
    assert res_state.is_mapped()
    assert res_state.result == []


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_can_handle_fixed_kwargs(executor):
    ll = ListTask()
    a = AddTask()

    with Flow(name="test") as f:
        res = a.map(ll, y=unmapped(5))

    s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_successful()
    assert isinstance(m.map_states, list)
    assert len(m.result) == 3
    assert m.result == [6, 7, 8]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_can_handle_nonkeyed_upstreams(executor):
    ll = ListTask()

    with Flow(name="test") as f:
        res = ll.map(upstream_tasks=[ll()])

    s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_successful()
    assert isinstance(m.map_states, list)
    assert len(m.result) == 3
    assert m.result == [[1, 2, 3] for _ in range(3)]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_can_handle_nonkeyed_mapped_upstreams(executor):
    ii = IdTask()
    ll = ListTask()

    with Flow(name="test") as f:
        mapped = ii.map(ll())  # 1, 2, 3
        res = ll.map(upstream_tasks=[mapped])

    s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_successful()
    assert isinstance(m.map_states, list)
    assert len(m.result) == 3
    assert m.result == [[1, 2, 3] for _ in range(3)]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_can_handle_nonkeyed_nonmapped_upstreams_and_mapped_args(executor):
    ii = IdTask()
    ll = ListTask()

    with Flow(name="test") as f:
        res = ll.map(start=ll(), upstream_tasks=[unmapped(ii(5))])

    s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_successful()
    assert isinstance(m.map_states, list)
    assert len(m.result) == 3
    assert m.result == [[1 + i, 2 + i, 3 + i] for i in range(3)]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_can_handle_nonkeyed_nonmapped_upstreams_and_mapped_args_2(executor):
    # identical to test_map_can_handle_nonkeyed_nonmapped_upstreams_and_mapped_args
    # but uses the `mapped()` annotation instead of calling .map()
    ii = IdTask()
    ll = ListTask()

    with Flow(name="test") as f:
        res = ll(start=mapped(ll()), upstream_tasks=[ii(5)])

    s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_successful()
    assert isinstance(m.map_states, list)
    assert len(m.result) == 3
    assert m.result == [[1 + i, 2 + i, 3 + i] for i in range(3)]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_tracks_non_mapped_upstream_tasks(executor):
    div = DivTask()

    @task
    def zeros():
        return [0, 0, 0]

    @task(trigger=prefect.triggers.all_failed)
    def register(x):
        return True

    with Flow(name="test") as f:
        res = register.map(div.map(zeros()), upstream_tasks=[unmapped(div(1))])

    s = f.run(executor=executor)
    assert s.is_failed()
    assert all(sub.is_failed() for sub in s.result[res].map_states)
    assert all(
        [
            isinstance(sub, prefect.engine.state.TriggerFailed)
            for sub in s.result[res].map_states
        ]
    )


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_preserves_flowrunners_run_context(executor):
    @task
    def whats_id():
        return prefect.context.get("special_id")

    with Flow(name="test-context-preservation") as flow:
        result = whats_id.map(upstream_tasks=[list(range(10))])

    with prefect.context(special_id="FOOBAR"):
        runner = FlowRunner(flow=flow)
        flow_state = runner.run(return_tasks=[result])

    assert flow_state.is_successful()
    assert flow_state.result[result].result == ["FOOBAR"] * 10


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_allows_for_retries(executor):
    ii = IdTask()
    ll = ListTask()
    div = DivTask(max_retries=1, retry_delay=datetime.timedelta(0))

    with Flow(name="test") as f:
        l_res = ll(start=0)
        divved = div.map(l_res)
        res = ii.map(divved)

    states = FlowRunner(flow=f).run(executor=executor, return_tasks=f.tasks)
    assert states.is_running()  # division by zero caused map to retry

    old = states.result[divved]
    assert old.result[1:] == [1.0, 0.5]
    assert old.map_states[0].is_retrying()

    # update upstream result
    states.result[l_res].result[0] = 0.01
    states = FlowRunner(flow=f).run(
        task_states=states.result, executor=executor, return_tasks=f.tasks
    )
    assert states.is_successful()  # no divison by 0

    new = states.result[res]
    assert new.result == [100, 1.0, 0.5]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_can_handle_nonkeyed_mapped_upstreams_and_mapped_args(executor):
    ii = IdTask()
    ll = ListTask()

    with Flow(name="test") as f:
        mapped = ii.map(ll())  # 1, 2, 3
        res = ll.map(start=ll(), upstream_tasks=[mapped])

    s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_successful()
    assert isinstance(m.map_states, list)
    assert len(m.map_states) == 3
    assert m.result == [[1 + i, 2 + i, 3 + i] for i in range(3)]


@pytest.mark.parametrize(
    "executor", ["local", "mproc", "mthread", "sync"], indirect=True
)
def test_map_behaves_like_zip_with_differing_length_results(executor):
    "Tests that map stops combining elements after the smallest list is exhausted."

    @prefect.task
    def ll(n):
        return list(range(n))

    add = AddTask()

    with Flow(name="test") as f:
        res = add.map(x=ll(3), y=ll(2))

    with raise_on_exception():
        s = f.run(executor=executor)
    m = s.result[res]
    assert s.is_successful()
    assert isinstance(m.map_states, list)
    assert len(m.map_states) == 2
    assert m.result == [0, 2]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_allows_retries_2(executor):
    """
    Another test of mapping and retries
    """

    @prefect.task
    def ll():
        return [0, 1, 2]

    div = DivTask(max_retries=1, retry_delay=datetime.timedelta(0))

    with Flow(name="test") as f:
        res = div.map(x=ll)

    s = FlowRunner(flow=f).run(executor=executor, return_tasks=f.tasks)
    assert s.is_running()
    m = s.result[res]
    assert m.map_states[0].is_pending()
    assert m.map_states[1].is_successful()
    assert m.map_states[2].is_successful()

    s.result[ll].result[0] = 10

    s = FlowRunner(flow=f).run(
        executor=executor, task_states=s.result, return_tasks=f.tasks
    )
    assert s.is_successful()
    assert s.result[res].result[0] == 1 / 10


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_reduce_task_honors_trigger_across_all_mapped_states(executor):
    """
    The `take_sum` task reduces over the `div` task, which is going to return one Success
    and one Failure. The `take_sum` should fail its trigger check.
    """

    @prefect.task
    def ll():
        return [0, 1]

    @prefect.task
    def div(x):
        return 1 / x

    @prefect.task
    def take_sum(x):
        return sum(x)

    with Flow(name="test") as f:
        d = div.map(ll)
        s = take_sum(d)

    state = f.run(executor=executor)
    assert state.is_failed()
    assert state.result[s].is_failed()
    assert isinstance(state.result[s], prefect.engine.state.TriggerFailed)


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_reduce_task_properly_applies_trigger_across_all_mapped_states(executor):
    """
    The `take_sum` task reduces over the `div` task, which is going to return one Success
    and one Retrying. The `take_sum` should fail its upstream finished check.
    """

    @prefect.task
    def ll():
        return [0, 1]

    @prefect.task(max_retries=5, retry_delay=datetime.timedelta(hours=1))
    def div(x):
        return 1 / x

    @prefect.task
    def take_sum(x):
        return sum(x)

    with Flow(name="test") as f:
        d = div.map(ll)
        t = div.map(d)
        s = take_sum(d)

    state = FlowRunner(flow=f).run(executor=executor, return_tasks=[s, t])
    assert state.is_running()
    assert state.result[s].is_pending()
    assert state.result[t].is_mapped()
    assert state.result[t].map_states[0].is_pending()
    assert all(s.is_successful() for s in state.result[t].map_states[1:])


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_reduce_task_properly_applies_trigger_across_all_mapped_states_for_deep_pipelines(
    executor,
):
    @prefect.task
    def ll():
        return [0, 1]

    @prefect.task(max_retries=5, retry_delay=datetime.timedelta(hours=1))
    def div(x):
        return 1 / x

    @prefect.task
    def take_sum(x):
        return sum(x)

    with Flow(name="test") as f:
        d = div.map(ll)
        s = take_sum(d)

    state = FlowRunner(flow=f).run(executor=executor, return_tasks=[s])
    assert state.is_running()
    assert state.result[s].is_pending()


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_task_map_downstreams_handle_single_failures(executor):
    @prefect.task
    def ll():
        return [1, 0, 3]

    @prefect.task
    def div(x):
        return 1 / x

    @prefect.task
    def append_four(l):
        return l + [4]

    with Flow(name="test") as f:
        dived = div.map(ll)  # middle task fails
        big_list = append_four(dived)  # this task should fail
        again = div.map(dived)

    state = f.run(executor=executor)
    assert state.is_failed()
    assert len(state.result[dived].result) == 3
    assert isinstance(state.result[big_list], prefect.engine.state.TriggerFailed)
    assert state.result[again].result[0::2] == [1, 3]
    assert isinstance(
        state.result[again].map_states[1], prefect.engine.state.TriggerFailed
    )


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_task_map_can_be_passed_to_upstream_with_and_without_map(executor):
    @prefect.task
    def ll():
        return [1, 2, 3]

    @prefect.task
    def add(x):
        return x + 1

    @prefect.task
    def append_four(l):
        return l + [4]

    with Flow(name="test") as f:
        added = add.map(ll)
        big_list = append_four(added)
        again = add.map(added)

    state = f.run(executor=executor)

    assert state.is_successful()
    assert len(state.result[added].result) == 3
    assert state.result[big_list].result == [2, 3, 4, 4]
    assert state.result[again].result == [3, 4, 5]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_task_map_doesnt_assume_purity_of_functions(executor):
    @prefect.task
    def ll():
        return [1, 1, 1]

    @prefect.task
    def zz(s):
        return round(random.random(), 6)

    with Flow(name="test") as f:
        res = zz.map(ll)

    state = f.run(executor=executor)
    assert state.is_successful()
    assert len(state.result[res].result) == 3


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_reduce(executor):
    @prefect.task
    def numbers():
        return [1, 2, 3]

    @prefect.task
    def add(x):
        return x + 1

    @prefect.task
    def reduce_sum(x):
        return sum(x)

    with Flow(name="test") as f:
        res = reduce_sum(add.map(add.map(numbers())))

    state = f.run(executor=executor)
    assert state.is_successful()
    assert state.result[res].result == 12


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_over_map_and_unmapped(executor):
    @prefect.task
    def numbers():
        return [1, 2, 3]

    @prefect.task
    def add(x):
        return x + 1

    @prefect.task
    def add_two(x, y):
        return x + y

    with Flow(name="test") as f:
        n = numbers()
        res = add_two.map(x=n, y=add.map(n))

    state = f.run(executor=executor)
    assert state.is_successful()
    assert state.result[res].result == [3, 5, 7]


@pytest.mark.parametrize("x,y,out", [(1, 2, 3), ([0, 2], [1, 7], [0, 2, 1, 7])])
def test_task_map_with_all_inputs_unmapped(x, y, out):
    @prefect.task
    def add(x, y):
        return x + y

    with Flow(name="test") as f:
        res = add.map(unmapped(x), unmapped(y))

    flow_state = f.run()
    assert flow_state.is_successful()
    assert flow_state.result[res].is_successful()
    assert flow_state.result[res].result == out


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_task_map_with_no_upstream_results_and_a_mapped_state(executor):
    """
    This test makes sure that mapped tasks properly generate children tasks even when
    run multiple times and without available upstream results. In this test, we run the pipeline
    from a variety of starting points, ensuring that some upstream results are unavailable and
    checking that children pipelines are properly regenerated.

    Note that upstream results will be hydrated from remote locations when running with a Cloud TaskRunner.
    """

    @prefect.task
    def numbers():
        return [1, 2, 3]

    @prefect.task
    def identity(x):
        return x

    with Flow(name="test") as f:
        n = numbers()
        x = identity.map(n)

    # first run with a missing result from `n` but map_states for `x`
    state = FlowRunner(flow=f).run(
        executor=executor,
        task_states={
            n: Success(),
            x: Mapped(map_states=[Pending() for i in range(1, 4)]),
        },
        return_tasks=f.tasks,
    )

    assert state.is_successful()
    assert state.result[x].result == [None] * 3


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_unmapped_on_mapped(executor):
    @prefect.task
    def add_one(x):
        if isinstance(x, list):
            return x + x
        return x + 1

    with Flow("wild") as flow:
        res = add_one.map(unmapped(add_one.map([1, 2, 3])))

    flow_state = flow.run(executor=executor)

    assert flow_state.is_successful()
    assert flow_state.result[res].result == [2, 3, 4, 2, 3, 4]


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_all_tasks_only_called_once(capsys, executor):
    """
    See https://github.com/PrefectHQ/prefect/issues/556
    """

    @prefect.task
    def my_list():
        return list(range(5))

    @prefect.task
    def add_one(x):
        print("adding one to {}".format(x))
        return x + 1

    with Flow(name="test") as f:
        first_level = add_one.map(my_list)
        split_one = add_one.map(first_level)
        split_two = add_one.map(first_level)

    state = f.run()

    captured = capsys.readouterr()
    printed_lines = [line for line in captured.out.split("\n") if line != ""]

    assert len(printed_lines) == 15


def test_mapping_over_constants():
    @prefect.task
    def add_one(x):
        return x + 1

    with Flow("constants") as f:
        output = add_one.map(x=[1, 2, 3, 4])

    with raise_on_exception():
        flow_state = f.run()
    assert flow_state.is_successful()
    assert flow_state.result[output].result == [2, 3, 4, 5]


class TestLooping:
    def test_looping_works_with_mapping(self):
        @prefect.task
        def my_task(i):
            if prefect.context.get("task_loop_count", 1) < 3:
                raise prefect.engine.signals.LOOP(
                    result=prefect.context.get("task_loop_result", i) + 3
                )
            return prefect.context.get("task_loop_result")

        with Flow("looping-mapping") as flow:
            output = my_task.map(i=[1, 20])

        flow_state = flow.run()

        assert flow_state.is_successful()

        state = flow_state.result[output]
        assert state.is_mapped()
        assert [s.result for s in state.map_states] == [7, 26]

    def test_looping_works_with_mapping_and_individual_retries(self):
        state_history = []

        def handler(task, old, new):
            state_history.append(new)

        @prefect.task(
            max_retries=1,
            retry_delay=datetime.timedelta(seconds=0),
            state_handlers=[handler],
        )
        def my_task(i):
            if prefect.context.get("task_loop_count", 1) < 3:
                raise prefect.engine.signals.LOOP(
                    result=prefect.context.get("task_loop_result", i) + 3
                )
            if (
                prefect.context.get("task_loop_count", 1) == 3
                and prefect.context.get("task_run_count", 0) <= 1
            ):
                raise ValueError("Can't do it")
            return prefect.context.get("task_loop_result")

        with Flow("looping-mapping") as flow:
            output = my_task.map(i=[1, 20])

        flow_state = flow.run()

        assert flow_state.is_successful()

        state = flow_state.result[output]
        assert state.is_mapped()
        assert state.map_states[0].is_successful()
        assert state.map_states[1].is_successful()
        assert state.map_states[0].result == 1 + 3 + 3
        assert state.map_states[1].result == 20 + 3 + 3

        # finally assert that retries actually ocurred correctly
        # Pending -> Mapped (parent)
        # (Pending -> (Running -> Looped) * 2 -> Running -> Failed -> Retrying -> Running -> Successful) * 2
        assert len(state_history) == 19


class TestFlatMap:
    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_flatmap_constant(self, executor):
        # flatmap over a constant
        add = AddTask()

        with Flow(name="test") as f:
            a = add.map(flatten([[1, 2, 3]]))
            b = add.map(flatten([[1], [2], [3]]))
            c = add.map(flatten([[1], [2, 3]]))
            d = add.map(flatten([1, 2, 3]))

        s = f.run(executor=executor)

        # all results should be the same
        for task in [a, b, c, d]:
            assert s.result[task].result == [2, 3, 4]

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_flatmap_task_result(self, executor):
        # flatmap over a task
        ll = ListTask()
        nest = NestTask()
        a = AddTask()

        with Flow(name="test") as f:
            nested = nest(ll())
            x = a.map(flatten(nested))

        s = f.run(executor=executor)

        assert s.result[x].result == [2, 3, 4]

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_flatmap_mapped_result(self, executor):
        # flatmap over a mapped task
        ll = ListTask()
        nest = NestTask()
        a = AddTask()

        with Flow(name="test") as f:
            nested = nest.map(ll())
            x = a.map(flatten(nested))

        s = f.run(executor=executor)

        assert s.result[x].result == [2, 3, 4]

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_flatmap_flatmapped_result(self, executor):
        # flatmap over a flattened mapped task
        ll = ListTask()
        nest = NestTask()
        a = AddTask()

        with Flow(name="test") as f:
            nested = nest.map(ll())
            nested2 = nest.map(flatten(nested))
            x = a.map(flatten(nested2))

        s = f.run(executor=executor)

        assert s.result[x].result == [2, 3, 4]

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_flatmap_reduced_result(self, executor):
        # flatmap over a reduced flattened mapped task
        ll = ListTask()
        nest = NestTask()
        a = AddTask()

        with Flow(name="test") as f:
            nested = nest.map(ll())
            nested2 = nest(flatten(nested))
            x = a.map(flatten(nested2))

        from prefect.utilities.debug import raise_on_exception

        with raise_on_exception():
            s = f.run(executor=executor)

        assert s.result[x].result == [2, 3, 4]

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_flatmap_unnested_input(self, executor):
        a = AddTask()
        with Flow("test") as flow:
            z = a.map(x=flatten([1]))

        state = flow.run()
        assert state.result[z].is_mapped()
        assert state.result[z].result == [2]

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_flatmap_one_unnested_input(self, executor):
        a = AddTask()
        with Flow("test") as flow:
            z = a.map(x=flatten([1]), y=flatten([[5]]))

        state = flow.run()
        assert state.result[z].is_mapped()
        assert state.result[z].result == [6]

    @pytest.mark.parametrize(
        "executor", ["local", "sync", "mproc", "mthread"], indirect=True
    )
    def test_flatmap_one_unmappable_input(self, executor):
        a = AddTask()
        with Flow("test") as flow:
            z = a.map(x=flatten(1), y=flatten([[1]]))

        state = flow.run()
        assert state.result[z].is_failed()
        assert (
            state.result[z].message
            == "At least one upstream state has an unmappable result."
        )


def test_mapped_retries_regenerate_child_pipelines():
    """
    This test sets up a situation analogous to one found in Cloud: if a reduce task fails, and a user
    retries it in the future, we want to make sure that the mapped children pipelines are correctly
    regenerated.  When run against Cloud, these child tasks will correctly query for their states and
    the run will proceed with the correct data.

    This test mimics this scenario by running this flow with a provided set of states that only contain
    metadata about the runs with no actual data to reference.  The child runs should still be produced
    based only on the n_map_states attribute of the parent.
    """
    idt = IdTask()
    ll = ListTask()
    with Flow("test") as flow:
        mapped = idt.map(ll)
        reduced = idt(mapped)

    flow_state = flow.run()
    assert flow_state.is_successful()
    assert flow_state.result[mapped].is_mapped()
    assert flow_state.result[reduced].is_successful()
    assert flow_state.result[reduced].result == [1, 2, 3]

    second_pass_states = {mapped: Mapped(n_map_states=3), ll: Success(result=Result())}

    new_state = flow.run(task_states=second_pass_states)
    assert new_state.is_successful()
    assert new_state.result[mapped].is_mapped()
    assert new_state.result[reduced].is_successful()
