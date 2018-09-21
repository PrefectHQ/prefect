import pytest
import random
import time

import prefect
from prefect.core import Edge, Flow, Parameter, Task
from prefect.utilities.tasks import task, unmapped
from prefect.utilities.tests import raise_on_exception


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

    with Flow():
        res = a.map(ll)

    assert res != a


def test_calling_map_with_bind_returns_self():
    ll = ListTask()
    a = AddTask()

    with Flow():
        res = a.bind(ll, mapped=True)

    assert res is a


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_map_spawns_new_tasks(executor):
    ll = ListTask()
    a = AddTask()

    with Flow() as f:
        res = a.map(ll)

    s = f.run(return_tasks=f.tasks, executor=executor)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [2, 3, 4]


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_map_over_parameters(executor):
    a = AddTask()

    with Flow() as f:
        ll = Parameter("list")
        res = a.map(ll)

    s = f.run(return_tasks=f.tasks, executor=executor, parameters=dict(list=[1, 2, 3]))
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [2, 3, 4]


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_map_internally_returns_a_list(executor):
    ll = ListTask()
    ii = IdTask()
    a = AddTask()

    with Flow() as f:
        res = ii(a.map(ll))

    s = f.run(return_tasks=f.tasks, executor=executor)
    assert s.result[res].result == [2, 3, 4]


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_map_composition(executor):
    ll = ListTask()
    a = AddTask()

    with Flow() as f:
        res = a.map(a.map(ll))

    s = f.run(return_tasks=f.tasks, executor=executor)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [3, 4, 5]


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_multiple_map_arguments(executor):
    ll = ListTask()
    a = AddTask()

    with Flow() as f:
        res = a.map(x=ll, y=ll())

    s = f.run(return_tasks=f.tasks, executor=executor)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [2, 4, 6]


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_map_failures_dont_leak_out(executor):
    ii = IdTask()
    ll = ListTask()
    a = AddTask()
    div = DivTask()

    with Flow() as f:
        res = ii.map(div.map(a.map(ll(start=-1))))

    s = f.run(return_tasks=f.tasks, executor=executor)
    slist = s.result[res]
    assert s.is_failed()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [None, 1, 0.5]


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_map_can_handle_fixed_kwargs(executor):
    ll = ListTask()
    a = AddTask()

    with Flow() as f:
        res = a.map(ll, y=unmapped(5))

    s = f.run(return_tasks=f.tasks, executor=executor)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [6, 7, 8]


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_map_can_handle_nonkeyed_upstreams(executor):
    ll = ListTask()

    with Flow() as f:
        res = ll.map(upstream_tasks=[ll()])

    s = f.run(return_tasks=f.tasks, executor=executor)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [[1, 2, 3] for _ in range(3)]


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_map_can_handle_nonkeyed_mapped_upstreams(executor):
    ii = IdTask()
    ll = ListTask()

    with Flow() as f:
        mapped = ii.map(ll())  # 1, 2, 3
        res = ll.map(upstream_tasks=[mapped])

    s = f.run(return_tasks=f.tasks, executor=executor)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [[1, 2, 3] for _ in range(3)]


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_map_can_handle_nonkeyed_nonmapped_upstreams_and_mapped_args(executor):
    ii = IdTask()
    ll = ListTask()

    with Flow() as f:
        res = ll.map(start=ll(), upstream_tasks=[unmapped(ii(5))])

    s = f.run(return_tasks=f.tasks, executor=executor)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [[1 + i, 2 + i, 3 + i] for i in range(3)]


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_map_tracks_non_mapped_upstream_tasks(executor):
    div = DivTask()

    @task
    def zeros():
        return [0, 0, 0]

    @task(trigger=prefect.triggers.all_failed)
    def register(x):
        return True

    with Flow() as f:
        res = register.map(div.map(zeros()), upstream_tasks=[unmapped(div(1))])

    s = f.run(return_tasks=f.tasks, executor=executor)
    assert s.is_failed()
    assert all([sub.is_failed() for sub in s.result[res]])
    assert all(
        [isinstance(sub, prefect.engine.state.TriggerFailed) for sub in s.result[res]]
    )


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_map_allows_for_retries(executor):
    ii = IdTask()
    ll = ListTask()
    div = DivTask()

    with Flow() as f:
        divved = div.map(ll(start=0))
        res = ii.map(divved)

    states = f.run(return_tasks=[divved], executor=executor)
    assert states.is_failed()  # division by zero

    old = states.result[divved]
    assert [s.result for s in old] == [None, 1.0, 0.5]

    old[0] = prefect.engine.state.Success(result=100)
    states = f.run(
        return_tasks=[res],
        start_tasks=[res],
        task_states={divved: old},
        executor=executor,
    )
    assert states.is_successful()  # no divison by 0

    new = states.result[res]
    assert [s.result for s in new] == [100, 1.0, 0.5]


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_map_can_handle_nonkeyed_mapped_upstreams_and_mapped_args(executor):
    ii = IdTask()
    ll = ListTask()

    with Flow() as f:
        mapped = ii.map(ll())  # 1, 2, 3
        res = ll.map(start=ll(), upstream_tasks=[mapped])

    s = f.run(return_tasks=f.tasks, executor=executor)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [[1 + i, 2 + i, 3 + i] for i in range(3)]


@pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
def test_map_behaves_like_zip_with_differing_length_results(executor):
    "Tests that map stops combining elements after the smallest list is exhausted."

    @prefect.task
    def ll(n):
        return list(range(n))

    add = AddTask()

    with Flow() as f:
        res = add.map(x=ll(3), y=ll(2))

    s = f.run(return_tasks=[res], executor=executor)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 2
    assert [r.result for r in slist] == [0, 2]


@pytest.mark.xfail(
    reason="Is sensitive to how dask.bag partitions -- occasionally passes."
)
@pytest.mark.parametrize("executor", ["sync"], indirect=True)
def test_synchronous_map_cannot_handle_mapping_different_length_results(executor):
    @prefect.task
    def ll(n):
        return list(range(n))

    add = AddTask()

    with Flow() as f:
        res = add.map(x=ll(3), y=ll(2))

    s = f.run(return_tasks=[res], executor=executor)
    assert s.is_failed()
    assert "map called with multiple bags that aren't identically partitioned" in str(
        s.message
    )


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_map_works_with_retries_and_cached_states(executor):
    """
    This test isn't meant to test the correct way of handling caching for mapped
    tasks, but is meant to test the only way that works right now - instead of
    passing in a list of states for the mapped task, we instead pass in a list of
    states for the _upstream_ task to the mapped task.
    """

    @prefect.task
    def ll():
        return [0, 1, 2]

    div = DivTask(max_retries=1)

    with Flow() as f:
        res = div.map(x=ll)

    s = f.run(return_tasks=[ll, res], executor=executor)
    assert s.is_pending()
    slist = s.result[res]
    assert slist[0].is_pending()
    assert slist[1].is_successful()
    assert slist[2].is_successful()

    # this is the part that is non-standard
    # we create a list of _new_ states for the _upstream_ tasks of res
    ll_state = s.result[ll]
    cached_state = [type(ll_state)(result=x) for x in ll_state.result]
    cached_state[0].result = 10

    s = f.run(
        return_tasks=[res],
        executor=executor,
        task_states={ll: cached_state},
        start_tasks=[res],
    )
    assert s.is_successful()
    assert s.result[res][0].result == 1 / 10


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_task_map_doesnt_bottleneck(executor):
    @prefect.task
    def ll():
        return [1, 2, 3]

    @prefect.task
    def zz(s):
        return s == 1 or time.sleep(1.5)  # we dont expect sleep to complete

    @prefect.task
    def rec(s):
        if s == 1:
            raise SyntaxError("flower")
        else:
            raise NotImplementedError("cactus")

    with Flow() as f:
        res = rec.map(zz.map(ll))

    with pytest.raises(SyntaxError) as exc:
        with raise_on_exception():
            state = f.run(executor=executor)


@pytest.mark.parametrize("executor", ["sync", "mproc", "mthread"], indirect=True)
def test_task_map_doesnt_assume_purity_of_functions(executor):
    @prefect.task
    def ll():
        return [1, 1, 1]

    @prefect.task
    def zz(s):
        return random.random()

    with Flow() as f:
        res = zz.map(ll)

    state = f.run(executor=executor, return_tasks=[res])
    assert state.is_successful()
    outputs = [s.result for s in state.result[res]]
    assert len(set(outputs)) == 3
    print(set(outputs))
