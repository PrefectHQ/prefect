import datetime
import json

import pytest

import prefect
from prefect.core import Edge, Flow, Parameter, Task
from prefect.serialization.flow import FlowSchema
from prefect.serialization.task import ParameterSchema


def test_serialize_empty_dict():
    assert FlowSchema().dump({})


def test_deserialize_empty_dict():
    assert isinstance(FlowSchema().load({}), Flow)


def test_serialize_flow():
    serialized = FlowSchema().dump(Flow(name="n", project="p", description="d"))
    assert serialized["name"] == "n"
    assert serialized["project"] == "p"
    assert serialized["description"] == "d"


def test_deserialize_flow():
    serialized = FlowSchema().dump(Flow(name="n", project="p", description="d"))
    deserialized = FlowSchema().load(serialized)
    assert isinstance(deserialized, Flow)
    assert deserialized.name == "n"
    assert deserialized.project == "p"
    assert deserialized.description == "d"


def test_deserialize_flow_subclass_is_flow_but_not_flow_subclass():
    class NewFlow(Flow):
        pass

    serialized = FlowSchema().dump(NewFlow())
    assert serialized["type"].endswith("<locals>.NewFlow")

    deserialized = FlowSchema().load(serialized)
    assert isinstance(deserialized, Flow)
    assert not isinstance(deserialized, NewFlow)


def test_deserialize_schedule():
    schedule = prefect.schedules.CronSchedule("* * 0 0 0")
    f = Flow(schedule=schedule)
    serialized = FlowSchema().dump(f)
    deserialized = FlowSchema().load(serialized)
    assert deserialized.schedule.next(5) == f.schedule.next(5)


def test_deserialize_id():
    f = Flow()
    serialized = FlowSchema().dump(f)
    deserialized = FlowSchema().load(serialized)
    assert deserialized.id == f.id


def test_deserialize_tasks():
    tasks = [Task(n) for n in ["a", "b", "c"]]
    f = Flow(tasks=tasks)
    serialized = FlowSchema().dump(f)
    deserialized = FlowSchema().load(serialized)
    assert len(deserialized.tasks) == len(f.tasks)


def test_deserialize_edges():
    """
    Tests that edges are appropriately deserialized, even in they involve keys.
    Also tests that tasks are deserialized in a way that reuses them in edges -- in other
    words, when edges are loaded they use their corresponding task IDs to access the
    correct Task objects out of a cache.
    """

    class ArgTask(Task):
        def run(self, x):
            return x

    f = Flow()
    t1, t2, t3 = Task("a"), Task("b"), ArgTask("c")

    f.add_edge(t1, t2)
    f.add_edge(t2, t3, key="x")
    f.add_edge(t1, t3, mapped=True)

    serialized = FlowSchema().dump(f)
    deserialized = FlowSchema().load(serialized)

    d1, d2, d3 = sorted(deserialized.tasks, key=lambda t: t.name)
    assert deserialized.edges == {
        Edge(d1, d2),
        Edge(d2, d3, key="x"),
        Edge(d1, d3, mapped=True),
    }


def test_parameters():
    f = Flow()
    x = Parameter("x")
    y = Parameter("y", default=5)
    f.add_task(x)
    f.add_task(y)

    serialized = FlowSchema().dump(f)
    assert "parameters" in serialized
    assert [
        isinstance(ParameterSchema().load(p), Parameter)
        for p in serialized["parameters"]
    ]


def test_deserialize_with_parameters_key():
    f = Flow()
    x = Parameter("x")
    f.add_task(x)

    f2 = FlowSchema().load(FlowSchema().dump(f))
    assert f2.parameters() == f.parameters()


def test_reference_tasks():
    x = Task("x")
    y = Task("y")
    z = Task("z")
    f = Flow(tasks=[x, y, z])

    f.set_reference_tasks([y])
    assert f.reference_tasks() == {y}
    f2 = FlowSchema().load(FlowSchema().dump(f))
    assert f2.reference_tasks() == {t for t in f2.tasks if t.name == "y"}
