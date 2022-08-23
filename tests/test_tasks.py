import datetime
import inspect
import warnings
from unittest.mock import MagicMock

import anyio
import pytest

from prefect import flow, get_run_logger, tags
from prefect.context import PrefectObjectRegistry
from prefect.engine import get_state_for_result
from prefect.exceptions import (
    MappingLengthMismatch,
    MappingMissingIterable,
    ReservedArgumentError,
)
from prefect.futures import PrefectFuture
from prefect.orion.schemas.core import TaskRunResult
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import State, StateType
from prefect.tasks import Task, task, task_input_hash
from prefect.testing.utilities import exceptions_equal, flaky_on_windows
from prefect.utilities.annotations import unmapped
from prefect.utilities.collections import quote


def comparable_inputs(d):
    return {k: set(v) for k, v in d.items()}


class TestTaskName:
    def test_name_from_function(self):
        @task
        def my_task():
            pass

        assert my_task.name == "my_task"

    def test_name_from_kwarg(self):
        @task(name="another_name")
        def my_task():
            pass

        assert my_task.name == "another_name"


class TestTaskCall:
    def test_task_called_outside_flow_raises(self):
        @task
        def foo():
            pass

        with pytest.raises(RuntimeError, match="Tasks cannot be run outside of a flow"):
            foo()

    def test_sync_task_called_inside_sync_flow(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1)

        assert bar() == 1

    async def test_async_task_called_inside_async_flow(self):
        @task
        async def foo(x):
            return x

        @flow
        async def bar():
            return await foo(1)

        assert await bar() == 1

    async def test_sync_task_called_inside_async_flow(self):
        @task
        def foo(x):
            return x

        @flow
        async def bar():
            return foo(1)

        assert await bar() == 1

    def test_async_task_called_inside_sync_flow(self):
        @task
        async def foo(x):
            return x

        @flow
        def bar():
            return foo(1)

        assert bar() == 1

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

        assert test_flow() == 2

    def test_task_with_variadic_args(self):
        @task
        def foo(*foo, bar):
            return foo, bar

        @flow
        def test_flow():
            return foo(1, 2, 3, bar=4)

        assert test_flow() == ((1, 2, 3), 4)

    def test_task_with_variadic_keyword_args(self):
        @task
        def foo(foo, bar, **foobar):
            return foo, bar, foobar

        @flow
        def test_flow():
            return foo(1, 2, x=3, y=4, z=5)

        assert test_flow() == (1, 2, dict(x=3, y=4, z=5))

    def test_task_failure_raises_in_flow(self):
        @task
        def foo():
            raise ValueError("Test")

        @flow
        def bar():
            foo()
            return "bar"

        state = bar._run()
        assert state.is_failed()
        with pytest.raises(ValueError, match="Test"):
            state.result()


