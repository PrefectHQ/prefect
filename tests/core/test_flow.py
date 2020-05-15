import datetime
import logging
import json
import os
import platform
import random
import sys
import tempfile
import time
import uuid
from unittest.mock import MagicMock, patch

import cloudpickle
import pendulum
import pytest
import toml

import prefect
from prefect.core.edge import Edge
from prefect.core.flow import Flow
from prefect.core.task import Parameter, Task
from prefect.engine.cache_validators import all_inputs, partial_inputs_only
from prefect.engine.executors import LocalExecutor
from prefect.engine.result import Result
from prefect.engine.results import LocalResult, PrefectResult
from prefect.engine.result_handlers import LocalResultHandler, ResultHandler
from prefect.engine.signals import PrefectError, FAIL, LOOP
from prefect.engine.state import (
    Cancelled,
    Failed,
    Finished,
    Mapped,
    Paused,
    Resume,
    Pending,
    Skipped,
    State,
    Success,
    TriggerFailed,
    TimedOut,
)
from prefect.schedules.clocks import ClockEvent
from prefect.tasks.core.function import FunctionTask
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.serialization import from_qualified_name
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


@pytest.fixture
def clear_context_cache():
    prefect.context["caches"] = {}


class TestCreateFlow:
    """ Test various Flow constructors """

    def test_create_flow_with_no_args(self):
        # name is required
        f1 = Flow("f1")
        assert f1.name

    def test_create_flow_with_no_name(self):
        with pytest.raises(TypeError):
            f1 = Flow()

    def test_create_flow_with_name_as_none(self):
        with pytest.raises(ValueError):
            f1 = Flow(name=None)

    def test_create_flow_with_name_as_empty_string(self):
        with pytest.raises(ValueError):
            f1 = Flow(name="")

    def test_create_flow_with_name_as_false(self):
        with pytest.raises(ValueError):
            f1 = Flow(name=False)

    def test_create_flow_with_name(self):
        f2 = Flow(name="test")
        assert f2.name == "test"

    def test_create_flow_with_edges(self):
        f1 = Flow(
            name="test",
            edges=[Edge(upstream_task=Task(), downstream_task=AddTask(), key="x")],
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
        assert f.logger.name == "prefect.test"

    def test_flow_has_logger_with_informative_name(self):
        f = Flow(name="foo")
        assert isinstance(f.logger, logging.Logger)
        assert f.logger.name == "prefect.foo"

    def test_create_flow_with_result(self):
        f = Flow(name="test", result=LocalResult())
        assert isinstance(f.result, Result)
        assert isinstance(f.result, LocalResult)

    def test_create_flow_with_storage(self):
        f2 = Flow(name="test", storage=prefect.environments.storage.Local())
        assert isinstance(f2.storage, prefect.environments.storage.Local)
        assert f2.result is None

    def test_create_flow_with_storage_and_result(self):
        result = LocalResult(dir="/")
        f2 = Flow(
            name="test", storage=prefect.environments.storage.Local(), result=result,
        )
        assert isinstance(f2.storage, prefect.environments.storage.Local)
        assert isinstance(f2.result, LocalResult)
        assert f2.result != f2.storage.result
        assert f2.result == result

    def test_create_flow_with_environment(self):
        f2 = Flow(name="test", environment=prefect.environments.RemoteEnvironment())
        assert isinstance(f2.environment, prefect.environments.RemoteEnvironment)

    def test_create_flow_has_default_environment(self):
        f2 = Flow(name="test")
        assert isinstance(f2.environment, prefect.environments.RemoteEnvironment)

    def test_create_flow_auto_generates_tasks(self):
        with Flow("auto") as f:
            res = AddTask()(x=1, y=2)

        assert res.auto_generated is False
        assert all(
            [
                t.auto_generated is True
                for t in f.get_tasks(task_type=prefect.tasks.core.constants.Constant)
            ]
        )


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


def test_set_dependencies_converts_unkeyed_arguments_to_tasks():
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
    assert len(f.tasks) == 3
    assert f.constants[t1] == dict(x=4)


@pytest.mark.parametrize(
    "val", [[[[3]]], [1, 2, (3, [4])], [([1, 2, 3],)], {"a": 1, "b": [2]}]
)
def test_set_dependencies_with_nested_ordered_constants_creates_a_single_constant(val):
    class ReturnTask(Task):
        def run(self, x):
            return x

    with Flow("test") as f:
        task = ReturnTask()(x=val)
    assert f.run().result[task].result == val
    assert f.constants[task] == dict(x=val)


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


def test_binding_a_task_adds_it_to_flow():
    flow = Flow(name="test")
    t = Task()
    assert t not in flow.tasks
    t.bind(flow=flow)
    assert t in flow.tasks


def test_binding_a_task_no_with_flow_raises_error():
    t = Task()
    with pytest.raises(ValueError):
        t.bind()


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


def test_calling_a_task_without_context_returns_a_copy():
    t = AddTask()

    f = Flow(name="test")
    t.bind(4, 2, flow=f)
    t2 = t(9, 0, flow=f)

    assert isinstance(t2, AddTask)
    assert t != t2

    res = f.run().result
    assert res[t].result == 6
    assert res[t2].result == 9


def test_calling_a_task_returns_a_copy():
    t = AddTask()

    with Flow(name="test") as f:
        t.bind(4, 2)
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


def test_add_edge_raise_error_for_downstream_parameter():
    f = Flow(name="test")
    t = Task()
    p = Parameter("p")

    with pytest.raises(ValueError, match="can not have upstream dependencies"):
        f.add_edge(upstream_task=t, downstream_task=p)


def test_add_edge_raise_error_for_duplicate_key_if_validate():
    f = Flow(name="test")
    t = Task()
    a = AddTask()

    f.add_edge(upstream_task=t, downstream_task=a, key="x")
    with pytest.raises(ValueError, match="already been assigned"):
        f.add_edge(upstream_task=t, downstream_task=a, key="x", validate=True)


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


def test_direct_cycles_are_always_detected_1():
    # edge classes prevent tasks from connecting to themselves, so
    # direct cycles should always be prevented
    f = Flow(name="test")
    t = Task()
    with pytest.raises(ValueError):
        f.add_edge(t, t)


def test_direct_cycles_are_always_detected_2():
    # edge classes prevent tasks from connecting to themselves, so
    # direct cycles should always be prevented
    f = Flow(name="test")
    t = Task()
    with f:
        with pytest.raises(ValueError):
            t.set_upstream(t)


def test_eager_validation_is_off_by_default(monkeypatch):
    # https://github.com/PrefectHQ/prefect/issues/919
    assert not prefect.config.flows.eager_edge_validation

    validate = MagicMock()
    monkeypatch.setattr("prefect.core.flow.Flow.validate", validate)

    @task
    def length(x):
        return len(x)

    data = list(range(10))
    with Flow(name="test") as f:
        length.map(data)

    assert validate.call_count == 0

    f.validate()

    assert validate.call_count == 1


def test_eager_cycle_detection_works():

    with set_temporary_config({"flows.eager_edge_validation": True}):
        f = Flow(name="test")
        t1 = Task()
        t2 = Task()

        f.add_edge(t1, t2)
        with pytest.raises(ValueError):
            f.add_edge(t2, t1)

    assert not prefect.config.flows.eager_edge_validation


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

    with pytest.raises(ValueError, match="must be part of the flow"):
        Flow(name="test", reference_tasks=[Task()])


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

    def test_object_inequality(self):
        assert Flow(name="test") != 1

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


def test_update():
    f1 = Flow(name="test")
    f2 = Flow(name="test")

    t1 = Task()
    t2 = Task()
    t3 = Task()

    f1.add_edge(t1, t2)
    f2.add_edge(t2, t3)

    f2.update(f1)
    assert f2.tasks == {t1, t2, t3}
    assert len(f2.edges) == 2


def test_update_with_constants():
    with Flow("math") as f:
        x = Parameter("x")
        d = x["d"] + 4

    new_flow = Flow("test")
    new_flow.update(f)

    flow_state = new_flow.run(x=dict(d=42))
    assert flow_state.is_successful()
    assert flow_state.result[d].result == 46


def test_update_with_mapped_edges():
    t1 = Task()
    t2 = Task()
    t3 = Task()

    with Flow(name="test") as f1:
        m = t2.map(upstream_tasks=[t1])

    f2 = Flow(name="test")
    f2.add_edge(t2, t3)

    f2.update(f1)
    assert f2.tasks == {m, t1, t2, t3}
    assert len(f2.edges) == 2
    assert len([e for e in f2.edges if e.mapped]) == 1


def test_upstream_and_downstream_error_msgs_when_task_is_not_in_flow():
    f = Flow(name="test")
    t = Task()

    with pytest.raises(ValueError, match="was not found in Flow"):
        f.edges_to(t)

    with pytest.raises(ValueError, match="was not found in Flow"):
        f.edges_from(t)

    with pytest.raises(ValueError, match="was not found in Flow"):
        f.upstream_tasks(t)

    with pytest.raises(ValueError, match="was not found in Flow"):
        f.downstream_tasks(t)


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

    with pytest.raises(ValueError, match="not found in Flow"):
        f.sorted_tasks(root_tasks=[t3])


def test_flow_raises_for_irrelevant_user_provided_parameters():
    class ParameterTask(Task):
        def run(self):
            return prefect.context.get("parameters")

    with Flow(name="test") as f:
        x = Parameter("x")
        t = ParameterTask()
        f.add_task(x)
        f.add_task(t)

    # errors because of the invalid parameter
    with pytest.raises(ValueError):
        state = f.run(parameters=dict(x=10, y=3, z=9))

    # errors because the parameter is passed to FlowRunner.run() as an invalid kwarg
    with pytest.raises(TypeError):
        state = f.run(x=10, y=3, z=9)


def test_flow_raises_for_missing_required_parameters():
    with Flow(name="test") as f:
        f.add_task(Parameter("x"))

    with pytest.raises(ValueError):
        f.run()


def test_flow_doesnt_raises_for_missing_nonrequired_parameters():
    with Flow(name="test") as f:
        p = Parameter("x", default=1)
        f.add_task(p)

    flow_state = f.run()
    assert flow_state.is_successful()
    assert flow_state.result[p].result == 1


def test_flow_accepts_unserializeable_parameters():
    with Flow(name="test") as f:
        p = Parameter("x")()

    value = lambda a: a + 1

    state = f.run(parameters={"x": value})
    assert state.result[p].result is value


def test_parameters_can_not_be_downstream_dependencies():
    with Flow(name="test") as f:
        p = Parameter("x")
        t = Task()
        with pytest.raises(ValueError):
            t.set_downstream(p)


def test_validate_cycles():
    f = Flow(name="test")
    t1 = Task()
    t2 = Task()
    f.add_edge(t1, t2)
    f.add_edge(t2, t1)
    with pytest.raises(ValueError, match="Cycle found"):
        f.validate()


def test_validate_missing_edge_downstream_tasks():
    f = Flow(name="test")
    t1 = Task()
    t2 = Task()
    f.add_edge(t1, t2)
    f.tasks.remove(t2)
    with pytest.raises(ValueError, match="edges refer to tasks"):
        f.validate()


def test_validate_missing_edge_upstream_tasks():
    f = Flow(name="test")
    t1 = Task()
    t2 = Task()
    f.add_edge(t1, t2)
    f.tasks.remove(t1)
    with pytest.raises(ValueError, match="edges refer to tasks"):
        f.validate()


def test_validate_missing_reference_tasks():
    f = Flow(name="test")
    t1 = Task()
    t2 = Task()
    f.add_task(t1)
    f.add_task(t2)
    f.set_reference_tasks([t1])
    f.tasks.remove(t1)
    with pytest.raises(ValueError, match="reference tasks are not contained"):
        f.validate()


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


@pytest.mark.xfail(raises=ImportError, reason="viz extras not installed.")
class TestFlowVisualize:
    def test_visualize_raises_informative_importerror_without_python_graphviz(
        self, monkeypatch
    ):
        f = Flow(name="test")
        f.add_task(Task())

        with monkeypatch.context() as m:
            m.setattr(sys, "path", "")
            with pytest.raises(ImportError, match=r"pip install 'prefect\[viz\]'"):
                f.visualize()

    def test_visualize_raises_informative_error_without_sys_graphviz(self, monkeypatch):
        f = Flow(name="test")
        f.add_task(Task())

        import graphviz as gviz

        err = gviz.backend.ExecutableNotFound
        graphviz = MagicMock(
            Digraph=lambda: MagicMock(
                render=MagicMock(side_effect=err("Can't find dot!"))
            )
        )
        graphviz.backend.ExecutableNotFound = err
        with patch.dict("sys.modules", graphviz=graphviz):
            with pytest.raises(err, match="Please install Graphviz"):
                f.visualize()

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

    @pytest.mark.skipif(sys.platform == "win32", reason="Test fails on Windows")
    def test_viz_saves_graph_object_if_filename(self):
        import graphviz

        f = Flow(name="test")
        f.add_task(Task(name="a_nice_task"))

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "viz"), "wb") as tmp:
                graph = f.visualize(filename=tmp.name)
            with open(tmp.name, "r") as f:
                contents = f.read()

        assert "label=a_nice_task" in contents
        assert "shape=ellipse" in contents

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

    def test_viz_can_handle_skipped_mapped_tasks(self):
        ipython = MagicMock(
            get_ipython=lambda: MagicMock(config=dict(IPKernelApp=True))
        )
        with patch.dict("sys.modules", IPython=ipython):
            with Flow(name="test") as f:
                t = Task(name="a_list_task")
                res = AddTask(name="a_nice_task").map(x=t, y=8)

            graph = f.visualize(
                flow_state=Success(result={t: Success(), res: Skipped()})
            )
        assert 'label="a_nice_task <map>" color="#62757f80"' in graph.source
        assert 'label=a_list_task color="#28a74580"' in graph.source
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
        assert (
            'label="a_nice_task <map>" color="{success}80"'.format(
                success=Success.color
            )
            in graph.source
        )
        assert (
            'label="a_nice_task <map>" color="{failed}80"'.format(failed=Failed.color)
            in graph.source
        )
        assert (
            'label=a_list_task color="{success}80"'.format(success=Success.color)
            in graph.source
        )

        for index in [0, 1]:
            assert "{0} [label=x style=dashed]".format(index) in graph.source

    def test_viz_reflects_reduce_mapping_states_if_flow_state_provided(self):
        ipython = MagicMock(
            get_ipython=lambda: MagicMock(config=dict(IPKernelApp=True))
        )
        add = AddTask(name="a_nice_task")
        list_task = Task(name="a_list_task")
        reduce_task = AddTask(name="reduce")

        map_state = Mapped(map_states=[Success(), Failed(), Success(), Success()])

        with patch.dict("sys.modules", IPython=ipython):
            with Flow(name="test") as f:
                res = add.map(x=list_task, y=8)
                final = reduce_task(res, y=9)

            graph = f.visualize(
                flow_state=Success(
                    result={res: map_state, list_task: Success(), final: Success()}
                )
            )

        print(graph.source)

        # one colored node for each mapped result from its upstream
        for index in [0, 1, 2, 3]:
            assert "{0} [label=x style=dashed]".format(index) in graph.source

        # one edge for each mapped result to the reduce task
        for index in [0, 1]:
            edge_string = "[label=x]".format(index)
            assert graph.source.count(edge_string) == 4

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

    def test_viz_saves_graph_object_with_correct_extension(self):
        import graphviz

        tested_formats = ["jpg", "png", "svg", "gif", "jpeg", "pdf"]
        f = Flow(name="test")
        f.add_task(Task(name="a_nice_task"))

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "viz"), "wb") as tmp:
                print(sorted(list(graphviz.FORMATS)))
                for _format in tested_formats:
                    graph = f.visualize(filename=tmp.name, format=_format)
                    assert os.path.exists(os.path.join(tmpdir, f"{tmp.name}.{_format}"))


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
        t4 = Task()
        f.add_edge(t1, t2)
        f.sorted_tasks()
        key = ("_sorted_tasks", (("root_tasks", ()),))
        f._cache[key] = 1
        assert f.sorted_tasks() == 1

        f2 = cloudpickle.loads(cloudpickle.dumps(f))
        assert f2.sorted_tasks() == 1
        f2.add_edge(t3, t4)
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

    def test_replace_converts_new_collections_to_tasks(self):
        add = AddTask()

        with Flow(name="test") as f:
            x, y = Parameter("x"), Parameter("y")
            res = add(x, y)

        f.replace(x, [55, 56])
        f.replace(y, [1, 2])

        assert len(f.tasks) == 3
        state = f.run()
        assert state.is_successful()
        assert state.result[res].result == [55, 56, 1, 2]


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
        assert isinstance(f2.schedule, prefect.schedules.Schedule)
        assert isinstance(f2.schedule.clocks[0], prefect.schedules.clocks.CronClock)

    def test_serialize_validates_invalid_flows(self):
        t1, t2 = Task(), Task()
        f = Flow(name="test")
        f.add_edge(t1, t2)
        # default settings should allow this even though it's illegal
        f.add_edge(t2, t1)

        with pytest.raises(ValueError, match="Cycle found"):
            f.serialize()

    def test_default_environment_is_cloud_environment(self):
        f = Flow(name="test")
        assert isinstance(f.environment, prefect.environments.RemoteEnvironment)

    def test_serialize_includes_storage(self):
        f = Flow(name="test", storage=prefect.environments.storage.Local())
        s_no_build = f.serialize()
        s_build = f.serialize(build=True)

        assert s_no_build["storage"]["type"] == "Local"
        assert s_build["storage"]["type"] == "Local"

    def test_serialize_adds_flow_to_storage_if_build(self, tmpdir):
        f = Flow(name="test", storage=prefect.environments.storage.Local(tmpdir))
        s_no_build = f.serialize()
        assert f.name not in f.storage

        s_build = f.serialize(build=True)
        assert f.name in f.storage

    def test_serialize_can_be_called_twice(self, tmpdir):
        f = Flow(name="test", storage=prefect.environments.storage.Local(tmpdir))
        s_no_build = f.serialize()
        assert f.name not in f.storage

        f.serialize(build=True)
        with pytest.warns(UserWarning) as warning:
            f.serialize(build=True)

        w = warning.pop()
        assert "already contained in storage" in str(w.message)

    def test_serialize_fails_with_no_storage(self):
        f = Flow(name="test")
        with pytest.raises(ValueError):
            s_build = f.serialize(build=True)


