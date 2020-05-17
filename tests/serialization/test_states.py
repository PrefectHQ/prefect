import base64
import datetime
import json

import cloudpickle
import marshmallow
import pendulum
import pytest

import prefect
from prefect.engine import results, state
from prefect.engine.result import NoResult, Result, SafeResult
from prefect.engine.result_handlers import JSONResultHandler, ResultHandler
from prefect.serialization.state import StateSchema

all_states = sorted(
    set(
        cls
        for cls in state.__dict__.values()
        if isinstance(cls, type)
        and issubclass(cls, state.State)
        and cls not in (state.State, state._MetaState)
    ),
    key=lambda c: c.__name__,
)


def complex_states():
    res1 = SafeResult(1, result_handler=JSONResultHandler())
    res2 = SafeResult({"z": 2}, result_handler=JSONResultHandler())
    res3 = SafeResult(dict(x=1, y={"z": 2}), result_handler=JSONResultHandler())
    naive_dt = datetime.datetime(2020, 1, 1)
    utc_dt = pendulum.datetime(2020, 1, 1)
    complex_result = {"x": res1, "y": res2}
    cached_state = state.Cached(
        cached_inputs=complex_result,
        result=res3,
        cached_parameters={"x": 1, "y": {"z": 2}},
        cached_result_expiration=utc_dt,
    )
    cached_state_naive = state.Cached(
        cached_inputs=complex_result,
        result=res3,
        cached_parameters={"x": 1, "y": {"z": 2}},
        cached_result_expiration=naive_dt,
    )
    running_tags = state.Running()
    running_tags.context = dict(tags=["1", "2", "3"])
    test_states = [
        state.Looped(loop_count=45),
        state.Pending(cached_inputs=complex_result),
        state.Paused(cached_inputs=complex_result),
        state.Retrying(start_time=utc_dt, run_count=3),
        state.Retrying(start_time=naive_dt, run_count=3),
        state.Scheduled(start_time=utc_dt),
        state.Scheduled(start_time=naive_dt),
        state.Resume(start_time=utc_dt),
        state.Resume(start_time=naive_dt),
        running_tags,
        state.Submitted(state=state.Retrying(start_time=utc_dt, run_count=2)),
        state.Submitted(state=state.Resume(start_time=utc_dt)),
        state.Queued(state=state.Pending()),
        state.Queued(state=state.Pending(), start_time=utc_dt),
        state.Queued(state=state.Retrying(start_time=utc_dt, run_count=2)),
        cached_state,
        cached_state_naive,
        state.TimedOut(cached_inputs=complex_result),
    ]
    return test_states


def test_all_states_have_serialization_schemas_in_stateschema():
    """
    Tests that all State subclasses in prefect.engine.states have corresponding schemas
    in prefect.serialization.state
    """
    assert set(s.__name__ for s in all_states) == set(StateSchema.type_schemas.keys())


def test_all_states_have_deserialization_schemas_in_stateschema():
    """
    Tests that all State subclasses in prefect.engine.states have corresponding schemas
    in prefect.serialization.state with that state assigned as the object class
    so it will be recreated at deserialization
    """
    assert set(all_states) == set(
        s.Meta.object_class for s in StateSchema.type_schemas.values()
    )


@pytest.mark.parametrize("cls", [s for s in all_states if s is not state.Mapped])
def test_serialize_state_with_un_handled_result(cls):
    serialized = StateSchema().dump(cls(message="message", result=1))
    assert isinstance(serialized, dict)
    assert serialized["type"] == cls.__name__
    assert serialized["message"] == "message"
    assert serialized["_result"]["type"] == "NoResultType"
    assert serialized["__version__"] == prefect.__version__


@pytest.mark.parametrize("cls", [s for s in all_states if s is not state.Mapped])
def test_serialize_state_with_no_result(cls):
    state = cls(message="message")
    serialized = StateSchema().dump(state)
    assert isinstance(serialized, dict)
    assert serialized["type"] == cls.__name__
    assert serialized["message"] == "message"
    assert serialized["_result"]["type"] == "NoResultType"
    assert serialized["__version__"] == prefect.__version__


