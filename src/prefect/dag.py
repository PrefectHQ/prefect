from typing import List
from unittest.mock import MagicMock

import pydantic

from prefect.context import ContextModel, ContextVar
from prefect.flows import Flow, P, R
from prefect.futures import PrefectFuture


class DAGBuildContext(ContextModel):
    bool_returns: bool = pydantic.Field(True)
    mocks: List[MagicMock] = pydantic.Field(default_factory=list)

    __var__ = ContextVar("tags")


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
    with DAGBuildContext() as ctx:
        flow(*args, **kwargs)

    return ctx.mocks


def is_building_dag() -> bool:
    return DAGBuildContext.get() is not None
