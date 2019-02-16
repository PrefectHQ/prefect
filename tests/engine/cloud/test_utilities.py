from prefect.engine.result import Result, NoResult, SafeResult
from prefect.engine.result_handlers import ResultHandler, JSONResultHandler
from prefect.engine.state import Cached, Pending, Success
from prefect.engine.cloud.utilities import prepare_state_for_cloud


def test_preparing_state_for_cloud_replaces_cached_inputs_with_safe():
    xres = Result(3, result_handler=JSONResultHandler())
    state = prepare_state_for_cloud(Pending(cached_inputs=dict(x=xres)))
    assert state.is_pending()
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
