import tempfile
import prefect
import pytest
from cryptography.fernet import Fernet
from prefect import Flow, Task
from prefect.core import registry
from prefect.core.registry import generate_flow_id, generate_task_ids

TASKS = {}
LOOKUP_TASKS = {}


def get_task(name):
    if name not in TASKS:
        task = Task()
        TASKS[name] = task
        LOOKUP_TASKS[task] = name
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
    with flow.restore_graph_on_error():
        for chain in chains:
            for name in chain:
                flow.add_task(get_task(name))
            for u_name, d_name in zip(chain, chain[1:]):
                flow.add_edge(get_task(u_name), get_task(d_name), validate=False)
    return flow


@pytest.fixture()
def flow():
    return flow_from_chains(["a", "b", "c"], ["b", "d", "e"], ["x", "y", "z"])


@pytest.fixture
def path():
    with tempfile.NamedTemporaryFile("w+b") as tmp:
        yield tmp.name


@pytest.fixture(autouse=True)
def clear_registry():
    registry.FLOW_REGISTRY.clear()


@pytest.fixture(autouse=True, scope="module")
def set_encryption_key():
    prefect.config.flows.registry.encryption_key = Fernet.generate_key()


class TestFlowIDs:
    def test_flow_id_returns_deterministic_bytes(self):
        id_1 = "d203b613-d35d-1c85-8472-d1b79dd72fb3"
        id_2 = "32852910-fefb-6028-8472-d1b79dd72fb3"

        assert generate_flow_id(Flow(name="flow")) == id_1
        assert generate_flow_id(Flow(name="flow", version="version")) == id_1
        assert generate_flow_id(Flow(name="flow", project="project")) == id_2
        assert (
            generate_flow_id(Flow(name="flow", project="project", version="version"))
            == id_2
        )

    def test_flow_id_is_not_affected_by_version(self):
        flow = Flow(name="flow")
        flow_v3 = Flow(name="flow", version=3)
        flow_v4 = Flow(name="flow", version=4)
        flow_v_default = Flow(name="flow", version=prefect.config.flows.default_project)
        assert generate_flow_id(flow) == generate_flow_id(flow_v3)
        assert generate_flow_id(flow_v3) == generate_flow_id(flow_v4)
        assert generate_flow_id(flow) == generate_flow_id(flow_v_default)

    def test_flow_id_is_affected_by_name(self):
        flow = Flow(name="flow")
        flow_2 = Flow(name="another flow")
        assert generate_flow_id(flow) != generate_flow_id(flow_2)

    def test_flow_id_is_affected_by_project(self):
        flow = Flow(name="flow")
        flow_p_default = Flow(name="flow", project=prefect.config.flows.default_project)
        flow_p = Flow(name="flow", project="another project")

        assert generate_flow_id(flow) == generate_flow_id(flow_p_default)
        assert generate_flow_id(flow) != generate_flow_id(flow_p)


