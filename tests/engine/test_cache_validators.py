import pytest
from datetime import datetime, timedelta

from prefect.engine.cache_validators import all_inputs, all_parameters, never_use, partial_inputs_only, duration_only, upstream_parameters_only
from prefect.engine.state import CachedState


all_validators = [all_inputs, all_parameters, never_use, partial_inputs_only, duration_only, upstream_parameters_only]


def test_never_use_returns_false():
    assert never_use(None, None, None) is False


@pytest.mark.parametrize('validator', all_validators)
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


#class TestAllInputs:
#    def test_unexpired_cache(self):
#        state = CachedState(cache_expiration=datetime.utcnow() + timedelta(days=1))
#        assert duration_only(state, None, None) is True
#
#    def test_expired_cache(self):
#        state = CachedState(cache_expiration=datetime.utcnow() - timedelta(days=1))
#        assert all_inputs(state, None, None) is False
#
#    def test_cache_expiration_none_is_interpreted_as_infinite(self):
#        state = CachedState(cache_expiration=None)
#        assert duration_only(state, None, None) is True
#
