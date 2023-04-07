from typing import Optional, Set
from unittest.mock import Mock

import pydantic

from prefect.context import ContextModel, ContextVar
from prefect.flows import Flow, P, R
from prefect.futures import PrefectFuture
from prefect.logging import get_logger

logger = get_logger("dag")


class DAGBuildContext(ContextModel):
    bool_returns: bool = pydantic.Field(True)
    mocks: Set[Mock] = pydantic.Field(default_factory=set)

    __var__ = ContextVar("tags")

    def add_mock(self, mock):
        self.mocks.add(mock)

    @classmethod
    def toggle(cls, last_ctx: Optional["DAGBuildContext"]) -> "DAGBuildContext":
        if last_ctx is None:
            return cls()

        return cls(
            # Toggle booleans
            bool_returns=not last_ctx.bool_returns,
            mocks=last_ctx.mocks,
        )


class DAGMock(Mock):
    def __hash__(self) -> int:
        return super().__hash__()


class FutureMock(DAGMock):
    def result(self, *args, **kwargs):
        return self._get_result_mock()

    async def _result(self, *args, **kwargs):
        return self._get_result_mock()

    def _get_result_mock(self):
        mock = ResultMock()
        mock.__iter__ = lambda _: iter([mock[0]])
        return mock


class ResultMock(DAGMock):
    pass


def get_mock_for_future(future: "PrefectFuture"):
    mock = FutureMock(name=future.name, spec=PrefectFuture)
    return mock


def build_dag(flow: Flow[P, R], *args: P.args, **kwargs: P.kwargs):
    last_ctx = None

    while True:
        logger.debug("Running iteration")
        with DAGBuildContext.toggle(last_ctx) as ctx:
            flow(*args, **kwargs)

        if stable_dag(last_ctx, ctx):
            break

        last_ctx = ctx

    return ctx.mocks


def stable_dag(previous, current) -> bool:
    if previous is None or current is None:
        return False

    return set(previous.mocks) == set(current.mocks)


def is_building_dag() -> bool:
    return DAGBuildContext.get() is not None
