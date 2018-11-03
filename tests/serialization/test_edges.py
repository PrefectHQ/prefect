import datetime
import json

import pytest

import prefect
from prefect.core import Edge, Flow, Parameter, Task
from prefect.serialization.schemas.edge import EdgeSchema


def test_serialize_empty_dict():
    assert EdgeSchema().dump({})


def test_deserialize_empty_dict_fails():
    with pytest.raises(TypeError) as exc:
        EdgeSchema().load({})
    assert "required positional arguments" in str(exc).lower()


def test_deserialize_empty_dict_without_create_object():
    t = EdgeSchema().load({}, create_object=False)


def test_serialize_edge():
    assert isinstance(EdgeSchema().dump(Edge(Task(), Task())), dict)


def test_serialize_edge_only_records_task_id():
    t1, t2 = Task("t1"), Task("t2")
    serialized = EdgeSchema().dump(Edge(t1, t2, key="x", mapped=True))
    assert serialized["upstream_task"] == {
        "id": None,
        "__version__": prefect.__version__,
    }
    assert serialized["downstream_task"] == {
        "id": None,
        "__version__": prefect.__version__,
    }


def test_deserialize_edge():
    t1, t2 = Task("t1"), Task("t2")
    serialized = EdgeSchema().dump(Edge(t1, t2, key="x", mapped=True))
    deserialized = EdgeSchema().load(serialized)
    assert isinstance(deserialized, Edge)
    assert deserialized.key == "x"
    assert deserialized.mapped is True


def test_deserialize_edge_has_no_task_info():
    """
    Edges only serialize task IDs (if available), so the task names will revert to default.
    """
    t1, t2 = Task("t1"), Task("t2")
    serialized = EdgeSchema().dump(Edge(t1, t2, key="x", mapped=True))
    deserialized = EdgeSchema().load(serialized)

    assert deserialized.upstream_task.name is "Task"
    assert deserialized.downstream_task.name is "Task"


def test_deserialize_edge_uses_task_ids():
    """
    If a Task ID context is available, the task attributes will use it
    """
    t1, t2 = Task("t1"), Task("t2")
    context = dict(task_ids={t1: "t1", t2: "t2"})

    serialized = EdgeSchema(context=context).dump(Edge(t1, t2, key="x", mapped=True))
    assert serialized["upstream_task"]["id"] == "t1"
    assert serialized["downstream_task"]["id"] == "t2"


def test_deserialize_edge_uses_task_cache():
    """
    If a Task Cache is available, the task attributes will use it
    """
    t1, t2 = Task("t1"), Task("t2")
    context = dict(task_ids={t1: "t1", t2: "t2"}, task_cache={"t1": t1, "t2": t2})
    serialized = EdgeSchema(context=context).dump(Edge(t1, t2, key="x", mapped=True))
    deserialized = EdgeSchema(context=context).load(serialized)

    assert deserialized.upstream_task is t1
    assert deserialized.downstream_task is t2
