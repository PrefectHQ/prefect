import datetime
import logging
import pendulum
import sys
import tempfile
import uuid
from unittest.mock import MagicMock, patch

import cloudpickle
import pytest

import prefect
from prefect.core.edge import Edge
from prefect.core.flow import Flow
from prefect.core.task import Parameter, Task
from prefect.engine.result_handlers import LocalResultHandler, ResultHandler
from prefect.engine.signals import PrefectError
from prefect.engine.state import (
    Failed,
    Finished,
    Pending,
    Mapped,
    Skipped,
    State,
    Success,
    TriggerFailed,
)
from prefect.tasks.core.function import FunctionTask
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.tasks import task, unmapped


class AddTask(Task):
    def run(self, x, y):
        return x + y


@pytest.fixture
def add_flow():
    with Flow(name="test") as f:
        x = Parameter("x")
        y = Parameter("y", default=10)
        z = AddTask()
        f.set_dependencies(z, keyword_results=dict(x=x, y=y))
    return f


class TestCreateFlow:
    """ Test various Flow constructors """

    def test_create_flow_with_no_args(self):
        # name is required
        with pytest.raises(TypeError):
            assert Flow()

    def test_create_flow_with_name(self):
        with pytest.raises(TypeError):
            f1 = Flow()
            assert f1.name

        f2 = Flow(name="test")
        assert f2.name == "test"

    def test_create_flow_with_edges(self):
        f1 = Flow(
            name="test", edges=[Edge(upstream_task=Task(), downstream_task=AddTask(), key="x")]
        )
        assert len(f1.edges) == 1
        assert len(f1.tasks) == 2

    def test_create_flow_with_schedule(self):
        f1 = Flow(name="test")
        assert f1.schedule is None

        cron = prefect.schedules.CronSchedule("* * * * *")
        f2 = Flow(name="test", schedule=cron)
        assert f2.schedule == cron

    def test_create_flow_without_state_handler(self):
        assert Flow(name="test").state_handlers == []

    def test_create_flow_with_on_failure(self):
        f = Flow(name="test", on_failure=lambda *args: None)
        assert len(f.state_handlers) == 1

    @pytest.mark.parametrize("handlers", [[lambda *a: 1], [lambda *a: 1, lambda *a: 2]])
    def test_create_flow_with_state_handler(self, handlers):
        assert Flow(name="test", state_handlers=handlers).state_handlers == handlers

    def test_create_flow_illegal_handler(self):
        with pytest.raises(TypeError):
            Flow(name="test", state_handlers=lambda *a: 1)

    def test_flow_has_logger(self):
        f = Flow(name="test")
        assert isinstance(f.logger, logging.Logger)

    def test_create_flow_with_result_handler(self):
        f = Flow(name="test", result_handler=LocalResultHandler())
        assert isinstance(f.result_handler, ResultHandler)
        assert isinstance(f.result_handler, LocalResultHandler)

    def test_create_flow_without_result_handler_uses_config(self):
        with set_temporary_config(
            {
                "engine.result_handler.default_class": "prefect.engine.result_handlers.local_result_handler.LocalResultHandler"
            }
        ):
            f = Flow(name="test")
            assert isinstance(f.result_handler, LocalResultHandler)


def test_add_task_to_flow():
    f = Flow(name="test")
    t = Task()
    f.add_task(t)
    assert t in f.tasks


def test_add_task_returns_task():
    f = Flow(name="test")
    t = Task()
    t2 = f.add_task(t)
    assert t2 is t


def test_add_task_raise_an_error_if_the_task_is_not_a_task_class():
    f = Flow(name="test")

    with pytest.raises(TypeError):
        f.add_task(1)


def test_set_dependencies_adds_all_arguments_to_flow():
    f = Flow(name="test")

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

    f = Flow(name="test")
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
    f = Flow(name="test")

    f.set_dependencies(task=t1, upstream_tasks=[t2], mapped=True)
    assert len(f.edges) == 1
    edge = f.edges.pop()
    assert edge.mapped is True


def test_set_dependencies_respects_unmapped():
    t1 = Task()
    t2 = Task()
    f = Flow(name="test")

    f.set_dependencies(task=t1, upstream_tasks=[unmapped(t2)], mapped=True)
    assert len(f.edges) == 1
    edge = f.edges.pop()
    assert edge.mapped is False


