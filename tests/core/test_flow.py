import datetime

import pytest

import prefect
from prefect.core.edge import Edge
from prefect.core.flow import Flow
from prefect.core.task import Parameter, Task
from prefect.engine.signals import PrefectError
from prefect.tasks.core.function import FunctionTask
from prefect.utilities.tasks import task
from prefect.utilities.tests import set_config


class AddTask(Task):
    def run(self, x, y):
        return x + y


@pytest.fixture
def add_flow():
    with Flow() as f:
        x = Parameter("x")
        y = Parameter("y", default=10)
        z = AddTask()
        f.set_dependencies(z, keyword_results=dict(x=x, y=y))
    return f


class TestCreateFlow:
    """ Test various Flow constructors """

    def test_create_flow_with_no_args(self):
        # name is not required
        assert Flow()

    def test_create_flow_with_name(self):
        f1 = Flow()
        assert f1.name is "Flow"

        f2 = Flow(name="test")
        assert f2.name == "test"

    def test_create_flow_with_version(self):
        f1 = Flow()
        assert f1.version == prefect.config.flows.default_version

        f2 = Flow(version="test")
        assert f2.version == "test"

    def test_create_flow_with_project(self):
        f1 = Flow()
        assert f1.project == prefect.config.flows.default_project

        f2 = Flow(project="test")
        assert f2.project == "test"

    def test_create_flow_with_description(self):
        f1 = Flow()
        assert f1.description is None

        f2 = Flow(description="test")
        assert f2.description == "test"

    def test_create_flow_with_schedule(self):
        f1 = Flow()
        assert isinstance(f1.schedule, prefect.schedules.NoSchedule)

        cron = prefect.schedules.CronSchedule("* * * * *")
        f2 = Flow(schedule=cron)
        assert f2.schedule == cron


def test_add_task_to_flow():
    f = Flow()
    t = Task()
    f.add_task(t)
    assert t in f.tasks


def test_add_task_returns_task():
    f = Flow()
    t = Task()
    t2 = f.add_task(t)
    assert t2 is t


def test_add_task_raise_an_error_if_the_task_is_not_a_task_class():
    f = Flow()

    with pytest.raises(TypeError):
        f.add_task(1)


def test_set_dependencies_adds_all_arguments_to_flow():
    f = Flow()

    class ArgTask(Task):
        def run(self, x):
            return x

    t1 = ArgTask()
    t2 = Task()
    t3 = Task()
    t4 = Task()

    f.set_dependencies(
        task=t1, upstream_tasks=[t2], downstream_tasks=[t3], keyword_tasks={"x": t4}
    )

    assert f.tasks == set([t1, t2, t3, t4])


def test_set_dependencies_converts_arguments_to_tasks():
    class ArgTask(Task):
        def run(self, x):
            return x

    f = Flow()
    t1 = ArgTask()
    t2 = 2
    t3 = 3
    t4 = 4

    f.set_dependencies(
        task=t1, upstream_tasks=[t2], downstream_tasks=[t3], keyword_tasks={"x": t4}
    )
    assert len(f.tasks) == 4


def test_calling_a_task_in_context_adds_it_to_flow():
    with Flow() as flow:
        t = Task()
        assert t not in flow.tasks
        t()
        assert t in flow.tasks


def test_adding_a_task_to_a_flow_twice_is_ok():
    f = Flow()
    t = Task()
    f.add_task(t)
    f.add_task(t)


def test_context_manager_is_properly_applied_to_tasks():
    t1 = Task()
    t2 = Task()
    t3 = Task()
    with Flow() as f1:
        with Flow() as f2:
            t2()
        t1()

    with pytest.raises(ValueError):
        t3()

    assert f1.tasks == set([t1])
    assert f2.tasks == set([t2])


def test_that_flow_adds_and_removes_itself_from_prefect_context():
    assert "_flow" not in prefect.context
    with Flow() as f1:
        assert prefect.context._flow is f1
        with Flow() as f2:
            assert prefect.context._flow is f2
        assert prefect.context._flow is f1
    assert "_flow" not in prefect.context


def test_add_edge():
    f = Flow()
    t1 = Task()
    t2 = Task()
    f.add_edge(upstream_task=t1, downstream_task=t2)
    assert f.upstream_tasks(t2) == set([t1])
    assert f.upstream_tasks(t1) == set()
    assert f.downstream_tasks(t2) == set()
    assert f.downstream_tasks(t1) == set([t2])
    assert f.edges_to(t2) == f.edges_from(t1)


def test_add_edge_returns_edge():
    f = Flow()
    t1 = Task()
    t2 = Task()
    edge = Edge(t1, t2)
    added_edge = f.add_edge(upstream_task=t1, downstream_task=t2)

    assert edge == added_edge
    assert added_edge in f.edges
    assert edge in f.edges


