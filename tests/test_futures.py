from collections import OrderedDict
from dataclasses import dataclass
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from prefect.client import OrionClient
from prefect.futures import PrefectFuture, resolve_futures_to_data
from prefect.orion.schemas.states import Completed
from prefect.orion.schemas.data import DataDocument

mock_client = MagicMock(spec=OrionClient)()
mock_client.read_flow_run_states.return_value = [Completed()]


async def test_resolve_futures_transforms_future():
    future = PrefectFuture(
        run_id=uuid4(),
        executor=None,
        _final_state=Completed(data=DataDocument.encode("json", "foo")),
    )
    assert await resolve_futures_to_data(future) == "foo"


@pytest.mark.parametrize("typ", [list, tuple, set])
async def test_resolve_futures_transforms_future_in_listlike_type(typ):
    future = PrefectFuture(
        run_id=uuid4(),
        executor=None,
        _final_state=Completed(data=DataDocument.encode("json", "foo")),
    )
    assert await resolve_futures_to_data(typ(["a", future, "b"])) == typ(
        ["a", "foo", "b"]
    )


async def test_resolve_futures_transforms_future_in_generator_type():
    def gen():
        yield "a"
        yield PrefectFuture(
            run_id=uuid4(),
            executor=None,
            _final_state=Completed(data=DataDocument.encode("json", "foo")),
        )
        yield "b"

    assert await resolve_futures_to_data(gen()) == ["a", "foo", "b"]


async def test_resolve_futures_transforms_future_in_nested_generator_types():
    def gen_a():
        yield PrefectFuture(
            run_id=uuid4(),
            executor=None,
            _final_state=Completed(data=DataDocument.encode("json", "foo")),
        )

    def gen_b():
        yield range(2)
        yield gen_a()
        yield "b"

    assert await resolve_futures_to_data(gen_b()) == [range(2), ["foo"], "b"]


@pytest.mark.parametrize("typ", [dict, OrderedDict])
async def test_resolve_futures_transforms_future_in_dictlike_type(typ):
    key_future = PrefectFuture(
        run_id=uuid4(),
        executor=None,
        _final_state=Completed(data=DataDocument.encode("json", "foo")),
    )
    value_future = PrefectFuture(
        run_id=uuid4(),
        executor=None,
        _final_state=Completed(data=DataDocument.encode("json", "bar")),
    )
    assert await resolve_futures_to_data(
        typ([("a", 1), (key_future, value_future), ("b", 2)])
    ) == typ([("a", 1), ("foo", "bar"), ("b", 2)])


async def test_resolve_futures_transforms_future_in_dataclass():
    @dataclass
    class Foo:
        a: int
        foo: str
        b: int = 2

    future = PrefectFuture(
        run_id=uuid4(),
        executor=None,
        _final_state=Completed(data=DataDocument.encode("json", "bar")),
    )
    assert await resolve_futures_to_data(Foo(a=1, foo=future)) == Foo(
        a=1, foo="bar", b=2
    )


async def test_resolves_futures_in_nested_collections():
    @dataclass
    class Foo:
        foo: str
        nested_list: list
        nested_dict: dict

    future = PrefectFuture(
        run_id=uuid4(),
        executor=None,
        _final_state=Completed(data=DataDocument.encode("json", "bar")),
    )
    assert await resolve_futures_to_data(
        Foo(foo=future, nested_list=[[future]], nested_dict={"key": [future]})
    ) == Foo(foo="bar", nested_list=[["bar"]], nested_dict={"key": ["bar"]})
