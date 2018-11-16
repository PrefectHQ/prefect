import datetime
import logging

import cloudpickle
import pytest

import prefect
from prefect.core.edge import Edge
from prefect.core.flow import Flow
from prefect.core.task import Parameter, Task
from prefect.engine.signals import PrefectError
from prefect.tasks.core.function import FunctionTask
from prefect.utilities.tasks import task, unmapped
from prefect.utilities.tests import set_temporary_config


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

    def test_create_flow_with_edges(self):
        f1 = Flow(
            edges=[Edge(upstream_task=Task(), downstream_task=AddTask(), key="x")]
        )
        assert len(f1.edges) == 1
        assert len(f1.tasks) == 2

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
        assert f1.schedule is None

        cron = prefect.schedules.CronSchedule("* * * * *")
        f2 = Flow(schedule=cron)
        assert f2.schedule == cron

    def test_flow_prevents_bad_throttle_values(self):
        with pytest.raises(ValueError):
            f = Flow(throttle=dict(x=5, y=0))

        with pytest.raises(ValueError):
            f = Flow(throttle=dict(x=-5, y=6))

        with pytest.raises(ValueError) as exc:
            f = Flow(throttle=dict(x=-5, y=0))

        base_msg = 'Cannot throttle tags "{0}", "{1}" - an invalid value less than 1 was provided.'
        assert str(exc.value) in [
            base_msg.format("x", "y"),
            base_msg.format("y", "x"),
        ]  # for py34

    def test_create_flow_without_state_handler(self):
        assert Flow().state_handlers == []

    @pytest.mark.parametrize("handlers", [[lambda *a: 1], [lambda *a: 1, lambda *a: 2]])
    def test_create_flow_with_state_handler(self, handlers):
        assert Flow(state_handlers=handlers).state_handlers == handlers

    def test_create_flow_illegal_handler(self):
        with pytest.raises(TypeError):
            Flow(state_handlers=lambda *a: 1)

    def test_flow_has_logger(self):
        f = Flow()
        assert isinstance(f.logger, logging.Logger)


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


def test_set_dependencies_creates_mapped_edges():
    t1 = Task()
    t2 = Task()
    f = Flow()

    f.set_dependencies(task=t1, upstream_tasks=[t2], mapped=True)
    assert len(f.edges) == 1
    edge = f.edges.pop()
    assert edge.mapped is True


def test_set_dependencies_respects_unmapped():
    t1 = Task()
    t2 = Task()
    f = Flow()

    f.set_dependencies(task=t1, upstream_tasks=[unmapped(t2)], mapped=True)
    assert len(f.edges) == 1
    edge = f.edges.pop()
    assert edge.mapped is False


def test_binding_a_task_in_context_adds_it_to_flow():
    with Flow() as flow:
        t = Task()
        assert t not in flow.tasks
        t.bind()
        assert t in flow.tasks


def test_adding_a_task_to_a_flow_twice_is_ok():
    f = Flow()
    t = Task()
    f.add_task(t)
    f.add_task(t)


def test_binding_a_task_to_two_different_flows_is_ok():
    t = AddTask()

    with Flow() as f:
        t.bind(4, 2)

    with Flow() as g:
        t.bind(7, 8)

    f_res = f.run(return_tasks=[t]).result[t].result
    g_res = g.run(return_tasks=[t]).result[t].result
    assert f_res == 6
    assert g_res == 15


def test_binding_a_task_with_var_kwargs_expands_the_kwargs():
    class KwargsTask(Task):
        def run(self, **kwargs):
            return kwargs

    t1 = Task()
    t2 = Task()
    t3 = Task()
    kw = KwargsTask()

    with Flow() as f:
        kw.bind(a=t1, b=t2, c=t3)

    assert t1 in f.tasks
    assert t2 in f.tasks
    assert t3 in f.tasks

    assert Edge(t1, kw, key="a") in f.edges
    assert Edge(t2, kw, key="b") in f.edges
    assert Edge(t3, kw, key="c") in f.edges


def test_calling_a_task_returns_a_copy():
    t = AddTask()

    with Flow() as f:
        t.bind(4, 2)
        with pytest.warns(UserWarning):
            t2 = t(9, 0)

    assert isinstance(t2, AddTask)
    assert t != t2

    res = f.run(return_tasks=[t, t2]).result
    assert res[t].result == 6
    assert res[t2].result == 9


def test_calling_a_slugged_task_in_different_flows_is_ok():
    t = AddTask(slug="add")

    with Flow() as f:
        three = t(1, 2)

    with Flow() as g:
        four = t(1, 3)


