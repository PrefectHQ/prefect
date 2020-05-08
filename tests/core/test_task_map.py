import datetime
import random
import time

import pytest

import prefect
from prefect.core import Edge, Flow, Parameter, Task
from prefect.engine.flow_runner import FlowRunner
from prefect.engine.result import NoResult, Result, NoResult
from prefect.engine.state import Mapped, Pending, Retrying, Success
from prefect.utilities.debug import raise_on_exception
from prefect.utilities.tasks import task, unmapped


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
    assert all([isinstance(ms, Success) for ms in m.map_states])
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
    assert isinstance(m.result[0], Exception)
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
    assert all([sub.is_failed() for sub in s.result[res].map_states])
    assert all(
        [
            isinstance(sub, prefect.engine.state.TriggerFailed)
            for sub in s.result[res].map_states
        ]
    )


@pytest.mark.parametrize(
    "executor", ["local", "sync", "mproc", "mthread"], indirect=True
)
def test_map_preserves_flowrunners_initial_context(executor):
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
    """

    @prefect.task
    def numbers():
        return [1, 2, 3]

    @prefect.task
    def plus_one(x):
        return x + 1

    @prefect.task
    def get_sum(x):
        return sum(x)

    with Flow(name="test") as f:
        n = numbers()
        x = plus_one.map(n)
        y = plus_one.map(x)
        s = get_sum(y)

    # first run with a missing result from `n` but map_states for `x`
    state = FlowRunner(flow=f).run(
        executor=executor,
        task_states={
            n: Success(),
            x: Mapped(
                map_states=[
                    Pending(cached_inputs={"x": Result(i)}) for i in range(1, 4)
                ]
            ),
        },
        return_tasks=f.tasks,
    )

    assert state.is_successful()
    assert state.result[s].result == 12

    # next run with missing results for n and x
    state = FlowRunner(flow=f).run(
        executor=executor,
        task_states={
            n: Success(),
            x: Mapped(map_states=[Success(), Success(), Success()]),
            y: Mapped(
                map_states=[
                    Success(result=3),
                    Success(result=4),
                    Retrying(cached_inputs={"x": Result(4)}),
                ]
            ),
        },
        return_tasks=f.tasks,
    )

    assert state.is_successful()
    assert state.result[s].result == 12

    # next run with missing results for n, x, and y
    state = FlowRunner(flow=f).run(
        executor=executor,
        task_states={
            n: Success(),
            x: Mapped(map_states=[Success(), Success(), Success()]),
            y: Mapped(
                map_states=[Success(result=3), Success(result=4), Success(result=5)]
            ),
        },
        return_tasks=f.tasks,
    )

    assert state.is_successful()
    assert state.result[s].result == 12


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