def test_chain():
    f = Flow()
    t1 = Task()
    t2 = Task()
    t3 = Task()
    t4 = Task()
    edges = f.chain(t1, t2, t3, t4)

    assert f.tasks == set([t1, t2, t3, t4])
    assert f.edges == set(edges)


def test_iter():
    """
    Tests that iterating over a Flow yields the tasks in order
    """
    with Flow("test") as f:
        t1 = Task()
        t2 = Task()
        f.add_edge(upstream_task=t2, downstream_task=t1)
    assert tuple(f) == f.sorted_tasks() == (t2, t1)


def test_detect_cycle():
    f = Flow()
    t1 = Task()
    t2 = Task()

    f.add_edge(t1, t2)
    with pytest.raises(ValueError):
        f.add_edge(t2, t1, validate=True)


def test_eager_cycle_detection_defaults_false():

    assert not prefect.config.flows.eager_edge_validation

    f = Flow()
    t1 = Task()
    t2 = Task()
    f.add_edge(t1, t2)

    # no cycle detected
    assert f.add_edge(t2, t1)
    with pytest.raises(ValueError):
        f.validate()


def test_eager_cycle_detection_works():

    with set_config("flows.eager_edge_validation", True):
        f = Flow()
        t1 = Task()
        t2 = Task()

        f.add_edge(t1, t2)
        with pytest.raises(ValueError):
            f.add_edge(t2, t1)

    assert not prefect.config.flows.eager_edge_validation


def test_copy():
    with Flow() as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)
    f.set_key_tasks([t1])

    f2 = f.copy()
    assert f2 == f

    f.add_edge(Task(), Task())
    assert len(f2.tasks) == len(f.tasks) - 2
    assert len(f2.edges) == len(f.edges) - 1
    assert f.key_tasks() == f2.key_tasks() == set([t1])


def test_infer_root_tasks():
    with Flow() as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)

    assert f.root_tasks() == set([t1])


def test_infer_terminal_tasks():
    with Flow() as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()
        t4 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)
    f.add_task(t4)

    assert f.terminal_tasks() == set([t3, t4])


def test_key_tasks_are_terminal_tasks_by_default():
    with Flow() as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()
        t4 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)
    f.add_task(t4)

    assert f.key_tasks() == f.terminal_tasks() == set([t3, t4])


def test_set_key_tasks():
    with Flow() as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)

    f.set_key_tasks([])
    assert f.key_tasks() == f.terminal_tasks()
    f.set_key_tasks([t2])
    assert f.key_tasks() == set([t2])


def test_reset_key_tasks_to_terminal_tasks():

    with Flow() as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)

    f.set_key_tasks([t2])
    assert f.key_tasks() == set([t2])
    f.set_key_tasks([])
    assert f.key_tasks() == f.terminal_tasks()


def test_key_states_raises_error_if_not_part_of_flow():
    f = Flow()
    t1 = Task()
    with pytest.raises(ValueError):
        f.set_key_tasks([t1])


def test_key_states_raises_error_if_not_iterable():
    f = Flow()
    t1 = Task()
    f.add_task(t1)
    with pytest.raises(TypeError):
        f.set_key_tasks(t1)


class TestEquality:
    def test_equality_based_on_tasks(self):
        f1 = Flow()
        f2 = Flow()

        t1 = Task()
        t2 = Task()
        t3 = Task()

        for f in [f1, f2]:
            f.add_task(t1)
            f.add_task(t2)
        assert f1 == f2

        f2.add_task(t3)
        assert f1 != f2

    def test_equality_based_on_edges(self):
        f1 = Flow()
        f2 = Flow()

        t1 = Task()
        t2 = Task()
        t3 = Task()

        for f in [f1, f2]:
            f.add_edge(t1, t2)
            f.add_edge(t1, t3)
        assert f1 == f2

        f2.add_edge(t2, t3)
        assert f1 != f2

    def test_equality_based_on_name(self):
        f1 = Flow("hi")
        f2 = Flow("bye")
        assert f1 != f2

    def test_equality_based_on_project(self):
        f1 = Flow("flow", project="1")
        f2 = Flow("flow", project="1")
        f3 = Flow("flow", project="2")
        assert f1 == f2
        assert f2 != f3

    def test_equality_based_on_version(self):
        f1 = Flow("flow", version="1")
        f2 = Flow("flow", version="1")
        f3 = Flow("flow", version="2")
        assert f1 == f2
        assert f2 != f3

    def test_equality_based_on_key_tasks(self):
        f1 = Flow()
        f2 = Flow()

        t1 = Task()
        t2 = Task()
        t3 = Task()

        for f in [f1, f2]:
            f.add_edge(t1, t2)
            f.add_edge(t1, t3)

        f1.set_key_tasks([t2])
        assert f1 != f2
        f2.set_key_tasks([t2])
        assert f1 == f2