def test_calling_a_slugged_task_twice_warns_error():
    t = AddTask(slug="add")
    with Flow() as f:
        t.bind(4, 2)
        with pytest.warns(UserWarning), pytest.raises(ValueError):
            t2 = t(9, 0)


def test_context_manager_is_properly_applied_to_tasks():
    t1 = Task()
    t2 = Task()
    t3 = Task()
    with Flow() as f1:
        with Flow() as f2:
            t2.bind()
        t1.bind()

    with pytest.raises(ValueError):
        t3.bind()

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

    with set_temporary_config("flows.eager_edge_validation", True):
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
    f.set_reference_tasks([t1])

    f2 = f.copy()
    assert f2 == f

    f.add_edge(Task(), Task())
    assert len(f2.tasks) == len(f.tasks) - 2
    assert len(f2.edges) == len(f.edges) - 1
    assert f.reference_tasks() == f2.reference_tasks() == set([t1])


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


def test_reference_tasks_are_terminal_tasks_by_default():
    with Flow() as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()
        t4 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)
    f.add_task(t4)

    assert f.reference_tasks() == f.terminal_tasks() == set([t3, t4])


def test_set_reference_tasks():
    with Flow() as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)

    f.set_reference_tasks([])
    assert f.reference_tasks() == f.terminal_tasks()
    f.set_reference_tasks([t2])
    assert f.reference_tasks() == set([t2])


def test_set_reference_tasks_at_init_with_empty_flow_raises_error():

    with pytest.raises(ValueError) as exc:
        Flow(reference_tasks=[Task()])
    assert "must be part of the flow" in str(exc.value)


def test_set_reference_tasks_at_init():
    t1 = Task()
    f = Flow(reference_tasks=[t1], tasks=[t1])
    assert f.reference_tasks() == set([t1]) == f.tasks == f.terminal_tasks()

    t2 = Task()
    f = Flow(reference_tasks=[t2], tasks=[t1, t2])
    assert f.reference_tasks() == set([t2])


def test_reset_reference_tasks_to_terminal_tasks():

    with Flow() as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)

    f.set_reference_tasks([t2])
    assert f.reference_tasks() == set([t2])
    f.set_reference_tasks([])
    assert f.reference_tasks() == f.terminal_tasks()


def test_key_states_raises_error_if_not_part_of_flow():
    f = Flow()
    t1 = Task()
    with pytest.raises(ValueError):
        f.set_reference_tasks([t1])


def test_key_states_raises_error_if_not_iterable():
    with Flow() as f:
        t1 = Task()
        f.add_task(t1)
        with pytest.raises(TypeError):
            f.set_reference_tasks(t1)


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

    def test_equality_based_on_reference_tasks(self):
        f1 = Flow()
        f2 = Flow()

        t1 = Task()
        t2 = Task()
        t3 = Task()

        for f in [f1, f2]:
            f.add_edge(t1, t2)
            f.add_edge(t1, t3)

        f1.set_reference_tasks([t2])
        assert f1 != f2
        f2.set_reference_tasks([t2])
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


def test_flow_raises_for_irrelevant_user_provided_parameters():
    class ParameterTask(Task):
        def run(self):
            return prefect.context.get("_parameters")

    with Flow() as f:
        x = Parameter("x")
        t = ParameterTask()
        f.add_task(x)
        f.add_task(t)

    with pytest.raises(TypeError):
        state = f.run(return_tasks=[t], parameters=dict(x=10, y=3, z=9))

    with pytest.raises(TypeError):
        state = f.run(return_tasks=[t], x=10, y=3, z=9)


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


def test_validate_missing_reference_tasks():
    f = Flow()
    t1 = Task()
    t2 = Task()
    f.add_task(t1)
    f.add_task(t2)
    f.set_reference_tasks([t1])
    f.tasks.remove(t1)
    with pytest.raises(ValueError) as exc:
        f.validate()
    assert "reference tasks are not contained" in str(exc.value).lower()


def test_validate_missing_task_info():
    f = Flow()
    t1 = Task()
    f.tasks.add(t1)
    with pytest.raises(ValueError) as exc:
        f.validate()
    assert "tasks are not in the task_info" in str(exc.value).lower()


def test_validate_edges_kwarg():
    f = Flow()
    t1, t2 = Task(), Task()  # these tasks don't support keyed edges
    with pytest.raises(TypeError):
        f.add_edge(t1, t2, key="x", validate=True)