def test_binding_a_task_in_context_adds_it_to_flow():
    with Flow(name="test") as flow:
        t = Task()
        assert t not in flow.tasks
        t.bind()
        assert t in flow.tasks


def test_adding_a_task_to_a_flow_twice_is_ok():
    f = Flow(name="test")
    t = Task()
    f.add_task(t)
    f.add_task(t)


def test_binding_a_task_to_two_different_flows_is_ok():
    t = AddTask()

    with Flow(name="test") as f:
        t.bind(4, 2)

    with Flow(name="test") as g:
        t.bind(7, 8)

    f_res = f.run().result[t].result
    g_res = g.run().result[t].result
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

    with Flow(name="test") as f:
        kw.bind(a=t1, b=t2, c=t3)

    assert t1 in f.tasks
    assert t2 in f.tasks
    assert t3 in f.tasks

    assert Edge(t1, kw, key="a") in f.edges
    assert Edge(t2, kw, key="b") in f.edges
    assert Edge(t3, kw, key="c") in f.edges


def test_calling_a_task_returns_a_copy():
    t = AddTask()

    with Flow(name="test") as f:
        t.bind(4, 2)
        with pytest.warns(UserWarning):
            t2 = t(9, 0)

    assert isinstance(t2, AddTask)
    assert t != t2

    res = f.run().result
    assert res[t].result == 6
    assert res[t2].result == 9


def test_calling_a_slugged_task_in_different_flows_is_ok():
    t = AddTask(slug="add")

    with Flow(name="test") as f:
        three = t(1, 2)

    with Flow(name="test") as g:
        four = t(1, 3)


def test_calling_a_slugged_task_twice_warns_error():
    t = AddTask(slug="add")
    with Flow(name="test") as f:
        t.bind(4, 2)
        with pytest.warns(UserWarning), pytest.raises(ValueError):
            t2 = t(9, 0)


def test_context_manager_is_properly_applied_to_tasks():
    t1 = Task()
    t2 = Task()
    t3 = Task()
    with Flow(name="test") as f1:
        with Flow(name="test") as f2:
            t2.bind()
        t1.bind()

    with pytest.raises(ValueError):
        t3.bind()

    assert f1.tasks == set([t1])
    assert f2.tasks == set([t2])


def test_that_flow_adds_and_removes_itself_from_prefect_context():
    assert "flow" not in prefect.context
    with Flow(name="test") as f1:
        assert prefect.context.flow is f1
        with Flow(name="test") as f2:
            assert prefect.context.flow is f2
        assert prefect.context.flow is f1
    assert "flow" not in prefect.context


def test_add_edge():
    f = Flow(name="test")
    t1 = Task()
    t2 = Task()
    f.add_edge(upstream_task=t1, downstream_task=t2)
    assert f.upstream_tasks(t2) == set([t1])
    assert f.upstream_tasks(t1) == set()
    assert f.downstream_tasks(t2) == set()
    assert f.downstream_tasks(t1) == set([t2])
    assert f.edges_to(t2) == f.edges_from(t1)


def test_add_edge_returns_edge():
    f = Flow(name="test")
    t1 = Task()
    t2 = Task()
    edge = Edge(t1, t2)
    added_edge = f.add_edge(upstream_task=t1, downstream_task=t2)

    assert edge == added_edge
    assert added_edge in f.edges
    assert edge in f.edges


def test_chain():
    f = Flow(name="test")
    t1 = Task()
    t2 = Task()
    t3 = Task()
    t4 = Task()
    edges = f.chain(t1, t2, t3, t4)

    assert f.tasks == set([t1, t2, t3, t4])
    assert f.edges == set(edges)


def test_splatting_chain_works_in_flow_context_without_duplication():
    @task
    def do_nothing():
        pass

    with Flow(name="test") as f:
        f.chain(*[do_nothing() for _ in range(10)])

    assert len(f.tasks) == 10
    assert len(f.edges) == 9


def test_chain_works_in_flow_context_without_duplication():
    @task
    def do_nothing():
        pass

    with Flow(name="test") as f:
        f.chain(do_nothing(), do_nothing(), do_nothing(), Task())

    assert len(f.tasks) == 4
    assert len(f.edges) == 3


def test_iter():
    """
    Tests that iterating over a Flow yields the tasks in order
    """
    with Flow(name="test") as f:
        t1 = Task()
        t2 = Task()
        f.add_edge(upstream_task=t2, downstream_task=t1)
    assert tuple(f) == f.sorted_tasks() == (t2, t1)


