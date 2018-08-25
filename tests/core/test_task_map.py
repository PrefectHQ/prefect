import pytest

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


class SetTask(Task):
    def run(self):
        return {1, 2, 3}


def test_map_returns_a_task_copy():
    ll = ListTask()
    a = AddTask()

    with Flow():
        res = a.map(ll)

    assert res != a


def test_map_returns_a_mapped_task():
    ll = ListTask()
    a = AddTask()

    with Flow():
        res = a.map(ll)

    assert res.mapped == True


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


@pytest.mark.xfail(reason="This might be too hard")
def test_map_internally_respects_iterator_type():
    ll = SetTask()
    ii = IdTask()
    a = AddTask()

    with Flow() as f:
        res = ii(a.map(ll))

    s = f.run(return_tasks=f.tasks)
    assert s.result[res].result == {2, 3, 4}


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
        res = a.map(x=ll, y=ll)

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
