import pytest

from prefect import Flow, Task
from prefect.utilities.ids import (
    generate_flow_id,
    generate_task_ids,
    get_flow_from_id,
    get_task_from_id,
    register_flow,
)

TASKS = {}
LOOKUP_TASKS = {}


def get_task(name):
    if name not in TASKS:
        task = Task()
        TASKS[name] = task
        LOOKUP_TASKS[task] = name
    return TASKS[name]


@pytest.fixture
def reset_tasks():
    TASKS.clear()
    LOOKUP_TASKS.clear()


def count_hashes(task_hashes):
    return len(set(task_hashes.values()))


def flow_from_chains(*chains):
    """
    Builds a Flow from chains of task names.

    To build a flow that runs x, then y, then z, and also runs x2 after x:
        flow_from_chains(
            ['x', 'y', 'z'],
            ['x', 'x2']
        )
    """

    flow = Flow()
    with flow.restore_graph_on_error():
        for chain in chains:
            for name in chain:
                flow.add_task(get_task(name))
            for u_name, d_name in zip(chain, chain[1:]):
                flow.add_edge(get_task(u_name), get_task(d_name), validate=False)
    return flow


class TestFlowIDs:
    def test_flow_id(self):
        flow = Flow(name="flow")
        flow_versioned = Flow(name="flow", version="2")
        flow_2 = Flow(name="flow_2")
        flow_id = generate_flow_id(flow, seed=0)
        flow_versioned_id = generate_flow_id(flow_versioned, seed=0)
        flow_2_id = generate_flow_id(flow_2, seed=0)

        assert flow_id == "6b8cc02e-e2ee-5899-1f05-bd4410417a02"
        assert flow_versioned_id == "738df697-db1a-c8a6-0aa6-63996ad8ccbb"
        assert flow_2_id == "3d5b99f6-a2de-27b5-70f0-543870e88b4d"

    def test_random_seed(self):
        foo = Flow(name="foo")
        assert generate_flow_id(foo) != generate_flow_id(foo)


class TestTaskIDs:
    def test_no_tasks(self):
        assert generate_task_ids(Flow()) == {}

    def test_one_task(self):
        f = Flow()
        f.add_task(get_task("x"))
        assert count_hashes(generate_task_ids(f)) == 1

    def test_flow_id_affects_task_ids(self):
        f = Flow()
        f.add_task(get_task("x"))

        f2 = Flow()
        f2.add_task(get_task("x"))

        f3 = Flow(name="foo")
        f3.add_task(get_task("x"))

        assert generate_task_ids(f, seed=0) == generate_task_ids(f2, seed=0)
        assert generate_task_ids(f, seed=0) != generate_task_ids(f3, seed=0)

    def test_random_seed(self):
        """Test that ids are random"""
        f = flow_from_chains(["x", "y", "z"])
        assert generate_task_ids(f) != generate_task_ids(f)

    def test_set_seed(self):
        """Tests that ids are always the same for a given seed"""
        f = flow_from_chains(["x", "y", "z"])
        assert generate_task_ids(f, seed=1) == generate_task_ids(f, seed=1)

    def test_modify_task_changes_hash(self):
        f = Flow()
        t = Task()
        f.add_task(t)
        hash1 = generate_task_ids(f, seed=1)
        t.new_value = 9
        hash2 = generate_task_ids(f, seed=1)
        assert hash1 != hash2

    def test_two_dependent_tasks(self):
        """ x1 -> x2"""
        f = Flow()
        f.add_edge(get_task("x1"), get_task("x2"))
        assert count_hashes(generate_task_ids(f)) == 2

    def test_two_identical_subflows(self):
        """
            x1 -> x2
            y1 -> y2
        """
        f = flow_from_chains(["x1", "x2"], ["y1", "y2"])
        assert count_hashes(generate_task_ids(f)) == len(f.tasks)

    def test_three_identical_subflows(self):
        """
            x1 -> x2 -> x3
            y1 -> y2 -> y3
            z1 -> z2 -> z3
        """
        f = flow_from_chains(["x1", "x2", "x3"], ["y1", "y2", "y3"], ["z1", "z2", "z3"])
        independent_hashes = generate_task_ids(f, seed=1)
        assert len(independent_hashes) == len(f.tasks)

    def test_two_linked_subflows_and_one_independent(self):
        r"""
            x1 -> x2 -> x3
                \
            y1 -> y2 -> y3

            z1 -> z2 -> z3
        """
        # first test them independently
        f = flow_from_chains(["x1", "x2", "x3"], ["y1", "y2", "y3"], ["z1", "z2", "z3"])
        independent_hashes = generate_task_ids(f, seed=1)

        # add edge
        f.add_edge(get_task("x1"), get_task("y2"))
        dependent_hashes = generate_task_ids(f, seed=1)
        assert len(dependent_hashes) == len(f.tasks)
        assert independent_hashes != dependent_hashes

    def test_four_subflows(self):
        r"""
            x1 -> x2
                \
            y1 -> y2

            z1 -> z2 -> z3

            a1 -> a2 -> a3
        """

        f = flow_from_chains(
            ["x1", "x2"],
            ["y1", "y2"],
            ["x1", "y2"],
            ["z1", "z2", "z3"],
            ["a1", "a2", "a3"],
        )
        assert count_hashes(generate_task_ids(f)) == len(f.tasks)

    def test_four_subflows(self):
        r"""
            x1 -> x2 -> x3
                \
            y1 -> y2 -> y3

            z1 -> z2 -> z3 -> z4
                    \
                        a1 -> a2
        """

        f = flow_from_chains(
            ["x1", "x2", "x3"],
            ["y1", "y2", "y3"],
            ["x1", "y2"],
            ["z1", "z2", "z3", "z4"],
            ["z2", "a1", "a2"],
        )
        assert count_hashes(generate_task_ids(f)) == len(f.tasks)

    def test_diamond_flow(self):
        r"""
            x1 -> x2 -> x3
                \    /
                y1
        """

        f = flow_from_chains(["x1", "x2", "x3"], ["x1", "y1", "x3"])
        assert count_hashes(generate_task_ids(f)) == len(f.tasks)

    def test_ids_are_stable(self, reset_tasks):
        r"""
            x1 -> x2 -> x3 -> x4
                \    /
                y1
        """
        f1 = flow_from_chains(["x1", "x2", "x3", "x4"])
        f2 = flow_from_chains(["x1", "x2", "x3", "x4"], ["x1", "y1", "x3"])

        get_task("x3").name = "x3"
        f1_hashes = generate_task_ids(f1, seed=0)
        f2_hashes = generate_task_ids(f2, seed=0)
        assert f1_hashes[get_task("x3")] == f2_hashes[get_task("x3")]
        assert f1_hashes[get_task("x4")] == f2_hashes[get_task("x4")]


class TestRetrieveIDs:
    def test_retrieve_flow_by_id(self):
        f = flow_from_chains(["a", "b", "c"], ["a", "x", "y"])
        ids = register_flow(f)
        assert get_flow_from_id(ids["flow_id"]) is f

    def test_retrieve_task_by_id(self):
        f = flow_from_chains(["a", "b", "c"], ["a", "x", "y"])
        ids = register_flow(f)
        assert all(get_task_from_id(i) is t for t, i in ids["task_ids"].items())
