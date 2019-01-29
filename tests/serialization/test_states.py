import base64
import datetime
import json

import cloudpickle
import marshmallow
import pendulum
import pytest

from collections import defaultdict

import prefect
from prefect.engine.result_handlers import ResultHandler
from prefect.engine import state
from prefect.serialization.state import ResultHandlerField, StateSchema

all_states = sorted(
    set(
        cls
        for cls in state.__dict__.values()
        if isinstance(cls, type)
        and issubclass(cls, state.State)
        and cls is not state.State
    ),
    key=lambda c: c.__name__,
)


def complex_states():
    naive_dt = datetime.datetime(2020, 1, 1)
    utc_dt = pendulum.datetime(2020, 1, 1)
    complex_result = {"x": 1, "y": {"z": 2}}
    cached_state = state.CachedState(
        cached_inputs=complex_result,
        cached_result=complex_result,
        cached_parameters=complex_result,
        cached_result_expiration=utc_dt,
    )
    cached_state_naive = state.CachedState(
        cached_inputs=complex_result,
        cached_result=complex_result,
        cached_parameters=complex_result,
        cached_result_expiration=naive_dt,
    )
    test_states = [
        state.Pending(cached_inputs=complex_result),
        state.Paused(cached_inputs=complex_result),
        state.Retrying(start_time=utc_dt, run_count=3),
        state.Retrying(start_time=naive_dt, run_count=3),
        state.Scheduled(start_time=utc_dt),
        state.Scheduled(start_time=naive_dt),
        state.Resume(start_time=utc_dt),
        state.Resume(start_time=naive_dt),
        state.Submitted(state=state.Retrying(start_time=utc_dt, run_count=2)),
        state.Submitted(state=state.Resume(start_time=utc_dt)),
        cached_state,
        cached_state_naive,
        state.Success(result=complex_result, cached=cached_state),
        state.Success(result=complex_result, cached=cached_state_naive),
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


class TestResultHandlerField:
    class Schema(marshmallow.Schema):
        field = ResultHandlerField()

    def test_serializes_normally_for_objs_without_metadata(self):
        schema = self.Schema()
        serialized = schema.dump({"field": 50})
        assert "field" in serialized
        assert serialized["field"] == 50

    def test_serializes_without_result_if_raw(self):
        s = state.Success(message="hi", result=42)
        schema = StateSchema()
        serialized = schema.dump(s)
        assert serialized["message"] == "hi"
        assert serialized["result"] is None

    def test_serializes_without_derived_result_attrs_if_raw(self):
        s = state.CachedState(
            message="hi",
            result=42,
            cached_inputs=dict(x=1, y="str"),
            cached_result={"x": {"y": {"z": 55}}},
            cached_parameters=dict(three=3),
        )
        schema = StateSchema()
        serialized = schema.dump(s)
        assert serialized["message"] == "hi"
        assert serialized["result"] is None
        assert serialized["cached_inputs"] is None
        assert serialized["cached_result"] is None
        assert serialized["cached_parameters"] == dict(three=3)

    def test_nested_serializes_without_derived_result_attrs_if_raw(self):
        s = state.CachedState(
            message="hi",
            result=42,
            cached_inputs=dict(x=1, y="str"),
            cached_result={"x": {"y": {"z": 55}}},
            cached_parameters=dict(three=3),
        )
        top_state = state.Success(message="hello", cached=s)
        schema = StateSchema()
        top_serialized = schema.dump(top_state)
        assert top_serialized["message"] == "hello"

        serialized = top_serialized["cached"]
        assert serialized["message"] == "hi"
        assert serialized["result"] is None
        assert serialized["cached_inputs"] is None
        assert serialized["cached_result"] is None
        assert serialized["cached_parameters"] == dict(three=3)

    def test_serializes_with_result_if_not_raw(self):
        s = state.Success(message="hi", result=42)
        s._metadata.update(result=dict(raw=False))
        schema = StateSchema()
        serialized = schema.dump(s)
        print(serialized)
        assert serialized["message"] == "hi"
        assert serialized["result"] == 42

    def test_serializes_with_derived_result_attrs_if_not_raw(self):
        s = state.CachedState(
            message="hi",
            result=42,
            cached_inputs=dict(x=1, y="str"),
            cached_result={"x": {"y": {"z": 55}}},
            cached_parameters=dict(three=3),
        )
        s._metadata.update(
            result=dict(raw=False),
            cached_result=dict(raw=True),
            cached_inputs=dict(raw=False),
        )
        schema = StateSchema()
        serialized = schema.dump(s)
        assert serialized["message"] == "hi"
        assert serialized["result"] == 42
        assert serialized["cached_inputs"] == dict(x=1, y="str")
        assert serialized["cached_result"] is None
        assert serialized["cached_parameters"] == dict(three=3)

    def test_nested_serializes_with_derived_result_attrs_if_not_raw(self):
        s = state.CachedState(
            message="hi",
            result=42,
            cached_inputs=dict(x=1, y="str"),
            cached_result={"x": {"y": {"z": 55}}},
            cached_parameters=dict(three=3),
        )
        s._metadata.update(
            result=dict(raw=False),
            cached_result=dict(raw=False),
            cached_inputs=dict(raw=False),
        )
        top_state = state.Success(message="hello", cached=s)
        schema = StateSchema()
        top_serialized = schema.dump(top_state)
        assert top_serialized["message"] == "hello"

        serialized = top_serialized["cached"]
        assert serialized["message"] == "hi"
        assert serialized["result"] == 42
        assert serialized["cached_inputs"] == dict(x=1, y="str")
        assert serialized["cached_result"] == {"x": {"y": {"z": 55}}}
        assert serialized["cached_parameters"] == dict(three=3)

    def test_metadata_structure_is_preserved(self):
        s = state.Success()
        s._metadata["cached_result"]["raw"] = False
        s._metadata["cached_inputs"]["x"]["raw"] = False
        schema = StateSchema()
        new = schema.load(schema.dump(s))
        assert "y" not in new._metadata.cached_inputs
        assert new._metadata.cached_inputs["y"]["raw"] is True


@pytest.mark.parametrize("cls", [s for s in all_states if s is not state.Mapped])
def test_serialize_state(cls):
    serialized = StateSchema().dump(cls(message="message", result=1))
    assert isinstance(serialized, dict)
    assert serialized["type"] == cls.__name__
    assert serialized["message"] is "message"
    assert serialized["result"] is None
    assert serialized["__version__"] == prefect.__version__


@pytest.mark.parametrize("cls", [s for s in all_states if s is not state.Mapped])
def test_serialize_state_with_metadata(cls):
    state = cls(message="message", result=1)
    state._metadata.update(result=dict(raw=False))
    serialized = StateSchema().dump(state)
    assert isinstance(serialized, dict)
    assert serialized["type"] == cls.__name__
    assert serialized["message"] is "message"
    assert serialized["result"] == 1
    assert serialized["__version__"] == prefect.__version__


def test_serialize_mapped():
    s = state.Success(message="1", result=1)
    f = state.Failed(message="2", result=2)
    s._metadata.update(result=dict(raw=False))
    f._metadata.update(result=dict(raw=False))
    serialized = StateSchema().dump(state.Mapped(message="message", map_states=[s, f]))
    assert isinstance(serialized, dict)
    assert serialized["type"] == "Mapped"
    assert serialized["message"] is "message"
    assert "result" not in serialized
    assert "map_states" not in serialized
    assert serialized["n_map_states"] == 2
    assert serialized["__version__"] == prefect.__version__


@pytest.mark.parametrize("cls", [s for s in all_states if s is not state.Mapped])
def test_deserialize_state(cls):
    s = cls(message="message", result=1)
    s._metadata.update(result=dict(raw=False))
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
    assert all([isinstance(s, state.Pending) for s in deserialized.map_states])
    assert deserialized.result == None


@pytest.mark.parametrize("cls", all_states)
def test_deserialize_state_from_only_type(cls):
    serialized = dict(type=cls.__name__)
    new_state = StateSchema().load(serialized)
    assert isinstance(new_state, cls)
    assert new_state.message is None
    assert new_state.result is None


def test_deserialize_state_without_type_fails():
    with pytest.raises(marshmallow.exceptions.ValidationError):
        StateSchema().load({})


def test_deserialize_state_with_unknown_type_fails():
    with pytest.raises(marshmallow.exceptions.ValidationError):
        StateSchema().load({"type": "FakeState"})


@pytest.mark.parametrize("state", complex_states())
def test_complex_state_attributes_are_handled(state):
    state._metadata.update(
        result=dict(raw=False),
        cached_result=dict(raw=False),
        cached_parameters=dict(raw=False),
        cached_inputs=dict(raw=False),
    )
    serialized = StateSchema().dump(state)
    deserialized = StateSchema().load(serialized)
    assert state == deserialized


def test_result_must_be_valid_json():
    s = state.Success(result={"x": {"y": {"z": 1}}})
    s._metadata.update(result=dict(raw=False))
    serialized = StateSchema().dump(s)
    assert serialized["result"] == s.result


def test_result_doesnt_raise_error_on_dump_if_raw():
    s = state.Success(result={"x": {"y": {"z": lambda: 1}}})
    s._metadata.update(result=dict(raw=True))
    serialized = StateSchema().dump(s)
    assert serialized["result"] is None


def test_result_raises_error_on_dump_if_not_valid_json():
    s = state.Success(result={"x": {"y": {"z": lambda: 1}}})
    s._metadata.update(result=dict(raw=False))
    with pytest.raises(TypeError):
        StateSchema().dump(s)


def test_deserialize_json_without_version():
    deserialized = StateSchema().load(
        {"type": "Running", "message": "test", "result": 1}
    )
    assert type(deserialized) is state.Running
    assert deserialized.is_running()
    assert deserialized.message == "test"
    assert deserialized.result == 1


def test_deserialize_handles_unknown_fields():
    """ensure that deserialization can happen even if a newer version of prefect created unknown fields"""
    deserialized = StateSchema().load(
        {
            "type": "Success",
            "success_message_that_definitely_wont_exist_on_a_real_state!": 1,
        }
    )

    assert deserialized.is_successful()