def test_validate_edges():
    with set_temporary_config("flows.eager_edge_validation", True):
        f = Flow()
        t1, t2 = Task(), Task()  # these tasks don't support keyed edges
        with pytest.raises(TypeError):
            f.add_edge(t1, t2, key="x")


def test_skip_validate_edges():
    f = Flow()
    t1, t2 = Task(), Task()  # these tasks don't support keyed edges
    f.add_edge(t1, t2, key="x", validate=False)
    f.add_edge(t2, t1, validate=False)  # this introduces a cycle


def test_skip_validation_in_init_with_kwarg():
    t1, t2 = Task(), Task()  # these tasks don't support keyed edges
    e1, e2 = Edge(t1, t2), Edge(t2, t1)
    with pytest.raises(ValueError):
        Flow(edges=[e1, e2], validate=True)

    assert Flow(edges=[e1, e2], validate=False)


def test_task_ids_are_cached():
    f = Flow()
    t1 = Task()
    t2 = Task()
    f.add_task(t1)
    f.add_task(t2)

    assert len(f.task_ids) == 2

    for t in [t1, t2]:
        assert not f.task_info[t]["mapped"]


def test_auto_create_task_info_entries():
    f = Flow()
    t1 = Task()
    t2 = Task()
    f.add_edge(t1, t2)

    assert len(f.task_info) == 2
    assert set([t1, t2]) == set(f.task_info)

    for t in [t1, t2]:
        assert not f.task_info[t]["mapped"]


def test_task_info_entries_not_created_if_task_already_exists():
    f = Flow()
    t1 = Task()

    assert f.task_info == {}
    f.add_task(t1)
    assert t1 in f.task_info
    t1_id = f.task_info[t1]["id"]
    f.add_task(t1)
    assert f.task_info[t1]["id"] == t1_id


def test_create_task_mapped_info_entries():
    f = Flow()
    t1 = Task()
    t2 = Task()

    # this is legal, though probably not useful
    f.add_edge(t1, t2, mapped=True)
    f.add_edge(t1, t2, mapped=False)

    assert not f.task_info[t1]["mapped"]
    assert f.task_info[t2]["mapped"]


def test_register():
    flow = Flow()
    assert flow.id not in prefect.core.registry.REGISTRY
    flow.register()
    assert prefect.core.registry.REGISTRY[flow.id] is flow


def test_register_nondefault():
    r = {}
    flow = Flow()
    flow.register(registry=r)
    assert r[flow.id] is flow


def test_register_init():
    flow = Flow(register=True)
    assert flow.id in prefect.core.registry.REGISTRY
    assert prefect.core.registry.REGISTRY[flow.id] is flow


def test_build_environment_with_none_set():
    flow = Flow()
    with pytest.raises(ValueError):
        flow.build_environment()


def test_build_environment():
    flow = Flow(environment=prefect.environments.LocalEnvironment())
    key = flow.build_environment()
    assert isinstance(key, prefect.environments.LocalEnvironment)


def test_visualize_raises_informative_importerror_without_graphviz(monkeypatch):
    f = Flow()
    f.add_task(Task())

    import sys

    with monkeypatch.context() as m:
        m.setattr(sys, "path", "")
        with pytest.raises(ImportError) as exc:
            f.visualize()

    assert "pip install prefect[viz]" in repr(exc.value)


