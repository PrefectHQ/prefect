import pytest
from datetime import datetime, timedelta

from prefect.engine.cache_validators import (
    all_inputs,
    all_parameters,
    never_use,
    partial_inputs_only,
    duration_only,
    partial_parameters_only,
)
from prefect.engine.state import CachedState


all_validators = [
    all_inputs,
    all_parameters,
    never_use,
    partial_inputs_only,
    duration_only,
    partial_parameters_only,
]


def test_never_use_returns_false():
    assert never_use(None, None, None) is False


@pytest.mark.parametrize("validator", all_validators)
def test_expired_cache(validator):
    state = CachedState(cache_expiration=datetime.utcnow() - timedelta(days=1))
    assert validator(state, None, None) is False


class TestDurationOnly:
    def test_unexpired_cache(self):
        state = CachedState(cache_expiration=datetime.utcnow() + timedelta(days=1))
        assert duration_only(state, None, None) is True

    def test_cache_expiration_none_is_interpreted_as_infinite(self):
        state = CachedState(cache_expiration=None)
        assert duration_only(state, None, None) is True


class TestAllInputs:
    def test_inputs_invalidate(self):
        state = CachedState(cached_inputs=dict(x=1, s="str"))
        assert all_inputs(state, dict(x=1, s="strs"), None) is False

    def test_inputs_validate(self):
        state = CachedState(cached_inputs=dict(x=1, s="str"))
        assert all_inputs(state, dict(x=1, s="str"), None) is True

    def test_additional_inputs_invalidate(self):
        state = CachedState(cached_inputs=dict(x=1, s="str"))
        assert all_inputs(state, dict(x=1, s="str", noise="e"), None) is False


class TestAllParameters:
    def test_parameters_invalidate(self):
        state = CachedState(cached_parameters=dict(x=1, s="str"))
        assert all_parameters(state, None, dict(x=1, s="strs")) is False

    def test_parameters_validate(self):
        state = CachedState(cached_parameters=dict(x=1, s="str"))
        assert all_parameters(state, None, dict(x=1, s="str")) is True

    def test_additional_parameters_invalidate(self):
        state = CachedState(cached_parameters=dict(x=1, s="str"))
        assert all_parameters(state, None, dict(x=1, s="str", noise="e")) is False


class TestPartialInputsOnly:
    def test_inputs_validate_with_defaults(self):
        state = CachedState(cached_inputs=dict(x=1, s="str"))
        assert partial_inputs_only(state, dict(x=1, s="str"), None) is True
        state = CachedState(cached_inputs=dict(x=1, s="str"))
        assert partial_inputs_only(state, dict(x=1, s="strs"), None) is True

    def test_validate_on_kwarg(self):
        state = CachedState(cached_inputs=dict(x=1, s="str"))
        assert (
            partial_inputs_only(state, dict(x=1, s="str"), None, validate_on=["x", "s"])
            is True
        )
        state = CachedState(cached_inputs=dict(x=1, s="str"))
        assert (
            partial_inputs_only(
                state, dict(x=1, s="strs"), None, validate_on=["x", "s"]
            )
            is False
        )
        assert (
            partial_inputs_only(state, dict(x=1, s="strs"), None, validate_on=["x"])
            is True
        )
        assert (
            partial_inputs_only(state, dict(x=1, s="strs"), None, validate_on=["s"])
            is False
        )

    def test_handles_none(self):
        state = CachedState(cached_parameters=dict(x=5))
        assert partial_inputs_only(state, dict(x=5), None, validate_on=["x"]) is False
        state = CachedState(cached_inputs=dict(x=5))
        assert partial_inputs_only(state, None, None, validate_on=["x"]) is False

    def test_curried(self):
        state = CachedState(cached_inputs=dict(x=1, s="str"))
        validator = partial_inputs_only(validate_on=["x"])
        assert validator(state, dict(x=1), None) is True
        assert validator(state, dict(x=2, s="str"), None) is False


class TestPartialParametersOnly:
    def test_parameters_validate_with_defaults(self):
        state = CachedState(cached_parameters=dict(x=1, s="str"))
        assert partial_parameters_only(state, None, dict(x=1, s="str")) is True
        state = CachedState(cached_parameters=dict(x=1, s="str"))
        assert partial_parameters_only(state, None, dict(x=1, s="strs")) is True

    def test_validate_on_kwarg(self):
        state = CachedState(cached_parameters=dict(x=1, s="str"))
        assert (
            partial_parameters_only(
                state, None, dict(x=1, s="str"), validate_on=["x", "s"]
            )
            is True
        )
        state = CachedState(cached_parameters=dict(x=1, s="str"))
        assert (
            partial_parameters_only(
                state, None, dict(x=1, s="strs"), validate_on=["x", "s"]
            )
            is False
        )
        assert (
            partial_parameters_only(state, None, dict(x=1, s="strs"), validate_on=["x"])
            is True
        )
        assert (
            partial_parameters_only(state, None, dict(x=1, s="strs"), validate_on=["s"])
            is False
        )

    def test_handles_none(self):
        state = CachedState(cached_inputs=dict(x=5))
        assert (
            partial_parameters_only(state, None, dict(x=5), validate_on=["x"]) is False
        )
        state = CachedState(cached_parameters=dict(x=5))
        assert partial_parameters_only(state, None, None, validate_on=["x"]) is False

    def test_curried(self):
        state = CachedState(cached_parameters=dict(x=1, s="str"))
        validator = partial_parameters_only(validate_on=["x"])
        assert validator(state, None, dict(x=1)) is True
        assert validator(state, None, dict(x=2, s="str")) is False