@pytest.mark.usefixtures("clear_context_cache")
class TestFlowRunMethod:
    @pytest.fixture
    def repeat_schedule(self):
        class RepeatSchedule(prefect.schedules.Schedule):
            def __init__(self, n, **kwargs):
                self.call_count = 0
                self.n = n
                super().__init__(clocks=[])

            def next(self, n, **kwargs):
                if self.call_count < self.n:
                    self.call_count += 1
                    return [ClockEvent(pendulum.now("UTC").add(seconds=0.1))]
                else:
                    return []

        return RepeatSchedule

    def test_flow_dot_run_runs_on_schedule(self, repeat_schedule):
        schedule = repeat_schedule(2)

        class StatefulTask(Task):
            call_count = 0

            def run(self):
                self.call_count += 1

        t = StatefulTask()
        f = Flow(name="test", tasks=[t], schedule=schedule)
        f.run()
        assert t.call_count == 2

    def test_flow_dot_run_passes_scheduled_parameters(self):
        a = prefect.schedules.clocks.DatesClock(
            [pendulum.now("UTC").add(seconds=0.1)], parameter_defaults=dict(x=1)
        )
        b = prefect.schedules.clocks.DatesClock(
            [pendulum.now("UTC").add(seconds=0.5)], parameter_defaults=dict(x=2)
        )

        x = prefect.Parameter("x", default=None, required=False)
        outputs = []

        @prefect.task
        def whats_the_param(x):
            outputs.append(x)

        with Flow("test", schedule=prefect.schedules.Schedule(clocks=[a, b])) as f:
            whats_the_param(x)

        f.run()

        assert outputs == [1, 2]

    def test_flow_dot_run_doesnt_persist_stale_scheduled_params(self):
        a = prefect.schedules.clocks.DatesClock(
            [pendulum.now("UTC").add(seconds=0.1)], parameter_defaults=dict(x=1)
        )
        b = prefect.schedules.clocks.DatesClock([pendulum.now("UTC").add(seconds=0.35)])

        x = prefect.Parameter("x", default=3, required=False)
        outputs = []

        @prefect.task
        def whats_the_param(x):
            outputs.append(x)

        with Flow("test", schedule=prefect.schedules.Schedule(clocks=[a, b])) as f:
            whats_the_param(x)

        f.run()

        assert outputs == [1, 3]

    def test_flow_dot_run_doesnt_run_on_schedule(self, repeat_schedule):
        schedule = repeat_schedule(2)

        class StatefulTask(Task):
            call_count = 0

            def run(self):
                self.call_count += 1

        t = StatefulTask()
        f = Flow(name="test", tasks=[t], schedule=schedule)
        state = f.run(run_on_schedule=False)
        assert t.call_count == 1

    def test_flow_dot_run_returns_tasks_when_running_off_schedule(self):
        @prefect.task
        def test_task():
            return 2

        f = Flow(name="test", tasks=[test_task])
        res = f.run(run_on_schedule=False)

        assert res.is_successful()
        assert res.result[test_task].is_successful()
        assert res.result[test_task].result == 2

    def test_flow_dot_run_responds_to_config(self, repeat_schedule):
        schedule = repeat_schedule(2)

        class StatefulTask(Task):
            call_count = 0

            def run(self):
                self.call_count += 1

        t = StatefulTask()
        f = Flow(name="test", tasks=[t], schedule=schedule)
        with set_temporary_config({"flows.run_on_schedule": False}):
            state = f.run()
        assert t.call_count == 1

    def test_flow_dot_run_stops_on_schedule(self, repeat_schedule):
        schedule = repeat_schedule(1)

        class StatefulTask(Task):
            call_count = 0

            def run(self):
                self.call_count += 1

        t = StatefulTask()
        f = Flow(name="test", tasks=[t], schedule=schedule)
        f.run()
        assert t.call_count == 1

    def test_flow_dot_run_schedule_continues_on_executor_failure(self, repeat_schedule):
        schedule = repeat_schedule(3)

        executor = MagicMock(side_effect=Exception)

        class StatefulTask(Task):
            call_count = 0

            def run(self):
                self.call_count += 1

        t = StatefulTask()
        f = Flow(name="test", tasks=[t], schedule=schedule)
        f.run(executor=executor)
        assert t.call_count == 0
        assert schedule.call_count == 3

    def test_scheduled_runs_handle_retries(self, repeat_schedule):
        schedule = repeat_schedule(1)

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
        f = Flow(name="test", tasks=[t], schedule=schedule)
        f.run()
        assert t.call_count == 2
        assert len(state_history) == 5  # Running, Failed, Retrying, Running, Success

    def test_flow_dot_run_handles_cached_states(self, repeat_schedule):
        schedule = repeat_schedule(3)

        class StatefulTask(Task):
            def __init__(self, maxit=False, **kwargs):
                self.maxit = maxit
                super().__init__(**kwargs)

            call_count = 0

            def run(self):
                self.call_count += 1
                if self.maxit:
                    return max(self.call_count, 2)
                else:
                    return self.call_count

        @task(
            cache_for=datetime.timedelta(minutes=1),
            cache_validator=partial_inputs_only(validate_on=["x"]),
        )
        def return_x(x, y):
            return y

        storage = {"y": []}

        @task
        def store_y(y):
            storage["y"].append(y)

        t1, t2 = StatefulTask(maxit=True), StatefulTask()
        with Flow(name="test", schedule=schedule) as f:
            res = store_y(return_x(x=t1, y=t2))

        f.run()

        assert storage == dict(y=[1, 1, 3])

    def test_flow_dot_run_handles_cached_states_across_runs(self):
        class StatefulTask(Task):
            def __init__(self, maxit=False, **kwargs):
                self.maxit = maxit
                super().__init__(**kwargs)

            call_count = 0

            def run(self):
                self.call_count += 1
                if self.maxit:
                    return max(self.call_count, 2)
                else:
                    return self.call_count

        @task(
            cache_for=datetime.timedelta(minutes=1),
            cache_validator=partial_inputs_only(validate_on=["x"]),
        )
        def return_x(x, y):
            return y

        storage = {"y": []}

        @task
        def store_y(y):
            storage["y"].append(y)

        t1, t2 = StatefulTask(maxit=True), StatefulTask()
        with Flow(name="test") as f:
            res = store_y(return_x(x=t1, y=t2))

        f.run()
        f.run()
        f.run()

        assert storage == dict(y=[1, 1, 3])

    def test_flow_dot_run_without_schedule_can_run_cached_tasks(self):
        # simulate fresh environment
        if "caches" in prefect.context:
            del prefect.context["caches"]

        @task(cache_for=datetime.timedelta(minutes=1))
        def noop():
            pass

        f = Flow("test-caches", tasks=[noop])
        flow_state = f.run(run_on_schedule=False)

        assert flow_state.is_successful()
        assert flow_state.result[noop].result is None

    def test_flow_dot_run_handles_mapped_cached_states(self, repeat_schedule):
        schedule = repeat_schedule(3)

        class StatefulTask(Task):
            def __init__(self, maxit=False, **kwargs):
                self.maxit = maxit
                super().__init__(**kwargs)

            call_count = 0

            def run(self):
                self.call_count += 1
                if self.maxit:
                    return [max(self.call_count, 2)] * 3
                else:
                    return [self.call_count] * 3

        @task(
            cache_for=datetime.timedelta(minutes=1),
            cache_validator=partial_inputs_only(validate_on=["x"]),
        )
        def return_x(x, y):
            return y

        storage = {"y": []}

        @task
        def store_y(y):
            storage["y"].append(y)

        t1, t2 = StatefulTask(maxit=True), StatefulTask()
        with Flow(name="test", schedule=schedule) as f:
            res = store_y(return_x.map(x=t1, y=t2))

        f.run()

        assert storage == dict(y=[[1, 1, 1], [1, 1, 1], [3, 3, 3]])

    def test_flow_dot_run_handles_cached_states_across_runs_with_always_run_trigger(
        self, repeat_schedule
    ):
        schedule = repeat_schedule(3)

        class StatefulTask(Task):
            def __init__(self, maxit=False, **kwargs):
                self.maxit = maxit
                super().__init__(**kwargs)

            call_count = 0

            def run(self):
                # returns 1 on the first run, 2 on the second run, and 1 on the third
                self.call_count += 1
                return self.call_count if self.call_count < 3 else 1

        @task(cache_for=datetime.timedelta(minutes=10), cache_validator=all_inputs)
        def return_x(x):
            return round(random.random(), 4)

        storage = {"output": []}

        @task(trigger=prefect.triggers.always_run)
        def store_output(y):
            storage["output"].append(y)

        t = StatefulTask()
        with Flow(name="test", schedule=schedule) as f:
            res = store_output(return_x(x=t))

        f.run()

        first_run = storage["output"][0]
        second_run = storage["output"][1]
        third_run = storage["output"][2]

        ## first run: nothing interesting
        assert first_run > 0

        ## second run: all tasks succeed, no cache used
        assert first_run != second_run

        ## third run: all tasks succeed, caching from previous runs used
        assert third_run == first_run

    def test_flow_dot_run_handles_mapped_cached_states_across_runs(
        self, repeat_schedule
    ):
        schedule = repeat_schedule(3)

        class StatefulTask(Task):
            def __init__(self, maxit=False, **kwargs):
                self.maxit = maxit
                super().__init__(**kwargs)

            call_count = 0
            return_vals = {1: [1], 2: [2, 2], 3: [1, 2, 3]}

            def run(self):
                # returns [1] on the first run, [2, 2] on the second run, and [1, 2, 3] on the third
                self.call_count += 1
                return self.return_vals[self.call_count]

        @task(cache_for=datetime.timedelta(minutes=10), cache_validator=all_inputs)
        def return_x(x):
            return round(random.random(), 4)

        storage = {"output": []}

        @task(trigger=prefect.triggers.always_run)
        def store_output(y):
            storage["output"].append(y)

        t = StatefulTask()
        with Flow(name="test", schedule=schedule) as f:
            res = store_output(return_x.map(x=t))

        f.run()

        first_run = storage["output"][0]
        second_run = storage["output"][1]
        third_run = storage["output"][2]

        ## first run: nothing interesting
        assert first_run[0] > 0

        ## second run: all tasks succeed, no cache used
        assert first_run[0] not in second_run

        ## third run: all tasks succeed, caching from previous runs used
        assert third_run[0] == first_run[0]
        assert third_run[1] == second_run[0]
        assert third_run[2] not in first_run
        assert third_run[2] not in second_run

    def test_flow_dot_run_handles_mapped_cached_states_with_differing_lengths(
        self, repeat_schedule
    ):
        schedule = repeat_schedule(3)

        class StatefulTask(Task):
            def __init__(self, maxit=False, **kwargs):
                self.maxit = maxit
                super().__init__(**kwargs)

            call_count = 0

            def run(self):
                self.call_count += 1
                # returns [2] on the first run, [2, 2] on the second run, and [3, 3, 3] on the third
                return [max(self.call_count, 2)] * self.call_count

        @task(cache_for=datetime.timedelta(minutes=10), cache_validator=all_inputs)
        def return_x(x):
            return 1 / (x - 1) + round(random.random(), 4)

        storage = {"output": []}

        @task(trigger=prefect.triggers.always_run)
        def store_output(y):
            storage["output"].append(y)

        t = StatefulTask()
        with Flow(name="test", schedule=schedule) as f:
            res = store_output(return_x.map(x=t))

        f.run()

        first_run = storage["output"][0]
        second_run = storage["output"][1]
        third_run = storage["output"][2]

        ## first run: nothing interesting
        assert first_run[0] > 0

        ## second run: all tasks succeed and use cache
        assert second_run == [first_run[0], first_run[0]]

        ## third run: all tasks succeed, no caching used
        assert all(x != first_run[0] for x in third_run)

    def test_flow_dot_run_handles_mapped_cached_states_with_non_cached(
        self, repeat_schedule
    ):
        schedule = repeat_schedule(3)

        class StatefulTask(Task):
            def __init__(self, maxit=False, **kwargs):
                self.maxit = maxit
                super().__init__(**kwargs)

            call_count = 0

            def run(self):
                self.call_count += 1
                if self.maxit:
                    return [max(self.call_count, 2)] * 3
                else:
                    return [self.call_count + i for i in range(3)]

        @task(cache_for=datetime.timedelta(minutes=10), cache_validator=all_inputs)
        def return_x(x, y):
            return 1 / (y - 1) + round(random.random(), 8)

        storage = {"y": []}

        @task(trigger=prefect.triggers.always_run)
        def store_y(y):
            storage["y"].append(y)

        t1, t2 = StatefulTask(maxit=True), StatefulTask()
        with Flow(name="test", schedule=schedule) as f:
            res = store_y(return_x.map(x=t1, y=t2))

        f.run()

        first_run = storage["y"][0]
        second_run = storage["y"][1]
        third_run = storage["y"][2]

        ## first run: one child fails, the other two succeed
        assert isinstance(first_run[0], ZeroDivisionError)

        ## second run: all tasks succeed, the first two use cached state
        assert second_run[:2] == first_run[1:]
        assert second_run[-1] not in first_run

        ## third run: all tasks succeed, no caching used
        assert all(x not in first_run + second_run for x in third_run)

    def test_scheduled_runs_handle_mapped_retries(self):
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
        assert len(state_history) == 13

    def test_flow_run_accepts_state_kwarg(self):
        f = Flow(name="test")
        state = f.run(state=Finished())
        assert state.is_finished()

    def test_flow_dot_run_sets_scheduled_start_time(self):

        # start very soon
        start_time = pendulum.now().add(seconds=0.2)

        @task
        def report_start_time():
            return prefect.context.scheduled_start_time

        f = Flow(
            name="test",
            tasks=[report_start_time],
            schedule=prefect.schedules.Schedule(
                clocks=[prefect.schedules.clocks.DatesClock(dates=[start_time])]
            ),
        )
        state = f.run()
        assert state.result[report_start_time].result is start_time

    def test_flow_dot_run_does_not_set_scheduled_start_time_globally(self):
        @task
        def report_start_time():
            return prefect.context.scheduled_start_time

        f = Flow(name="test", tasks=[report_start_time])
        state = f.run()
        assert isinstance(state.result[report_start_time].result, datetime.datetime)
        assert "scheduled_start_time" not in prefect.context

    def test_flow_dot_run_persists_scheduled_start_time_across_retries(self):
        # start very soon
        start_time = pendulum.now().add(seconds=0.2)

        @task(max_retries=1, retry_delay=datetime.timedelta(0))
        def report_start_time():
            if prefect.context.task_run_count == 1:
                raise ValueError("I'm not ready to tell you the start time yet")
            return prefect.context.scheduled_start_time

        f = Flow(
            name="test",
            tasks=[report_start_time],
            schedule=prefect.schedules.Schedule(
                clocks=[prefect.schedules.clocks.DatesClock(dates=[start_time])]
            ),
        )
        state = f.run()
        assert state.result[report_start_time].result is start_time

    def test_flow_dot_run_updates_the_scheduled_start_time_of_each_scheduled_run(self):

        start_times = [pendulum.now().add(seconds=i * 0.2) for i in range(1, 4)]
        REPORTED_START_TIMES = []

        @task
        def record_start_time():
            REPORTED_START_TIMES.append(prefect.context.scheduled_start_time)

        f = Flow(
            name="test",
            tasks=[record_start_time],
            schedule=prefect.schedules.Schedule(
                clocks=[prefect.schedules.clocks.DatesClock(dates=start_times)]
            ),
        )
        f.run()
        assert REPORTED_START_TIMES == start_times

    def test_flow_dot_run_handles_keyboard_signals_gracefully(self):
        class BadExecutor(LocalExecutor):
            def submit(self, *args, **kwargs):
                raise KeyboardInterrupt

        @task
        def do_something():
            pass

        f = Flow("test", tasks=[do_something])
        state = f.run(executor=BadExecutor())
        assert isinstance(state, Cancelled)
        assert "interrupt" in state.message.lower()


