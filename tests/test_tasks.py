import datetime
from itertools import repeat
from unittest.mock import MagicMock

import pytest

from prefect import flow, get_result, tags
from prefect.engine import raise_failed_state
from prefect.client import OrionClient
from prefect.orion.schemas.states import State, StateType
from prefect.orion.schemas.data import DataDocument
from prefect.tasks import task, task_input_hash
from prefect.utilities.testing import exceptions_equal


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

        flow_state = bar()
        task_state = get_result(flow_state)
        assert isinstance(task_state, State)
        assert get_result(task_state) == 1

    async def test_async_task_called_inside_async_flow(self):
        @task
        async def foo(x):
            return x

        @flow
        async def bar():
            return await foo(1)

        flow_state = await bar()
        task_state = await get_result(flow_state)
        assert isinstance(task_state, State)
        assert await get_result(task_state) == 1

    async def test_sync_task_called_inside_async_flow(self):
        @task
        def foo(x):
            return x

        @flow
        async def bar():
            return foo(1)

        flow_state = await bar()
        task_state = await get_result(flow_state)
        assert isinstance(task_state, State)
        assert await get_result(task_state) == 1

    def test_async_task_called_inside_sync_flow_raises_clear_error(self):
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
            raise_failed_state(bar())

    @pytest.mark.parametrize("error", [ValueError("Hello"), None])
    def test_final_state_reflects_exceptions_during_run(self, error):
        @task
        def bar():
            if error:
                raise error

        @flow(version="test")
        def foo():
            return bar()

        flow_state = foo()
        task_state = get_result(flow_state, raise_failures=False)

        # Assert the final state is correct
        assert task_state.is_failed() if error else task_state.is_completed()
        result = get_result(task_state, raise_failures=False)
        assert exceptions_equal(result, error)

    def test_final_task_state_respects_returned_state(sel):
        @task
        def bar():
            return State(
                type=StateType.FAILED,
                message="Test returned state",
                data=DataDocument.encode("json", True),
            )

        @flow(version="test")
        def foo():
            return bar()

        flow_state = foo()
        task_state = get_result(flow_state, raise_failures=False)

        # Assert the final state is correct
        assert task_state.is_failed()
        assert get_result(task_state, raise_failures=False) is True
        assert task_state.message == "Test returned state"

    async def test_task_runs_correctly_populate_dynamic_keys(self):
        @task
        def bar():
            return "foo"

        @flow(version="test")
        def foo():
            return bar().run_id, bar().run_id

        flow_state = foo()
        task_run_ids = await get_result(flow_state)

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

        flow_state = test_flow()
        task_state = get_result(flow_state)
        assert get_result(task_state) == 2


class TestTaskRetries:
    """
    Note, task retry delays are tested in `test_engine` because we need to mock the
    sleep call which requires a task run id before the task is called.
    """

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
            return future.run_id, future.wait()

        flow_state = test_flow()
        task_run_id, task_run_state = await get_result(flow_state)

        if always_fail:
            assert task_run_state.is_failed()
            assert exceptions_equal(
                await get_result(task_run_state, raise_failures=False), exc
            )
            assert mock.call_count == 4
        else:
            assert task_run_state.is_completed()
            assert await get_result(task_run_state) is True
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
            return future.run_id, future.wait()

        flow_state = test_flow()
        task_run_id, task_run_state = await get_result(flow_state)

        assert task_run_state.is_completed()
        assert await get_result(task_run_state) is True
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


