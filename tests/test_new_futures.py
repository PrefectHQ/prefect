import uuid
from collections import OrderedDict
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any, Optional

import pytest

from prefect.new_futures import (
    PrefectConcurrentFuture,
    PrefectFuture,
    resolve_futures_to_states,
)
from prefect.states import Completed, Failed


class MockFuture(PrefectFuture):
    def __init__(self, data: Any = 42):
        super().__init__(uuid.uuid4(), Future())
        self._final_state = Completed(data=data)

    def wait(self, timeout: Optional[float] = None) -> None:
        pass

    def result(
        self,
        timeout: Optional[float] = None,
        raise_on_failure: bool = True,
    ) -> Any:
        return self._final_state.result()


class TestPrefectConcurrentFuture:
    def test_wait_with_timeout(self):
        wrapped_future = Future()
        future = PrefectConcurrentFuture(uuid.uuid4(), wrapped_future)
        future.wait(timeout=0.01)  # should not raise a TimeoutError

        assert (
            future.state.is_pending()
        )  # should return a Pending state when task run is not found

    def test_wait_without_timeout(self):
        wrapped_future = Future()
        future = PrefectConcurrentFuture(uuid.uuid4(), wrapped_future)
        wrapped_future.set_result(Completed())
        future.wait(timeout=0)

        assert future.state.is_completed()

    def test_result_with_final_state(self):
        final_state = Completed(data=42)
        wrapped_future = Future()
        future = PrefectConcurrentFuture(uuid.uuid4(), wrapped_future)
        wrapped_future.set_result(final_state)
        result = future.result()

        assert result == 42

    def test_result_without_final_state(self):
        wrapped_future = Future()
        future = PrefectConcurrentFuture(uuid.uuid4(), wrapped_future)
        wrapped_future.set_result(42)
        result = future.result()

        assert result == 42

    def test_result_with_final_state_and_raise_on_failure(self):
        final_state = Failed(data=ValueError("oops"))
        wrapped_future = Future()
        future = PrefectConcurrentFuture(uuid.uuid4(), wrapped_future)
        wrapped_future.set_result(final_state)

        with pytest.raises(ValueError, match="oops"):
            future.result(raise_on_failure=True)


class TestResolveFuturesToStates:
    async def test_resolve_futures_transforms_future(self):
        future = future = MockFuture()
        assert resolve_futures_to_states(future).is_completed()

    def test_resolve_futures_to_states_with_no_futures(self):
        expr = [1, 2, 3]
        result = resolve_futures_to_states(expr)
        assert result == [1, 2, 3]

    @pytest.mark.parametrize("_type", [list, tuple, set])
    def test_resolve_futures_transforms_future_in_listlike_type(self, _type):
        future = MockFuture(data="foo")
        result = resolve_futures_to_states(_type(["a", future, "b"]))
        assert result == _type(["a", future.state, "b"])

    @pytest.mark.parametrize("_type", [dict, OrderedDict])
    def test_resolve_futures_transforms_future_in_dictlike_type(self, _type):
        key_future = MockFuture(data="foo")
        value_future = MockFuture(data="bar")
        result = resolve_futures_to_states(
            _type([("a", 1), (key_future, value_future), ("b", 2)])
        )
        assert result == _type(
            [("a", 1), (key_future.state, value_future.state), ("b", 2)]
        )

    def test_resolve_futures_transforms_future_in_dataclass(self):
        @dataclass
        class Foo:
            a: int
            foo: str
            b: int = 2

        future = MockFuture(data="bar")
        assert resolve_futures_to_states(Foo(a=1, foo=future)) == Foo(
            a=1, foo=future.state, b=2
        )

    def test_resolves_futures_in_nested_collections(self):
        @dataclass
        class Foo:
            foo: str
            nested_list: list
            nested_dict: dict

        future = MockFuture(data="bar")
        assert resolve_futures_to_states(
            Foo(foo=future, nested_list=[[future]], nested_dict={"key": [future]})
        ) == Foo(
            foo=future.state,
            nested_list=[[future.state]],
            nested_dict={"key": [future.state]},
        )
