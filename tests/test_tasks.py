import datetime
from itertools import repeat
from unittest.mock import MagicMock

import pytest

from prefect import flow
from prefect.client import OrionClient
from prefect.orion.schemas.states import State, StateType
from prefect.tasks import task, task_input_hash


class TestTaskCall:
    def test_task_called_outside_flow_raises(self):
        @task
        def foo():
            pass

        with pytest.raises(
            RuntimeError, match="Tasks cannot be called outside of a flow"
        ):
            foo()

    def test_sync_task_called_inside_sync_flow(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1)

        flow_future = bar()
        task_state = flow_future.result().data
        assert isinstance(task_state, State)
        assert task_state.data == 1

    async def test_async_task_called_inside_async_flow(self):
        @task
        async def foo(x):
            return x

        @flow
        async def bar():
            return await foo(1)

        flow_future = await bar()
        task_state = flow_future.result().data
        assert isinstance(task_state, State)
        assert task_state.data == 1

    async def test_sync_task_called_inside_async_flow(self):
        @task
        def foo(x):
            return x

        @flow
        async def bar():
            return foo(1)

        flow_future = await bar()
        task_state = flow_future.result().data
        assert isinstance(task_state, State)
        assert task_state.data == 1

    async def test_async_task_called_inside_sync_flow_raises_clear_error(self):
        @task
        def foo(x):
            return x

        @flow
        async def bar():
            return foo(1)

        flow_future = await bar()
        task_state = flow_future.result().data
        assert isinstance(task_state, State)
        assert task_state.data == 1

    async def test_async_task_called_inside_sync_flow_raises_clear_error(self):
        @task
        async def foo(x):
            return x

        @flow
        def bar():
            return foo(1)

        with pytest.raises(
            RuntimeError,
            match="Your task is async, but your flow is sync",
        ):
            # Normally, this would just return the coro which was never awaited but we
            # want to fail instead to provide a better error
            raise bar().result().data

    @pytest.mark.parametrize("error", [ValueError("Hello"), None])
    def test_final_state_reflects_exceptions_during_run(self, error):
        @task
        def bar():
            if error:
                raise error

        @flow(version="test")
        def foo():
            return bar()

        flow_future = foo()
        task_state = flow_future.result().data

        # Assert the final state is correct
        assert task_state.is_failed() if error else task_state.is_completed()
        assert task_state.data is error

    def test_final_task_state_respects_returned_state(sel):
        @task
        def bar():
            return State(
                type=StateType.FAILED, message="Test returned state", data=True
            )

        @flow(version="test")
        def foo():
            return bar()

        flow_future = foo()
        task_state = flow_future.result().data

        # Assert the final state is correct
        assert task_state.is_failed()
        assert task_state.data is True
        assert task_state.message == "Test returned state"

    async def test_task_runs_correctly_populate_dynamic_keys(self):
        @task
        def bar():
            return "foo"

        @flow(version="test")
        def foo():
            return bar().run_id, bar().run_id

        flow_future = foo()
        task_run_ids = flow_future.result().data

        async with OrionClient() as client:
            task_runs = [await client.read_task_run(run_id) for run_id in task_run_ids]

        # Assert dynamic key is set correctly
        assert task_runs[0].dynamic_key == "0"
        assert task_runs[1].dynamic_key == "1"

    def test_task_called_with_task_dependency(self):
        @task
        def foo(x):
            return x

        @task
        def bar(y):
            return y + 1

        @flow
        def test_flow():
            return bar(foo(1))

        flow_future = test_flow()
        task_state = flow_future.result().data
        assert task_state.data == 2


class TestTaskRetries:
    @pytest.mark.parametrize("always_fail", [True, False])
    async def test_task_respects_retry_count(self, always_fail):
        mock = MagicMock()
        exc = ValueError()

        @task(retries=3)
        def flaky_function():
            mock()

            # 3 retries means 4 attempts
            # Succeed on the final retry unless we're ending in a failure
            if not always_fail and mock.call_count == 4:
                return True

            raise exc

        @flow
        def test_flow():
            future = flaky_function()
            return future.run_id, future.result()

        flow_future = test_flow()
        task_run_id, task_run_state = flow_future.result().data

        if always_fail:
            assert task_run_state.is_failed()
            assert task_run_state.data is exc
            assert mock.call_count == 4
        else:
            assert task_run_state.is_completed()
            assert task_run_state.data is True
            assert mock.call_count == 4

        async with OrionClient() as client:
            states = await client.read_task_run_states(task_run_id)

        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Awaiting Retry",
            "Running",
            "Awaiting Retry",
            "Running",
            "Awaiting Retry",
            "Running",
            "Failed" if always_fail else "Completed",
        ]

    async def test_task_only_uses_necessary_retries(self):
        mock = MagicMock()
        exc = ValueError()

        @task(retries=3)
        def flaky_function():
            mock()
            if mock.call_count == 2:
                return True
            raise exc

        @flow
        def test_flow():
            future = flaky_function()
            return future.run_id, future.result()

        flow_future = test_flow()
        task_run_id, task_run_state = flow_future.result().data

        assert task_run_state.is_completed()
        assert task_run_state.data is True
        assert mock.call_count == 2

        async with OrionClient() as client:
            states = await client.read_task_run_states(task_run_id)
        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Awaiting Retry",
            "Running",
            "Completed",
        ]

    async def test_task_respects_retry_delay(self, monkeypatch):
        mock = MagicMock()
        sleep = MagicMock()  # Mock sleep for fast testing
        monkeypatch.setattr("time.sleep", sleep)

        @task(retries=1, retry_delay_seconds=43)
        def flaky_function():
            mock()

            if mock.call_count == 2:
                return True

            raise ValueError("try again, but only once")

        @flow
        def test_flow():
            future = flaky_function()
            return future.run_id

        flow_future = test_flow()
        task_run_id = flow_future.result().data

        assert sleep.call_count == 1
        # due to rounding, the expected sleep time will be less than 43 seconds
        # we test for a 3-second window to account for delays in CI
        assert 40 < sleep.call_args[0][0] < 43

        async with OrionClient() as client:
            states = await client.read_task_run_states(task_run_id)
        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Awaiting Retry",
            "Running",
            "Completed",
        ]


