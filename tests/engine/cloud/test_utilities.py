import pytest

import prefect
from prefect.engine.cloud.utilities import prepare_state_for_cloud
from prefect.engine.result import NoResult, Result, SafeResult
from prefect.engine.result_handlers import JSONResultHandler, ResultHandler
from prefect.engine.state import Cached, Failed, Pending, Success, _MetaState

all_states = sorted(
    set(
        cls
        for cls in prefect.engine.state.__dict__.values()
        if isinstance(cls, type)
        and issubclass(cls, prefect.engine.state.State)
        and not cls is _MetaState
    ),
    key=lambda c: c.__name__,
)

cached_input_states = sorted(
    set(cls for cls in all_states if hasattr(cls(), "cached_inputs")),
    key=lambda c: c.__name__,
)


@pytest.mark.parametrize("cls", cached_input_states)
def test_preparing_state_for_cloud_replaces_cached_inputs_with_safe(cls):
    xres = Result(3, result_handler=JSONResultHandler())
    state = prepare_state_for_cloud(cls(cached_inputs=dict(x=xres)))
    assert isinstance(state, cls)
    assert state.result == NoResult
    assert state.cached_inputs == dict(x=xres)


@pytest.mark.parametrize(
    "cls", [s for s in cached_input_states if not issubclass(s, Failed)]
)
def test_preparing_state_for_cloud_fails_if_cached_inputs_have_no_handler(cls):
    xres = Result(3, result_handler=None)
    with pytest.raises(AssertionError, match="no ResultHandler"):
        state = prepare_state_for_cloud(cls(cached_inputs=dict(x=xres)))


@pytest.mark.parametrize(
    "cls", [s for s in cached_input_states if issubclass(s, Failed)]
)
def test_preparing_state_for_cloud_passes_if_cached_inputs_dont_exist(cls):
    state = prepare_state_for_cloud(cls())
    assert isinstance(state, cls)
    assert state.result == NoResult
    assert state.cached_inputs is None


@pytest.mark.parametrize(
    "cls", [s for s in cached_input_states if issubclass(s, Failed)]
)
def test_preparing_state_for_cloud_passes_if_cached_inputs_have_no_handler_for_failed(
    cls,
):
    xres = Result(3, result_handler=None)
    state = prepare_state_for_cloud(cls(cached_inputs=dict(x=xres)))
    assert isinstance(state, cls)
    assert state.result == NoResult
    assert state.cached_inputs == dict(x=xres)


def test_preparing_state_for_cloud_doesnt_copy_data():
    class FakeHandler(ResultHandler):
        def read(self, val):
            return val

        def write(self, val):
            return val

    value = 124.090909
    result = Result(value, result_handler=FakeHandler())
    state = Cached(result=result)
    cloud_state = prepare_state_for_cloud(state)
    assert cloud_state.is_cached()
    assert cloud_state.result is state.result