class TestTaskIDs:
    def test_no_tasks_returns_empty_dict(self):
        assert generate_task_ids(Flow()) == {}

    def test_one_task(self):
        f = Flow()
        f.add_task(get_task("x"))
        assert len(generate_task_ids(f)) == 1

    def test_flow_id_affects_task_ids(self):
        f = Flow()
        f.add_task(get_task("x"))

        f2 = Flow()
        f2.add_task(get_task("x"))

        f3 = Flow(name="foo")
        f3.add_task(get_task("x"))

        assert generate_task_ids(f) == generate_task_ids(f2)
        assert generate_task_ids(f) != generate_task_ids(f3)

    def test_modify_task_changes_hash(self):
        f = Flow()
        t = Task()
        f.add_task(t)
        hash1 = generate_task_ids(f)
        # this is not an attribute referenced in task.serialize(), so it should not affect the id
        t.new_attribute = "hi"
        hash2 = generate_task_ids(f)
        # this is an attribute referenced in task.serialize(), so it should affect the id
        t.slug = "hi"
        hash3 = generate_task_ids(f)
        assert hash1 == hash2
        assert hash1 != hash3

    def test_two_dependent_tasks(self):
        """
        x1 -> x2

        Each task can be identified just by walking forward through the flow.
        """
        f = Flow()
        f.add_edge(get_task("x1"), get_task("x2"))
        assert len(generate_task_ids(f)) == 2
        assert max(generate_task_ids(f)) == "8de57e3b-43aa-86e9-8de5-7e3b43aa86e9"

    def test_two_identical_subflows(self):
        """
            x1 -> x2
            y1 -> y2

        The tasks in each subgraph are indistinguishable from each other. One will be
        randomly selected and adjusted.
        """
        f = flow_from_chains(["x1", "x2"], ["y1", "y2"])
        assert len(generate_task_ids(f)) == len(f.tasks)
        assert max(generate_task_ids(f)) == "f3b1038c-7736-33e9-f3b1-038c773633e9"

    def test_two_linked_subflows(self):
        r"""
            x1 -> x2 -> x3
                \
            y1 -> y2 -> y3

        x1 and y1 can not be distinguished by walking forward through the graph, but can
        if the graph is walked backward after walking forward.
        """
        # first test them independently
        f = flow_from_chains(["x1", "x2", "x3"], ["y1", "y2", "y3"])
        independent_ids = generate_task_ids(f)
        assert max(independent_ids) == "f306215f-6fd5-31ba-f306-215f6fd531ba"

        # add edge
        f.add_edge(get_task("x1"), get_task("y2"))
        dependent_ids = generate_task_ids(f)
        assert len(dependent_ids) == len(f.tasks)
        assert independent_ids != dependent_ids
        assert max(dependent_ids) == "f96df94b-21d3-53ef-f96d-f94b21d353ef"

    def test_three_identical_subflows(self):
        """
            x1 -> x2 -> x3
            y1 -> y2 -> y3
            z1 -> z2 -> z3

        These subflows are indistinguishable.
        """
        f = flow_from_chains(["x1", "x2", "x3"], ["y1", "y2", "y3"], ["z1", "z2", "z3"])
        ids = generate_task_ids(f)
        assert len(ids) == len(f.tasks)
        assert max(ids) == "f306215f-6fd5-31ba-f306-215f6fd531ba"

    def test_two_linked_subflows_and_one_independent(self):
        r"""
            x1 -> x2 -> x3
                \
            y1 -> y2 -> y3

            z1 -> z2 -> z3

        Walking forward and backward is enough to distinguish x1 from y1, but not enough
        to distinguish x3 from z3. A final forward pass is needed.

        """
        # first test them independently
        f = flow_from_chains(["x1", "x2", "x3"], ["y1", "y2", "y3"], ["z1", "z2", "z3"])
        independent_ids = generate_task_ids(f)
        assert max(independent_ids) == "f306215f-6fd5-31ba-f306-215f6fd531ba"
        # add edge
        f.add_edge(get_task("x1"), get_task("y2"))
        dependent_ids = generate_task_ids(f)
        assert len(dependent_ids) == len(f.tasks)
        assert independent_ids != dependent_ids
        assert max(dependent_ids) == "f96df94b-21d3-53ef-f96d-f94b21d353ef"

    def test_pathological_flow(self):
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
        passes. We test to make sure that our algorithm converges.
        """
        # first test them independently
        f = flow_from_chains(
            *[["{}{}".format(l, i) for i in range(10)] for l in "abcde"]
        )
        independent_ids = generate_task_ids(f)

        # add edge
        f.add_edge(get_task("a5"), get_task("b6"))
        f.add_edge(get_task("b4"), get_task("c5"))
        f.add_edge(get_task("c3"), get_task("d4"))
        f.add_edge(get_task("d2"), get_task("e3"))
        dependent_ids = generate_task_ids(f)
        assert len(dependent_ids) == len(f.tasks)
        assert independent_ids != dependent_ids
        assert max(dependent_ids) == "f9ca134e-76a2-8b9e-f9ca-134e76a28b9e"

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
        ids = generate_task_ids(f)
        assert len(ids) == len(f.tasks)
        assert max(ids) == "f96df94b-21d3-53ef-f96d-f94b21d353ef"

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
        ids = generate_task_ids(f)
        assert len(ids) == len(f.tasks)
        assert max(ids) == "f96df94b-21d3-53ef-f96d-f94b21d353ef"

    def test_diamond_flow(self):
        r"""
            x1 -> x2 -> x3
                \    /
                y1
        """

        f = flow_from_chains(["x1", "x2", "x3"], ["x1", "y1", "x3"])
        ids = generate_task_ids(f)
        assert len(ids) == len(f.tasks)
        assert max(ids) == "b40af1cb-ddca-a2c4-b40a-f1cbddcaa2c4"


class TestRegistry:
    def test_register_flow(self, flow):
        flow_id = (flow.project, flow.name, flow.version)
        assert flow_id not in registry.FLOW_REGISTRY
        registry.register_flow(flow)
        assert registry.FLOW_REGISTRY[flow_id] is flow

    def test_register_flow_warning_on_duplicate(self, flow):
        assert prefect.config.flows.registry.warn_on_duplicate_registration
        registry.register_flow(flow)
        with pytest.warns(UserWarning):
            registry.register_flow(flow)

    def load_flow(self, flow):
        with pytest.raises(KeyError):
            registry.load_flow(None, None, None)
        registry.register_flow(flow)
        assert registry.load_flow(flow.project, flow.name, flow.version) is flow

    def test_serialize_registry(self, flow, path):
        registry.register_flow(flow)
        registry.serialize_registry(path=path)

        with open(path, "rb") as f:
            assert len(f.read()) > 1000

    def test_deserialize_registry(self, flow, path):
        registry.register_flow(flow)
        registry.serialize_registry(path=path)
        registry.FLOW_REGISTRY.clear()
        assert not registry.FLOW_REGISTRY

        registry.deserialize_registry(path=path)
        assert registry.FLOW_REGISTRY
        new_flow = registry.load_flow(flow.project, flow.name, flow.version)
        assert (new_flow.name, new_flow.version) == (flow.name, flow.version)

    def test_serialize_and_deserialize_registry_warns_about_encryption(
        self, flow, path
    ):
        key = prefect.config.flows.registry.encryption_key
        prefect.config.flows.registry.encryption_key = ""
        try:
            assert not prefect.config.flows.registry.encryption_key
            registry.register_flow(flow)

            with pytest.warns(UserWarning):
                registry.serialize_registry(path=path)
            with pytest.warns(UserWarning):
                registry.deserialize_registry(path=path)
        finally:
            prefect.config.flows.registry.encryption_key = key

    def test_automatic_registration(self):
        flow = Flow(name="hello", register=True)
        assert (flow.project, flow.name, flow.version) in registry.FLOW_REGISTRY