@pytest.mark.parametrize("cls", [s for s in all_states if s is not state.Mapped])
def test_serialize_state_with_handled_result(cls):
    res = Result(value=1, result_handler=JSONResultHandler())
    res.store_safe_value()
    state = cls(message="message", result=res)
    serialized = StateSchema().dump(state)
    assert isinstance(serialized, dict)
    assert serialized["type"] == cls.__name__
    assert serialized["message"] == "message"
    assert serialized["_result"]["type"] == "SafeResult"
    assert serialized["_result"]["value"] == "1"
    assert serialized["__version__"] == prefect.__version__


@pytest.mark.parametrize("cls", [s for s in all_states if s is not state.Mapped])
def test_serialize_state_with_safe_result(cls):
    res = SafeResult(value="1", result_handler=JSONResultHandler())
    state = cls(message="message", result=res)
    serialized = StateSchema().dump(state)
    assert isinstance(serialized, dict)
    assert serialized["type"] == cls.__name__
    assert serialized["message"] == "message"
    assert serialized["_result"]["type"] == "SafeResult"
    assert serialized["_result"]["value"] == "1"
    assert serialized["__version__"] == prefect.__version__


@pytest.mark.parametrize("cls", all_states)
def test_serialize_state_with_context(cls):
    with prefect.context(task_tags=set(["foo", "bar"])):
        s = cls(message="hi")
    serialized = StateSchema().dump(s)
    assert isinstance(serialized, dict)
    assert serialized["type"] == cls.__name__
    assert serialized["message"] == "hi"
    assert serialized["__version__"] == prefect.__version__
    assert isinstance(serialized["context"], dict)
    assert set(serialized["context"]["tags"]) == set(["foo", "bar"])

    deserialized = StateSchema().load(serialized)
    assert isinstance(deserialized, cls)
    assert set(deserialized.context["tags"]) == set(["foo", "bar"])


def test_serialize_scheduled_state_with_context():
    with prefect.context(task_run_count=42):
        s = state.Scheduled(message="hi")

    serialized = StateSchema().dump(s)
    assert isinstance(serialized, dict)
    assert serialized["type"] == "Scheduled"
    assert serialized["message"] == "hi"
    assert serialized["__version__"] == prefect.__version__
    assert serialized["context"] == dict(task_run_count=42)

    deserialized = StateSchema().load(serialized)
    assert deserialized.is_scheduled()
    assert deserialized.context == dict(task_run_count=42)


def test_serialize_state_with_context_allows_for_diverse_values():
    s = state.Running(message="hi")
    s.context = dict(tags=["foo", "bar"], info=dict(x=42), baz="99")
    serialized = StateSchema().dump(s)
    assert isinstance(serialized, dict)
    assert serialized["type"] == "Running"
    assert serialized["message"] == "hi"
    assert serialized["__version__"] == prefect.__version__
    assert serialized["context"] == s.context

    deserialized = StateSchema().load(serialized)
    assert deserialized.is_running()
    assert deserialized.context == s.context


def test_serialize_mapped():
    s = state.Success(message="1", result=1)
    f = state.Failed(message="2", result=2)
    serialized = StateSchema().dump(state.Mapped(message="message", map_states=[s, f]))
    assert isinstance(serialized, dict)
    assert serialized["type"] == "Mapped"
    assert serialized["message"] == "message"
    assert "_result" not in serialized
    assert "map_states" not in serialized
    assert serialized["n_map_states"] == 2
    assert serialized["__version__"] == prefect.__version__


@pytest.mark.parametrize("cls", [s for s in all_states if s is not state.Mapped])
def test_deserialize_state(cls):
    s = cls(message="message")
    serialized = StateSchema().dump(s)
    deserialized = StateSchema().load(serialized)
    assert isinstance(deserialized, cls)
    assert deserialized == s


@pytest.mark.parametrize("cls", [s for s in all_states if s is not state.Mapped])
def test_deserialize_state_with_safe_result(cls):
    s = cls(message="message")
    serialized = StateSchema().dump(s)
    deserialized = StateSchema().load(serialized)
    assert isinstance(deserialized, cls)
    assert deserialized == s


def test_deserialize_mapped():
    s = state.Success(message="1", result=1)
    f = state.Failed(message="2", result=2)
    serialized = StateSchema().dump(state.Mapped(message="message", map_states=[s, f]))
    deserialized = StateSchema().load(serialized)
    assert isinstance(deserialized, state.Mapped)
    assert len(deserialized.map_states) == 2
    assert deserialized.map_states == [None, None]
    assert deserialized._result == NoResult


