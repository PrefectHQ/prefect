from unittest.mock import MagicMock

from prefect.flows import Flow, P, R
from prefect.futures import PrefectFuture
from prefect.settings import PREFECT_BUILDING_DAG, temporary_settings


class FutureMock(MagicMock):
    def result(self, *args, **kwargs):
        return self._get_result_mock()

    async def _result(self, *args, **kwargs):
        return self._get_result_mock()

    def _get_result_mock(self):
        mock = ResultMock()
        mock.__iter__ = lambda _: iter([mock[0]])
        return mock


class ResultMock(MagicMock):
    pass


def get_mock_for_future(future: "PrefectFuture"):
    mock = FutureMock(name=future.name, spec=PrefectFuture)
    return mock


def build_dag(flow: Flow[P, R], *args: P.args, **kwargs: P.kwargs):
    with temporary_settings({PREFECT_BUILDING_DAG: True}):
        kwargs.pop("return_state", None)  # You can't control this we need the state
        state = flow(*args, return_state=True, **kwargs)

    # Get the mocks
    mocks = state._mocks
    return mocks