class TestCache:
    def test_cache_created(self):
        f = Flow()
        assert isinstance(f._cache, dict)
        assert len(f._cache) == 0

    def test_cache_sorted_tasks(self):
        f = Flow()
        t1 = Task()
        t2 = Task()
        t3 = Task()
        f.add_edge(t1, t2)
        f.sorted_tasks()

        # check that cache holds result
        key = ("_sorted_tasks", (("root_tasks", ()),))
        assert f._cache[key] == (t1, t2)

        # check that cache is read
        f._cache[key] = 1
        assert f.sorted_tasks() == 1

        f.add_edge(t2, t3)
        assert f.sorted_tasks() == (t1, t2, t3)

    def test_cache_sorted_tasks_with_args(self):
        f = Flow()
        t1 = Task()
        t2 = Task()
        t3 = Task()
        f.add_edge(t1, t2)
        f.sorted_tasks([t2])

        # check that cache holds result
        key = ("_sorted_tasks", (("root_tasks", (t2,)),))
        assert f._cache[key] == (t2,)

        # check that cache is read
        f._cache[key] = 1
        assert f.sorted_tasks([t2]) == 1
        assert f.sorted_tasks() == (t1, t2)

        f.add_edge(t2, t3)
        assert f.sorted_tasks([t2]) == (t2, t3)

    def test_cache_root_tasks(self):
        f = Flow()
        t1 = Task()
        t2 = Task()
        t3 = Task()
        f.add_edge(t1, t2)

        f.root_tasks()

        # check that cache holds result
        key = ("root_tasks", ())
        assert f._cache[key] == set([t1])

        # check that cache is read
        f._cache[key] = 1
        assert f.root_tasks() == 1

        f.add_edge(t2, t3)
        assert f.root_tasks() == set([t1])

    def test_cache_task_ids(self):
        f = Flow()
        t1 = Task()
        t2 = Task()
        t3 = Task()
        f.add_edge(t1, t2)

        ids = f.task_ids

        # check that cache holds result
        key = ("task_ids", ())
        assert f._cache[key] == ids

        # check that cache is read
        f._cache[key] = 1
        assert f.task_ids == 1

        f.add_edge(t2, t3)
        assert len(f.task_ids) == 3

    def test_cache_terminal_tasks(self):
        f = Flow()
        t1 = Task()
        t2 = Task()
        t3 = Task()
        f.add_edge(t1, t2)

        f.terminal_tasks()

        # check that cache holds result
        key = ("terminal_tasks", ())
        assert f._cache[key] == set([t2])

        # check that cache is read
        f._cache[key] = 1
        assert f.terminal_tasks() == 1

        f.add_edge(t2, t3)
        assert f.terminal_tasks() == set([t3])

    def test_cache_parameters(self):
        f = Flow()
        t1 = Parameter("t1")
        t2 = Task()
        t3 = Task()
        f.add_edge(t1, t2)

        f.parameters()

        # check that cache holds result
        key = ("parameters", ())
        assert f._cache[key] == {t1}

        # check that cache is read
        f._cache[key] = 1
        assert f.parameters() == 1

        f.add_edge(t2, t3)
        assert f.parameters() == {t1}

    def test_cache_all_upstream_edges(self):
        f = Flow()
        t1 = Task()
        t2 = Task()
        t3 = Task()
        f.add_edge(t1, t2)

        f.all_upstream_edges()
        key = ("all_upstream_edges", ())
        f._cache[key] = 1
        assert f.all_upstream_edges() == 1

        f.add_edge(t2, t3)
        assert f.all_upstream_edges() != 1

    def test_cache_all_downstream_edges(self):
        f = Flow()
        t1 = Task()
        t2 = Task()
        t3 = Task()
        f.add_edge(t1, t2)
        f.all_downstream_edges()
        key = ("all_downstream_edges", ())
        f._cache[key] = 1
        assert f.all_downstream_edges() == 1

        f.add_edge(t2, t3)
        assert f.all_downstream_edges() != 1

    def test_cache_build_environment(self):
        f = Flow(environment=prefect.environments.LocalEnvironment())
        t1 = Task()
        t2 = Task()
        t3 = Task()
        f.add_edge(t1, t2)

        f.build_environment()

        key = ("build_environment", ())
        f._cache[key] = 1
        assert f.build_environment() == 1

        f.add_edge(t2, t3)
        assert f.build_environment() != 1

    def test_cache_survives_pickling(self):
        f = Flow()
        t1 = Task()
        t2 = Task()
        t3 = Task()
        f.add_edge(t1, t2)
        f.sorted_tasks()
        key = ("_sorted_tasks", (("root_tasks", ()),))
        f._cache[key] = 1
        assert f.sorted_tasks() == 1

        f2 = cloudpickle.loads(cloudpickle.dumps(f))
        assert f2.sorted_tasks() == 1
        f2.add_edge(t2, t3)
        assert f2.sorted_tasks() != 1

    def test_adding_task_clears_cache(self):
        f = Flow()
        f._cache[1] = 2
        f.add_task(Task())
        assert 1 not in f._cache

    def test_adding_edge_clears_cache(self):
        f = Flow()
        f._cache[1] = 2
        f.add_edge(Task(), Task())
        assert 1 not in f._cache

    def test_setting_reference_tasks_clears_cache(self):
        f = Flow()
        t1 = Task()
        f.add_task(t1)
        f._cache[1] = 2
        f.set_reference_tasks([t1])
        assert 1 not in f._cache


