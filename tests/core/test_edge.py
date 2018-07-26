import pytest

from prefect.core import Edge, Flow, Task


class TaskWithKey(Task):
    def run(self, a_key):
        return a_key


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
    flow = Flow()
    t1 = TaskWithKey()
    t2 = TaskWithKey()
    flow.add_edge(t1, t2, key="a_key")

    assert Edge(t1, t2, key="a_key") in flow.edges
