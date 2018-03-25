import pytest
from prefect.utilities.ids import generate_task_ids, generate_flow_id
from prefect import Flow, Task

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
                flow.add_edge(
                    get_task(u_name), get_task(d_name), validate=False)
    return flow

class TestFlowIDs:
    def test_flow_id(self):
        foo = Flow(name='foo')
        foo2 = Flow(name='foo', version='2')
        bar = Flow(name='bar')
        foo_id = generate_flow_id(foo, seed=0)
        foo2_id = generate_flow_id(foo2, seed=0)
        bar_id = generate_flow_id(bar, seed=0)

        assert foo_id == 'a356e1cd-2caf-2b7c-2511-63efa50ed5f3'
        assert foo2_id == '5d2d25f5-c223-fbcd-c583-094bd451df0f'
        assert bar_id == 'ff9571b7-5abb-c4aa-12e6-212725977111'

    def test_random_seed(self):
        foo = Flow(name='foo')
        assert generate_flow_id(foo) != generate_flow_id(foo)

class TestTaskIDs:

    def test_no_tasks(self):
        assert generate_task_ids(Flow()) == {}


    def test_one_task(self):
        f = Flow()
        f.add_task(get_task('x'))
        assert count_hashes(generate_task_ids(f)) == 1

    def test_flow_id_affects_task_ids(self):
        f = Flow()
        f.add_task(get_task('x'))

        f2 = Flow()
        f2.add_task(get_task('x'))

        f3 = Flow(name='foo')
        f3.add_task(get_task('x'))

        assert generate_task_ids(f, seed=0) == generate_task_ids(f2, seed=0)
        assert generate_task_ids(f, seed=0) != generate_task_ids(f3, seed=0)

    def test_random_seed(self):
        """Test that ids are random"""
        f = flow_from_chains(['x', 'y', 'z'])
        assert generate_task_ids(f) != generate_task_ids(f)


    def test_set_seed(self):
        """Tests that ids are always the same for a given seed"""
        f = flow_from_chains(['x', 'y', 'z'])
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
        f.add_edge(get_task('x1'), get_task('x2'))
        assert count_hashes(generate_task_ids(f)) == 2


    def test_two_identical_subflows(self):
        """
            x1 -> x2
            y1 -> y2
        """
        f = flow_from_chains(
            ['x1', 'x2'],
            ['y1', 'y2'],
        )
        assert count_hashes(generate_task_ids(f)) == len(f.tasks)


    def test_three_identical_subflows(self):
        """
            x1 -> x2 -> x3
            y1 -> y2 -> y3
            z1 -> z2 -> z3
        """
        f = flow_from_chains(
            ['x1', 'x2', 'x3'],
            ['y1', 'y2', 'y3'],
            ['z1', 'z2', 'z3'],
        )
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
        f = flow_from_chains(
            ['x1', 'x2', 'x3'],
            ['y1', 'y2', 'y3'],
            ['z1', 'z2', 'z3'],
        )
        independent_hashes = generate_task_ids(f, seed=1)

        # add edge
        f.add_edge(get_task('x1'), get_task('y2'))
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
            ['x1', 'x2'],
            ['y1', 'y2'],
            ['x1', 'y2'],
            ['z1', 'z2', 'z3'],
            ['a1', 'a2', 'a3'],
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
            ['x1', 'x2', 'x3'],
            ['y1', 'y2', 'y3'],
            ['x1', 'y2'],
            ['z1', 'z2', 'z3', 'z4'],
            ['z2', 'a1', 'a2'],
        )
        assert count_hashes(generate_task_ids(f)) == len(f.tasks)


    def test_diamond_flow(self):
        r"""
            x1 -> x2 -> x3
                \    /
                y1
        """

        f = flow_from_chains(
            ['x1', 'x2', 'x3'],
            ['x1', 'y1', 'x3'],
        )
        assert count_hashes(generate_task_ids(f)) == len(f.tasks)


    def test_ids_are_stable(self, reset_tasks):
        r"""
            x1 -> x2 -> x3 -> x4
                \    /
                y1
        """
        f1 = flow_from_chains(['x1', 'x2', 'x3', 'x4'],)
        f2 = flow_from_chains(
            ['x1', 'x2', 'x3', 'x4'],
            ['x1', 'y1', 'x3'],
        )

        get_task('x3').name = 'x3'
        f1_hashes = generate_task_ids(f1, seed=0)
        f2_hashes = generate_task_ids(f2, seed=0)
        assert f1_hashes[get_task('x3')] == f2_hashes[get_task('x3')]
        assert f1_hashes[get_task('x4')] == f2_hashes[get_task('x4')]
