import pytest

import prefect
from prefect.core import Edge, Flow, Parameter, Task
from prefect.serialization.edge import EdgeSchema


def test_serialize_empty_dict():
    assert EdgeSchema().dump({})


def test_deserialize_empty_dict_fails():
    with pytest.raises(TypeError, match="required positional arguments"):
        EdgeSchema().load({})


def test_deserialize_empty_dict_without_create_object():
    t = EdgeSchema().load({}, create_object=False)


def test_serialize_edge():
    assert isinstance(EdgeSchema().dump(Edge(Task(), Task())), dict)


def test_serialize_edge_only_records_task_slug():
    t1, t2 = Task("t1"), Task("t2")
    serialized = EdgeSchema().dump(Edge(t1, t2, key="x", mapped=True))
    assert serialized["upstream_task"] == {
        "slug": t1.slug,
        "__version__": prefect.__version__,
    }
    assert serialized["downstream_task"] == {
        "slug": t2.slug,
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
    Edges only serialize task slugs, so the task names will revert to default.
    """
    t1, t2 = Task("t1"), Task("t2")
    serialized = EdgeSchema().dump(Edge(t1, t2, key="x", mapped=True))
    deserialized = EdgeSchema().load(serialized)

    assert deserialized.upstream_task.name == "Task"
    assert deserialized.downstream_task.name == "Task"


def test_deserialize_edge_uses_task_cache():
    """
    If a Task Cache is available, the task attributes will use it
    """
    t1, t2 = Task("t1"), Task("t2")
    context = dict(task_cache={t1.slug: t1, t2.slug: t2})
    serialized = EdgeSchema().dump(Edge(t1, t2, key="x", mapped=True))
    deserialized = EdgeSchema(context=context).load(serialized)

    assert deserialized.upstream_task is t1
    assert deserialized.downstream_task is t2
