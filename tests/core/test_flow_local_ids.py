import pytest

from prefect import Flow, Task

TASKS = {}


@pytest.fixture(autouse=True)
def clear_data():
    TASKS.clear()


class IdenticalTask(Task):
    def __init__(self, _name):
        self._name = _name
        super().__init__()

    def __repr__():
        return self._name


def get_task(name):
    """
    Returns a generic task that can be retrieved by the provided name.
    """
    if name not in TASKS:
        task = IdenticalTask(name)
        TASKS[name] = task
    return TASKS[name]


def count_unique_ids(id_dict):
    """
    Helper functions to count the number of unique task ids returned by
    generate_local_task_ids
    """

    return len(set(id_dict.values()))


def flow_from_chains(*chains):
    """
    Builds a Flow from chains of task names.

    To build a flow that runs x, then y, then z, and also runs x2 after x:
        flow_from_chains(
            ['x', 'y', 'z'],
            ['x', 'x2']
        )

    The tasks in the returned flow are all completely identical.
    """

    flow = Flow()
    for chain in chains:
        for name in chain:
            flow.add_task(get_task(name))
        for u_name, d_name in zip(chain, chain[1:]):
            flow.add_edge(get_task(u_name), get_task(d_name), validate=False)
    return flow


def test_no_tasks_returns_empty_dict():
    assert Flow().generate_local_task_ids() == {}


def test_one_task():
    f = Flow()
    f.add_task(get_task("x"))
    assert len(f.generate_local_task_ids) == 1


def test_flow_id_affects_task_ids():
    f = Flow()
    f.add_task(get_task("x"))

    f2 = Flow()
    f2.add_task(get_task("x"))

    f3 = Flow(name="foo")
    f3.add_task(get_task("x"))

    assert f.generate_local_task_ids() == f2.generate_local_task_ids()
    assert f.generate_local_task_ids() != f3.generate_local_task_ids()


def test_modify_task_changes_hash():
    f = Flow()
    t = Task()
    f.add_task(t)
    hash1 = f.generate_local_task_ids()
    # this is not an attribute referenced in task.serialize(), so it should not affect the id
    t.new_attribute = "hi"
    hash2 = f.generate_local_task_ids()
    # this is an attribute referenced in task.serialize(), so it should affect the id
    t.slug = "hi"
    hash3 = f.generate_local_task_ids()
    assert hash1 == hash2
    assert hash1 != hash3


def test_one_task():
    """
    x1

    A single task
    """
    f = Flow()
    f.add_task(get_task("x1"))
    steps = f.generate_local_task_ids(_debug_steps=True)

    # the task is uniquely identified by its own characteristics
    assert count_unique_ids(steps[1]) == 1

    # no further processing
    assert steps[1] == steps[2] == steps[3] == steps[4] == steps[5]


def test_two_independent_tasks():
    """
    x1
    x2

    Two identical but independent tasks
    """
    f = Flow()
    f.add_task(get_task("x1"))
    f.add_task(get_task("x2"))

    steps = f.generate_local_task_ids(_debug_steps=True)

    # each task generates the same id based on its own characteristics
    assert count_unique_ids(steps[1]) == 1

    # each step generates new ids
    assert steps[1] != steps[2] != steps[3] != steps[4] != steps[5]

    # ...but the ids are not unique
    for i in range(1, 5):
        assert count_unique_ids(steps[i]) == 1

    # disambiguation finally takes place in step 5
    assert count_unique_ids(steps[5]) == 2


def test_ten_independent_tasks():
    """
    x1
    x2
    ...
    x10

    Ten identical but independent tasks
    """
    f = Flow()
    for i in range(1, 11):
        f.add_task(get_task("x{}".format(i)))

    steps = f.generate_local_task_ids(_debug_steps=True)

    # each task generates the same id based on its own characteristics
    assert count_unique_ids(steps[1]) == 1

    # each step generates new ids
    assert steps[1] != steps[2] != steps[3] != steps[4] != steps[5]

    # ...but the ids are not unique
    for i in range(1, 5):
        assert count_unique_ids(steps[i]) == 1

    # disambiguation finally takes place in step 5
    assert count_unique_ids(steps[5]) == 10