class TestFlowDiagnostics:
    def test_flow_diagnostics(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tempdir:
            file = open("{}/config.toml".format(tempdir), "w+")
            toml.dump({"secrets": {"key": "value"}}, file)
            file.close()

            monkeypatch.setattr(
                "prefect.configuration.USER_CONFIG", "{}/config.toml".format(tempdir)
            )

            @prefect.task
            def t1():
                pass

            @prefect.task
            def t2():
                pass

            flow = prefect.Flow(
                "test",
                tasks=[t1, t2],
                storage=prefect.environments.storage.Local(),
                schedule=prefect.schedules.Schedule(clocks=[]),
                result_handler=prefect.engine.result_handlers.JSONResultHandler(),
            )

            monkeypatch.setenv("PREFECT__TEST", "VALUE" "NOT__PREFECT", "VALUE2")

            diagnostic_info = flow.diagnostics()
            diagnostic_info = json.loads(diagnostic_info)

            config_overrides = diagnostic_info["config_overrides"]
            env_vars = diagnostic_info["env_vars"]
            flow_information = diagnostic_info["flow_information"]
            system_info = diagnostic_info["system_information"]

            assert config_overrides == {"secrets": False}

            assert "PREFECT__TEST" in env_vars
            assert "NOT__PREFECT" not in env_vars

            assert flow_information

            # Type information
            assert flow_information["environment"]["type"] == "RemoteEnvironment"
            assert flow_information["storage"]["type"] == "Local"
            assert flow_information["result"]["type"] == "PrefectResult"
            assert flow_information["schedule"]["type"] == "Schedule"
            assert flow_information["task_count"] == 2

            # Kwargs presence check
            assert flow_information["environment"]["executor"] is True
            assert flow_information["environment"]["executor_kwargs"] is False
            assert flow_information["environment"]["labels"] is False
            assert flow_information["environment"]["on_start"] is False
            assert flow_information["environment"]["on_exit"] is False
            assert flow_information["environment"]["logger"] is True

            assert system_info["prefect_version"] == prefect.__version__
            assert system_info["platform"] == platform.platform()
            assert system_info["python_version"] == platform.python_version()


class TestFlowRegister:
    @pytest.mark.parametrize(
        "storage",
        ["prefect.environments.storage.Docker", "prefect.environments.storage.Local",],
    )
    def test_flow_register_uses_default_storage(self, monkeypatch, storage):
        monkeypatch.setattr("prefect.Client", MagicMock())
        f = Flow(name="test")

        assert f.storage is None
        with set_temporary_config({"flows.defaults.storage.default_class": storage}):
            f.register("My-project")

        assert isinstance(f.storage, from_qualified_name(storage))
        assert f.result == from_qualified_name(storage)().result

    def test_flow_register_passes_kwargs_to_storage(self, monkeypatch):
        monkeypatch.setattr("prefect.Client", MagicMock())
        f = Flow(name="test")

        assert f.storage is None
        with set_temporary_config(
            {
                "flows.defaults.storage.default_class": "prefect.environments.storage.Docker"
            }
        ):
            f.register(
                "My-project",
                registry_url="FOO",
                image_name="BAR",
                image_tag="BIG",
                no_url=True,
            )

        assert isinstance(f.storage, prefect.environments.storage.Docker)
        assert f.storage.registry_url == "FOO"
        assert f.storage.image_name == "BAR"
        assert f.storage.image_tag == "BIG"
        assert f.environment.labels == set()

    @pytest.mark.parametrize(
        "storage",
        [
            prefect.environments.storage.Local(),
            prefect.environments.storage.S3(bucket="blah"),
            prefect.environments.storage.GCS(bucket="test"),
            prefect.environments.storage.Azure(container="windows"),
        ],
    )
    def test_flow_register_auto_labels_environment_if_labeled_storage_used(
        self, monkeypatch, storage
    ):
        monkeypatch.setattr("prefect.Client", MagicMock())
        f = Flow(name="Test me!! I should get labeled", storage=storage)

        f.register("My-project", build=False)

        assert len(f.environment.labels) == 1

    @pytest.mark.parametrize(
        "storage",
        [
            prefect.environments.storage.Local(),
            prefect.environments.storage.S3(bucket="blah"),
            prefect.environments.storage.GCS(bucket="test"),
            prefect.environments.storage.Azure(container="windows"),
        ],
    )
    def test_flow_register_auto_sets_result_if_storage_has_default(
        self, monkeypatch, storage
    ):
        monkeypatch.setattr("prefect.Client", MagicMock())
        f = Flow(name="Test me!! I should get labeled", storage=storage)
        assert f.result is None

        f.register("My-project", build=False)
        assert isinstance(f.result, Result)
        assert f.result == storage.result

    def test_flow_register_doesnt_override_custom_set_result(self, monkeypatch):
        monkeypatch.setattr("prefect.Client", MagicMock())
        f = Flow(
            name="Test me!! I should get labeled",
            storage=prefect.environments.storage.S3(bucket="t"),
            result=LocalResult(),
        )
        assert isinstance(f.result, LocalResult)

        f.register("My-project", build=False)
        assert isinstance(f.result, LocalResult)

    def test_flow_register_auto_labels_environment_with_storage_labels(
        self, monkeypatch
    ):
        class MyStorage(prefect.environments.storage.Local):
            @property
            def labels(self):
                return ["a", "b", "c"]

        monkeypatch.setattr("prefect.Client", MagicMock())
        f = Flow(name="Test me!! I should get labeled", storage=MyStorage())
        f.register("My-project")

        assert f.environment.labels == {"a", "b", "c"}

    def test_flow_register_doesnt_overwrite_labels_if_local_storage_is_used(
        self, monkeypatch
    ):
        monkeypatch.setattr("prefect.Client", MagicMock())
        f = Flow(
            name="test",
            environment=prefect.environments.RemoteEnvironment(labels=["foo"]),
        )

        assert f.storage is None
        with set_temporary_config(
            {
                "flows.defaults.storage.default_class": "prefect.environments.storage.Local"
            }
        ):
            f.register("My-project")

        assert isinstance(f.storage, prefect.environments.storage.Local)
        assert "foo" in f.environment.labels
        assert len(f.environment.labels) == 2


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
    with pytest.raises(ValueError, match="`return_tasks` keyword cannot be provided"):
        f.run(return_tasks=f.tasks)


def test_flow_run_raises_if_no_more_scheduled_runs():
    schedule = prefect.schedules.Schedule(
        clocks=[
            prefect.schedules.clocks.DatesClock(
                dates=[pendulum.now("utc").add(days=-1)]
            )
        ]
    )
    f = Flow(name="test", schedule=schedule)
    with pytest.raises(ValueError, match="no more scheduled runs"):
        f.run()


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


def test_looping_works_in_a_flow():
    @task
    def looper(x):
        if prefect.context.get("task_loop_count", 1) < 20:
            raise LOOP(result=prefect.context.get("task_loop_result", 0) + x)
        return prefect.context.get("task_loop_result") + x

    @task
    def downstream(l):
        return l ** 2

    with Flow(name="looping") as f:
        inter = looper(10)
        final = downstream(inter)

    flow_state = f.run()

    assert flow_state.is_successful()
    assert flow_state.result[inter].result == 200
    assert flow_state.result[final].result == 200 ** 2


def test_pause_resume_works_with_retries():
    runs = []

    def state_handler(obj, old, new):
        if isinstance(new, Paused):
            return Resume()
        elif old.is_running():
            raise FAIL("cant pass go")

    @task(
        max_retries=2,
        retry_delay=datetime.timedelta(seconds=0),
        state_handlers=[state_handler],
        trigger=prefect.triggers.manual_only,
    )
    def fail():
        runs.append(1)

    f = Flow("huh", tasks=[fail])
    flow_state = f.run()

    assert flow_state.is_failed()
    assert len(runs) == 3


def test_looping_with_retries_works_in_a_flow():
    @task(max_retries=1, retry_delay=datetime.timedelta(seconds=0))
    def looper(x):
        if (
            prefect.context.get("task_loop_count") == 2
            and prefect.context.get("task_run_count", 1) == 1
        ):
            raise ValueError("err")

        if prefect.context.get("task_loop_count", 1) < 20:
            raise LOOP(result=prefect.context.get("task_loop_result", 0) + x)
        return prefect.context.get("task_loop_result") + x

    @task
    def downstream(l):
        return l ** 2

    with Flow(name="looping") as f:
        inter = looper(10)
        final = downstream(inter)

    flow_state = f.run()

    assert flow_state.is_successful()
    assert flow_state.result[inter].result == 200
    assert flow_state.result[final].result == 200 ** 2


def test_looping_with_retries_resets_run_count():
    run_counts = []

    @task(max_retries=1, retry_delay=datetime.timedelta(seconds=0))
    def looper(x):
        run_counts.append(prefect.context.get("task_run_count"))

        if (
            prefect.context.get("task_loop_count") == 2
            and prefect.context.get("task_run_count", 1) == 1
        ):
            raise ValueError("err")

        if prefect.context.get("task_loop_count", 1) < 20:
            raise LOOP(result=prefect.context.get("task_loop_result", 0) + x)
        return prefect.context.get("task_loop_result") + x

    with Flow(name="looping") as f:
        inter = looper(1)

    flow_state = f.run()

    assert flow_state.is_successful()
    assert flow_state.result[inter].result == 20
    assert list(filter(lambda x: x == 2, run_counts)) == [2]


def test_starting_at_arbitrary_loop_index():
    @task
    def looper(x):
        if prefect.context.get("task_loop_count", 1) < 20:
            raise LOOP(result=prefect.context.get("task_loop_result", 0) + x)
        return prefect.context.get("task_loop_result", 0) + x

    @task
    def downstream(l):
        return l ** 2

    with Flow(name="looping") as f:
        inter = looper(10)
        final = downstream(inter)

    flow_state = f.run(context={"task_loop_count": 20})

    assert flow_state.is_successful()
    assert flow_state.result[inter].result == 10
    assert flow_state.result[final].result == 100


class TestSaveLoad:
    def test_save_saves_and_load_loads(self):
        t = Task(name="foo")
        f = Flow("test", tasks=[t])

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "save"), "wb") as tmp:
                assert f.save(tmp.name) == tmp.name

            new_obj = Flow.load(tmp.name)

        assert isinstance(new_obj, Flow)
        assert len(new_obj.tasks) == 1
        assert list(new_obj.tasks)[0].name == "foo"
        assert list(new_obj.tasks)[0].slug == t.slug
        assert new_obj.name == "test"

    def test_save_saves_has_a_default(self):
        t = Task(name="foo")
        f = Flow("test", tasks=[t])

        with tempfile.TemporaryDirectory() as tmpdir:
            with set_temporary_config({"home_dir": tmpdir}):
                f.save()

            new_obj = Flow.load(os.path.join(tmpdir, "flows", "test.prefect"))

        assert isinstance(new_obj, Flow)
        assert len(new_obj.tasks) == 1
        assert list(new_obj.tasks)[0].name == "foo"
        assert list(new_obj.tasks)[0].slug == t.slug
        assert new_obj.name == "test"

    def test_load_accepts_name_and_sluggified_name(self):
        t = Task(name="foo")
        f = Flow("I aM a-test!", tasks=[t])

        with tempfile.TemporaryDirectory() as tmpdir:
            with set_temporary_config({"home_dir": tmpdir}):
                f.save()

                new_obj_from_name = Flow.load("I aM a-test!")
                new_obj_from_slug = Flow.load("i-am-a-test")

        assert isinstance(new_obj_from_name, Flow)
        assert len(new_obj_from_name.tasks) == 1
        assert list(new_obj_from_name.tasks)[0].name == "foo"
        assert list(new_obj_from_name.tasks)[0].slug == t.slug
        assert new_obj_from_name.name == "I aM a-test!"

        assert isinstance(new_obj_from_slug, Flow)
        assert len(new_obj_from_slug.tasks) == 1
        assert list(new_obj_from_slug.tasks)[0].name == "foo"
        assert list(new_obj_from_slug.tasks)[0].slug == t.slug
        assert new_obj_from_slug.name == "I aM a-test!"


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows doesn't support any timeout logic"
)
@pytest.mark.parametrize("executor", ["local", "sync", "mthread"], indirect=True)
def test_timeout_actually_stops_execution(executor):
    # Note: this is a potentially brittle test! In some cases (local and sync) signal.alarm
    # is used as the mechanism for timing out a task. This passes off the job of measuring
    # the time for the timeout to the OS, which uses the "wallclock" as reference (the real
    # amount of time passed in the real world). However, since the OS balances which processes
    # can use the CPU and for how long, it is possible when the CPU is strained for the
    # Python process running the Flow to not be given "enough" time on the CPU after the signal
    # alarm is registered with the OS. This could result in the Task.run() only percieving a small
    # amount of CPU time elapsed when in reality the full timeout period had elapsed.

    # For that reason, this test cannot validate timeout functionality by testing "how far into
    # the task implementation" we got, but instead do a simple task (create a file) and sleep.
    # This will drastically reduce the brittleness of the test (but not completely).

    with tempfile.TemporaryDirectory() as call_dir:
        # Note: a real file must be used in the case of "mthread"
        FILE = os.path.join(call_dir, "test.txt")

        @prefect.task(timeout=1)
        def slow_fn():
            with open(FILE, "w") as f:
                f.write("called!")
            time.sleep(2)
            with open(FILE, "a") as f:
                f.write("invalid")

        flow = Flow("timeouts", tasks=[slow_fn])

        assert not os.path.exists(FILE)

        start_time = time.time()
        state = flow.run(executor=executor)
        stop_time = time.time()
        time.sleep(max(0, 3 - (stop_time - start_time)))

        assert os.path.exists(FILE)
        with open(FILE, "r") as f:
            assert "invalid" not in f.read()

    assert state.is_failed()
    assert isinstance(state.result[slow_fn], TimedOut)
    assert isinstance(state.result[slow_fn].result, TimeoutError)


@pytest.mark.skip("Result handlers not yet deprecated")
def test_result_handler_option_shows_deprecation():
    with pytest.warns(
        UserWarning, match="the result_handler Flow option will be deprecated*"
    ):
        Flow("dummy", result_handler=object())


def test_results_write_to_formatted_locations(tmpdir):
    with Flow("results", result=LocalResult(dir=tmpdir)) as flow:

        @task(target="{config.backend}/{map_index}.txt")
        def return_x(x):
            return x

        vals = return_x.map(x=[1, 42, None, "string-type"])

    with set_temporary_config({"flows.checkpointing": True, "backend": "foobar-test"}):
        flow_state = flow.run()

    assert flow_state.is_successful()
    assert os.listdir(tmpdir) == ["foobar-test"]
    assert set(os.listdir(os.path.join(tmpdir, "foobar-test"))) == {
        "0.txt",
        "1.txt",
        "3.txt",
    }