def test_detect_cycle():
    f = Flow(name="test")
    t1 = Task()
    t2 = Task()

    f.add_edge(t1, t2)
    with pytest.raises(ValueError):
        f.add_edge(t2, t1, validate=True)


def test_eager_cycle_detection_defaults_false():

    assert not prefect.config.flows.eager_edge_validation

    f = Flow(name="test")
    t1 = Task()
    t2 = Task()
    f.add_edge(t1, t2)

    # no cycle detected
    assert f.add_edge(t2, t1)
    with pytest.raises(ValueError):
        f.validate()


def test_eager_cycle_detection_works():

    with set_temporary_config({"flows.eager_edge_validation": True}):
        f = Flow(name="test")
        t1 = Task()
        t2 = Task()

        f.add_edge(t1, t2)
        with pytest.raises(ValueError):
            f.add_edge(t2, t1)

    assert not prefect.config.flows.eager_edge_validation


def test_id_must_be_valid_uuid():
    f = Flow(name="test")

    with pytest.raises(ValueError):
        f.id = 1

    with pytest.raises(ValueError):
        f.id = "1"

    f.id = str(uuid.uuid4())


def test_copy():
    with Flow(name="test") as f:
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


def test_copy_creates_new_id():
    f = Flow(name="test")
    f2 = f.copy()
    assert f.id != f2.id


def test_infer_root_tasks():
    with Flow(name="test") as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)

    assert f.root_tasks() == set([t1])


def test_infer_terminal_tasks():
    with Flow(name="test") as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()
        t4 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)
    f.add_task(t4)

    assert f.terminal_tasks() == set([t3, t4])


def test_reference_tasks_are_terminal_tasks_by_default():
    with Flow(name="test") as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()
        t4 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)
    f.add_task(t4)

    assert f.reference_tasks() == f.terminal_tasks() == set([t3, t4])


def test_set_reference_tasks():
    with Flow(name="test") as f:
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
        Flow(name="test", reference_tasks=[Task()])
    assert "must be part of the flow" in str(exc.value)


def test_set_reference_tasks_at_init():
    t1 = Task()
    f = Flow(name="test", reference_tasks=[t1], tasks=[t1])
    assert f.reference_tasks() == set([t1]) == f.tasks == f.terminal_tasks()

    t2 = Task()
    f = Flow(name="test", reference_tasks=[t2], tasks=[t1, t2])
    assert f.reference_tasks() == set([t2])


def test_reset_reference_tasks_to_terminal_tasks():

    with Flow(name="test") as f:
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
    f = Flow(name="test")
    t1 = Task()
    with pytest.raises(ValueError):
        f.set_reference_tasks([t1])


def test_key_states_raises_error_if_not_iterable():
    with Flow(name="test") as f:
        t1 = Task()
        f.add_task(t1)
        with pytest.raises(TypeError):
            f.set_reference_tasks(t1)


class TestEquality:
    def test_equality_based_on_tasks(self):
        f1 = Flow(name="test")
        f2 = Flow(name="test")

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
        f1 = Flow(name="test")
        f2 = Flow(name="test")

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

    def test_equality_based_on_reference_tasks(self):
        f1 = Flow(name="test")
        f2 = Flow(name="test")

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
    f1 = Flow(name="test")
    f2 = Flow(name="test")

    t1 = Task()
    t2 = Task()
    t3 = Task()

    f1.add_edge(t1, t2)
    f2.add_edge(t2, t3)

    f2.update(f1)
    assert f2.tasks == set([t1, t2, t3])
    assert len(f2.edges) == 2


def test_upstream_and_downstream_error_msgs_when_task_is_not_in_flow():
    f = Flow(name="test")
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
    f = Flow(name="test")
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

    f = Flow(name="test")
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
    f = Flow(name="test")
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


def test_sorted_tasks_with_invalid_start_task():
    """
    t1 -> t2 -> t3 -> t4
                  t3 -> t5
    """
    f = Flow(name="test")
    t1 = Task("1")
    t2 = Task("2")
    t3 = Task("3")
    f.add_edge(t1, t2)

    with pytest.raises(ValueError) as exc:
        f.sorted_tasks(root_tasks=[t3])
    assert "not found in Flow" in str(exc.value)


