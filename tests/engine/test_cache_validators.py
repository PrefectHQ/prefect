from dask.base import tokenize
from datetime import timedelta

import pendulum
import pytest

from prefect.engine.cache_validators import (
    all_inputs,
    all_parameters,
    duration_only,
    never_use,
    partial_inputs_only,
    partial_parameters_only,
)
from prefect.engine.result import Result
from prefect.engine.state import Cached

all_validators = [all_inputs, all_parameters, never_use, duration_only]
stateful_validators = [partial_inputs_only, partial_parameters_only]


def test_never_use_returns_false():
    assert never_use(None, None, None) is False


@pytest.mark.parametrize("validator", all_validators)
def test_expired_cache(validator):
    state = Cached(cached_result_expiration=pendulum.now("utc") - timedelta(days=1))
    assert validator(state, None, None) is False


@pytest.mark.parametrize("validator", stateful_validators)
def test_expired_cache_stateful(validator):
    state = Cached(cached_result_expiration=pendulum.now("utc") - timedelta(days=1))
    assert validator()(state, None, None) is False


class TestDurationOnly:
    def test_unexpired_cache(self):
        state = Cached(cached_result_expiration=pendulum.now("utc") + timedelta(days=1))
        assert duration_only(state, None, None) is True

    def test_cached_result_expiration_none_is_interpreted_as_infinite(self):
        state = Cached(cached_result_expiration=None)
        assert duration_only(state, None, None) is True


class TestAllInputs:
    def test_inputs_invalidate(self):
        state = Cached(cached_inputs=dict(x=Result(1), s=Result("str")))
        assert all_inputs(state, dict(x=1, s="strs"), None) is False

    def test_hashed_inputs_invalidate(self):
        state = Cached(hashed_inputs=dict(x=tokenize(2), s=tokenize("str")))
        assert all_inputs(state, dict(x=1, s="str"), None) is False

    def test_inputs_validate(self):
        state = Cached(cached_inputs=dict(x=Result(1), s=Result("str")))
        assert all_inputs(state, dict(x=1, s="str"), None) is True

    def test_hashed_inputs_validate(self):
        state = Cached(hashed_inputs=dict(x=tokenize(1), s=tokenize("str")))
        assert all_inputs(state, dict(x=1, s="str"), None) is True

    def test_additional_inputs_invalidate(self):
        state = Cached(cached_inputs=dict(x=Result(1), s=Result("str")))
        assert all_inputs(state, dict(x=1, s="str", noise="e"), None) is False


class TestAllParameters:
    def test_parameters_invalidate(self):
        state = Cached(cached_parameters=dict(x=1, s="str"))
        assert all_parameters(state, None, dict(x=1, s="strs")) is False

    def test_parameters_validate(self):
        state = Cached(cached_parameters=dict(x=1, s="str"))
        assert all_parameters(state, None, dict(x=1, s="str")) is True

    def test_additional_parameters_invalidate(self):
        state = Cached(cached_parameters=dict(x=1, s="str"))
        assert all_parameters(state, None, dict(x=1, s="str", noise="e")) is False


class TestPartialInputsOnly:
    def test_inputs_validate_with_defaults(self):
        state = Cached(cached_inputs=dict(x=Result(1), s=Result("str")))
        assert partial_inputs_only(None)(state, dict(x=1, s="str"), None) is True
        state = Cached(cached_inputs=dict(x=Result(1), s=Result("str")))
        assert partial_inputs_only(None)(state, dict(x=1, s="strs"), None) is True

    def test_validate_on_kwarg(self):
        state = Cached(cached_inputs=dict(x=Result(1), s=Result("str")))
        assert (
            partial_inputs_only(validate_on=["x", "s"])(state, dict(x=1, s="str"), None)
            is True
        )
        state = Cached(cached_inputs=dict(x=Result(1), s=Result("str")))
        assert (
            partial_inputs_only(validate_on=["x", "s"])(
                state, dict(x=1, s="strs"), None
            )
            is False
        )
        assert (
            partial_inputs_only(validate_on=["x"])(state, dict(x=1, s="strs"), None)
            is True
        )
        assert (
            partial_inputs_only(validate_on=["s"])(state, dict(x=1, s="strs"), None)
            is False
        )

    def test_handles_none(self):
        state = Cached(cached_parameters=dict(x=5))
        assert partial_inputs_only(validate_on=["x"])(state, dict(x=5), None) is False
        state = Cached(cached_inputs=dict(x=Result(5)))
        assert partial_inputs_only(validate_on=["x"])(state, None, None) is False

    def test_curried(self):
        state = Cached(cached_inputs=dict(x=Result(1), s=Result("str")))
        validator = partial_inputs_only(validate_on=["x"])
        assert validator(state, dict(x=1), None) is True
        assert validator(state, dict(x=2, s="str"), None) is False


class TestPartialParametersOnly:
    def test_parameters_validate_with_defaults(self):
        state = Cached(cached_parameters=dict(x=1, s="str"))
        assert partial_parameters_only()(state, None, dict(x=1, s="str")) is True
        state = Cached(cached_parameters=dict(x=1, s="str"))
        assert partial_parameters_only()(state, None, dict(x=1, s="strs")) is True

    def test_validate_on_kwarg(self):
        state = Cached(cached_parameters=dict(x=1, s="str"))
        assert (
            partial_parameters_only(validate_on=["x", "s"])(
                state, None, dict(x=1, s="str")
            )
            is True
        )
        state = Cached(cached_parameters=dict(x=1, s="str"))
        assert (
            partial_parameters_only(validate_on=["x", "s"])(
                state, None, dict(x=1, s="strs")
            )
            is False
        )
        assert (
            partial_parameters_only(validate_on=["x"])(state, None, dict(x=1, s="strs"))
            is True
        )
        assert (
            partial_parameters_only(validate_on=["s"])(state, None, dict(x=1, s="strs"))
            is False
        )

    def test_handles_none(self):
        state = Cached(cached_inputs=dict(x=Result(5)))
        assert (
            partial_parameters_only(validate_on=["x"])(state, None, dict(x=5)) is False
        )
        state = Cached(cached_parameters=dict(x=5))
        assert partial_parameters_only(validate_on=["x"])(state, None, None) is False

    def test_curried(self):
        state = Cached(cached_parameters=dict(x=1, s="str"))
        validator = partial_parameters_only(validate_on=["x"])
        assert validator(state, None, dict(x=1)) is True
        assert validator(state, None, dict(x=2, s="str")) is False