@pytest.mark.parametrize("cls", all_states)
def test_deserialize_state_from_only_type(cls):
    serialized = dict(type=cls.__name__)
    new_state = StateSchema().load(serialized)
    assert isinstance(new_state, cls)
    assert new_state.message is None
    assert new_state._result == NoResult


def test_deserialize_state_without_type_fails():
    with pytest.raises(marshmallow.exceptions.ValidationError):
        StateSchema().load({})


def test_deserialize_state_with_unknown_type_fails():
    with pytest.raises(marshmallow.exceptions.ValidationError):
        StateSchema().load({"type": "FakeState"})


@pytest.mark.parametrize("state", complex_states())
def test_complex_state_attributes_are_handled(state):
    serialized = StateSchema().dump(state)
    deserialized = StateSchema().load(serialized)
    assert state == deserialized


def test_result_must_be_valid_json():
    res = SafeResult({"x": {"y": {"z": 1}}}, result_handler=JSONResultHandler())
    s = state.Success(result=res)
    serialized = StateSchema().dump(s)
    assert serialized["_result"]["value"] == s.result


def test_result_raises_error_on_dump_if_not_valid_json():
    res = SafeResult({"x": {"y": {"z": lambda: 1}}}, result_handler=JSONResultHandler())
    s = state.Success(result=res)
    with pytest.raises(marshmallow.exceptions.ValidationError):
        StateSchema().dump(s)


def test_deserialize_json_with_context():
    deserialized = StateSchema().load(
        {"type": "Running", "context": {"boo": ["a", "b", "c"]}}
    )
    assert type(deserialized) is state.Running
    assert deserialized.is_running()
    assert deserialized.message is None
    assert deserialized.context == dict(boo=["a", "b", "c"])
    assert deserialized._result == NoResult


def test_deserialize_json_without_version():
    deserialized = StateSchema().load({"type": "Running", "message": "test"})
    assert type(deserialized) is state.Running
    assert deserialized.is_running()
    assert deserialized.message == "test"
    assert deserialized.context == dict()
    assert deserialized._result == NoResult


def test_deserialize_handles_unknown_fields():
    """ensure that deserialization can happen even if a newer version of prefect created unknown fields"""
    deserialized = StateSchema().load(
        {
            "type": "Success",
            "success_message_that_definitely_wont_exist_on_a_real_state!": 1,
        }
    )

    assert deserialized.is_successful()


class TestNewStyleResults:
    def test_new_result_with_no_location_serializes_as_no_result(self):
        s = state.Success(message="test", result=results.S3Result(bucket="foo"))
        serialized = StateSchema().dump(s)
        assert serialized["message"] == "test"
        assert serialized["_result"]["type"] == "NoResultType"

    def test_new_result_with_location_serializes_correctly(self):
        s = state.Success(
            message="test",
            result=results.S3Result(bucket="foo", location="dir/place.txt"),
        )
        serialized = StateSchema().dump(s)
        assert serialized["message"] == "test"
        assert serialized["_result"]["type"] == "S3Result"

    def test_new_result_with_location_deserializes_correctly(self):
        s = state.Success(
            message="test",
            result=results.S3Result(bucket="foo", location="dir/place.txt"),
        )
        schema = StateSchema()
        new_state = schema.load(schema.dump(s))

        assert new_state.is_successful()
        assert new_state.result is None
        assert new_state._result.bucket == "foo"
        assert isinstance(new_state._result, results.S3Result)
        assert new_state._result.location == "dir/place.txt"

    def test_cached_inputs_are_serialized_correctly(self):
        s = state.Cached(
            message="test",
            result=results.PrefectResult(value=1, location="1"),
            cached_inputs=dict(
                x=results.PrefectResult(location='"foo"'),
                y=results.PrefectResult(location='"bar"'),
            ),
        )
        schema = StateSchema()
        serialized = schema.dump(s)

        assert serialized["cached_inputs"]["x"]["location"] == '"foo"'
        assert serialized["cached_inputs"]["y"]["location"] == '"bar"'

        new_state = schema.load(serialized)

        assert new_state.cached_inputs["x"].location == '"foo"'
        assert new_state.cached_inputs["y"].location == '"bar"'