def test_flow_raises_for_irrelevant_user_provided_parameters():
    class ParameterTask(Task):
        def run(self):
            return prefect.context.get("parameters")

    with Flow(name="test") as f:
        x = Parameter("x")
        t = ParameterTask()
        f.add_task(x)
        f.add_task(t)

    with pytest.raises(TypeError):
        state = f.run(parameters=dict(x=10, y=3, z=9))

    with pytest.raises(TypeError):
        state = f.run(x=10, y=3, z=9)


def test_validate_cycles():
    f = Flow(name="test")
    t1 = Task()
    t2 = Task()
    f.add_edge(t1, t2)
    f.add_edge(t2, t1)
    with pytest.raises(ValueError) as exc:
        f.validate()
    assert "cycle found" in str(exc.value).lower()


def test_validate_missing_edge_downstream_tasks():
    f = Flow(name="test")
    t1 = Task()
    t2 = Task()
    f.add_edge(t1, t2)
    f.tasks.remove(t2)
    with pytest.raises(ValueError) as exc:
        f.validate()
    assert "edges refer to tasks" in str(exc.value).lower()


def test_validate_missing_edge_upstream_tasks():
    f = Flow(name="test")
    t1 = Task()
    t2 = Task()
    f.add_edge(t1, t2)
    f.tasks.remove(t1)
    with pytest.raises(ValueError) as exc:
        f.validate()
    assert "edges refer to tasks" in str(exc.value).lower()


def test_validate_missing_reference_tasks():
    f = Flow(name="test")
    t1 = Task()
    t2 = Task()
    f.add_task(t1)
    f.add_task(t2)
    f.set_reference_tasks([t1])
    f.tasks.remove(t1)
    with pytest.raises(ValueError) as exc:
        f.validate()
    assert "reference tasks are not contained" in str(exc.value).lower()


def test_validate_edges_kwarg():
    f = Flow(name="test")
    t1, t2 = Task(), Task()  # these tasks don't support keyed edges
    with pytest.raises(TypeError):
        f.add_edge(t1, t2, key="x", validate=True)


def test_validate_edges():
    with set_temporary_config({"flows.eager_edge_validation": True}):
        f = Flow(name="test")
        t1, t2 = Task(), Task()  # these tasks don't support keyed edges
        with pytest.raises(TypeError):
            f.add_edge(t1, t2, key="x")


def test_skip_validate_edges():
    f = Flow(name="test")
    t1, t2 = Task(), Task()  # these tasks don't support keyed edges
    f.add_edge(t1, t2, key="x", validate=False)
    f.add_edge(t2, t1, validate=False)  # this introduces a cycle


def test_skip_validation_in_init_with_kwarg():
    t1, t2 = Task(), Task()  # these tasks don't support keyed edges
    e1, e2 = Edge(t1, t2), Edge(t2, t1)
    with pytest.raises(ValueError):
        Flow(name="test", edges=[e1, e2], validate=True)

    assert Flow(name="test", edges=[e1, e2], validate=False)


