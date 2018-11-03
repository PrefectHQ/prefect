import datetime
import json

import pytest

import prefect
from prefect.core import Edge, Flow, Parameter, Task
from prefect.serialization.task import TaskSchema, ParameterSchema


def test_serialize_empty_dict():
    assert TaskSchema().dump({})


def test_deserialize_empty_dict():
    t = TaskSchema().load({})
    assert isinstance(t, Task)


def test_serialize_task():
    assert isinstance(TaskSchema().dump(Task()), dict)


def test_deserialize_task():
    task = Task(
        name="hi",
        slug="hi-1",
        description="hello",
        max_retries=5,
        retry_delay=datetime.timedelta(seconds=5),
        timeout=datetime.timedelta(minutes=1),
        trigger=prefect.triggers.all_failed,
        skip_on_upstream_skip=False,
        cache_for=datetime.timedelta(hours=1),
    )
    deserialized = TaskSchema().load(TaskSchema().dump(task))
    assert isinstance(deserialized, Task)
    for key in [
        "name",
        "slug",
        "description",
        "max_retries",
        "retry_delay",
        "timeout",
        "trigger",
        "skip_on_upstream_skip",
        "cache_for",
    ]:
        assert getattr(task, key) == getattr(deserialized, key)


def test_deserialize_task_subclass_is_task_but_not_task_subclass():
    class NewTask(Task):
        pass

    serialized = TaskSchema().dump(NewTask())
    assert serialized["type"].endswith("<locals>.NewTask")

    deserialized = TaskSchema().load(serialized)
    assert isinstance(deserialized, Task)
    assert not isinstance(deserialized, NewTask)


def test_serialize_task_with_id():
    t = Task()
    context = dict(task_ids={t: "xyz"})
    serialized = TaskSchema(context=context).dump(t)
    assert serialized["id"] == "xyz"


def test_deserialize_task_with_id():
    """
    When tasks are deserialized, they put their ID in a special task_cache in context
    so it can be reused elsewhere.
    """
    t = Task()
    context = dict(task_ids={t: "xyz"})
    serialized = TaskSchema(context=context).dump(t)
    deserialized = TaskSchema(context=context).load(serialized)
    assert "task_cache" in context
    assert context["task_cache"]["xyz"] is deserialized


def test_deserializing_tasks_with_ids_reuses_task_cache_to_recreate_object():
    """
    If an id is found in the task cache, the corresponding object is loaded
    """
    t = Task()
    context = dict(task_ids={t: "xyz"}, task_cache={"xyz": t})
    serialized = TaskSchema(context=context).dump(t)
    deserialized = TaskSchema(context=context).load(serialized)
    assert deserialized is t


def test_serialize_parameter():
    p = Parameter(name="p")
    ps = ParameterSchema().dump(p)
    assert ps["default"] == "null"
    assert ps["required"] is True


def test_deserialize_parameter():
    p = Parameter(name="p")
    p2 = ParameterSchema().load(ParameterSchema().dump(p))
    assert isinstance(p2, Parameter)