class TestTaskRun:
    def test_task_run_outside_flow_raises(self):
        @task
        def foo():
            pass

        with pytest.raises(RuntimeError, match="Tasks cannot be run outside of a flow"):
            foo()

    def test_sync_task_run_inside_sync_flow(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            return foo._run(1)

        task_state = bar()
        assert isinstance(task_state, State)
        assert task_state.result() == 1

    async def test_async_task_run_inside_async_flow(self):
        @task
        async def foo(x):
            return x

        @flow
        async def bar():
            return await foo._run(1)

        task_state = await bar()
        assert isinstance(task_state, State)
        assert task_state.result() == 1

    async def test_sync_task_run_inside_async_flow(self):
        @task
        def foo(x):
            return x

        @flow
        async def bar():
            return foo._run(1)

        task_state = await bar()
        assert isinstance(task_state, State)
        assert task_state.result() == 1

    def test_async_task_run_inside_sync_flow(self):
        @task
        async def foo(x):
            return x

        @flow
        def bar():
            return foo._run(1)

        task_state = bar()
        assert isinstance(task_state, State)
        assert task_state.result() == 1

    def test_task_failure_does_not_affect_flow(self):
        @task
        def foo():
            raise ValueError("Test")

        @flow
        def bar():
            foo._run()
            return "bar"

        assert bar() == "bar"

    def test_task_with_return_state_true(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1, return_state=True)

        task_state = bar()
        assert isinstance(task_state, State)
        assert task_state.result() == 1


class TestTaskSubmit:
    def test_task_submitted_outside_flow_raises(self):
        @task
        def foo():
            pass

        with pytest.raises(RuntimeError, match="Tasks cannot be run outside of a flow"):
            foo()

    def test_sync_task_submitted_inside_sync_flow(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            future = foo.submit(1)
            assert isinstance(future, PrefectFuture)
            return future

        task_state = bar()
        assert task_state.result() == 1

    def test_sync_task_with_return_state_true(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            state = foo.submit(1, return_state=True)
            assert isinstance(state, State)
            return state

        task_state = bar()
        assert task_state.result() == 1

    async def test_async_task_submitted_inside_async_flow(self):
        @task
        async def foo(x):
            return x

        @flow
        async def bar():
            future = await foo.submit(1)
            assert isinstance(future, PrefectFuture)
            return future

        task_state = await bar()
        assert task_state.result() == 1

    async def test_sync_task_submitted_inside_async_flow(self):
        @task
        def foo(x):
            return x

        @flow
        async def bar():
            future = foo.submit(1)
            assert isinstance(future, PrefectFuture)
            return future

        task_state = await bar()
        assert task_state.result() == 1

    def test_async_task_submitted_inside_sync_flow(self):
        @task
        async def foo(x):
            return x

        @flow
        def bar():
            future = foo.submit(1)
            assert isinstance(future, PrefectFuture)
            return future

        task_state = bar()
        assert task_state.result() == 1

    def test_task_failure_does_not_affect_flow(self):
        @task
        def foo():
            raise ValueError("Test")

        @flow
        def bar():
            foo.submit()
            return "bar"

        assert bar() == "bar"


class TestTaskStates:
    @pytest.mark.parametrize("error", [ValueError("Hello"), None])
    def test_final_state_reflects_exceptions_during_run(self, error):
        @task
        def bar():
            if error:
                raise error

        @flow(version="test")
        def foo():
            return quote(bar._run())

        task_state = foo().unquote()

        # Assert the final state is correct
        assert task_state.is_failed() if error else task_state.is_completed()
        assert exceptions_equal(task_state.result(raise_on_failure=False), error)

    def test_final_task_state_respects_returned_state(self):
        @task
        def bar():
            return State(
                type=StateType.FAILED,
                message="Test returned state",
                data=DataDocument.encode("json", True),
            )

        @flow(version="test")
        def foo():
            return quote(bar._run())

        task_state = foo().unquote()

        # Assert the final state is correct
        assert task_state.is_failed()
        assert task_state.result(raise_on_failure=False) is True
        assert task_state.message == "Test returned state"


class TestTaskVersion:
    def test_task_version_defaults_to_null(self):
        @task
        def my_task():
            pass

        assert my_task.version is None

    def test_task_version_can_be_provided(self):
        @task(version="test-dev-experimental")
        def my_task():
            pass

        assert my_task.version == "test-dev-experimental"

    async def test_task_version_is_set_in_backend(self, orion_client):
        @task(version="test-dev-experimental")
        def my_task():
            pass

        @flow
        def test():
            return my_task._run()

        task_state = test()
        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert task_run.task_version == "test-dev-experimental"


class TestTaskFutures:
    async def test_wait_gets_final_state(self, orion_client):
        @task
        async def foo():
            return 1

        @flow
        async def my_flow():
            future = await foo.submit()
            state = await future.wait()

            assert state.is_completed()

            # TODO: The ids are not equal here, why?
            # task_run = await orion_client.read_task_run(state.state_details.task_run_id)
            # assert task_run.state.dict(exclude={"data"}) == state.dict(exclude={"data"})

        await my_flow()

    async def test_wait_returns_none_with_timeout_exceeded(self):
        @task
        async def foo():
            await anyio.sleep(0.1)
            return 1

        @flow
        async def my_flow():
            future = await foo.submit()
            state = await future.wait(0.01)
            assert state is None

        await my_flow()

    async def test_wait_returns_final_state_with_timeout_not_exceeded(self):
        @task
        async def foo():
            return 1

        @flow
        async def my_flow():
            future = await foo.submit()
            state = await future.wait(5)
            assert state is not None
            assert state.is_completed()

        await my_flow()

    async def test_result_raises_with_timeout_exceeded(self):
        @task
        async def foo():
            await anyio.sleep(0.1)
            return 1

        @flow
        async def my_flow():
            future = await foo.submit()
            with pytest.raises(TimeoutError):
                await future.result(timeout=0.01)

        await my_flow()

    async def test_result_returns_data_with_timeout_not_exceeded(self):
        @task
        async def foo():
            return 1

        @flow
        async def my_flow():
            future = await foo.submit()
            result = await future.result(timeout=5)
            assert result == 1

        await my_flow()

    async def test_result_returns_data_without_timeout(self):
        @task
        async def foo():
            return 1

        @flow
        async def my_flow():
            future = await foo.submit()
            result = await future.result()
            assert result == 1

        await my_flow()

    async def test_result_raises_exception_from_task(self):
        @task
        async def foo():
            raise ValueError("Test")

        @flow
        async def my_flow():
            future = await foo.submit()
            with pytest.raises(ValueError, match="Test"):
                await future.result()
            return True  # Ignore failed tasks

        await my_flow()

    async def test_result_returns_exception_from_task_if_asked(self):
        @task
        async def foo():
            raise ValueError("Test")

        @flow
        async def my_flow():
            future = await foo.submit()
            result = await future.result(raise_on_failure=False)
            assert exceptions_equal(result, ValueError("Test"))
            return True  # Ignore failed tasks

        await my_flow()

    async def test_async_tasks_in_sync_flows_return_sync_futures(self):
        data = {"value": 1}

        @task
        async def get_data():
            return data

        # note this flow is purposely not async
        @flow
        def test_flow():
            future = get_data.submit()
            assert not future.asynchronous, "The async task should return a sync future"
            result = future.result()
            assert result == data, "Retrieving the result returns data"
            return result

        assert test_flow() == data


class TestTaskRetries:
    """
    Note, task retry delays are tested in `test_engine` because we need to mock the
    sleep call which requires a task run id before the task is called.
    """

    @pytest.mark.parametrize("always_fail", [True, False])
    async def test_task_respects_retry_count(self, always_fail, orion_client):
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
            future = flaky_function.submit()
            return future.task_run.id, future.wait()

        task_run_id, task_run_state = test_flow()

        if always_fail:
            assert task_run_state.is_failed()
            assert exceptions_equal(task_run_state.result(raise_on_failure=False), exc)
            assert mock.call_count == 4
        else:
            assert task_run_state.is_completed()
            assert task_run_state.result() is True
            assert mock.call_count == 4

        states = await orion_client.read_task_run_states(task_run_id)

        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "AwaitingRetry",
            "Retrying",
            "AwaitingRetry",
            "Retrying",
            "AwaitingRetry",
            "Retrying",
            "Failed" if always_fail else "Completed",
        ]

    async def test_task_only_uses_necessary_retries(self, orion_client):
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
            future = flaky_function.submit()
            return future.task_run.id, future.wait()

        task_run_id, task_run_state = test_flow()

        assert task_run_state.is_completed()
        assert task_run_state.result() is True
        assert mock.call_count == 2

        states = await orion_client.read_task_run_states(task_run_id)
        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "AwaitingRetry",
            "Retrying",
            "Completed",
        ]


class TestTaskCaching:
    def test_repeated_task_call_within_flow_is_not_cached_by_default(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            return foo._run(1), foo._run(1)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert second_state.result() == first_state.result()

    def test_cache_hits_within_flows_are_cached(self):
        @task(cache_key_fn=lambda *_: "cache hit")
        def foo(x):
            return x

        @flow
        def bar():
            return foo._run(1), foo._run(2)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert second_state.result() == first_state.result()

    def test_many_repeated_cache_hits_within_flows_cached(self):
        @task(cache_key_fn=lambda *_: "cache hit")
        def foo(x):
            return x

        @flow
        def bar():
            foo._run(1)  # populate the cache
            return [foo._run(i) for i in range(5)]

        states = bar()
        assert all(state.name == "Cached" for state in states), states

    def test_cache_hits_between_flows_are_cached(self):
        @task(cache_key_fn=lambda *_: "cache hit")
        def foo(x):
            return x

        @flow
        def bar(x):
            return foo._run(x)

        first_state = bar(1)
        second_state = bar(2)
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert second_state.result() == first_state.result() == 1

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
            return foo._run(1), foo._run(1)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"

    def test_cache_key_fn_receives_context(self):
        def get_flow_run_id(context, args):
            return str(context.task_run.flow_run_id)

        @task(cache_key_fn=get_flow_run_id)
        def foo(x):
            return x

        @flow
        def bar():
            return foo._run("something"), foo._run("different")

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert first_state.result() == "something"

        assert second_state.name == "Cached"
        assert second_state.result() == "something"

        third_state, fourth_state = bar()
        assert third_state.name == "Completed"
        assert fourth_state.name == "Cached"
        assert third_state.result() == "something"
        assert fourth_state.result() == "something"

    def test_cache_key_fn_receives_resolved_futures(self):
        def check_args(context, params):
            assert params["x"] == "something"
            assert len(params) == 1
            return params["x"]

        @task
        def foo(x):
            return x

        @task(cache_key_fn=check_args)
        def bar(x):
            return x

        @flow
        def my_flow():
            future = foo.submit("something")
            # Mix run/submit to cover both cases
            return bar._run(future), bar.submit(future).wait()

        first_state, second_state = my_flow()
        assert first_state.name == "Completed"
        assert first_state.result() == "something"

        assert second_state.name == "Cached"
        assert second_state.result() == "something"

    def test_cache_key_fn_arg_inputs_are_stable(self):
        def stringed_inputs(context, args):
            return str(args)

        @task(cache_key_fn=stringed_inputs)
        def foo(a, b, c=3):
            return a + b + c

        @flow
        def bar():
            return (
                foo._run(1, 2, 3),
                foo._run(1, b=2),
                foo._run(c=3, a=1, b=2),
            )

        first_state, second_state, third_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert third_state.name == "Cached"

        # same output
        assert first_state.result() == 6
        assert second_state.result() == 6
        assert third_state.result() == 6

    @flaky_on_windows
    def test_cache_key_hits_with_future_expiration_are_cached(self):
        @task(
            cache_key_fn=lambda *_: "cache hit",
            cache_expiration=datetime.timedelta(seconds=5),
        )
        def foo(x):
            return x

        @flow
        def bar():
            return foo._run(1), foo._run(2)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert second_state.result() == 1

    def test_cache_key_hits_with_past_expiration_are_not_cached(self):
        @task(
            cache_key_fn=lambda *_: "cache hit",
            cache_expiration=datetime.timedelta(seconds=-5),
        )
        def foo(x):
            return x

        @flow
        def bar():
            return foo._run(1), foo._run(2)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert second_state.result() != first_state.result()


class TestCacheFunctionBuiltins:
    def test_task_input_hash_within_flows(self):
        @task(cache_key_fn=task_input_hash)
        def foo(x):
            return x

        @flow
        def bar():
            return foo._run(1), foo._run(2), foo._run(1)

        first_state, second_state, third_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"

        assert first_state.result() != second_state.result()
        assert first_state.result() == third_state.result()
        assert first_state.result() == 1

    def test_task_input_hash_between_flows(self):
        @task(cache_key_fn=task_input_hash)
        def foo(x):
            return x

        @flow
        def bar(x):
            return foo._run(x)

        first_state = bar(1)
        second_state = bar(2)
        third_state = bar(1)
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"
        assert first_state.result() != second_state.result()
        assert first_state.result() == third_state.result() == 1

    def test_task_input_hash_works_with_object_return_types(self):
        """
        This is a regression test for a weird bug where `task_input_hash` would always
        use cloudpickle to generate the hash since we were passing in the raw function
        which is not JSON serializable. In this case, the return value could affect
        the pickle which would change the hash across runs. To fix this,
        `task_input_hash` hashes the function before passing data to `hash_objects` so
        the JSON serializer can be used.
        """

        class TestClass:
            def __init__(self, x):
                self.x = x

            def __eq__(self, other) -> bool:
                return type(self) == type(other) and self.x == other.x

        @task(cache_key_fn=task_input_hash)
        def foo(x):
            return TestClass(x)

        @flow
        def bar():
            return foo._run(1), foo._run(2), foo._run(1)

        first_state, second_state, third_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"

        assert first_state.result() != second_state.result()
        assert first_state.result() == third_state.result()

    def test_task_input_hash_works_with_object_input_types(self):
        class TestClass:
            def __init__(self, x):
                self.x = x

            def __eq__(self, other) -> bool:
                return type(self) == type(other) and self.x == other.x

        @task(cache_key_fn=task_input_hash)
        def foo(instance):
            return instance.x

        @flow
        def bar():
            return (
                foo._run(TestClass(1)),
                foo._run(TestClass(2)),
                foo._run(TestClass(1)),
            )

        first_state, second_state, third_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"

        assert first_state.result() != second_state.result()
        assert first_state.result() == third_state.result() == 1

    def test_task_input_hash_depends_on_task_key_and_code(self):
        @task(cache_key_fn=task_input_hash)
        def foo(x):
            return x

        def foo_new_code(x):
            return x + 1

        def foo_same_code(x):
            return x

        @task(cache_key_fn=task_input_hash)
        def bar(x):
            return x

        @flow
        def my_flow():
            first = foo._run(1)
            foo.fn = foo_same_code
            second = foo._run(1)
            foo.fn = foo_new_code
            third = foo._run(1)
            fourth = bar._run(1)
            fifth = bar._run(1)
            return first, second, third, fourth, fifth

        (
            first_state,
            second_state,
            third_state,
            fourth_state,
            fifth_state,
        ) = my_flow()
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert third_state.name == "Completed"
        assert fourth_state.name == "Completed"
        assert fifth_state.name == "Cached"

        assert first_state.result() == second_state.result() == 1
        assert first_state.result() != third_state.result()
        assert fourth_state.result() == fifth_state.result() == 1


class TestTaskRunTags:
    async def test_task_run_tags_added_at_submission(self, orion_client):
        @flow
        def my_flow():
            with tags("a", "b"):
                future = my_task.submit()

            return future

        @task
        def my_task():
            pass

        task_state = my_flow()
        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b"}

    async def test_task_run_tags_added_at_run(self, orion_client):
        @flow
        def my_flow():
            with tags("a", "b"):
                state = my_task._run()

            return state

        @task
        def my_task():
            pass

        task_state = my_flow()
        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b"}

    async def test_task_run_tags_added_at_call(self, orion_client):
        @flow
        def my_flow():
            with tags("a", "b"):
                result = my_task()

            return get_state_for_result(result)

        @task
        def my_task():
            return "foo"

        task_state = my_flow()
        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b"}

    async def test_task_run_tags_include_tags_on_task_object(self, orion_client):
        @flow
        def my_flow():
            with tags("c", "d"):
                state = my_task._run()

            return state

        @task(tags={"a", "b"})
        def my_task():
            pass

        task_state = my_flow()
        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b", "c", "d"}

    async def test_task_run_tags_include_flow_run_tags(self, orion_client):
        @flow
        def my_flow():
            with tags("c", "d"):
                state = my_task._run()

            return state

        @task
        def my_task():
            pass

        with tags("a", "b"):
            task_state = my_flow()

        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b", "c", "d"}

    async def test_task_run_tags_not_added_outside_context(self, orion_client):
        @flow
        def my_flow():
            with tags("a", "b"):
                my_task()
            state = my_task._run()

            return state

        @task
        def my_task():
            pass

        task_state = my_flow()
        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert not task_run.tags

    async def test_task_run_tags_respects_nesting(self, orion_client):
        @flow
        def my_flow():
            with tags("a", "b"):
                with tags("c", "d"):
                    state = my_task._run()

            return state

        @task
        def my_task():
            pass

        task_state = my_flow()
        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b", "c", "d"}


class TestTaskInputs:
    """Tests relationship tracking between tasks"""

    @pytest.fixture
    def flow_with_upstream_downstream(self):
        @task
        def upstream(result):
            return result

        @task
        def downstream(value):
            return value

        @flow
        def upstream_downstream_flow(result):
            upstream_state = upstream._run(result)
            downstream_state = downstream._run(upstream_state.result())
            return upstream_state, downstream_state

        return upstream_downstream_flow

    async def test_task_inputs_populated_with_no_upstreams(self, orion_client):
        @task
        def foo(x):
            return x

        @flow
        def test_flow():
            return foo.submit(1)

        flow_state = test_flow._run()
        x = flow_state.result()

        task_run = await orion_client.read_task_run(x.state_details.task_run_id)

        assert task_run.task_inputs == dict(x=[])

    async def test_task_inputs_populated_with_no_upstreams_and_multiple_parameters(
        self, orion_client
    ):
        @task
        def foo(x, *a, **k):
            return x

        @flow
        def test_flow():
            return foo.submit(1)

        flow_state = test_flow._run()
        x = flow_state.result()

        task_run = await orion_client.read_task_run(x.state_details.task_run_id)

        assert task_run.task_inputs == dict(x=[], a=[], k=[])

    async def test_task_inputs_populated_with_one_upstream_positional_future(
        self, orion_client
    ):
        @task
        def foo(x):
            return x

        @task
        def bar(x, y):
            return x + y

        @flow
        def test_flow():
            a = foo.submit(1)
            b = foo.submit(2)
            c = bar._run(a, 1)
            return a, b, c

        flow_state = test_flow._run()
        a, b, c = flow_state.result()

        task_run = await orion_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[],
        )

    async def test_task_inputs_populated_with_one_upstream_keyword_future(
        self, orion_client
    ):
        @task
        def foo(x):
            return x

        @task
        def bar(x, y):
            return x + y

        @flow
        def test_flow():
            a = foo.submit(1)
            b = foo.submit(2)
            c = bar._run(x=a, y=1)
            return a, b, c

        flow_state = test_flow._run()
        a, b, c = flow_state.result()

        task_run = await orion_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[],
        )

    async def test_task_inputs_populated_with_two_upstream_futures(self, orion_client):
        @task
        def foo(x):
            return x

        @task
        def bar(x, y):
            return x + y

        @flow
        def test_flow():
            a = foo.submit(1)
            b = foo.submit(2)
            c = bar._run(a, b)
            return a, b, c

        flow_state = test_flow._run()
        a, b, c = flow_state.result()

        task_run = await orion_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[TaskRunResult(id=b.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_two_upstream_futures_from_same_task(
        self, orion_client
    ):
        @task
        def foo(x):
            return x

        @task
        def bar(x, y):
            return x + y

        @flow
        def test_flow():
            a = foo.submit(1)
            c = bar._run(a, a)
            return a, c

        flow_state = test_flow._run()
        a, c = flow_state.result()

        task_run = await orion_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[TaskRunResult(id=a.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_nested_upstream_futures(
        self, orion_client
    ):
        @task
        def foo(x):
            return x

        @task
        def bar(x, y):
            return x, y

        @flow
        def test_flow():
            a = foo.submit(1)
            b = foo.submit(2)
            c = foo.submit(3)
            d = bar._run([a, a, b], {3: b, 4: {5: {c, 4}}})
            return a, b, c, d

        flow_state = test_flow._run()

        a, b, c, d = flow_state.result()

        task_run = await orion_client.read_task_run(d.state_details.task_run_id)

        assert comparable_inputs(task_run.task_inputs) == dict(
            x={
                TaskRunResult(id=a.state_details.task_run_id),
                TaskRunResult(id=b.state_details.task_run_id),
            },
            y={
                TaskRunResult(id=b.state_details.task_run_id),
                TaskRunResult(id=c.state_details.task_run_id),
            },
        )

    async def test_task_inputs_populated_with_subflow_upstream(self, orion_client):
        @task
        def foo(x):
            return x

        @flow
        def child(x):
            return x

        @flow
        def parent():
            child_state = child._run(1)
            return child_state, foo.submit(child_state)

        parent_state = parent._run()
        child_state, task_state = parent_state.result()

        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=child_state.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_result_upstream(self, orion_client):
        @task
        def name():
            return "Fred"

        @task
        def say_hi(name):
            return f"Hi {name}"

        @flow
        def test_flow():
            my_name = name._run()
            hi = say_hi._run(my_name.result())
            return my_name, hi

        flow_state = test_flow._run()
        name_state, hi_state = flow_state.result()

        task_run = await orion_client.read_task_run(hi_state.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            name=[TaskRunResult(id=name_state.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_result_upstream_from_future(
        self, orion_client
    ):
        @task
        def upstream(x):
            return x

        @task
        def downstream(x):
            return x

        @flow
        def test_flow():
            upstream_future = upstream.submit(257)
            upstream_result = upstream_future.result()
            downstream_state = downstream._run(upstream_result)
            upstream_state = upstream_future.wait()
            return upstream_state, downstream_state

        upstream_state, downstream_state = test_flow()

        task_run = await orion_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_result_upstream_from_state(
        self, orion_client
    ):
        @task
        def upstream(x):
            return x

        @task
        def downstream(x):
            return x

        @flow
        def test_flow():
            upstream_state = upstream._run(1)
            upstream_result = upstream_state.result()
            downstream_state = downstream._run(upstream_result)
            return upstream_state, downstream_state

        upstream_state, downstream_state = test_flow()

        task_run = await orion_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

    async def test_task_inputs_populated_with_state_upstream(self, orion_client):
        @task
        def upstream(x):
            return x

        @task
        def downstream(x):
            return x

        @flow
        def test_flow():
            upstream_state = upstream._run(1)
            downstream_state = downstream._run(upstream_state)
            return upstream_state, downstream_state

        upstream_state, downstream_state = test_flow()

        task_run = await orion_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    @pytest.mark.parametrize("result", [["Fred"], {"one": 1}, {1, 2, 2}, (1, 2)])
    async def test_task_inputs_populated_with_collection_result_upstream(
        self, result, orion_client, flow_with_upstream_downstream
    ):
        flow_state = flow_with_upstream_downstream._run(result)
        upstream_state, downstream_state = flow_state.result()

        task_run = await orion_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            value=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    @pytest.mark.parametrize("result", ["Fred", 5.1])
    async def test_task_inputs_populated_with_basic_result_types_upstream(
        self, result, orion_client, flow_with_upstream_downstream
    ):
        flow_state = flow_with_upstream_downstream._run(result)
        upstream_state, downstream_state = flow_state.result()

        task_run = await orion_client.read_task_run(
            downstream_state.state_details.task_run_id
        )
        assert task_run.task_inputs == dict(
            value=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    @pytest.mark.parametrize("result", [True, False, None, ..., NotImplemented])
    async def test_task_inputs_not_populated_with_singleton_results_upstream(
        self, result, orion_client, flow_with_upstream_downstream
    ):
        flow_state = flow_with_upstream_downstream._run(result)
        _, downstream_state = flow_state.result()

        task_run = await orion_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(value=[])

    async def test_task_inputs_populated_with_result_upstream_from_state_with_unpacking_trackables(
        self, orion_client
    ):
        @task
        def task_1():
            task_3_in = [1, 2, 3]
            task_2_in = "Woof!"
            return task_2_in, task_3_in

        @task
        def task_2(task_2_input):
            return (task_2_input + " Bark!",)

        @task
        def task_3(task_3_input):
            task_3_input.append(4)
            return task_3_input

        @flow
        def unpacking_flow():
            t1_state = task_1._run()
            t1_res_1, t1_res_2 = t1_state.result()
            t2_state = task_2._run(t1_res_1)
            t3_state = task_3._run(t1_res_2)
            return t1_state, t2_state, t3_state

        t1_state, t2_state, t3_state = unpacking_flow()

        task_3_run = await orion_client.read_task_run(
            t3_state.state_details.task_run_id
        )

        assert task_3_run.task_inputs == dict(
            task_3_input=[TaskRunResult(id=t1_state.state_details.task_run_id)],
        )

        task_2_run = await orion_client.read_task_run(
            t2_state.state_details.task_run_id
        )

        assert task_2_run.task_inputs == dict(
            task_2_input=[TaskRunResult(id=t1_state.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_result_upstream_from_state_with_unpacking_mixed_untrackable_types(
        self, orion_client
    ):
        @task
        def task_1():
            task_3_in = [1, 2, 3]
            task_2_in = 2
            return task_2_in, task_3_in

        @task
        def task_2(task_2_input):
            return task_2_input + 1

        @task
        def task_3(task_3_input):
            task_3_input.append(4)
            return task_3_input

        @flow
        def unpacking_flow():
            t1_state = task_1._run()
            t1_res_1, t1_res_2 = t1_state.result()
            t2_state = task_2._run(t1_res_1)
            t3_state = task_3._run(t1_res_2)
            return t1_state, t2_state, t3_state

        t1_state, t2_state, t3_state = unpacking_flow()

        task_3_run = await orion_client.read_task_run(
            t3_state.state_details.task_run_id
        )

        assert task_3_run.task_inputs == dict(
            task_3_input=[TaskRunResult(id=t1_state.state_details.task_run_id)],
        )

        task_2_run = await orion_client.read_task_run(
            t2_state.state_details.task_run_id
        )

        assert task_2_run.task_inputs == dict(
            task_2_input=[],
        )

    async def test_task_inputs_populated_with_result_upstream_from_state_with_unpacking_no_trackable_types(
        self, orion_client
    ):
        @task
        def task_1():
            task_3_in = True
            task_2_in = 2
            return task_2_in, task_3_in

        @task
        def task_2(task_2_input):
            return task_2_input + 1

        @task
        def task_3(task_3_input):
            return task_3_input

        @flow
        def unpacking_flow():
            t1_state = task_1._run()
            t1_res_1, t1_res_2 = t1_state.result()
            t2_state = task_2._run(t1_res_1)
            t3_state = task_3._run(t1_res_2)
            return t1_state, t2_state, t3_state

        t1_state, t2_state, t3_state = unpacking_flow()

        task_3_run = await orion_client.read_task_run(
            t3_state.state_details.task_run_id
        )

        assert task_3_run.task_inputs == dict(
            task_3_input=[],
        )

        task_2_run = await orion_client.read_task_run(
            t2_state.state_details.task_run_id
        )

        assert task_2_run.task_inputs == dict(
            task_2_input=[],
        )


class TestTaskWaitFor:
    def test_downstream_does_not_run_if_upstream_fails(self):
        @task
        def fails():
            raise ValueError("Fail task!")

        @task
        def bar(y):
            return y

        @flow
        def test_flow():
            f = fails.submit()
            b = bar._run(2, wait_for=[f])
            return b

        flow_state = test_flow._run()
        task_state = flow_state.result(raise_on_failure=False)
        assert task_state.is_pending()
        assert task_state.name == "NotReady"

    def test_downstream_runs_if_upstream_succeeds(self):
        @task
        def foo(x):
            return x

        @task
        def bar(y):
            return y

        @flow
        def test_flow():
            f = foo(1)
            b = bar(2, wait_for=[f])
            return b

        assert test_flow() == 2

    async def test_backend_task_inputs_includes_wait_for_tasks(self, orion_client):
        @task
        def foo(x):
            return x

        @flow
        def test_flow():
            a, b = foo.submit(1), foo.submit(2)
            c = foo.submit(3)
            d = foo.submit(c, wait_for=[a, b])
            return (a, b, c, d)

        a, b, c, d = test_flow()
        d_task_run = await orion_client.read_task_run(d.state_details.task_run_id)

        assert d_task_run.task_inputs["x"] == [
            TaskRunResult(id=c.state_details.task_run_id)
        ], "Data passing inputs are preserved"

        assert set(d_task_run.task_inputs["wait_for"]) == {
            TaskRunResult(id=a.state_details.task_run_id),
            TaskRunResult(id=b.state_details.task_run_id),
        }, "'wait_for' included as a key with upstreams"

        assert set(d_task_run.task_inputs.keys()) == {
            "x",
            "wait_for",
        }, "No extra keys around"

    def test_using_wait_for_in_task_definition_raises_reserved(self):
        with pytest.raises(
            ReservedArgumentError, match="'wait_for' is a reserved argument name"
        ):

            @task
            def foo(wait_for):
                pass


@pytest.mark.enable_orion_handler
class TestTaskRunLogs:
    async def test_user_logs_are_sent_to_orion(self, orion_client):
        @task
        def my_task():
            logger = get_run_logger()
            logger.info("Hello world!")

        @flow
        def my_flow():
            my_task()

        my_flow()

        logs = await orion_client.read_logs()
        assert "Hello world!" in {log.message for log in logs}

    async def test_tracebacks_are_logged(self, orion_client):
        @task
        def my_task():
            logger = get_run_logger()
            try:
                x + y
            except:
                logger.error("There was an issue", exc_info=True)

        @flow
        def my_flow():
            my_task()

        my_flow()

        logs = await orion_client.read_logs()
        error_log = [log.message for log in logs if log.level == 40].pop()
        assert "NameError" in error_log
        assert "x + y" in error_log

    async def test_opt_out_logs_are_not_sent_to_orion(self, orion_client):
        @task
        def my_task():
            logger = get_run_logger()
            logger.info("Hello world!", extra={"send_to_orion": False})

        @flow
        def my_flow():
            my_task()

        my_flow()

        logs = await orion_client.read_logs()
        assert "Hello world!" not in {log.message for log in logs}

    async def test_logs_are_given_correct_ids(self, orion_client):
        @task
        def my_task():
            logger = get_run_logger()
            logger.info("Hello world!")

        @flow
        def my_flow():
            return my_task._run()

        task_state = my_flow()
        flow_run_id = task_state.state_details.flow_run_id
        task_run_id = task_state.state_details.task_run_id

        logs = await orion_client.read_logs()
        assert logs, "There should be logs"
        assert all([log.flow_run_id == flow_run_id for log in logs])
        task_run_logs = [log for log in logs if log.task_run_id is not None]
        assert task_run_logs, f"There should be task run logs in {logs}"
        assert all([log.task_run_id == task_run_id for log in task_run_logs])


class TestTaskWithOptions:
    def test_with_options_allows_override_of_task_settings(self):
        def first_cache_key_fn(*_):
            return "first cache hit"

        def second_cache_key_fn(*_):
            return "second cache hit"

        @task(
            name="Initial task",
            description="Task before with options",
            tags=["tag1", "tag2"],
            cache_key_fn=first_cache_key_fn,
            cache_expiration=datetime.timedelta(days=1),
            retries=2,
            retry_delay_seconds=5,
        )
        def initial_task():
            pass

        task_with_options = initial_task.with_options(
            name="Copied task",
            description="A copied task",
            tags=["tag3", "tag4"],
            cache_key_fn=second_cache_key_fn,
            cache_expiration=datetime.timedelta(days=2),
            retries=5,
            retry_delay_seconds=10,
        )

        assert task_with_options.name == "Copied task"
        assert task_with_options.description == "A copied task"
        assert set(task_with_options.tags) == {"tag3", "tag4"}
        assert task_with_options.cache_key_fn is second_cache_key_fn
        assert task_with_options.cache_expiration == datetime.timedelta(days=2)
        assert task_with_options.retries == 5
        assert task_with_options.retry_delay_seconds == 10

    def test_with_options_uses_existing_settings_when_no_override(self):
        def cache_key_fn(*_):
            return "cache hit"

        @task(
            name="Initial task",
            description="Task before with options",
            tags=["tag1", "tag2"],
            cache_key_fn=cache_key_fn,
            cache_expiration=datetime.timedelta(days=1),
            retries=2,
            retry_delay_seconds=5,
        )
        def initial_task():
            pass

        task_with_options = initial_task.with_options()

        assert task_with_options is not initial_task
        assert (
            task_with_options.name == "Initial task"
        )  # The registry renames tasks to avoid collisions.
        assert task_with_options.description == "Task before with options"
        assert set(task_with_options.tags) == {"tag1", "tag2"}
        assert task_with_options.tags is not initial_task.tags
        assert task_with_options.cache_key_fn is cache_key_fn
        assert task_with_options.cache_expiration == datetime.timedelta(days=1)
        assert task_with_options.retries == 2
        assert task_with_options.retry_delay_seconds == 5

    def test_tags_are_copied_from_original_task(self):
        "Ensure changes to the tags on the original task don't affect the new task"

        @task(name="Initial task", tags=["tag1", "tag2"])
        def initial_task():
            pass

        with_options_task = initial_task.with_options(name="With options task")
        initial_task.tags.add("tag3")

        assert initial_task.tags == {"tag1", "tag2", "tag3"}
        assert with_options_task.tags == {"tag1", "tag2"}

    def test_with_options_signature_aligns_with_task_signature(self):
        task_params = set(inspect.signature(task).parameters.keys())
        with_options_params = set(
            inspect.signature(Task.with_options).parameters.keys()
        )
        # `with_options` does not accept a new function
        task_params.remove("__fn")
        # it doesn't make sense to take the same task definition and change versions
        # tags should be used for distinguishing different calls where necessary
        task_params.remove("version")
        # `self` isn't in task decorator
        with_options_params.remove("self")
        assert task_params == with_options_params


class TestTaskRegistration:
    def test_task_is_registered(self):
        @task
        def my_task():
            pass

        registry = PrefectObjectRegistry.get()
        assert my_task in registry.get_instances(Task)

    def test_warning_name_conflict_different_function(self):
        with pytest.warns(
            UserWarning,
            match=r"A task named 'my_task' and defined at '.+:\d+' conflicts with another task.",
        ):

            @task(name="my_task")
            def task_one():
                pass

            @task(name="my_task")
            def task_two():
                pass

    def test_no_warning_name_conflict_task_with_options(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")

            @task(name="my_task")
            def task_one():
                pass

            task_one.with_options(tags=["hello"])


class TestTaskMap:
    @task
    async def add_one(x):
        return x + 1

    @task
    def add_together(x, y):
        return x + y

    def test_simple_map(self):
        @flow
        def my_flow():
            futures = TestTaskMap.add_one.map([1, 2, 3])
            assert all(isinstance(f, PrefectFuture) for f in futures)
            return futures

        futures = my_flow()
        assert [future.result() for future in futures] == [2, 3, 4]

    def test_simple_map_return_state_true(self):
        @flow
        def my_flow():
            states = TestTaskMap.add_one.map([1, 2, 3], return_state=True)
            assert all(isinstance(s, State) for s in states)
            return states

        states = my_flow()
        assert [state.result() for state in states] == [2, 3, 4]

    def test_map_can_take_tuple_as_input(self):
        @flow
        def my_flow():
            futures = TestTaskMap.add_one.map((1, 2, 3))
            assert all(isinstance(f, PrefectFuture) for f in futures)
            return futures

        futures = my_flow()
        assert [future.result() for future in futures] == [2, 3, 4]

    def test_map_can_take_generator_as_input(self):
        def generate_numbers():
            i = 1
            while i <= 3:
                yield i
                i += 1

        @flow
        def my_flow():
            futures = TestTaskMap.add_one.map(generate_numbers())
            assert all(isinstance(f, PrefectFuture) for f in futures)
            return futures

        futures = my_flow()
        assert [future.result() for future in futures] == [2, 3, 4]

    def test_map_can_take_state_as_input(self):
        @task
        def some_numbers():
            return [1, 2, 3]

        @flow
        def my_flow():
            numbers_state = some_numbers._run()
            return TestTaskMap.add_one.map(numbers_state)

        futures = my_flow()
        assert [future.result() for future in futures] == [2, 3, 4]

    def test_map_can_take_future_as_input(self):
        @task
        def some_numbers():
            return [1, 2, 3]

        @flow
        def my_flow():
            numbers_future = some_numbers.submit()
            return TestTaskMap.add_one.map(numbers_future)

        futures = my_flow()
        assert [future.result() for future in futures] == [2, 3, 4]

    def test_map_can_take_flow_state_as_input(self):
        @flow
        def child_flow():
            return [1, 2, 3]

        @flow
        def my_flow():
            numbers_state = child_flow._run()
            return TestTaskMap.add_one.map(numbers_state)

        futures = my_flow()
        assert [future.result() for future in futures] == [2, 3, 4]

    def test_multiple_inputs(self):
        @flow
        def my_flow():
            numbers = [1, 2, 3]
            others = [4, 5, 6]
            return TestTaskMap.add_together.map(numbers, others)

        futures = my_flow()
        assert [future.result() for future in futures] == [5, 7, 9]

    def test_missing_iterable_argument(self):
        @flow
        def my_flow():
            return TestTaskMap.add_together.map(5, 6)

        with pytest.raises(MappingMissingIterable):
            assert my_flow()

    def test_mismatching_input_lengths(self):
        @flow
        def my_flow():
            numbers = [1, 2, 3]
            others = [4, 5, 6, 7]
            return TestTaskMap.add_together.map(numbers, others)

        with pytest.raises(MappingLengthMismatch):
            assert my_flow()

    async def test_async_flow_with_async_map(self):
        @task
        async def some_numbers():
            return [1, 2, 3]

        @flow
        async def my_flow():
            return await TestTaskMap.add_one.map(await some_numbers())

        futures = await my_flow()
        assert [future.result() for future in futures] == [2, 3, 4]

    async def test_async_flow_with_sync_map(self):
        @task
        def subtract_them(x, y):
            return x - y

        @flow
        async def my_flow():
            return subtract_them.map([4, 5, 6], [1, 2, 3])

        futures = await my_flow()
        assert [future.result() for future in futures] == [3, 3, 3]

    async def test_unmapped_value(self):
        @flow
        def my_flow():
            numbers = [1, 2, 3]
            other = unmapped(5)
            return TestTaskMap.add_together.map(numbers, other)

        futures = my_flow()
        assert [future.result() for future in futures] == [6, 7, 8]

    async def test_with_default_kwargs(self):
        @task
        def add_some(x, y=5):
            return x + y

        @flow
        def my_flow():
            numbers = [1, 2, 3]
            return add_some.map(numbers)

        futures = my_flow()
        assert [future.result() for future in futures] == [6, 7, 8]