class TestFlowVisualize:
    def test_visualize_raises_informative_importerror_without_graphviz(
        self, monkeypatch
    ):
        f = Flow(name="test")
        f.add_task(Task())

        with monkeypatch.context() as m:
            m.setattr(sys, "path", "")
            with pytest.raises(ImportError) as exc:
                f.visualize()

        assert "pip install prefect[viz]" in repr(exc.value)

    def test_viz_returns_graph_object_if_in_ipython(self):
        import graphviz

        ipython = MagicMock(
            get_ipython=lambda: MagicMock(config=dict(IPKernelApp=True))
        )
        with patch.dict("sys.modules", IPython=ipython):
            f = Flow(name="test")
            f.add_task(Task(name="a_nice_task"))
            graph = f.visualize()
        assert "label=a_nice_task" in graph.source
        assert "shape=ellipse" in graph.source

    def test_viz_reflects_mapping(self):
        ipython = MagicMock(
            get_ipython=lambda: MagicMock(config=dict(IPKernelApp=True))
        )
        with patch.dict("sys.modules", IPython=ipython):
            with Flow(name="test") as f:
                res = AddTask(name="a_nice_task").map(x=Task(name="a_list_task"), y=8)
            graph = f.visualize()
        assert 'label="a_nice_task <map>" shape=box' in graph.source
        assert "label=a_list_task shape=ellipse" in graph.source
        assert "label=x style=dashed" in graph.source
        assert "label=y style=dashed" in graph.source

    @pytest.mark.parametrize("state", [Success(), Failed(), Skipped()])
    def test_viz_if_flow_state_provided(self, state):
        import graphviz

        ipython = MagicMock(
            get_ipython=lambda: MagicMock(config=dict(IPKernelApp=True))
        )
        with patch.dict("sys.modules", IPython=ipython):
            t = Task(name="a_nice_task")
            f = Flow(name="test")
            f.add_task(t)
            graph = f.visualize(flow_state=Success(result={t: state}))
        assert "label=a_nice_task" in graph.source
        assert 'color="' + state.color + '80"' in graph.source
        assert "shape=ellipse" in graph.source

    def test_viz_reflects_mapping_if_flow_state_provided(self):
        ipython = MagicMock(
            get_ipython=lambda: MagicMock(config=dict(IPKernelApp=True))
        )
        add = AddTask(name="a_nice_task")
        list_task = Task(name="a_list_task")

        map_state = Mapped(map_states=[Success(), Failed()])
        with patch.dict("sys.modules", IPython=ipython):
            with Flow(name="test") as f:
                res = add.map(x=list_task, y=8)
            graph = f.visualize(
                flow_state=Success(result={res: map_state, list_task: Success()})
            )

        # one colored node for each mapped result
        assert 'label="a_nice_task <map>" color="#00800080"' in graph.source
        assert 'label="a_nice_task <map>" color="#FF000080"' in graph.source
        assert 'label=a_list_task color="#00800080"' in graph.source
        assert 'label=8 color="#00000080"' in graph.source

        # two edges for each input to add()
        for var in ["x", "y"]:
            for index in [0, 1]:
                assert "{0} [label={1} style=dashed]".format(index, var) in graph.source

    def test_viz_reflects_multiple_mapping_if_flow_state_provided(self):
        ipython = MagicMock(
            get_ipython=lambda: MagicMock(config=dict(IPKernelApp=True))
        )
        add = AddTask(name="a_nice_task")
        list_task = Task(name="a_list_task")

        map_state1 = Mapped(map_states=[Success(), TriggerFailed()])
        map_state2 = Mapped(map_states=[Success(), Failed()])

        with patch.dict("sys.modules", IPython=ipython):
            with Flow(name="test") as f:
                first_res = add.map(x=list_task, y=8)
                with pytest.warns(
                    UserWarning
                ):  # making a copy of a task with dependencies
                    res = first_res.map(x=first_res, y=9)
            graph = f.visualize(
                flow_state=Success(
                    result={
                        res: map_state1,
                        list_task: Success(),
                        first_res: map_state2,
                    }
                )
            )

        assert "{first} -> {second} [label=x style=dashed]".format(
            first=str(id(first_res)) + "0", second=str(id(res)) + "0"
        )
        assert "{first} -> {second} [label=x style=dashed]".format(
            first=str(id(first_res)) + "1", second=str(id(res)) + "1"
        )

    @pytest.mark.parametrize(
        "error",
        [
            ImportError("abc"),
            ValueError("abc"),
            TypeError("abc"),
            NameError("abc"),
            AttributeError("abc"),
        ],
    )
    def test_viz_renders_if_ipython_isnt_installed_or_errors(self, error):
        graphviz = MagicMock()
        ipython = MagicMock(get_ipython=MagicMock(side_effect=error))
        with patch.dict("sys.modules", graphviz=graphviz, IPython=ipython):
            with Flow(name="test") as f:
                res = AddTask(name="a_nice_task").map(x=Task(name="a_list_task"), y=8)
            f.visualize()


class TestCache:
    def test_cache_created(self):
        f = Flow(name="test")
        assert isinstance(f._cache, dict)
        assert len(f._cache) == 0

    def test_cache_sorted_tasks(self):
        f = Flow(name="test")
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
        f = Flow(name="test")
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
        f = Flow(name="test")
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
        f = Flow(name="test")
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
        f = Flow(name="test")
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
        f = Flow(name="test")
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
        f = Flow(name="test")
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
        f = Flow(name="test")
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

    def test_cache_survives_pickling(self):
        f = Flow(name="test")
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
        f = Flow(name="test")
        f._cache[1] = 2
        f.add_task(Task())
        assert 1 not in f._cache

    def test_adding_edge_clears_cache(self):
        f = Flow(name="test")
        f._cache[1] = 2
        f.add_edge(Task(), Task())
        assert 1 not in f._cache

    def test_setting_reference_tasks_clears_cache(self):
        f = Flow(name="test")
        t1 = Task()
        f.add_task(t1)
        f._cache[1] = 2
        f.set_reference_tasks([t1])
        assert 1 not in f._cache