def test_ten_different_tasks():
    """
    x1
    x2
    ...
    x10

    Ten non-identical and independent tasks
    """
    f = Flow()
    for i in range(1, 11):
        f.add_task(Task(name=str(i)))

    steps = f.generate_local_task_ids(_debug_steps=True)

    # tasks are immediately identifiable
    assert count_unique_ids(steps[1]) == 10

    # no further processing
    assert steps[1] == steps[2] == steps[3] == steps[4] == steps[5]


def test_two_dependent_tasks():
    """
    x1 -> x2

    Two identical tasks in a row
    """
    f = Flow()
    f.add_edge(get_task("x1"), get_task("x2"))
    steps = f.generate_local_task_ids(_debug_steps=True)

    # step 1 isn't enough to differentiate the tasks
    assert count_unique_ids(steps[1]) == 1

    # step 2 is able to differentiate them
    assert count_unique_ids(steps[2]) == 2

    # no further processing
    assert steps[2] == steps[3] == steps[4] == steps[5]


def test_two_identical_subflows():
    """
        x1 -> x2
        y1 -> y2

    The tasks in each subgraph are indistinguishable from each other. One will be
    randomly selected and adjusted.
    """
    f = flow_from_chains(["x1", "x2"], ["y1", "y2"])
    steps = f.generate_local_task_ids(_debug_steps=True)

    # step 1 can't tell any of the tasks apart
    assert count_unique_ids(steps[1]) == 1

    # step 2 is able to differentiate them but only within their respective sub-flows
    assert count_unique_ids(steps[2]) == 2

    # steps 3 and 4 are ineffective
    assert count_unique_ids(steps[3]) == 2
    assert count_unique_ids(steps[4]) == 2

    # step 5 can tell them apart
    assert count_unique_ids(steps[5]) == 4


def test_two_linked_subflows():
    r"""
        x1 -> x2 -> x3
            \
        y1 -> y2 -> y3

    All of these tasks except x1 / y1 can be distinguished by walking through the graph
    forwards (step 2); x1/y1 can be distinguished by additionally walking backwards
    (step 3).
    """
    # first test them independently
    f = flow_from_chains(["x1", "x2", "x3"], ["y1", "y2", "y3"], ["x1", "y2"])
    steps = f.generate_local_task_ids(_debug_steps=True)

    # all tasks are individually indistinguishable
    assert count_unique_ids(steps[1]) == 1

    # forward walk id's all but x1 / y1
    assert count_unique_ids(steps[2]) == 5

    # backwards walk ids x1 / y1
    assert count_unique_ids(steps[3]) == len(f.tasks) == 6

    # no further processing
    assert steps[3] == steps[4] == steps[5]


def test_three_identical_subflows():
    """
        x1 -> x2 -> x3
        y1 -> y2 -> y3
        z1 -> z2 -> z3

    These subflows are indistinguishable from each other
    """
    f = flow_from_chains(["x1", "x2", "x3"], ["y1", "y2", "y3"], ["z1", "z2", "z3"])
    steps = f.generate_local_task_ids(_debug_steps=True)

    # all tasks are individually indistinguishable
    assert count_unique_ids(steps[1]) == 1

    # forward walk id's each task in each subflow, no other neighbor-based
    # detection possible
    for step in [2, 3, 4]:
        assert count_unique_ids(steps[step]) == 3

    # step 5 disambiguates the 3 subflows
    assert count_unique_ids(steps[5]) == len(f.tasks) == 9


def test_two_linked_subflows_and_one_independent():
    r"""
        x1 -> x2 -> x3
            \
        y1 -> y2 -> y3

        z1 -> z2 -> z3

    Walking forward and backward is enough to distinguish x1 from y1, but not enough
    to distinguish x3 from z3. Concentric neighbor detection is, however.

    """
    # first test them independently
    f = flow_from_chains(
        ["x1", "x2", "x3"], ["y1", "y2", "y3"], ["z1", "z2", "z3"], ["x1", "y2"]
    )
    steps = f.generate_local_task_ids(_debug_steps=True)

    # all tasks are individually indistinguishable
    assert count_unique_ids(steps[1]) == 1

    # forward walk is able to identify:
    # -  y2, y3 uniquely
    # -  (x1/y1/z1), (x2/z2), (x3/z3) as differentiated groups
    assert count_unique_ids(steps[2]) == 5

    # reverse walk is able to additionally identify:
    # - y1, x1
    assert count_unique_ids(steps[3]) == 7

    # because the subgraphs are not identical, concentric neighbor search identifies
    # all remaining tasks
    assert count_unique_ids(steps[4]) == count_unique_ids(steps[5]) == len(f.tasks) == 9