def test_merge():
    f1 = Flow()
    f2 = Flow()

    t1 = Task()
    t2 = Task()
    t3 = Task()

    f1.add_edge(t1, t2)
    f2.add_edge(t2, t3)

    f2.update(f1)
    assert f2.tasks == set([t1, t2, t3])
    assert len(f2.edges) == 2


def test_upstream_and_downstream_error_msgs_when_task_is_not_in_flow():
    f = Flow()
    t = Task()

    with pytest.raises(ValueError) as e:
        f.edges_to(t)
        assert "was not found in Flow" in e

    with pytest.raises(ValueError) as e:
        f.edges_from(t)
        assert "was not found in Flow" in e

    with pytest.raises(ValueError) as e:
        f.upstream_tasks(t)
        assert "was not found in Flow" in e

    with pytest.raises(ValueError) as e:
        f.downstream_tasks(t)
        assert "was not found in Flow" in e


def test_sorted_tasks():
    """
    t1 -> t2 -> t3 -> t4
    """
    f = Flow()
    t1 = Task("1")
    t2 = Task("2")
    t3 = Task("3")
    t4 = Task("4")
    f.add_edge(t1, t2)
    f.add_edge(t2, t3)
    f.add_edge(t3, t4)
    assert f.sorted_tasks() == (t1, t2, t3, t4)


def test_sorted_tasks_with_ambiguous_sort():
    """
    t1 -> bottleneck
    t2 -> bottleneck
    t3 -> bottleneck
           bottleneck -> t4
           bottleneck -> t5
           bottleneck -> t6
    """

    f = Flow()
    t1 = Task("1")
    t2 = Task("2")
    t3 = Task("3")
    t4 = Task("4")
    t5 = Task("5")
    t6 = Task("6")
    bottleneck = Task("bottleneck")
    f.add_edge(t1, bottleneck)
    f.add_edge(t2, bottleneck)
    f.add_edge(t3, bottleneck)
    f.add_edge(bottleneck, t4)
    f.add_edge(bottleneck, t5)
    f.add_edge(bottleneck, t6)

    tasks = f.sorted_tasks()
    assert set(tasks[:3]) == set([t1, t2, t3])
    assert list(tasks)[3] is bottleneck
    assert set(tasks[4:]) == set([t4, t5, t6])


def test_sorted_tasks_with_start_task():
    """
    t1 -> t2 -> t3 -> t4
                  t3 -> t5
    """
    f = Flow()
    t1 = Task("1")
    t2 = Task("2")
    t3 = Task("3")
    t4 = Task("4")
    t5 = Task("5")
    f.add_edge(t1, t2)
    f.add_edge(t2, t3)
    f.add_edge(t3, t4)
    f.add_edge(t3, t5)
    assert set(f.sorted_tasks(root_tasks=[])) == set([t1, t2, t3, t4, t5])
    assert set(f.sorted_tasks(root_tasks=[t3])) == set([t3, t4, t5])


def test_flow_ignores_irrelevant_user_provided_parameters():
    class ParameterTask(Task):
        def run(self):
            return prefect.context.get("_parameters")

    with Flow() as f:
        x = Parameter("x")
        t = ParameterTask()
        f.add_task(x)
        f.add_task(t)

    state = f.run(return_tasks=[t], parameters=dict(x=10, y=3, z=9))
    assert state.result[t].result == dict(x=10)


def test_validate_cycles():
    f = Flow()
    t1 = Task()
    t2 = Task()
    f.add_edge(t1, t2)
    f.add_edge(t2, t1)
    with pytest.raises(ValueError) as exc:
        f.validate()
    assert "cycle found" in str(exc.value).lower()


def test_validate_missing_edge_downstream_tasks():
    f = Flow()
    t1 = Task()
    t2 = Task()
    f.add_edge(t1, t2)
    f.tasks.remove(t2)
    with pytest.raises(ValueError) as exc:
        f.validate()
    assert "edges refer to tasks" in str(exc.value).lower()


def test_validate_missing_edge_upstream_tasks():
    f = Flow()
    t1 = Task()
    t2 = Task()
    f.add_edge(t1, t2)
    f.tasks.remove(t1)
    with pytest.raises(ValueError) as exc:
        f.validate()
    assert "edges refer to tasks" in str(exc.value).lower()


def test_validate_missing_key_tasks():
    f = Flow()
    t1 = Task()
    t2 = Task()
    f.add_task(t1)
    f.add_task(t2)
    f.set_key_tasks([t1])
    f.tasks.remove(t1)
    with pytest.raises(ValueError) as exc:
        f.validate()
    assert "key tasks are not contained" in str(exc.value).lower()
