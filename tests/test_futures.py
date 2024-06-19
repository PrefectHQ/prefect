import asyncio
import uuid
from collections import OrderedDict
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any, Optional

import pytest

from prefect import task
from prefect.exceptions import FailedRun, MissingResult
from prefect.filesystems import LocalFileSystem
from prefect.futures import (
    PrefectConcurrentFuture,
    PrefectDistributedFuture,
    PrefectWrappedFuture,
    resolve_futures_to_states,
)
from prefect.states import Completed, Failed
from prefect.task_engine import run_task_async, run_task_sync


class MockFuture(PrefectWrappedFuture):
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

    def test_warns_if_not_resolved_when_garbage_collected(self, caplog):
        PrefectConcurrentFuture(uuid.uuid4(), Future())

        assert "A future was garbage collected before it resolved" in caplog.text

    def test_does_not_warn_if_resolved_when_garbage_collected(self, caplog):
        wrapped_future = Future()
        wrapped_future.set_result(Completed())
        PrefectConcurrentFuture(uuid.uuid4(), wrapped_future)

        assert "A future was garbage collected before it resolved" not in caplog.text


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


class TestPrefectDistributedFuture:
    async def test_wait_with_timeout(self, task_run):
        @task
        async def my_task():
            return 42

        task_run = await my_task.create_run()
        future = PrefectDistributedFuture(task_run_id=task_run.id)

        asyncio.create_task(
            run_task_async(
                task=my_task,
                task_run_id=future.task_run_id,
                task_run=task_run,
                parameters={},
                return_type="state",
            )
        )

        future = PrefectDistributedFuture(task_run_id=task_run.id)
        future.wait(timeout=0.25)
        assert future.state.is_pending()

    async def test_wait_without_timeout(self):
        @task
        def my_task():
            return 42

        task_run = await my_task.create_run()
        future = PrefectDistributedFuture(task_run_id=task_run.id)

        state = run_task_sync(
            task=my_task,
            task_run_id=future.task_run_id,
            task_run=task_run,
            parameters={},
            return_type="state",
        )
        assert state.is_completed()

        future.wait()
        assert future.state.is_completed()

    async def test_result_with_final_state(self, tmp_path):
        # TODO: The default result storage block gets deleted during the
        # execution of this test when it's run in as a suite, so we have to load
        # a specific block and pass it in manually as the task's result storage.
        # But why does the result storage block get deleted in the first place?
        storage = LocalFileSystem(basepath=tmp_path)

        @task(persist_result=True, result_storage=storage)
        def my_task():
            return 42

        task_run = await my_task.create_run()
        future = PrefectDistributedFuture(task_run_id=task_run.id)

        state = run_task_sync(
            task=my_task,
            task_run_id=future.task_run_id,
            task_run=task_run,
            parameters={},
            return_type="state",
        )
        assert state.is_completed()
        assert await state.result() == 42

        # When this test is run as a suite and the task uses default result
        # storage, this line fails because the result storage block no longer
        # exists.
        assert future.result() == 42

    async def test_final_state_without_result(self):
        @task(persist_result=False)
        def my_task():
            return 42

        task_run = await my_task.create_run()
        future = PrefectDistributedFuture(task_run_id=task_run.id)

        state = run_task_sync(
            task=my_task,
            task_run_id=future.task_run_id,
            task_run=task_run,
            parameters={},
            return_type="state",
        )
        assert state.is_completed()

        with pytest.raises(MissingResult):
            future.result()

    async def test_result_with_final_state_and_raise_on_failure(self):
        @task(persist_result=False)
        def my_task():
            raise ValueError("oops")

        task_run = await my_task.create_run()
        future = PrefectDistributedFuture(task_run_id=task_run.id)

        state = run_task_sync(
            task=my_task,
            task_run_id=future.task_run_id,
            task_run=task_run,
            parameters={},
            return_type="state",
        )
        assert state.is_failed()

        with pytest.raises(FailedRun, match="oops"):
            future.result(raise_on_failure=True)

    async def test_final_state_missing_result(self):
        @task(persist_result=False)
        def my_task():
            return 42

        task_run = await my_task.create_run()
        future = PrefectDistributedFuture(task_run_id=task_run.id)

        state = run_task_sync(
            task=my_task,
            task_run_id=future.task_run_id,
            task_run=task_run,
            parameters={},
            return_type="state",
        )
        assert state.is_completed()

        with pytest.raises(MissingResult, match="State data is missing"):
            future.result()