class TestTaskCaching:
    def test_repeated_task_call_within_flow_is_not_cached_by_default(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1).result(), foo(1).result()

        flow_future = bar()
        first_state, second_state = flow_future.result().data
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert second_state.data == first_state.data

    def test_cache_hits_within_flows_are_cached(self):
        @task(cache_key_fn=lambda *_: "cache hit")
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1).result(), foo(2).result()

        flow_future = bar()
        first_state, second_state = flow_future.result().data
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert second_state.data == first_state.data

    def test_many_repeated_cache_hits_within_flows_cached(self):
        @task(cache_key_fn=lambda *_: "cache hit")
        def foo(x):
            return x

        @flow
        def bar():
            foo(1)
            calls = repeat(foo(1), 5)
            return [call.result() for call in calls]

        flow_future = bar()
        states = flow_future.result().data
        assert all(state.name == "Cached" for state in states)

    def test_cache_hits_between_flows_are_cached(self):
        @task(cache_key_fn=lambda *_: "cache hit")
        def foo(x):
            return x

        @flow
        def bar(x):
            return foo(x).result()

        first_state = bar(1).result()
        second_state = bar(2).result()
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert second_state.data == first_state.data

    def test_cache_misses_arent_cached(self):

        # this hash fn won't return the same value twice
        def mutating_key(*_, tally=[]):
            tally.append("x")
            return "call tally:" + "".join(tally)

        @task(cache_key_fn=mutating_key)
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1).result(), foo(1).result()

        flow_future = bar()
        first_state, second_state = flow_future.result().data
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"

    def test_cache_key_fn_context(self):
        def stringed_context(context, args):
            return str(context.flow_run_id)

        @task(cache_key_fn=stringed_context)
        def foo(x):
            return x

        @flow
        def bar():
            return foo("something").result(), foo("different").result()

        first_future = bar()
        first_state, second_state = first_future.result().data
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert second_state.data == first_state.data

        second_future = bar()
        third_state, fourth_state = second_future.result().data
        assert third_state.name == "Completed"
        assert fourth_state.name == "Cached"
        assert fourth_state.data == first_state.data

    def test_cache_key_fn_arg_inputs_are_stable(self):
        def stringed_inputs(context, args):
            return str(args)

        @task(cache_key_fn=stringed_inputs)
        def foo(a, b, c=3):
            return a + b + c

        @flow
        def bar():
            return (
                foo(1, 2, 3).result(),
                foo(1, b=2).result(),
                foo(c=3, a=1, b=2).result(),
            )

        flow_future = bar()
        first_state, second_state, third_state = flow_future.result().data
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert third_state.name == "Cached"

        assert second_state.data == first_state.data
        assert third_state.data == first_state.data

    def test_cache_key_hits_with_future_expiration_are_cached(self):
        @task(
            cache_key_fn=lambda *_: "cache hit",
            cache_expiration=datetime.timedelta(seconds=5),
        )
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1).result(), foo(2).result()

        flow_future = bar()
        first_state, second_state = flow_future.result().data
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert second_state.data == first_state.data

    def test_cache_key_hits_with_past_expiration_are_not_cached(self):
        @task(
            cache_key_fn=lambda *_: "cache hit",
            cache_expiration=datetime.timedelta(seconds=-5),
        )
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1).result(), foo(2).result()

        flow_future = bar()
        first_state, second_state = flow_future.result().data
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert second_state.data != first_state.data


class TestCacheFunctionBuiltins:
    def test_task_input_hash_within_flows(self):
        @task(cache_key_fn=task_input_hash)
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1).result(), foo(2).result(), foo(1).result()

        flow_future = bar()
        first_state, second_state, third_state = flow_future.result().data
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"
        assert first_state.data != second_state.data
        assert first_state.data == third_state.data

    def test_task_input_hash_between_flows(self):
        @task(cache_key_fn=task_input_hash)
        def foo(x):
            return x

        @flow
        def bar(x):
            return foo(x).result()

        first_state = bar(1).result()
        second_state = bar(2).result()
        third_state = bar(1).result()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"
        assert first_state.data != second_state.data
        assert first_state.data == third_state.data
