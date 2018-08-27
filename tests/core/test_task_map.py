import pytest
import time

import prefect
from prefect.core import Edge, Flow, Parameter, Task
from prefect.utilities.tasks import task
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


def test_map_spawns_new_tasks():
    ll = ListTask()
    a = AddTask()

    with Flow() as f:
        res = a.map(ll)

    s = f.run(return_tasks=f.tasks)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [2, 3, 4]


def test_map_internally_returns_a_list():
    ll = ListTask()
    ii = IdTask()
    a = AddTask()

    with Flow() as f:
        res = ii(a.map(ll))

    s = f.run(return_tasks=f.tasks)
    assert s.result[res].result == [2, 3, 4]


def test_map_composition():
    ll = ListTask()
    a = AddTask()

    with Flow() as f:
        res = a.map(a.map(ll))

    s = f.run(return_tasks=f.tasks)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [3, 4, 5]


def test_multiple_map_arguments():
    ll = ListTask()
    a = AddTask()

    with Flow() as f:
        res = a.map(x=ll, y=ll())

    s = f.run(return_tasks=f.tasks)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [2, 4, 6]


def test_map_failures_dont_leak_out():
    ii = IdTask()
    ll = ListTask()
    a = AddTask()
    div = DivTask()

    with Flow() as f:
        res = ii.map(div.map(a.map(ll(start=-1))))

    s = f.run(return_tasks=f.tasks)
    slist = s.result[res]
    assert s.is_failed()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [None, 1, 0.5]


def test_map_can_handle_fixed_kwargs():
    ll = ListTask()
    a = AddTask()

    with Flow() as f:
        res = a.map(ll, unmapped=dict(y=5))

    s = f.run(return_tasks=f.tasks)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [6, 7, 8]


def test_map_can_handle_nonkeyed_upstreams():
    ll = ListTask()

    with Flow() as f:
        res = ll.map(upstream_tasks=[ll()])

    s = f.run(return_tasks=f.tasks)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [[1, 2, 3] for _ in range(3)]


def test_map_can_handle_nonkeyed_mapped_upstreams():
    ii = IdTask()
    ll = ListTask()

    with Flow() as f:
        mapped = ii.map(ll())  # 1, 2, 3
        res = ll.map(upstream_tasks=[mapped])

    s = f.run(return_tasks=f.tasks)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [[1, 2, 3] for _ in range(3)]


def test_map_can_handle_nonkeyed_nonmapped_upstreams_and_mapped_args():
    ii = IdTask()
    ll = ListTask()

    with Flow() as f:
        res = ll.map(start=ll(), unmapped={None: [ii(5)]})

    s = f.run(return_tasks=f.tasks)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [[1 + i, 2 + i, 3 + i] for i in range(3)]


def test_map_tracks_non_mapped_upstream_tasks():
    div = DivTask()

    @task
    def zeros():
        return [0, 0, 0]

    @task(trigger=prefect.triggers.all_failed)
    def register(x):
        return True

    with Flow() as f:
        res = register.map(div.map(zeros()), unmapped={None: [div(1)]})

    s = f.run(return_tasks=f.tasks)
    assert s.is_failed()
    assert all([sub.is_failed() for sub in s.result[res]])
    assert all(
        [isinstance(sub, prefect.engine.state.TriggerFailed) for sub in s.result[res]]
    )


def test_map_allows_for_retries():
    ii = IdTask()
    ll = ListTask()
    div = DivTask()

    with Flow() as f:
        divved = div.map(ll(start=0))
        res = ii.map(divved)

    states = f.run(return_tasks=[divved])
    assert states.is_failed()  # division by zero

    old = states.result[divved]
    assert [s.result for s in old] == [None, 1.0, 0.5]

    old[0] = prefect.engine.state.Success(result=100)
    states = f.run(return_tasks=[res], start_tasks=[res], task_states={divved: old})
    assert states.is_successful()  # no divison by 0

    new = states.result[res]
    assert [s.result for s in new] == [100, 1.0, 0.5]


def test_map_can_handle_nonkeyed_mapped_upstreams_and_mapped_args():
    ii = IdTask()
    ll = ListTask()

    with Flow() as f:
        mapped = ii.map(ll())  # 1, 2, 3
        res = ll.map(start=ll(), upstream_tasks=[mapped])

    s = f.run(return_tasks=f.tasks)
    slist = s.result[res]
    assert s.is_successful()
    assert isinstance(slist, list)
    assert len(slist) == 3
    assert [r.result for r in slist] == [[1 + i, 2 + i, 3 + i] for i in range(3)]
