import pytest

import prefect
from prefect.core import Edge, Flow, Task


class TaskWithKey(Task):
    def run(self, a_key):
        return a_key


def test_edge_doesnt_allow_direct_cycles():
    with pytest.raises(ValueError, match="Edges can not connect a task to itself"):
        Edge(1, 1)

    with pytest.raises(ValueError, match="Edges can not connect a task to itself"):
        Edge(None, None)

    with pytest.raises(ValueError, match="Edges can not connect a task to itself"):
        t = Task()
        Edge(t, t)


def test_edge_key_must_be_valid():
    assert Edge(Task(), Task(), key=None)
    assert Edge(Task(), Task(), key="test")
    assert Edge(Task(), Task(), key="test_underscore")

    # int key is not allowed
    with pytest.raises(ValueError):
        Edge(Task(), Task(), key=1)

    with pytest.raises(ValueError):
        Edge(Task(), Task(), key=Task())

    with pytest.raises(ValueError):
        Edge(Task(), Task(), key="name with space")

    with pytest.raises(ValueError):
        Edge(Task(), Task(), key="5number")

    with pytest.raises(ValueError):
        Edge(Task(), Task(), key="this.that")


def test_edge_hashes_match():
    """
    Edges that are identical have the same hash, and can be used to test inclusion in
    dicts (or index a dict)
    """

    t1 = Task()
    t2 = Task()
    e1 = Edge(t1, t2, key="a_key")
    e2 = Edge(t1, t2, key="a_key")
    assert hash(e1) == hash(e2)
    assert hash(Edge(Task(), Task(), key=None)) != hash(Edge(Task(), Task(), key=None))


def test_new_edge_objects_can_test_membership_in_flow():
    flow = Flow(name="test")
    t1 = TaskWithKey()
    t2 = TaskWithKey()
    flow.add_edge(t1, t2, key="a_key")

    assert Edge(t1, t2, key="a_key") in flow.edges


def test_edge_has_tasks_property():
    t1 = Task()
    t2 = TaskWithKey()
    t3 = Task()
    edge = Edge(t1, t2, key="a_key")
    assert edge.tasks == {t1, t2}


def test_edge_equality():
    t1 = Task()
    t2 = Task()

    assert Edge(t1, t2) == Edge(t1, t2)
    assert Edge(t1, t2, "key") == Edge(t1, t2, "key")
    assert Edge(t1, t2, "key", True) == Edge(t1, t2, "key", True)

    assert Edge(t1, t2) != Edge(t2, t1)
    assert Edge(t1, t2, "key") != Edge(t1, t2, "other_key")
    assert Edge(t1, t2, "key", True) != Edge(t1, t2, "key", False)


def test_object_inequality():
    assert Edge(Task(), Task()) != 1


def test_serialize_edge():
    t1 = Task()
    t2 = Task()
    edge = Edge(t1, t2, key="key", mapped=True)
    assert edge.serialize() == dict(
        upstream_task=dict(slug=t1.slug, __version__=prefect.__version__),
        downstream_task=dict(slug=t2.slug, __version__=prefect.__version__),
        key="key",
        mapped=True,
        __version__=prefect.__version__,
    )