def test_pathological_flow():
    r"""

        a0 -> a1 -> a2 -> a3 -> a4 -> a5 -> a6 -> a7 -> a8 -> a9
                                    \
        b0 -> b1 -> b2 -> b3 -> b4 -> b5 -> b6 -> b7 -> b8 -> b9
                                    \
        c0 -> c1 -> c2 -> c3 -> c4 -> c5 -> c6 -> c7 -> c8 -> c9
                                    \
        d0 -> d1 -> d2 -> d3 -> d4 -> d5 -> d6 -> d7 -> d8 -> d9
                                    \
        e0 -> e1 -> e2 -> e3 -> e4 -> e5 -> e6 -> e7 -> e8 -> e9

    To fully diffuse all information across this flow would take five forward and backward
    passes. However, concentric neighbor search should be able to solve it (albeit slowly)

    This is called "pathological" because an original algorithm included one forward and
    one backward pass and no neighbor search and was defeated.
    """

    f = flow_from_chains(*[["{}{}".format(l, i) for i in range(10)] for l in "abcde"])
    f.add_edge(get_task("a3"), get_task("b4"))
    f.add_edge(get_task("b3"), get_task("c4"))
    f.add_edge(get_task("c3"), get_task("d4"))
    f.add_edge(get_task("d3"), get_task("e4"))

    steps = f.generate_local_task_ids(_debug_steps=True)

    # all tasks are individually indistinguishable
    assert count_unique_ids(steps[1]) == 1

    # forward walk is able to identify that tasks following cross-subgraph edges are
    # different, but unable to tell them apart from flows in neighboring subgraphs
    # specifically, it can determine [possibly shared] ids for:
    # - the four tasks before the edge (all branches)
    # - the six tasks after the edge (a branch)
    # - the six tasks after the edge (b-e branches)
    assert count_unique_ids(steps[2]) == 16

    # reverse walk is able to additionally identify:
    # - the four tasks before the edge (a branch)
    # - the four tasks before the edge (e branch)
    assert count_unique_ids(steps[3]) == 24

    # concentric neighbor search identifies all remaining tasks; no further processing
    assert (
        count_unique_ids(steps[4]) == count_unique_ids(steps[5]) == len(f.tasks) == 50
    )


def test_near_pathological_flow():
    r"""
        a0 -> a1 -> a2 -> a3 -> a4 -> a5 -> a6 -> a7 -> a8 -> a9
                                        \
                b0 -> b1 -> b2 -> b3 -> b4 -> b5 -> b6 -> b7 -> b8 -> b9
                                                \
                        c0 -> c1 -> c2 -> c3 -> c4 -> c5 -> c6 -> c7 -> c8 -> c9
                                                        \
                                d0 -> d1 -> d2 -> d3 -> d4 -> d5 -> d6 -> d7 -> ...
                                                                \
                                        e0 -> e1 -> e2 -> e3 -> e4 -> e5 -> e6 -> ...

    This graph is similar to the pathological one, above, but can be solved with just
    two passes, forward and back.
    """

    f = flow_from_chains(*[["{}{}".format(l, i) for i in range(10)] for l in "abcde"])
    f.add_edge(get_task("a4"), get_task("b3"))
    f.add_edge(get_task("b4"), get_task("c3"))
    f.add_edge(get_task("c4"), get_task("d3"))
    f.add_edge(get_task("d4"), get_task("e3"))

    steps = f.generate_local_task_ids(_debug_steps=True)

    # all tasks are individually indistinguishable
    assert count_unique_ids(steps[1]) == 1

    # forward walk is able to uniquely identify all tasks except the first three of each
    # branch, which is 50 - 15 = 35 unique ids and 3 shared ids (for those first three)
    assert count_unique_ids(steps[2]) == 38

    # reverse walk is able to identify all remaining tasks
    assert (
        count_unique_ids(steps[3])
        == count_unique_ids(steps[4])
        == count_unique_ids(steps[5])
        == len(f.tasks)
        == 50
    )


