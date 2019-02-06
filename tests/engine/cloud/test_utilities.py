from prefect.engine.result import Result
from prefect.engine.result_handlers import ResultHandler
from prefect.engine.state import Cached
from prefect.engine.cloud.utilities import prepare_state_for_cloud


def test_preparing_state_for_cloud_doesnt_copy_data():
    class FakeHandler(ResultHandler):
        def read(self, val):
            return val

        def write(self, val):
            return val

    value = 124.090909
    result = Result(value, handled=False, result_handler=FakeHandler())
    state = Cached(result=result)
    cloud_state = prepare_state_for_cloud(state)
    assert cloud_state.is_cached()
    assert cloud_state is not state
    assert cloud_state.result is state.result
