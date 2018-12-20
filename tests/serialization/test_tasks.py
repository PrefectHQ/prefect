import datetime

import pytest

import marshmallow
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
        "id",
        "name",
        "slug",
        "max_retries",
        "retry_delay",
        "timeout",
        "trigger",
        "skip_on_upstream_skip",
        "cache_for",
    ]:
        assert getattr(task, key) == getattr(deserialized, key)


def test_deserialize_id():
    t = Task()
    t2 = TaskSchema().load(TaskSchema().dump(t))

    assert t.id and t.id == t2.id


def test_deserialize_task_subclass_is_task_but_not_task_subclass():
    class NewTask(Task):
        pass

    serialized = TaskSchema().dump(NewTask())
    assert serialized["type"].endswith("<locals>.NewTask")

    deserialized = TaskSchema().load(serialized)
    assert isinstance(deserialized, Task)
    assert not isinstance(deserialized, NewTask)


def test_deserialize_task_with_id():
    """
    When tasks are deserialized, they put their ID in a special task_id_cache in context
    so it can be reused elsewhere.
    """
    t = Task()
    # empty contexts are replaced
    context = {1: 1}
    serialized = TaskSchema(context=context).dump(t)
    deserialized = TaskSchema(context=context).load(serialized)
    assert "task_id_cache" in context
    assert context["task_id_cache"][t.id] is deserialized


def test_deserializing_tasks_with_ids_reuses_task_cache_to_recreate_object():
    """
    If an id is found in the task cache, the corresponding object is loaded
    """
    t = Task()
    context = dict(task_id_cache={t.id: t})
    serialized = TaskSchema(context=context).dump(t)
    deserialized = TaskSchema(context=context).load(serialized)
    assert deserialized is t


def test_serialize_parameter():
    p = Parameter(name="p")
    ps = ParameterSchema().dump(p)
    assert ps["default"] == None
    assert ps["required"] is True


def test_deserialize_parameter():
    p = Parameter(name="p")
    p2 = ParameterSchema().load(ParameterSchema().dump(p))
    assert isinstance(p2, Parameter)


def test_deserialize_parameter_requires_name():
    with pytest.raises(marshmallow.ValidationError):
        ParameterSchema().load({})


@pytest.mark.parametrize(
    "trigger",
    [
        prefect.triggers.all_finished,
        prefect.triggers.manual_only,
        prefect.triggers.always_run,
        prefect.triggers.all_successful,
        prefect.triggers.all_failed,
        prefect.triggers.any_successful,
        prefect.triggers.any_failed,
    ],
)
def test_trigger(trigger):
    t = Task(trigger=trigger)
    t2 = TaskSchema().load(TaskSchema().dump(t))
    assert t2.trigger is trigger


def test_unknown_trigger():
    def hello():
        pass

    t = Task(trigger=hello)
    t2 = TaskSchema().load(TaskSchema().dump(t))
    assert isinstance(t2.trigger, str)
    assert t2.trigger.endswith("hello")


@pytest.mark.parametrize(
    "cache_validator",
    [
        prefect.engine.cache_validators.never_use,
        prefect.engine.cache_validators.duration_only,
        prefect.engine.cache_validators.all_inputs,
        prefect.engine.cache_validators.all_parameters,
        prefect.engine.cache_validators.partial_inputs_only,
        prefect.engine.cache_validators.partial_parameters_only,
    ],
)
def test_cache_validator(cache_validator):
    t = Task(cache_validator=cache_validator)
    t2 = TaskSchema().load(TaskSchema().dump(t))
    assert t2.cache_validator is cache_validator


def test_unknown_cache_validator():
    def hello():
        pass

    t = Task(cache_validator=hello)
    t2 = TaskSchema().load(TaskSchema().dump(t))
    assert isinstance(t2.cache_validator, str)
    assert t2.cache_validator.endswith("hello")