class TestReplace:
    def test_replace_replaces_all_the_things(self):
        with Flow() as f:
            t1 = Task(name="t1")()
            t2 = Task(name="t2")(upstream_tasks=[t1])
        t3 = Task(name="t3")
        f.set_reference_tasks([t1])
        f.replace(t1, t3)

        assert f.tasks == {t2, t3}
        assert {e.upstream_task for e in f.edges} == {t3}
        assert {e.downstream_task for e in f.edges} == {t2}
        assert f.reference_tasks() == {t3}
        assert f.terminal_tasks() == {t2}

        with pytest.raises(ValueError):
            f.edges_to(t1)

    def test_replace_complains_about_tasks_not_in_flow(self):
        with Flow() as f:
            t1 = Task(name="t1")()
        t3 = Task(name="t3")
        with pytest.raises(ValueError):
            f.replace(t3, t1)

    def test_replace_runs_smoothly(self):
        add = AddTask()

        class SubTask(Task):
            def run(self, x, y):
                return x - y

        sub = SubTask()

        with Flow() as f:
            x, y = Parameter("x"), Parameter("y")
            res = add(x, y)

        state = f.run(return_tasks=[res], x=10, y=11)
        assert state.result[res].result == 21

        f.replace(res, sub)
        state = f.run(return_tasks=[sub], x=10, y=11)
        assert state.result[sub].result == -1

    def test_replace_converts_new_to_task(self):
        add = AddTask()
        with Flow() as f:
            x, y = Parameter("x"), Parameter("y")
            res = add(x, y)
        f.replace(x, 55)
        assert len(f.tasks) == 3
        state = f.run(return_tasks=[res], y=6)
        assert state.is_successful()
        assert state.result[res].result == 61


class TestGetTasks:
    def test_get_tasks_defaults_to_return_everything(self):
        t1, t2 = Task(name="t1"), Task(name="t2")
        f = Flow(tasks=[t1, t2])
        assert f.get_tasks() == [t1, t2]

    def test_get_tasks_defaults_to_name(self):
        t1, t2 = Task(name="t1"), Task(name="t2")
        f = Flow(tasks=[t1, t2])
        assert f.get_tasks("t1") == [t1]

    def test_get_tasks_takes_intersection(self):
        t1, t2 = Task(name="t1", slug="11"), Task(name="t1", slug="22")
        f = Flow(tasks=[t1, t2])
        assert f.get_tasks(name="t1") == [t1, t2]
        assert f.get_tasks(name="t1", slug="11") == [t1]
        assert f.get_tasks(name="t1", slug="11", tags=["atag"]) == []

    def test_get_tasks_accepts_tags_and_requires_all_tags(self):
        t1, t2 = Task(name="t1", tags=["a", "b"]), Task(name="t1", tags=["a"])
        f = Flow(tasks=[t1, t2])
        assert f.get_tasks(tags=["a", "b"]) == [t1]

    def test_get_tasks_can_check_types(self):
        class Specific(Task):
            pass

        t1, t2 = Task(name="t1", tags=["a", "b"]), Specific(name="t1", tags=["a"])
        f = Flow(tasks=[t1, t2])
        assert f.get_tasks(task_type=Specific) == [t2]


class TestSerialize:
    def test_serialization(self):
        p1, t2, t3, = Parameter("1"), Task("2"), Task("3")

        f = Flow(tasks=[p1, t2, t3])
        f.add_edge(p1, t2)
        f.add_edge(p1, t3)

        serialized = f.serialize()
        assert isinstance(serialized, dict)
        assert len(serialized["tasks"]) == len(f.tasks)

    def test_deserialization(self):
        p1, t2, t3, = Parameter("1"), Task("2"), Task("3")

        f = Flow(
            name="hi",
            version="2",
            tasks=[p1, t2, t3],
            schedule=prefect.schedules.CronSchedule("* * 0 0 0"),
        )
        f.add_edge(p1, t2)
        f.add_edge(p1, t3)

        serialized = f.serialize()
        f2 = prefect.serialization.flow.FlowSchema().load(serialized)

        assert len(f2.tasks) == 3
        assert len(f2.edges) == 2
        assert len(f2.reference_tasks()) == 2
        assert {t.name for t in f2.reference_tasks()} == {"2", "3"}
        assert f2.name == f.name
        assert f2.version == f.version
        assert isinstance(f2.schedule, prefect.schedules.CronSchedule)

    def test_serialize_validates_invalid_flows(self):
        t1, t2 = Task(), Task()
        f = Flow()
        f.add_edge(t1, t2)
        # default settings should allow this even though it's illegal
        f.add_edge(t2, t1)

        with pytest.raises(ValueError) as exc:
            f.serialize()
        assert "cycle found" in str(exc).lower()