class TestReplace:
    def test_replace_replaces_all_the_things(self):
        with Flow(name="test") as f:
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
        with Flow(name="test") as f:
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

        with Flow(name="test") as f:
            x, y = Parameter("x"), Parameter("y")
            res = add(x, y)

        state = f.run(x=10, y=11)
        assert state.result[res].result == 21

        f.replace(res, sub)
        state = f.run(x=10, y=11)
        assert state.result[sub].result == -1

    def test_replace_converts_new_to_task(self):
        add = AddTask()
        with Flow(name="test") as f:
            x, y = Parameter("x"), Parameter("y")
            res = add(x, y)
        f.replace(x, 55)
        assert len(f.tasks) == 3
        state = f.run(y=6)
        assert state.is_successful()
        assert state.result[res].result == 61


class TestGetTasks:
    def test_get_tasks_defaults_to_return_everything(self):
        t1, t2 = Task(name="t1"), Task(name="t2")
        f = Flow(name="test", tasks=[t1, t2])
        assert f.get_tasks() == [t1, t2]

    def test_get_tasks_defaults_to_name(self):
        t1, t2 = Task(name="t1"), Task(name="t2")
        f = Flow(name="test", tasks=[t1, t2])
        assert f.get_tasks("t1") == [t1]

    def test_get_tasks_takes_intersection(self):
        t1, t2 = Task(name="t1", slug="11"), Task(name="t1", slug="22")
        f = Flow(name="test", tasks=[t1, t2])
        assert f.get_tasks(name="t1") == [t1, t2]
        assert f.get_tasks(name="t1", slug="11") == [t1]
        assert f.get_tasks(name="t1", slug="11", tags=["atag"]) == []

    def test_get_tasks_accepts_tags_and_requires_all_tags(self):
        t1, t2 = Task(name="t1", tags=["a", "b"]), Task(name="t1", tags=["a"])
        f = Flow(name="test", tasks=[t1, t2])
        assert f.get_tasks(tags=["a", "b"]) == [t1]

    def test_get_tasks_can_check_types(self):
        class Specific(Task):
            pass

        t1, t2 = Task(name="t1", tags=["a", "b"]), Specific(name="t1", tags=["a"])
        f = Flow(name="test", tasks=[t1, t2])
        assert f.get_tasks(task_type=Specific) == [t2]