def test_two_connected_subflows_and_two_independent_subflows():
    r"""
        x1 -> x2
            \
        y1 -> y2

        z1 -> z2 -> z3

        a1 -> a2 -> a3
    """

    f = flow_from_chains(
        ["x1", "x2"], ["y1", "y2"], ["x1", "y2"], ["z1", "z2", "z3"], ["a1", "a2", "a3"]
    )
    steps = f.generate_local_task_ids(_debug_steps=True)

    # all tasks are individually indistinguishable
    assert count_unique_ids(steps[1]) == 1

    # forward pass can uniquely identify x2 and y2, but conflates (x1 / y1 / z1 / a1)
    # (z2 / a2) and (z3 / a3)
    assert count_unique_ids(steps[2]) == 4

    # reverse pass can distinguish x1/y1
    assert count_unique_ids(steps[3]) == 7

    # concentric doesn't help
    assert steps[4] != steps[3]
    assert count_unique_ids(steps[4]) == 7

    assert count_unique_ids(steps[5]) == len(f.tasks) == 10


def test_y_shaped_flow():
    r"""
        x1 -> x2 -> x3
            \
                y1 -> y2

    y1 / x2 and y2 / x3 can't be distinguished
    """

    f = flow_from_chains(["x1", "x2", "x3"], ["x1", "y1", "y2"])
    steps = f.generate_local_task_ids(_debug_steps=True)

    # all tasks are individually indistinguishable
    assert count_unique_ids(steps[1]) == 1
    assert (
        count_unique_ids(steps[2])
        == count_unique_ids(steps[3])
        == count_unique_ids(steps[4])
        == 3
    )
    # need duplicate disambiguation
    assert count_unique_ids(steps[5]) == len(f.tasks) == 5


def test_y_shaped_flow_with_one_unique_task():
    r"""
        x1 -> x2 -> x3
            \
                y1 -> y2*

    y1 / x2 and y2 / x3 can't be distinguished
    """

    f = flow_from_chains(["x1", "x2", "x3"], ["x1", "y1", "y2"])
    # give one task a name
    get_task("y2").name = "y2"
    steps = f.generate_local_task_ids(_debug_steps=True)

    # all tasks are individually indistinguishable except y2
    assert count_unique_ids(steps[1]) == 2

    # forward pass can't tell between y1 and x2
    assert count_unique_ids(steps[2]) == 4

    # reverse pass can tell them apart
    assert (
        count_unique_ids(steps[3])
        == count_unique_ids(steps[4])
        == count_unique_ids(steps[5])
        == len(f.tasks)
        == 5
    )

    # no work was done after reverse pass
    assert steps[3] == steps[4] == steps[5]


def test_two_groups_of_two_subflows():
    r"""
                    x1 -> x2 -> x3
                    \
        y1 -> y2 -> y3

        z1 -> z2 -> z3 -> z4
                \
                    a1 -> a2

    Tasks z3 / z4 and a1/a2 are very difficult to tell apart
    """

    f = flow_from_chains(
        ["x1", "x2", "x3"],
        ["y1", "y2", "y3"],
        ["x1", "y3"],
        ["z1", "z2", "z3", "z4"],
        ["z2", "a1", "a2"],
    )
    steps = f.generate_local_task_ids(_debug_steps=True)

    # all tasks are individually indistinguishable
    assert count_unique_ids(steps[1]) == 1

    # forward pass can distinguish:
    # - x1 / y1 / z1
    # - x2 / y2 / z2
    # - x3 / z3 / a1
    # - z4 / a2
    # - y3
    assert count_unique_ids(steps[2]) == 5

    # reverse pass can't distinguish (z3 / z4) and (a1 / a2)
    assert count_unique_ids(steps[3]) == 10

    # concentric doesn't help
    assert steps[4] != steps[3]
    assert count_unique_ids(steps[4]) == 10

    # need duplicate disambiguation
    assert count_unique_ids(steps[5]) == len(f.tasks) == 12


