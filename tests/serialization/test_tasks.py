import datetime
from typing import Any

import marshmallow
import pytest

import prefect
from prefect.core import Edge, Flow, Parameter, Task
from prefect.serialization.task import ParameterSchema, TaskSchema
from prefect.utilities.serialization import to_qualified_name


def test_serialize_empty_dict():
    assert TaskSchema().dump({})


def test_deserialize_empty_dict():
    t = TaskSchema().load({})
    assert isinstance(t, Task)
    assert t.auto_generated is False
    assert t.cache_key is None


def test_serialize_task():
    assert isinstance(TaskSchema().dump(Task()), dict)


def test_deserialize_task():
    task = Task(
        name="hi",
        slug="hi-1",
        max_retries=5,
        retry_delay=datetime.timedelta(seconds=5),
        timeout=60,
        trigger=prefect.triggers.all_failed,
        skip_on_upstream_skip=False,
        cache_for=datetime.timedelta(hours=1),
        cache_key="test",
    )
    deserialized = TaskSchema().load(TaskSchema().dump(task))
    assert isinstance(deserialized, Task)
    for key in [
        "name",
        "slug",
        "max_retries",
        "retry_delay",
        "timeout",
        "trigger",
        "skip_on_upstream_skip",
        "cache_for",
        "cache_key",
    ]:
        assert getattr(task, key) == getattr(deserialized, key)
    assert task.auto_generated is False


def test_deserialize_auto_generated_task():
    task = Task(name="hi")
    task.auto_generated = True
    deserialized = TaskSchema().load(TaskSchema().dump(task))
    assert task.auto_generated is True


def test_deserialize_task_subclass_is_task_but_not_task_subclass():
    class NewTask(Task):
        pass

    serialized = TaskSchema().dump(NewTask())
    assert serialized["type"].endswith("<locals>.NewTask")

    deserialized = TaskSchema().load(serialized)
    assert isinstance(deserialized, Task)
    assert not isinstance(deserialized, NewTask)


def test_deserialize_task_with_cache():
    """
    When tasks are deserialized, they put their slugs in a special task_cache in context
    so it can be reused elsewhere.
    """
    t = Task()
    # empty contexts are replaced
    context = {1: 1}
    serialized = TaskSchema(context=context).dump(t)
    deserialized = TaskSchema(context=context).load(serialized)
    assert "task_cache" in context
    assert context["task_cache"][t.slug] is deserialized


def test_deserializing_tasks_reuses_task_cache_to_recreate_object():
    """
    If an slug is found in the task cache, the corresponding object is loaded
    """
    t = Task()
    context = dict(task_cache={t.slug: t})
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


@pytest.mark.parametrize(
    "trigger", [prefect.triggers.some_failed, prefect.triggers.some_successful]
)
@pytest.mark.parametrize(
    "bounds", [(1, 5), (0.1, 0.9), (1, None), (0.1, None), (None, 42), (None, 0.5)]
)
def test_stateful_trigger(trigger, bounds):

    kwargs = dict(zip(("at_least", "at_most"), bounds))
    t = Task(trigger=trigger(**kwargs))
    serialized = TaskSchema().dump(t)

    assert serialized["trigger"]["fn"] == to_qualified_name(trigger)
    assert set(serialized["trigger"]["kwargs"].values()) == set(bounds)

    t2 = TaskSchema().load(serialized)
    assert t2.trigger is not trigger
    assert to_qualified_name(type(t2.trigger)) == to_qualified_name(trigger)


def test_unknown_trigger():
    def hello():
        pass

    t = Task(trigger=hello)
    t2 = TaskSchema().load(TaskSchema().dump(t))
    assert t2.trigger is prefect.triggers.all_successful  # falls back to default


@pytest.mark.parametrize(
    "cache_validator",
    [
        prefect.engine.cache_validators.duration_only,
        prefect.engine.cache_validators.all_inputs,
        prefect.engine.cache_validators.all_parameters,
    ],
)
def test_cache_validator(cache_validator):
    with pytest.warns(UserWarning):
        t = Task(cache_validator=cache_validator)
    with pytest.warns(UserWarning):
        t2 = TaskSchema().load(TaskSchema().dump(t))
    assert t2.cache_validator is cache_validator


def test_cache_validator_never_use():
    t = Task(cache_validator=prefect.engine.cache_validators.never_use)
    t2 = TaskSchema().load(TaskSchema().dump(t))
    assert t2.cache_validator is prefect.engine.cache_validators.never_use


@pytest.mark.parametrize(
    "validator",
    [
        prefect.engine.cache_validators.partial_inputs_only,
        prefect.engine.cache_validators.partial_parameters_only,
    ],
)
@pytest.mark.parametrize("validate_on", [["x"], ["longer"], ["x", "y"]])
def test_stateful_validators(validator, validate_on):
    with pytest.warns(UserWarning):
        t = Task(cache_validator=validator(validate_on))
    serialized = TaskSchema().dump(t)

    assert serialized["cache_validator"]["fn"] == to_qualified_name(validator)
    assert set(serialized["cache_validator"]["kwargs"]["validate_on"]) == set(
        validate_on
    )

    with pytest.warns(UserWarning):
        t2 = TaskSchema().load(serialized)
    assert t2.cache_validator is not validator
    assert to_qualified_name(type(t2.cache_validator)) == to_qualified_name(validator)


def test_unknown_cache_validator():
    def hello():
        pass

    with pytest.warns(UserWarning):
        t = Task(cache_validator=hello)
    t2 = TaskSchema().load(TaskSchema().dump(t))

    # falls back to default
    assert t2.cache_validator is prefect.engine.cache_validators.never_use


def test_inputs_outputs():
    class TestTask(Task):
        def run(self, x, y: int = 1) -> int:
            pass

    serialized = TaskSchema().dump(TestTask())

    assert serialized["inputs"] == dict(
        x=dict(type=str(Any), required=True), y=dict(type=str(int), required=False)
    )

    assert serialized["outputs"] == str(int)

    assert isinstance(TaskSchema().load(serialized), Task)
