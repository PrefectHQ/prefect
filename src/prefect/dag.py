from typing import Set
from unittest.mock import MagicProxy, Mock

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


magic_methods = [
    "__lt__",
    "__le__",
    "__gt__",
    "__ge__",
    "__eq__",
    "__ne__",
    "__getitem__",
    "__setitem__",
    "__delitem__",
    "__len__",
    "__contains__",
    "__str__",
    "__sizeof__",
    "__enter__",
    "__exit__",
    "__divmod__",
    "__rdivmod__",
    "__neg__",
    "__pos__",
    "__abs__",
    "__invert__",
    "__complex__",
    "__int__",
    "__float__",
    "__index__",
    "__round__",
    "__trunc__",
    "__floor__",
    "__ceil__",
    "__bool__",
    "__next__",
    "__fspath__",
    "__aiter__",
]


class DAGMock(Mock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        _type = type(self)
        for entry in magic_methods:
            setattr(_type, entry, MagicProxy(entry, self))

    def __hash__(self) -> int:
        return super().__hash__()


class FutureMock(DAGMock):
    def result(self, *args, **kwargs):
        return self._get_result_mock()

    async def _result(self, *args, **kwargs):
        return self._get_result_mock()

    def _get_result_mock(self):
        return ResultMock()


class ResultMock(DAGMock):
    def __iter__(self):
        return iter([self[0]])


def get_mock_for_future(future: "PrefectFuture"):
    mock = FutureMock(name=future.name, spec=PrefectFuture)
    return mock


def build_dag(flow: Flow[P, R], *args: P.args, **kwargs: P.kwargs):
    with DAGBuildContext(bool_returns=True) as ctx_true:
        flow(*args, **kwargs)

    with DAGBuildContext(bool_returns=False) as ctx_false:
        flow(*args, **kwargs)

    return ctx_true.mocks.union(ctx_false.mocks)


def is_building_dag() -> bool:
    return DAGBuildContext.get() is not None