class TestTaskCaching:
    def test_repeated_task_call_within_flow_is_not_cached_by_default(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1).wait(), foo(1).wait()

        flow_state = bar()
        first_state, second_state = get_result(flow_state)
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert get_result(second_state) == get_result(first_state)

    def test_cache_hits_within_flows_are_cached(self):
        @task(cache_key_fn=lambda *_: "cache hit")
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1).wait(), foo(2).wait()

        flow_state = bar()
        first_state, second_state = get_result(flow_state)
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert get_result(second_state) == get_result(first_state)

    def test_many_repeated_cache_hits_within_flows_cached(self):
        @task(cache_key_fn=lambda *_: "cache hit")
        def foo(x):
            return x

        @flow
        def bar():
            foo(1)
            calls = repeat(foo(1), 5)
            return [call.wait() for call in calls]

        flow_state = bar()
        states = get_result(flow_state)
        assert all(state.name == "Cached" for state in states)

    def test_cache_hits_between_flows_are_cached(self):
        @task(cache_key_fn=lambda *_: "cache hit")
        def foo(x):
            return x

        @flow
        def bar(x):
            return foo(x).wait()

        first_state = bar(1)
        second_state = bar(2)
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert get_result(second_state) == get_result(first_state)

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
            return foo(1).wait(), foo(1).wait()

        flow_state = bar()
        first_state, second_state = get_result(flow_state)
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
            return foo("something").wait(), foo("different").wait()

        first_state, second_state = get_result(bar())
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert get_result(second_state) == get_result(first_state)

        third_state, fourth_state = get_result(bar())
        assert third_state.name == "Completed"
        assert fourth_state.name == "Cached"
        assert get_result(fourth_state) == get_result(first_state)

    def test_cache_key_fn_arg_inputs_are_stable(self):
        def stringed_inputs(context, args):
            return str(args)

        @task(cache_key_fn=stringed_inputs)
        def foo(a, b, c=3):
            return a + b + c

        @flow
        def bar():
            return (
                foo(1, 2, 3).wait(),
                foo(1, b=2).wait(),
                foo(c=3, a=1, b=2).wait(),
            )

        flow_state = bar()
        first_state, second_state, third_state = get_result(flow_state)
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert third_state.name == "Cached"

        assert get_result(second_state) == get_result(first_state)
        assert get_result(third_state) == get_result(first_state)

    def test_cache_key_hits_with_future_expiration_are_cached(self):
        @task(
            cache_key_fn=lambda *_: "cache hit",
            cache_expiration=datetime.timedelta(seconds=5),
        )
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1).wait(), foo(2).wait()

        flow_state = bar()
        first_state, second_state = get_result(flow_state)
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert get_result(second_state) == get_result(first_state)

    def test_cache_key_hits_with_past_expiration_are_not_cached(self):
        @task(
            cache_key_fn=lambda *_: "cache hit",
            cache_expiration=datetime.timedelta(seconds=-5),
        )
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1).wait(), foo(2).wait()

        flow_state = bar()
        first_state, second_state = get_result(flow_state)
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert get_result(second_state) != get_result(first_state)


class TestCacheFunctionBuiltins:
    def test_task_input_hash_within_flows(self):
        @task(cache_key_fn=task_input_hash)
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1).wait(), foo(2).wait(), foo(1).wait()

        flow_state = bar()
        first_state, second_state, third_state = get_result(flow_state)
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"
        assert get_result(first_state) != get_result(second_state)
        assert get_result(first_state) == get_result(third_state)

    def test_task_input_hash_between_flows(self):
        @task(cache_key_fn=task_input_hash)
        def foo(x):
            return x

        @flow
        def bar(x):
            return foo(x).wait()

        first_state = bar(1)
        second_state = bar(2)
        third_state = bar(1)
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"
        assert get_result(first_state) != get_result(second_state)
        assert get_result(first_state) == get_result(third_state)


class TestTaskRunTags:
    async def test_task_run_tags_added_at_call(self, orion_client):
        @flow
        def my_flow():
            with tags("a", "b"):
                future = my_task()

            return future

        @task
        def my_task():
            pass

        task_state = await get_result(my_flow())
        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b"}

    async def test_task_run_tags_include_tags_on_task_object(self, orion_client):
        @flow
        def my_flow():
            with tags("c", "d"):
                future = my_task()

            return future

        @task(tags={"a", "b"})
        def my_task():
            pass

        task_state = await get_result(my_flow())
        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b", "c", "d"}

    async def test_task_run_tags_include_flow_run_tags(self, orion_client):
        @flow
        def my_flow():
            with tags("c", "d"):
                future = my_task()

            return future

        @task
        def my_task():
            pass

        with tags("a", "b"):
            task_state = await get_result(my_flow())

        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b", "c", "d"}

    async def test_task_run_tags_not_added_outside_context(self, orion_client):
        @flow
        def my_flow():
            with tags("a", "b"):
                my_task()
            future = my_task()

            return future

        @task
        def my_task():
            pass

        task_state = await get_result(my_flow())
        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert not task_run.tags

    @pytest.mark.parametrize("include_existing", [True, False])
    async def test_task_run_tags_respects_include_existing(self, orion_client, include_existing):
        @flow
        def my_flow():
            with tags("a", "b"):
                with tags("c", "d", include_existing=False):
                    future = my_task()

            return future

        @task
        def my_task():
            pass

        task_state = await get_result(my_flow())
        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"c", "d"}
