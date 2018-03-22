import pytest
from prefect.utilities.hashing import hash_object, get_task_hashes
from prefect import Flow, Task, task

TASKS = {}


def get_task(name):
    if name not in TASKS:
        TASKS[name] = Task()
    return TASKS[name]


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
    for chain in chains:
        for name in chain:
            flow.add_task(get_task(name))
        for u_name, d_name in zip(chain, chain[1:]):
            flow.add_edge(get_task(u_name), get_task(d_name))
    return flow


def test_no_tasks():
    assert get_task_hashes(Flow()) == {}


def test_one_task():
    f = Flow()
    f.add_task(get_task('x'))
    assert len(get_task_hashes(f)) == 1


def test_random_seed():
    """Test that hashes are random"""
    f = flow_from_chains(['x', 'y', 'z'])
    assert get_task_hashes(f) != get_task_hashes(f)


def test_set_seed():
    """Tests that hashes are always the same for a given seed"""
    f = flow_from_chains(['x', 'y', 'z'])
    assert get_task_hashes(f, seed=1) == get_task_hashes(f, seed=1)


def test_modify_task_changes_hash():
    f = Flow()
    t = Task()
    f.add_task(t)
    hash1 = get_task_hashes(f, seed=1)
    t.new_value = 9
    hash2 = get_task_hashes(f, seed=1)
    assert hash1 != hash2


def test_two_dependent_tasks():
    """ x1 -> x2"""
    f = Flow()
    f.add_edge(get_task('x1'), get_task('x2'))
    assert len(get_task_hashes(f)) == 2


def test_two_identical_subflows():
    """
        x1 -> x2
        y1 -> y2
    """
    f = flow_from_chains(
        ['x1', 'x2'],
        ['y1', 'y2'],
    )
    assert len(get_task_hashes(f)) == len(f.tasks)


def test_three_identical_subflows():
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
    independent_hashes = get_task_hashes(f, seed=1)
    assert len(independent_hashes) == len(f.tasks)


def test_two_linked_subflows_and_one_independent():
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
    independent_hashes = get_task_hashes(f, seed=1)

    # add edge
    f.add_edge(get_task('x1'), get_task('y2'))
    dependent_hashes = get_task_hashes(f, seed=1)
    assert len(dependent_hashes) == len(f.tasks)
    assert independent_hashes != dependent_hashes


def test_four_subflows():
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
    assert len(get_task_hashes(f)) == len(f.tasks)


def test_four_subflows():
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
    assert len(get_task_hashes(f)) == len(f.tasks)