class TestSerialize:
    def test_serialization(self):
        p1, t2, t3, = Parameter("1"), Task("2"), Task("3")

        f = Flow(name="test", tasks=[p1, t2, t3])
        f.add_edge(p1, t2)
        f.add_edge(p1, t3)

        serialized = f.serialize()
        assert isinstance(serialized, dict)
        assert len(serialized["tasks"]) == len(f.tasks)

    def test_deserialization(self):
        p1, t2, t3, = Parameter("1"), Task("2"), Task("3")

        f = Flow(
            name="hi",
            tasks=[p1, t2, t3],
            schedule=prefect.schedules.CronSchedule("0 0 * * *"),
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
        assert isinstance(f2.schedule, prefect.schedules.CronSchedule)

    def test_serialize_validates_invalid_flows(self):
        t1, t2 = Task(), Task()
        f = Flow(name="test")
        f.add_edge(t1, t2)
        # default settings should allow this even though it's illegal
        f.add_edge(t2, t1)

        with pytest.raises(ValueError) as exc:
            f.serialize()
        assert "cycle found" in str(exc).lower()

    def test_default_environment_is_local_environment(self):
        f = Flow(name="test")
        assert isinstance(f.environment, prefect.environments.LocalEnvironment)

    def test_serialize_includes_environment(self):
        f = Flow(name="test", environment=prefect.environments.LocalEnvironment())
        s_no_build = f.serialize()
        s_build = f.serialize(build=True)

        assert s_no_build["environment"]["type"] == "LocalEnvironment"
        assert s_no_build["environment"]["serialized_flow"] is None
        assert s_build["environment"]["type"] == "LocalEnvironment"

    def test_to_environment_file_writes_data(self):
        f = Flow(name="test")
        with tempfile.NamedTemporaryFile() as tmp:
            f.to_environment_file(tmp.name)
            with open(tmp.name, "r") as f:
                assert f.read()


def test_flow_dot_run_runs_on_schedule():
    class MockSchedule(prefect.schedules.Schedule):
        call_count = 0

        def next(self, n):
            if self.call_count < 2:
                self.call_count += 1
                return [pendulum.now("utc")]
            else:
                raise SyntaxError("Cease scheduling!")

    class StatefulTask(Task):
        call_count = 0

        def run(self):
            self.call_count += 1

    t = StatefulTask()
    schedule = MockSchedule()
    f = Flow(name="test", tasks=[t], schedule=schedule)
    with pytest.raises(SyntaxError) as exc:
        f.run()
    assert "Cease" in str(exc.value)
    assert t.call_count == 2


def test_scheduled_runs_handle_retries():
    class MockSchedule(prefect.schedules.Schedule):
        call_count = 0

        def next(self, n):
            if self.call_count < 1:
                self.call_count += 1
                return [pendulum.now("utc")]
            else:
                raise SyntaxError("Cease scheduling!")

    class StatefulTask(Task):
        call_count = 0

        def run(self):
            self.call_count += 1
            if self.call_count == 1:
                raise OSError("I need to run again.")

    state_history = []

    def handler(task, old, new):
        state_history.append(new)
        return new

    t = StatefulTask(
        max_retries=1,
        retry_delay=datetime.timedelta(minutes=0),
        state_handlers=[handler],
    )
    schedule = MockSchedule()
    f = Flow(name="test", tasks=[t], schedule=schedule)
    with pytest.raises(SyntaxError) as exc:
        f.run()
    assert "Cease" in str(exc.value)
    assert t.call_count == 2
    assert len(state_history) == 5  # Running, Failed, Retrying, Running, Success


def test_scheduled_runs_handle_mapped_retries():
    class StatefulTask(Task):
        call_count = 0

        def run(self):
            self.call_count += 1
            if self.call_count == 1:
                raise OSError("I need to run again.")

    state_history = []

    def handler(task, old, new):
        state_history.append(new)
        return new

    t = StatefulTask(
        max_retries=1,
        retry_delay=datetime.timedelta(minutes=0),
        state_handlers=[handler],
    )
    with Flow(name="test") as f:
        res = t.map(upstream_tasks=[[1, 2, 3]])

    flow_state = f.run()
    assert flow_state.is_successful()
    assert all([s.is_successful() for s in flow_state.result[res].map_states])
    assert res.call_count == 4
    assert len(state_history) == 11


def test_flow_run_accepts_state_kwarg():
    f = Flow(name="test")
    state = f.run(state=Finished())
    assert state.is_finished()


def test_bad_flow_runner_code_still_returns_state_obj():
    class BadFlowRunner(prefect.engine.flow_runner.FlowRunner):
        def initialize_run(self, *args, **kwargs):
            import blig  # will raise ImportError

    f = Flow(name="test", tasks=[Task()])
    res = f.run(runner_cls=BadFlowRunner)
    assert isinstance(res, State)
    assert res.is_failed()
    assert isinstance(res.result, ImportError)


def test_flow_run_raises_informative_error_for_certain_kwargs():
    f = Flow(name="test")
    with pytest.raises(ValueError) as exc:
        f.run(return_tasks=f.tasks)
    assert "`return_tasks` keyword cannot be provided" in str(exc.value)


def test_flow_run_raises_if_no_more_scheduled_runs():
    schedule = prefect.schedules.OneTimeSchedule(
        start_date=pendulum.now("utc").add(days=-1)
    )
    f = Flow(name="test", schedule=schedule)
    with pytest.raises(ValueError) as exc:
        f.run()
    assert "no more scheduled runs" in str(exc.value)


def test_flow_run_respects_state_kwarg():
    f = Flow(name="test")
    state = f.run(state=Failed("Unique."))
    assert state.is_failed()
    assert state.message == "Unique."


def test_flow_run_respects_task_state_kwarg():
    t, s = Task(), Task()
    f = Flow(name="test", tasks=[t, s])
    flow_state = f.run(task_states={t: Failed("unique.")})
    assert flow_state.is_failed()
    assert flow_state.result[t].is_failed()
    assert flow_state.result[t].message == "unique."
    assert flow_state.result[s].is_successful()


def test_flow_run_handles_error_states_when_initial_state_is_provided():
    with Flow(name="test") as f:
        res = AddTask()("5", 5)
    state = f.run(state=Pending())
    assert state.is_failed()
