import datetime
import json
import marshmallow
import pendulum
import pytest

import prefect
from prefect.engine import results, state
from prefect.engine.result import Result, NoResult
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

from marshmallow import Schema


def complex_states():
    res1 = results.PrefectResult(value=1)
    res2 = results.PrefectResult(value={"z": 2})
    res3 = results.PrefectResult(location=json.dumps(dict(x=1, y={"z": 2})))
    naive_dt = datetime.datetime(2020, 1, 1)
    utc_dt = pendulum.datetime(2020, 1, 1)
    cached_state = state.Cached(
        hashed_inputs=dict(x="foo", y="bar"),
        result=res3,
        cached_result_expiration=utc_dt,
    )
    cached_state_naive = state.Cached(
        hashed_inputs=dict(x="foo", y="bar"),
        result=res3,
        cached_result_expiration=naive_dt,
    )
    running_tags = state.Running()
    running_tags.context = dict(tags=["1", "2", "3"])
    test_states = [
        state.Looped(loop_count=45),
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
    res = Result(value=1, location="src/place")
    state = cls(message="message", result=res)
    serialized = StateSchema().dump(state)
    assert isinstance(serialized, dict)
    assert serialized["type"] == cls.__name__
    assert serialized["message"] == "message"
    assert serialized["_result"]["type"] == "Result"
    assert serialized["_result"]["location"] == "src/place"
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


def test_serialize_mapped_uses_set_n_map_states():
    serialized = StateSchema().dump(state.Mapped(message="message", n_map_states=20))
    assert isinstance(serialized, dict)
    assert serialized["type"] == "Mapped"
    assert serialized["message"] == "message"
    assert "_result" not in serialized
    assert "map_states" not in serialized
    assert serialized["n_map_states"] == 20
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
    assert deserialized.result is None


@pytest.mark.parametrize("cls", all_states)
def test_deserialize_state_from_only_type(cls):
    serialized = dict(type=cls.__name__)
    new_state = StateSchema().load(serialized)
    assert isinstance(new_state, cls)
    assert new_state.message is None
    assert new_state._result == NoResult
    assert new_state.result is None


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


def test_deserialize_json_with_context():
    deserialized = StateSchema().load(
        {"type": "Running", "context": {"boo": ["a", "b", "c"]}}
    )
    assert type(deserialized) is state.Running
    assert deserialized.is_running()
    assert deserialized.message is None
    assert deserialized.context == dict(boo=["a", "b", "c"])
    assert deserialized.result is None
    assert deserialized._result == NoResult


def test_deserialize_json_without_version():
    deserialized = StateSchema().load({"type": "Running", "message": "test"})
    assert type(deserialized) is state.Running
    assert deserialized.is_running()
    assert deserialized.message == "test"
    assert deserialized.result is None
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
    def test_new_result_with_no_location_serializes_correctly(self):
        s = state.Success(message="test", result=results.S3Result(bucket="foo"))
        serialized = StateSchema().dump(s)
        assert serialized["message"] == "test"
        assert serialized["_result"]["type"] == "S3Result"
        assert serialized["_result"]["location"] is None

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


@pytest.mark.parametrize(
    "old_json",
    [
        {
            "type": "Success",
            "_result": {"type": "NoResultType", "__version__": "0.6.0"},
            "message": "Task run succeeded.",
            "__version__": "0.6.0",
        },
        {
            "type": "Mapped",
            "context": {"tags": []},
            "message": "Mapped tasks submitted for execution.",
            "__version__": "0.7.1+108.g3ad8ced1",
            "n_map_states": 2,
        },
        {
            "type": "Success",
            "_result": {
                "type": "SafeResult",
                "value": '["test1.zip", "test2.zip"]',
                "__version__": "0.7.1+108.g3ad8ced1",
                "result_handler": {
                    "type": "JSONResultHandler",
                    "__version__": "0.7.1+108.g3ad8ced1",
                },
            },
            "context": {"tags": []},
            "message": "Task run succeeded.",
            "__version__": "0.7.1+108.g3ad8ced1",
        },
        {
            "type": "Success",
            "_result": {
                "type": "SafeResult",
                "value": "/src/prefect-result-2020-06-09t15-32-47-297967-00-00",
                "__version__": "0.11.5+59.gdba764390",
                "result_handler": {
                    "dir": "/src",
                    "type": "LocalResultHandler",
                    "__version__": "0.11.5+59.gdba764390",
                },
            },
            "context": {"tags": []},
            "message": "Task run succeeded.",
            "__version__": "0.11.5+59.gdba764390",
            "cached_inputs": {
                "report": {
                    "type": "SafeResult",
                    "value": "/src/prefect-result-2020-06-09t15-32-38-403718-00-00",
                    "__version__": "0.11.5+59.gdba764390",
                    "result_handler": {
                        "dir": "/src",
                        "type": "LocalResultHandler",
                        "__version__": "0.11.5+59.gdba764390",
                    },
                }
            },
        },
    ],
)
def test_can_deserialize_old_no_result(old_json):
    schema = StateSchema()

    state = schema.load(old_json)
    assert state.is_successful()