def test_diamond_flow():
    r"""
        x1 -> x2 -> x3
            \    /
                y1

    y1 and x2 are impossible to tell apart
    """

    f = flow_from_chains(["x1", "x2", "x3"], ["x1", "y1", "x3"])
    steps = f.generate_local_task_ids(_debug_steps=True)

    # all tasks are individually indistinguishable
    assert count_unique_ids(steps[1]) == 1

    # forward pass can distinguish:
    assert (
        count_unique_ids(steps[2])
        == count_unique_ids(steps[3])
        == count_unique_ids(steps[4])
        == 3
    )
    # need duplicate disambiguation
    assert count_unique_ids(steps[5]) == len(f.tasks) == 4


def test_ids_stable_across_identical_flows():
    """
    x1 -> x2 -> x3
            \
                y1 -> y2

    a1 -> a2

    """
    f1 = flow_from_chains(["x1", "x2", "x3"], ["x2", "y1", "y2"], ["a1", "a2"])
    f2 = f1.copy()

    f1_task_ids = f1.generate_local_task_ids()
    f2_task_ids = f2.generate_local_task_ids()
    assert f1_task_ids == f2_task_ids


def test_id_values_stable_across_identical_flows_with_duplicates():
    """
    x1 -> x2 -> x3
            \
                y1 -> y2

    a1 -> a2

    b1 -> b2
    """
    f1 = flow_from_chains(
        ["x1", "x2", "x3"], ["x2", "y1", "y2"], ["a1", "a2"], ["b1", "b2"]
    )
    f2 = f1.copy()

    f1_task_ids = f1.generate_local_task_ids()
    f2_task_ids = f2.generate_local_task_ids()
    # the task_ids are not necessarily equal because the a's and b's
    # could switch ids. But the values are the same.
    assert set(f1_task_ids.values()) == set(f2_task_ids.values())


def test_ids_change_if_flow_name_changes():
    """
    x1 -> x2 -> x3
            \
                y1 -> y2

    a1 -> a2

    """
    f1 = flow_from_chains(["x1", "x2", "x3"], ["x2", "y1", "y2"], ["a1", "a2"])

    f2 = f1.copy()
    f2.name = "another flow name"

    f1_task_ids = f1.generate_local_task_ids()
    f2_task_ids = f2.generate_local_task_ids()
    # no overlap
    assert not set(f1_task_ids.values()).intersection(f2_task_ids.values())


def test_ids_are_stable_even_if_some_tasks_change():
    """
    x1 -> x2 -> x3 -> x4 -> x5 -> x6 -> x7

    - change name of x5
    - should affect x5, x6, x7


    """
    f = flow_from_chains(["x1", "x2", "x3", "x4", "x5", "x6", "x7"])

    task_ids_1 = f.generate_local_task_ids()

    # give x5 a new name
    # this should result in a new ID for x5, x6, and x7
    get_task("x5").name = "x5-renamed"

    task_ids_2 = f.generate_local_task_ids()

    assert task_ids_1[get_task("x5")] != task_ids_2[get_task("x5")]
    assert task_ids_1[get_task("x6")] != task_ids_2[get_task("x6")]
    assert task_ids_1[get_task("x7")] != task_ids_2[get_task("x7")]
    assert len(set(task_ids_1.values()).intersection(task_ids_2.values())) == 4


def test_ids_are_stable_even_if_some_tasks_change_contained():
    """
    x1 -> x2 -> x3 -> x4 -> x5 -> x6 -> x7
    - x6 has a unique name
    - change name of x5
    - should only affect x5's id


    """
    f = flow_from_chains(["x1", "x2", "x3", "x4", "x5", "x6", "x7"])

    get_task("x6").name = "x6-renamed"

    task_ids_1 = f.generate_local_task_ids()

    # give x5 a new name
    # this should result in a new ID for x5, x6, and x7
    get_task("x5").name = "x5-renamed"

    task_ids_2 = f.generate_local_task_ids()

    assert task_ids_1[get_task("x5")] != task_ids_2[get_task("x5")]
    assert len(set(task_ids_1.values()).intersection(task_ids_2.values())) == 6
