import datetime
import inspect
import time
import warnings
import regex as re
from asyncio import Event, sleep
from typing import Any, Dict, List
from unittest.mock import MagicMock, call
from uuid import UUID

import anyio
import pytest

from prefect import flow, get_run_logger, tags
from prefect.blocks.core import Block
from prefect.client.schemas.objects import StateType, TaskRunResult
from prefect.context import PrefectObjectRegistry, TaskRunContext, get_run_context
from prefect.engine import get_state_for_result
from prefect.exceptions import (
    MappingLengthMismatch,
    MappingMissingIterable,
    ReservedArgumentError,
)
from prefect.filesystems import LocalFileSystem
from prefect.futures import PrefectFuture
from prefect.runtime import task_run as task_run_ctx
from prefect.server import models
from prefect.settings import (
    PREFECT_DEBUG_MODE,
    PREFECT_TASK_DEFAULT_RETRIES,
    PREFECT_TASKS_REFRESH_CACHE,
    temporary_settings,
)
from prefect.states import State
from prefect.task_runners import SequentialTaskRunner
from prefect.tasks import Task, task, task_input_hash
from prefect.testing.utilities import exceptions_equal, flaky_on_windows
from prefect.utilities.annotations import allow_failure, unmapped
from prefect.utilities.collections import quote


def comparable_inputs(d):
    return {k: set(v) for k, v in d.items()}


@pytest.fixture
def timeout_test_flow():
    @task(timeout_seconds=0.1)
    def times_out(x):
        time.sleep(1)
        return x

    @task
    def depends(x):
        return x

    @task
    def independent():
        return 42

    @flow
    def test_flow():
        ax = times_out.submit(1)
        bx = depends.submit(ax)
        cx = independent.submit()
        return ax, bx, cx

    return test_flow


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


class TestTaskRunName:
    def test_run_name_default(self):
        @task
        def my_task():
            pass

        assert my_task.task_run_name is None

    def test_invalid_run_name(self):
        class InvalidTaskRunNameArg:
            def format(*args, **kwargs):
                pass

        with pytest.raises(
            TypeError,
            match=(
                "Expected string or callable for 'task_run_name'; got"
                " InvalidTaskRunNameArg instead."
            ),
        ):

            @task(task_run_name=InvalidTaskRunNameArg())
            def my_task():
                pass

    def test_invalid_runtime_run_name(self):
        class InvalidTaskRunNameArg:
            def format(*args, **kwargs):
                pass

        @task
        def my_task():
            pass

        @flow
        def my_flow():
            my_task()

        my_task.task_run_name = InvalidTaskRunNameArg()

        with pytest.raises(
            TypeError,
            match=(
                "Expected string or callable for 'task_run_name'; got"
                " InvalidTaskRunNameArg instead."
            ),
        ):
            my_flow()

    def test_run_name_from_kwarg(self):
        @task(task_run_name="another_name")
        def my_task():
            pass

        assert my_task.task_run_name == "another_name"

    def test_run_name_from_function(self):
        def generate_task_run_name():
            return "another_name"

        @task(task_run_name=generate_task_run_name)
        def my_task():
            pass

        assert my_task.task_run_name() == "another_name"

    def test_run_name_from_options(self):
        @task(task_run_name="first_name")
        def my_task():
            pass

        assert my_task.task_run_name == "first_name"

        new_task = my_task.with_options(task_run_name=lambda: "second_name")
        assert new_task.task_run_name() == "second_name"


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

    def test_task_call_with_debug_mode(self):
        @task
        async def foo(x):
            return x

        @flow
        def bar():
            return foo(1)

        with temporary_settings({PREFECT_DEBUG_MODE: True}):
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

    def test_task_with_name_supports_callable_objects(self):
        class A:
            def __call__(self, *_args: Any, **_kwargs: Any) -> Any:
                return "hello"

        a = A()
        task = Task(fn=a, name="Task")
        assert task.fn is a

    def test_task_supports_callable_objects(self):
        class A:
            def __call__(self, *_args: Any, **_kwargs: Any) -> Any:
                return "hello"

        a = A()
        task = Task(fn=a)
        assert task.fn is a

    def test_task_run_with_name_from_callable_object(self):
        class Foo:
            message = "hello"

            def __call__(self, prefix: str, suffix: str) -> Any:
                return prefix + self.message + suffix

        obj = Foo()
        foo = Task(fn=obj, name="Task")

        @flow
        def bar():
            return foo("a", suffix="b")

        assert bar() == "ahellob"

    def test_task_run_from_callable_object(self):
        class Foo:
            message = "hello"

            def __call__(self, prefix: str, suffix: str) -> Any:
                return prefix + self.message + suffix

        obj = Foo()
        foo = Task(fn=obj)

        @flow
        def bar():
            return foo("a", suffix="b")

        assert bar() == "ahellob"


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
        assert await task_state.result() == 1

    async def test_sync_task_run_inside_async_flow(self):
        @task
        def foo(x):
            return x

        @flow
        async def bar():
            return foo._run(1)

        task_state = await bar()
        assert isinstance(task_state, State)
        assert await task_state.result() == 1

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

    def test_task_returns_generator_implicit_list(self):
        @task
        def my_generator(n):
            for i in range(n):
                yield i

        @flow
        def my_flow():
            return my_generator(5)

        assert my_flow() == [0, 1, 2, 3, 4]


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
        assert await task_state.result() == 1

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
        assert await task_state.result() == 1

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
            b = bar.submit(f)
            return b

        flow_state = test_flow(return_state=True)
        task_state = flow_state.result(raise_on_failure=False)
        assert task_state.is_pending()
        assert task_state.name == "NotReady"

    def test_downstream_runs_if_upstream_succeeds(self):
        @task
        def foo(x):
            return x

        @task
        def bar(y):
            return y + 1

        @flow
        def test_flow():
            f = foo.submit(1)
            b = bar.submit(f)
            return b.result()

        assert test_flow() == 2

    def test_downstream_receives_exception_if_upstream_fails_and_allow_failure(self):
        @task
        def fails():
            raise ValueError("Fail task!")

        @task
        def bar(y):
            return y

        @flow
        def test_flow():
            f = fails.submit()
            b = bar.submit(allow_failure(f))
            return b.result()

        result = test_flow()
        assert isinstance(result, ValueError)
        assert "Fail task!" in str(result)

    def test_downstream_receives_exception_in_collection_if_upstream_fails_and_allow_failure(
        self,
    ):
        @task
        def fails():
            raise ValueError("Fail task!")

        @task
        def bar(y):
            return y

        @flow
        def test_flow():
            f = fails.submit()
            b = bar.submit(allow_failure([f, 1, 2]))
            return b.result()

        result = test_flow()
        assert isinstance(result, list), f"Expected list; got {type(result)}"
        assert isinstance(result[0], ValueError)
        assert result[1:] == [1, 2]
        assert "Fail task!" in str(result)

    def test_allow_failure_chained_mapped_tasks(
        self,
    ):
        @task
        def fails_on_two(x):
            if x == 2:
                raise ValueError("Fail task")
            return x

        @task
        def identity(y):
            return y

        @flow
        def test_flow():
            f = fails_on_two.map([1, 2, 3])
            b = identity.map(allow_failure(f))
            return b

        states = test_flow()
        assert isinstance(states, list), f"Expected list; got {type(states)}"

        assert states[0].result(), states[2].result() == [1, 3]

        assert states[1].is_completed()
        assert exceptions_equal(states[1].result(), ValueError("Fail task"))

    def test_allow_failure_mapped_with_noniterable_upstream(
        self,
    ):
        @task
        def fails():
            raise ValueError("Fail task")

        @task
        def identity(y, z):
            return y, z

        @flow
        def test_flow():
            f = fails.submit()
            b = identity.map([1, 2, 3], allow_failure(f))
            return b

        states = test_flow()
        assert isinstance(states, list), f"Expected list; got {type(states)}"

        assert len(states) == 3
        for i, state in enumerate(states):
            y, z = state.result()
            assert y == i + 1
            assert exceptions_equal(z, ValueError("Fail task"))


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
                data=True,
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

    async def test_task_version_is_set_in_backend(self, prefect_client):
        @task(version="test-dev-experimental")
        def my_task():
            pass

        @flow
        def test():
            return my_task._run()

        task_state = test()
        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert task_run.task_version == "test-dev-experimental"


class TestTaskFutures:
    async def test_wait_gets_final_state(self, prefect_client):
        @task
        async def foo():
            return 1

        @flow
        async def my_flow():
            future = await foo.submit()
            state = await future.wait()

            assert state.is_completed()

            # TODO: The ids are not equal here, why?
            # task_run = await prefect_client.read_task_run(state.state_details.task_run_id)
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
    async def test_task_respects_retry_count(self, always_fail, prefect_client):
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
            return future.wait(), ...

        task_run_state, _ = test_flow()
        task_run_id = task_run_state.state_details.task_run_id

        if always_fail:
            assert task_run_state.is_failed()
            assert exceptions_equal(
                await task_run_state.result(raise_on_failure=False), exc
            )
            assert mock.call_count == 4
        else:
            assert task_run_state.is_completed()
            assert await task_run_state.result() is True
            assert mock.call_count == 4

        states = await prefect_client.read_task_run_states(task_run_id)

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

    async def test_task_only_uses_necessary_retries(self, prefect_client):
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
            return future.wait()

        task_run_state = test_flow()
        task_run_id = task_run_state.state_details.task_run_id

        assert task_run_state.is_completed()
        assert await task_run_state.result() is True
        assert mock.call_count == 2

        states = await prefect_client.read_task_run_states(task_run_id)
        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "AwaitingRetry",
            "Retrying",
            "Completed",
        ]

    async def test_task_retries_receive_latest_task_run_in_context(self):
        contexts: List[TaskRunContext] = []

        @task(retries=3)
        def flaky_function():
            contexts.append(get_run_context())
            raise ValueError()

        @flow
        def test_flow():
            flaky_function()

        with pytest.raises(ValueError):
            test_flow()

        expected_state_names = [
            "Running",
            "Retrying",
            "Retrying",
            "Retrying",
        ]
        assert len(contexts) == len(expected_state_names)
        for i, context in enumerate(contexts):
            assert context.task_run.run_count == i + 1
            assert context.task_run.state_name == expected_state_names[i]

            if i > 0:
                last_context = contexts[i - 1]
                assert (
                    last_context.start_time < context.start_time
                ), "Timestamps should be increasing"

    async def test_global_task_retry_config(self):
        with temporary_settings(updates={PREFECT_TASK_DEFAULT_RETRIES: "1"}):
            mock = MagicMock()
            exc = ValueError()

            @task()
            def flaky_function():
                mock()
                if mock.call_count == 2:
                    return True
                raise exc

            @flow
            def test_flow():
                future = flaky_function.submit()
                return future.wait()

            test_flow()
            assert mock.call_count == 2


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

    def test_cache_misses_w_refresh_cache(self):
        @task(cache_key_fn=lambda *_: "cache hit", refresh_cache=True)
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1, return_state=True), foo(2, return_state=True)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert second_state.result() != first_state.result()

    def test_cache_hits_wo_refresh_cache(self):
        @task(cache_key_fn=lambda *_: "cache hit", refresh_cache=False)
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1, return_state=True), foo(2, return_state=True)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert second_state.result() == first_state.result()

    def test_tasks_refresh_cache_setting(self):
        @task(cache_key_fn=lambda *_: "cache hit")
        def foo(x):
            return x

        @task(cache_key_fn=lambda *_: "cache hit", refresh_cache=True)
        def refresh_task(x):
            return x

        @task(cache_key_fn=lambda *_: "cache hit", refresh_cache=False)
        def not_refresh_task(x):
            return x

        @flow
        def bar():
            foo(0)
            return (
                foo(1, return_state=True),
                refresh_task(2, return_state=True),
                not_refresh_task(3, return_state=True),
            )

        with temporary_settings({PREFECT_TASKS_REFRESH_CACHE: True}):
            first_state, second_state, third_state = bar()
            assert first_state.name == "Completed"
            assert second_state.name == "Completed"
            assert third_state.name == "Cached"
            assert second_state.result() != first_state.result()
            assert third_state.result() == second_state.result()


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

    def test_task_input_hash_works_with_block_input_types(self):
        class TestBlock(Block):
            x: int
            y: int
            z: int

        @task(cache_key_fn=task_input_hash)
        def foo(instance):
            return instance.x

        @flow
        def bar():
            return (
                foo._run(TestBlock(x=1, y=2, z=3)),
                foo._run(TestBlock(x=4, y=2, z=3)),
                foo._run(TestBlock(x=1, y=2, z=3)),
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

    def test_task_input_hash_works_with_block_input_types_and_bytes(self):
        class TestBlock(Block):
            x: int
            y: int
            z: bytes

        @task(cache_key_fn=task_input_hash)
        def foo(instance):
            return instance.x

        @flow
        def bar():
            return (
                foo._run(TestBlock(x=1, y=2, z="dog".encode("utf-8"))),  # same
                foo._run(TestBlock(x=4, y=2, z="dog".encode("utf-8"))),  # different x
                foo._run(TestBlock(x=1, y=2, z="dog".encode("utf-8"))),  # same
                foo._run(TestBlock(x=1, y=2, z="dog".encode("latin-1"))),  # same
                foo._run(TestBlock(x=1, y=2, z="cat".encode("utf-8"))),  # different z
            )

        first_state, second_state, third_state, fourth_state, fifth_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"
        assert fourth_state.name == "Cached"
        assert fifth_state.name == "Completed"

        assert first_state.result() != second_state.result()
        assert (
            first_state.result() == third_state.result() == fourth_state.result() == 1
        )


class TestTaskTimeouts:
    async def test_task_timeouts_actually_timeout(self, timeout_test_flow):
        flow_state = timeout_test_flow._run()
        timed_out, _, _ = await flow_state.result(raise_on_failure=False)
        assert timed_out.name == "TimedOut"
        assert timed_out.is_failed()

    async def test_task_timeouts_are_not_task_crashes(self, timeout_test_flow):
        flow_state = timeout_test_flow._run()
        timed_out, _, _ = await flow_state.result(raise_on_failure=False)
        assert timed_out.is_crashed() is False

    async def test_task_timeouts_do_not_crash_flow_runs(self, timeout_test_flow):
        flow_state = timeout_test_flow._run()
        timed_out, _, _ = await flow_state.result(raise_on_failure=False)

        assert timed_out.name == "TimedOut"
        assert timed_out.is_failed()
        assert flow_state.is_failed()
        assert flow_state.is_crashed() is False

    async def test_task_timeouts_do_not_timeout_prematurely(self):
        @task(timeout_seconds=100)
        def my_task():
            time.sleep(1)
            return 42

        @flow
        def my_flow():
            x = my_task.submit()
            return x

        flow_state = my_flow._run()
        assert flow_state.type == StateType.COMPLETED

        task_res = await flow_state.result()
        assert task_res.type == StateType.COMPLETED


class TestTaskRunTags:
    async def test_task_run_tags_added_at_submission(self, prefect_client):
        @flow
        def my_flow():
            with tags("a", "b"):
                future = my_task.submit()

            return future

        @task
        def my_task():
            pass

        task_state = my_flow()
        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b"}

    async def test_task_run_tags_added_at_run(self, prefect_client):
        @flow
        def my_flow():
            with tags("a", "b"):
                state = my_task._run()

            return state

        @task
        def my_task():
            pass

        task_state = my_flow()
        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b"}

    async def test_task_run_tags_added_at_call(self, prefect_client):
        @flow
        def my_flow():
            with tags("a", "b"):
                result = my_task()

            return get_state_for_result(result)

        @task
        def my_task():
            return "foo"

        task_state = my_flow()
        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b"}

    async def test_task_run_tags_include_tags_on_task_object(self, prefect_client):
        @flow
        def my_flow():
            with tags("c", "d"):
                state = my_task._run()

            return state

        @task(tags={"a", "b"})
        def my_task():
            pass

        task_state = my_flow()
        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b", "c", "d"}

    async def test_task_run_tags_include_flow_run_tags(self, prefect_client):
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

        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b", "c", "d"}

    async def test_task_run_tags_not_added_outside_context(self, prefect_client):
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
        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert not task_run.tags

    async def test_task_run_tags_respects_nesting(self, prefect_client):
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
        task_run = await prefect_client.read_task_run(
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

    async def test_task_inputs_populated_with_no_upstreams(self, prefect_client):
        @task
        def foo(x):
            return x

        @flow
        def test_flow():
            return foo.submit(1)

        flow_state = test_flow._run()
        x = await flow_state.result()

        task_run = await prefect_client.read_task_run(x.state_details.task_run_id)

        assert task_run.task_inputs == dict(x=[])

    async def test_task_inputs_populated_with_no_upstreams_and_multiple_parameters(
        self, prefect_client
    ):
        @task
        def foo(x, *a, **k):
            return x

        @flow
        def test_flow():
            return foo.submit(1)

        flow_state = test_flow._run()
        x = await flow_state.result()

        task_run = await prefect_client.read_task_run(x.state_details.task_run_id)

        assert task_run.task_inputs == dict(x=[], a=[], k=[])

    async def test_task_inputs_populated_with_one_upstream_positional_future(
        self, prefect_client
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
        a, b, c = await flow_state.result()

        task_run = await prefect_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[],
        )

    async def test_task_inputs_populated_with_one_upstream_keyword_future(
        self, prefect_client
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
        a, b, c = await flow_state.result()

        task_run = await prefect_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[],
        )

    async def test_task_inputs_populated_with_two_upstream_futures(
        self, prefect_client
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
            c = bar._run(a, b)
            return a, b, c

        flow_state = test_flow._run()
        a, b, c = await flow_state.result()

        task_run = await prefect_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[TaskRunResult(id=b.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_two_upstream_futures_from_same_task(
        self, prefect_client
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
        a, c = await flow_state.result()

        task_run = await prefect_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[TaskRunResult(id=a.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_nested_upstream_futures(
        self, prefect_client
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

        a, b, c, d = await flow_state.result()

        task_run = await prefect_client.read_task_run(d.state_details.task_run_id)

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

    async def test_task_inputs_populated_with_subflow_upstream(self, prefect_client):
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
        child_state, task_state = await parent_state.result()

        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=child_state.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_result_upstream(self, prefect_client):
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
        name_state, hi_state = await flow_state.result()

        task_run = await prefect_client.read_task_run(
            hi_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            name=[TaskRunResult(id=name_state.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_result_upstream_from_future(
        self, prefect_client
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

        task_run = await prefect_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_result_upstream_from_state(
        self, prefect_client
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

        await prefect_client.read_task_run(downstream_state.state_details.task_run_id)

    async def test_task_inputs_populated_with_state_upstream(self, prefect_client):
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

        task_run = await prefect_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_state_upstream_wrapped_with_allow_failure(
        self, prefect_client
    ):
        @task
        def upstream(x):
            return x

        @task
        def downstream(x):
            return x

        @flow
        def test_flow():
            upstream_state = upstream(1, return_state=True)
            downstream_state = downstream(
                allow_failure(upstream_state), return_state=True
            )
            return upstream_state, downstream_state

        upstream_state, downstream_state = test_flow()

        task_run = await prefect_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    @pytest.mark.parametrize("result", [["Fred"], {"one": 1}, {1, 2, 2}, (1, 2)])
    async def test_task_inputs_populated_with_collection_result_upstream(
        self, result, prefect_client, flow_with_upstream_downstream
    ):
        flow_state = flow_with_upstream_downstream._run(result)
        upstream_state, downstream_state = await flow_state.result()

        task_run = await prefect_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            value=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    @pytest.mark.parametrize("result", ["Fred", 5.1])
    async def test_task_inputs_populated_with_basic_result_types_upstream(
        self, result, prefect_client, flow_with_upstream_downstream
    ):
        flow_state = flow_with_upstream_downstream._run(result)
        upstream_state, downstream_state = await flow_state.result()

        task_run = await prefect_client.read_task_run(
            downstream_state.state_details.task_run_id
        )
        assert task_run.task_inputs == dict(
            value=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    @pytest.mark.parametrize("result", [True, False, None, ..., NotImplemented])
    async def test_task_inputs_not_populated_with_singleton_results_upstream(
        self, result, prefect_client, flow_with_upstream_downstream
    ):
        flow_state = flow_with_upstream_downstream._run(result)
        _, downstream_state = await flow_state.result()

        task_run = await prefect_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(value=[])

    async def test_task_inputs_populated_with_result_upstream_from_state_with_unpacking_trackables(
        self, prefect_client
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

        task_3_run = await prefect_client.read_task_run(
            t3_state.state_details.task_run_id
        )

        assert task_3_run.task_inputs == dict(
            task_3_input=[TaskRunResult(id=t1_state.state_details.task_run_id)],
        )

        task_2_run = await prefect_client.read_task_run(
            t2_state.state_details.task_run_id
        )

        assert task_2_run.task_inputs == dict(
            task_2_input=[TaskRunResult(id=t1_state.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_result_upstream_from_state_with_unpacking_mixed_untrackable_types(
        self, prefect_client
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

        task_3_run = await prefect_client.read_task_run(
            t3_state.state_details.task_run_id
        )

        assert task_3_run.task_inputs == dict(
            task_3_input=[TaskRunResult(id=t1_state.state_details.task_run_id)],
        )

        task_2_run = await prefect_client.read_task_run(
            t2_state.state_details.task_run_id
        )

        assert task_2_run.task_inputs == dict(
            task_2_input=[],
        )

    async def test_task_inputs_populated_with_result_upstream_from_state_with_unpacking_no_trackable_types(
        self, prefect_client
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

        task_3_run = await prefect_client.read_task_run(
            t3_state.state_details.task_run_id
        )

        assert task_3_run.task_inputs == dict(
            task_3_input=[],
        )

        task_2_run = await prefect_client.read_task_run(
            t2_state.state_details.task_run_id
        )

        assert task_2_run.task_inputs == dict(
            task_2_input=[],
        )


class TestSubflowWaitForTasks:
    def test_downstream_does_not_run_if_upstream_fails(self):
        @task
        def fails():
            raise ValueError("Fail task!")

        @flow
        def bar(y):
            return y

        @flow
        def test_flow():
            f = fails.submit()
            b = bar._run(2, wait_for=[f])
            return b

        flow_state = test_flow._run()
        subflow_state = flow_state.result(raise_on_failure=False)
        assert subflow_state.is_pending()
        assert subflow_state.name == "NotReady"

    def test_downstream_runs_if_upstream_succeeds(self):
        @flow
        def foo(x):
            return x

        @flow
        def bar(y):
            return y

        @flow
        def test_flow():
            f = foo(1)
            b = bar(2, wait_for=[f])
            return b

        assert test_flow() == 2

    async def test_backend_task_inputs_includes_wait_for_tasks(self, prefect_client):
        @task
        def foo(x):
            return x

        @flow
        def flow_foo(x):
            return x

        @flow
        def test_flow():
            a, b = foo.submit(1), foo.submit(2)
            c = foo.submit(3)
            d = flow_foo(c, wait_for=[a, b], return_state=True)
            return (a, b, c, d)

        a, b, c, d = test_flow()
        d_subflow_run = await prefect_client.read_flow_run(d.state_details.flow_run_id)
        d_virtual_task_run = await prefect_client.read_task_run(
            d_subflow_run.parent_task_run_id
        )

        assert d_virtual_task_run.task_inputs["x"] == [
            TaskRunResult(id=c.state_details.task_run_id)
        ], "Data passing inputs are preserved"

        assert set(d_virtual_task_run.task_inputs["wait_for"]) == {
            TaskRunResult(id=a.state_details.task_run_id),
            TaskRunResult(id=b.state_details.task_run_id),
        }, "'wait_for' included as a key with upstreams"

        assert set(d_virtual_task_run.task_inputs.keys()) == {
            "x",
            "wait_for",
        }, "No extra keys around"

    async def test_subflows_run_concurrently_with_tasks(self):
        @task
        async def waiter_task(event, delay):
            await sleep(delay)
            if event.is_set():
                pass
            else:
                raise RuntimeError("The event hasn't been set!")

        @flow
        async def setter_flow(event):
            event.set()
            return 42

        @flow
        async def test_flow():
            e = Event()
            await waiter_task.submit(e, 1)
            b = await setter_flow(e)
            return b

        assert (await test_flow()) == 42

    async def test_subflows_waiting_for_tasks_can_deadlock(self):
        @task
        async def waiter_task(event, delay):
            await sleep(delay)
            if event.is_set():
                pass
            else:
                raise RuntimeError("The event hasn't been set!")

        @flow
        async def setter_flow(event):
            event.set()
            return 42

        @flow
        async def test_flow():
            e = Event()
            f = await waiter_task.submit(e, 1)
            b = await setter_flow(e, wait_for=[f])
            return b

        flow_state = await test_flow._run()
        assert flow_state.is_failed()
        assert "UnfinishedRun" in flow_state.message

    def test_using_wait_for_in_task_definition_raises_reserved(self):
        with pytest.raises(
            ReservedArgumentError, match="'wait_for' is a reserved argument name"
        ):

            @flow
            def foo(wait_for):
                pass

    def test_downstream_runs_if_upstream_fails_with_allow_failure_annotation(self):
        @task
        def fails():
            raise ValueError("Fail task!")

        @flow
        def bar(y):
            return y

        @flow
        def test_flow():
            f = fails.submit()
            b = bar(2, wait_for=[allow_failure(f)], return_state=True)
            return b

        flow_state = test_flow(return_state=True)
        subflow_state = flow_state.result(raise_on_failure=False)
        assert subflow_state.result() == 2


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

    async def test_backend_task_inputs_includes_wait_for_tasks(self, prefect_client):
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
        d_task_run = await prefect_client.read_task_run(d.state_details.task_run_id)

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

    def test_downstream_runs_if_upstream_fails_with_allow_failure_annotation(self):
        @task
        def fails():
            raise ValueError("Fail task!")

        @task
        def bar(y):
            return y

        @flow
        def test_flow():
            f = fails.submit()
            b = bar(2, wait_for=[allow_failure(f)], return_state=True)
            return b

        flow_state = test_flow(return_state=True)
        task_state = flow_state.result(raise_on_failure=False)
        assert task_state.result() == 2


@pytest.mark.enable_api_log_handler
class TestTaskRunLogs:
    async def test_user_logs_are_sent_to_orion(self, prefect_client):
        @task
        def my_task():
            logger = get_run_logger()
            logger.info("Hello world!")

        @flow
        def my_flow():
            my_task()

        my_flow()

        logs = await prefect_client.read_logs()
        assert "Hello world!" in {log.message for log in logs}

    async def test_tracebacks_are_logged(self, prefect_client):
        @task
        def my_task():
            logger = get_run_logger()
            try:
                x + y  # noqa: F821
            except Exception:
                logger.error("There was an issue", exc_info=True)

        @flow
        def my_flow():
            my_task()

        my_flow()

        logs = await prefect_client.read_logs()
        error_log = [log.message for log in logs if log.level == 40].pop()
        assert "NameError" in error_log
        assert "x + y" in error_log

    async def test_opt_out_logs_are_not_sent_to_api(self, prefect_client):
        @task
        def my_task():
            logger = get_run_logger()
            logger.info("Hello world!", extra={"send_to_api": False})

        @flow
        def my_flow():
            my_task()

        my_flow()

        logs = await prefect_client.read_logs()
        assert "Hello world!" not in {log.message for log in logs}

    async def test_logs_are_given_correct_ids(self, prefect_client):
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

        logs = await prefect_client.read_logs()
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
            persist_result=True,
            result_serializer="pickle",
            result_storage=LocalFileSystem(basepath="foo"),
            cache_result_in_memory=False,
            timeout_seconds=None,
            refresh_cache=False,
            result_storage_key="foo",
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
            persist_result=False,
            result_serializer="json",
            result_storage=LocalFileSystem(basepath="bar"),
            cache_result_in_memory=True,
            timeout_seconds=42,
            refresh_cache=True,
            result_storage_key="bar",
        )

        assert task_with_options.name == "Copied task"
        assert task_with_options.description == "A copied task"
        assert set(task_with_options.tags) == {"tag3", "tag4"}
        assert task_with_options.cache_key_fn is second_cache_key_fn
        assert task_with_options.cache_expiration == datetime.timedelta(days=2)
        assert task_with_options.retries == 5
        assert task_with_options.retry_delay_seconds == 10
        assert task_with_options.persist_result is False
        assert task_with_options.result_serializer == "json"
        assert task_with_options.result_storage == LocalFileSystem(basepath="bar")
        assert task_with_options.cache_result_in_memory is True
        assert task_with_options.timeout_seconds == 42
        assert task_with_options.refresh_cache is True
        assert task_with_options.result_storage_key == "bar"

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
            persist_result=False,
            result_serializer="json",
            result_storage=LocalFileSystem(),
            cache_result_in_memory=False,
            timeout_seconds=42,
            refresh_cache=True,
            result_storage_key="test",
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
        assert task_with_options.persist_result is False
        assert task_with_options.result_serializer == "json"
        assert task_with_options.result_storage == LocalFileSystem()
        assert task_with_options.cache_result_in_memory is False
        assert task_with_options.timeout_seconds == 42
        assert task_with_options.refresh_cache is True
        assert task_with_options.result_storage_key == "test"

    def test_with_options_can_unset_result_options_with_none(self):
        @task(
            persist_result=True,
            result_serializer="json",
            result_storage=LocalFileSystem(),
            refresh_cache=True,
            result_storage_key="test",
        )
        def initial_task():
            pass

        task_with_options = initial_task.with_options(
            persist_result=None,
            result_serializer=None,
            result_storage=None,
            refresh_cache=None,
            result_storage_key=None,
        )
        assert task_with_options.persist_result is None
        assert task_with_options.result_serializer is None
        assert task_with_options.result_storage is None
        assert task_with_options.refresh_cache is None
        assert task_with_options.result_storage_key is None

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

    def test_with_options_allows_override_of_0_retries(self):
        @task(retries=3, retry_delay_seconds=10)
        def initial_task():
            pass

        task_with_options = initial_task.with_options(retries=0, retry_delay_seconds=0)
        assert task_with_options.retries == 0
        assert task_with_options.retry_delay_seconds == 0

    def test_with_options_refresh_cache(self):
        @task(cache_key_fn=lambda *_: "cache hit")
        def foo(x):
            return x

        @flow
        def bar():
            return (
                foo(1, return_state=True),
                foo(2, return_state=True),
                foo.with_options(refresh_cache=True)(3, return_state=True),
                foo(4, return_state=True),
            )

        first, second, third, fourth = bar()
        assert first.name == "Completed"
        assert second.name == "Cached"
        assert third.name == "Completed"
        assert fourth.name == "Cached"

        assert first.result() == second.result()
        assert second.result() != third.result()
        assert third.result() == fourth.result()
        assert fourth.result() != first.result()


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
            match=(
                r"A task named 'my_task' and defined at '.+:\d+' conflicts with another"
                r" task."
            ),
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

        task_states = my_flow()
        assert [state.result() for state in task_states] == [2, 3, 4]

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

        task_states = my_flow()
        assert [state.result() for state in task_states] == [2, 3, 4]

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

        task_states = my_flow()
        assert [state.result() for state in task_states] == [2, 3, 4]

    def test_map_can_take_state_as_input(self):
        @task
        def some_numbers():
            return [1, 2, 3]

        @flow
        def my_flow():
            numbers_state = some_numbers._run()
            return TestTaskMap.add_one.map(numbers_state)

        task_states = my_flow()
        assert [state.result() for state in task_states] == [2, 3, 4]

    def test_can_take_quoted_iterable_as_input(self):
        @flow
        def my_flow():
            futures = TestTaskMap.add_together.map(quote(1), [1, 2, 3])
            assert all(isinstance(f, PrefectFuture) for f in futures)
            return futures

        task_states = my_flow()
        assert [state.result() for state in task_states] == [2, 3, 4]

    def test_does_not_treat_quote_as_iterable(self):
        @flow
        def my_flow():
            futures = TestTaskMap.add_one.map(quote([1, 2, 3]))
            assert all(isinstance(f, PrefectFuture) for f in futures)
            return futures

        task_states = my_flow()
        assert [state.result() for state in task_states] == [2, 3, 4]

    def test_map_can_take_future_as_input(self):
        @task
        def some_numbers():
            return [1, 2, 3]

        @flow
        def my_flow():
            numbers_future = some_numbers.submit()
            return TestTaskMap.add_one.map(numbers_future)

        task_states = my_flow()
        assert [state.result() for state in task_states] == [2, 3, 4]

    @task
    def echo(x):
        return x

    @task
    def numbers():
        return [1, 2, 3]

    async def get_dependency_ids(self, session, flow_run_id) -> Dict[UUID, List[UUID]]:
        graph = await models.flow_runs.read_task_run_dependencies(
            session=session, flow_run_id=flow_run_id
        )

        return {x["id"]: [d.id for d in x["upstream_dependencies"]] for x in graph}

    async def test_map_preserves_dependencies_between_futures_all_mapped_children(
        self, session
    ):
        @flow
        def my_flow():
            """
                    ┌─►add_together
            numbers─┼─►add_together
                    └─►add_together
            """

            numbers = TestTaskMap.numbers.submit()
            return numbers, TestTaskMap.add_together.map(numbers, y=0)

        numbers_state, add_task_states = my_flow()
        dependency_ids = await self.get_dependency_ids(
            session, numbers_state.state_details.flow_run_id
        )

        assert [await a.result() for a in add_task_states] == [1, 2, 3]

        assert dependency_ids[numbers_state.state_details.task_run_id] == []
        assert all(
            dependency_ids[a.state_details.task_run_id]
            == [numbers_state.state_details.task_run_id]
            for a in add_task_states
        )

    async def test_map_preserves_dependencies_between_futures_all_mapped_children_multiple(
        self, session
    ):
        @flow
        def my_flow():
            """
            numbers1─┬►add_together
                     ├►add_together
            numbers2─┴►add_together
            """

            numbers1 = TestTaskMap.numbers.submit()
            numbers2 = TestTaskMap.numbers.submit()
            return (numbers1, numbers2), TestTaskMap.add_together.map(
                numbers1, numbers2
            )

        numbers_states, add_task_states = my_flow()
        dependency_ids = await self.get_dependency_ids(
            session, numbers_states[0].state_details.flow_run_id
        )

        assert [await a.result() for a in add_task_states] == [2, 4, 6]

        assert all(
            dependency_ids[n.state_details.task_run_id] == [] for n in numbers_states
        )
        assert all(
            set(dependency_ids[a.state_details.task_run_id])
            == {n.state_details.task_run_id for n in numbers_states}
            and len(dependency_ids[a.state_details.task_run_id]) == 2
            for a in add_task_states
        )

    async def test_map_preserves_dependencies_between_futures_differing_parents(
        self, session
    ):
        @flow
        def my_flow():
            """
            x1─►add_together
            x2─►add_together
            """

            x1 = TestTaskMap.echo.submit(1)
            x2 = TestTaskMap.echo.submit(2)
            return (x1, x2), TestTaskMap.add_together.map([x1, x2], y=0)

        echo_futures, add_task_states = my_flow()
        dependency_ids = await self.get_dependency_ids(
            session, echo_futures[0].state_details.flow_run_id
        )

        assert [await a.result() for a in add_task_states] == [1, 2]

        assert all(
            dependency_ids[e.state_details.task_run_id] == [] for e in echo_futures
        )
        assert all(
            dependency_ids[a.state_details.task_run_id] == [e.state_details.task_run_id]
            for a, e in zip(add_task_states, echo_futures)
        )

    async def test_map_preserves_dependencies_between_futures_static_arg(self, session):
        @flow
        def my_flow():
            """
              ┌─►add_together
            x─┼─►add_together
              └─►add_together
            """

            x = TestTaskMap.echo.submit(1)
            return x, TestTaskMap.add_together.map([1, 2, 3], y=x)

        echo_future, add_task_states = my_flow()
        dependency_ids = await self.get_dependency_ids(
            session, echo_future.state_details.flow_run_id
        )

        assert [await a.result() for a in add_task_states] == [2, 3, 4]

        assert dependency_ids[echo_future.state_details.task_run_id] == []
        assert all(
            dependency_ids[a.state_details.task_run_id]
            == [echo_future.state_details.task_run_id]
            for a in add_task_states
        )

    async def test_map_preserves_dependencies_between_futures_mixed_map(self, session):
        @flow
        def my_flow():
            """
            x─►add_together
               add_together
            """

            x = TestTaskMap.echo.submit(1)
            return x, TestTaskMap.add_together.map([x, 2], y=1)

        echo_future, add_task_states = my_flow()
        dependency_ids = await self.get_dependency_ids(
            session, echo_future.state_details.flow_run_id
        )

        assert [await a.result() for a in add_task_states] == [2, 3]

        assert dependency_ids[echo_future.state_details.task_run_id] == []
        assert dependency_ids[add_task_states[0].state_details.task_run_id] == [
            echo_future.state_details.task_run_id
        ]
        assert dependency_ids[add_task_states[1].state_details.task_run_id] == []

    async def test_map_preserves_dependencies_between_futures_deep_nesting(
        self, session
    ):
        @flow
        def my_flow():
            """
            x1─┬─►add_together
            x2─┴─►add_together
            """

            x1 = TestTaskMap.echo.submit(1)
            x2 = TestTaskMap.echo.submit(2)
            return (x1, x2), TestTaskMap.add_together.map(
                [[x1, x2], [x1, x2]], y=[[3], [4]]
            )

        echo_futures, add_task_states = my_flow()
        dependency_ids = await self.get_dependency_ids(
            session, echo_futures[0].state_details.flow_run_id
        )

        assert [await a.result() for a in add_task_states] == [[1, 2, 3], [1, 2, 4]]

        assert all(
            dependency_ids[e.state_details.task_run_id] == [] for e in echo_futures
        )
        assert all(
            set(dependency_ids[a.state_details.task_run_id])
            == {e.state_details.task_run_id for e in echo_futures}
            and len(dependency_ids[a.state_details.task_run_id]) == 2
            for a in add_task_states
        )

    def test_map_can_take_flow_state_as_input(self):
        @flow
        def child_flow():
            return [1, 2, 3]

        @flow
        def my_flow():
            numbers_state = child_flow._run()
            return TestTaskMap.add_one.map(numbers_state)

        task_states = my_flow()
        assert [state.result() for state in task_states] == [2, 3, 4]

    def test_multiple_inputs(self):
        @flow
        def my_flow():
            numbers = [1, 2, 3]
            others = [4, 5, 6]
            return TestTaskMap.add_together.map(numbers, others)

        task_states = my_flow()
        assert [state.result() for state in task_states] == [5, 7, 9]

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

        task_states = await my_flow()
        assert [await state.result() for state in task_states] == [2, 3, 4]

    async def test_async_flow_with_sync_map(self):
        @task
        def subtract_them(x, y):
            return x - y

        @flow
        async def my_flow():
            return subtract_them.map([4, 5, 6], [1, 2, 3])

        task_states = await my_flow()
        assert [await state.result() for state in task_states] == [3, 3, 3]

    @pytest.mark.parametrize("explicit", [True, False])
    def test_unmapped_int(self, explicit):
        @flow
        def my_flow():
            numbers = [1, 2, 3]
            other = unmapped(5) if explicit else 5
            return TestTaskMap.add_together.map(numbers, other)

        task_states = my_flow()
        assert [state.result() for state in task_states] == [6, 7, 8]

    @pytest.mark.parametrize("explicit", [True, False])
    def test_unmapped_str(self, explicit):
        @flow
        def my_flow():
            letters = ["a", "b", "c"]
            other = unmapped("test") if explicit else "test"
            return TestTaskMap.add_together.map(letters, other)

        task_states = my_flow()
        assert [state.result() for state in task_states] == ["atest", "btest", "ctest"]

    def test_unmapped_iterable(self):
        @flow
        def my_flow():
            numbers = [[], [], []]
            others = [4, 5, 6, 7]  # Different length!
            return TestTaskMap.add_together.map(numbers, unmapped(others))

        task_states = my_flow()
        assert [state.result() for state in task_states] == [
            [4, 5, 6, 7],
            [4, 5, 6, 7],
            [4, 5, 6, 7],
        ]

    def test_with_keyword_with_default(self):
        @task
        def add_some(x, y=5):
            return x + y

        @flow
        def my_flow():
            numbers = [1, 2, 3]
            return add_some.map(numbers)

        task_states = my_flow()
        assert [state.result() for state in task_states] == [6, 7, 8]

    def test_with_keyword_with_iterable_default(self):
        @task
        def add_some(x, y=[1, 4]):
            return x + sum(y)

        @flow
        def my_flow():
            numbers = [1, 2, 3]
            return add_some.map(numbers)

        task_states = my_flow()
        assert [state.result() for state in task_states] == [6, 7, 8]

    def test_with_variadic_keywords_and_iterable(self):
        @task
        def add_some(x, **kwargs):
            return x + kwargs["y"]

        @flow
        def my_flow():
            numbers = [1, 2, 3]
            return add_some.map(numbers, y=[4, 5, 6])

        task_states = my_flow()
        assert [state.result() for state in task_states] == [5, 7, 9]

    def test_with_variadic_keywords_and_noniterable(self):
        @task
        def add_some(x, **kwargs):
            return x + kwargs["y"]

        @flow
        def my_flow():
            numbers = [1, 2, 3]
            return add_some.map(numbers, y=1)

        task_states = my_flow()
        assert [state.result() for state in task_states] == [2, 3, 4]

    def test_map_with_sequential_runner_is_sequential_sync_flow_sync_map(self):
        """Tests that the sequential runner executes mapped tasks sequentially. Tasks sleep for
        1/100th the value of their input, starting with the longest sleep first. If the tasks
        do not execute sequentially, we expect the later tasks to append before the earlier.
        """

        @task
        def sleepy_task(n, mock_item):
            time.sleep(n / 100)
            mock_item(n)
            return n

        @flow
        def my_flow(mock_item, nums):
            sleepy_task.map(nums, unmapped(mock_item))

        nums = [i for i in range(10, 0, -1)]

        mock_item = MagicMock()
        my_flow(mock_item, nums)
        assert mock_item.call_args_list != [call(n) for n in nums]

        @flow(task_runner=SequentialTaskRunner())
        def seq_flow(mock_item, nums):
            sleepy_task.map(nums, unmapped(mock_item))

        sync_mock_item = MagicMock()
        seq_flow(sync_mock_item, nums)

        assert sync_mock_item.call_args_list == [call(n) for n in nums]

    async def test_map_with_sequential_runner_is_sequential_async_flow_sync_map(self):
        """Tests that the sequential runner executes mapped tasks sequentially. Tasks sleep for
        1/100th the value of their input, starting with the longest sleep first. If the tasks
        do not execute sequentially, we expect the later tasks to append before the earlier.
        """

        @task
        def sleepy_task(n, mock_item):
            time.sleep(n / 100)
            mock_item(n)
            return n

        @flow
        async def my_flow(mock_item, nums):
            sleepy_task.map(nums, unmapped(mock_item))

        nums = [i for i in range(10, 0, -1)]

        mock_item = MagicMock()
        await my_flow(mock_item, nums)
        assert mock_item.call_args_list != [call(n) for n in nums]

        @flow(task_runner=SequentialTaskRunner())
        async def seq_flow(mock_item, nums):
            sleepy_task.map(nums, unmapped(mock_item))

        sync_mock_item = MagicMock()
        await seq_flow(sync_mock_item, nums)

        assert sync_mock_item.call_args_list == [call(n) for n in nums]

    async def test_map_with_sequential_runner_is_sequential_async_flow_async_map(self):
        """Tests that the sequential runner executes mapped tasks sequentially. Tasks sleep for
        1/100th the value of their input, starting with the longest sleep first. If the tasks
        do not execute sequentially, we expect the later tasks to append before the earlier.
        """

        @task
        async def sleepy_task(n, mock_item):
            time.sleep(n / 100)
            mock_item(n)
            return n

        @flow
        async def my_flow(mock_item, nums):
            await sleepy_task.map(nums, unmapped(mock_item))

        nums = [i for i in range(10, 0, -1)]

        mock_item = MagicMock()
        await my_flow(mock_item, nums)
        assert mock_item.call_args_list != [call(n) for n in nums]

        @flow(task_runner=SequentialTaskRunner())
        async def seq_flow(mock_item, nums):
            await sleepy_task.map(nums, unmapped(mock_item))

        sync_mock_item = MagicMock()
        await seq_flow(sync_mock_item, nums)

        assert sync_mock_item.call_args_list == [call(n) for n in nums]


class TestTaskConstructorValidation:
    async def test_task_cannot_configure_too_many_custom_retry_delays(self):
        with pytest.raises(ValueError, match="Can not configure more"):

            @task(retries=42, retry_delay_seconds=list(range(51)))
            async def insanity():
                raise RuntimeError("try again!")

    async def test_task_cannot_configure_negative_relative_jitter(self):
        with pytest.raises(ValueError, match="`retry_jitter_factor` must be >= 0"):

            @task(retries=42, retry_delay_seconds=100, retry_jitter_factor=-10)
            async def insanity():
                raise RuntimeError("try again!")


async def test_task_run_name_is_set(prefect_client):
    @task(task_run_name="fixed-name")
    def my_task(name):
        return name

    @flow
    def my_flow(name):
        return my_task(name, return_state=True)

    tr_state = my_flow(name="chris")

    # Check that the state completed happily
    assert tr_state.is_completed()
    task_run = await prefect_client.read_task_run(tr_state.state_details.task_run_id)
    assert task_run.name == "fixed-name"


async def test_task_run_name_is_set_with_kwargs_including_defaults(prefect_client):
    @task(task_run_name="{name}-wuz-{where}")
    def my_task(name, where="here"):
        return name

    @flow
    def my_flow(name):
        return my_task(name, return_state=True)

    tr_state = my_flow(name="chris")

    # Check that the state completed happily
    assert tr_state.is_completed()
    task_run = await prefect_client.read_task_run(tr_state.state_details.task_run_id)
    assert task_run.name == "chris-wuz-here"


async def test_task_run_name_is_set_with_function(prefect_client):
    def generate_task_run_name():
        return "is-this-a-bird"

    @task(task_run_name=generate_task_run_name)
    def my_task(name, where="here"):
        return name

    @flow
    def my_flow(name):
        return my_task(name, return_state=True)

    tr_state = my_flow(name="butterfly")

    # Check that the state completed happily
    assert tr_state.is_completed()
    task_run = await prefect_client.read_task_run(tr_state.state_details.task_run_id)
    assert task_run.name == "is-this-a-bird"


async def test_task_run_name_is_set_with_function_using_runtime_context(prefect_client):
    def generate_task_run_name():
        params = task_run_ctx.parameters
        tokens = []
        tokens.append("anon" if "name" not in params else str(params["name"]))
        tokens.append("wuz")
        tokens.append("where?" if "where" not in params else str(params["where"]))

        return "-".join(tokens)

    @task(task_run_name=generate_task_run_name)
    def my_task(name, where="here"):
        return name

    @flow
    def my_flow(name):
        return my_task(name, return_state=True)

    tr_state = my_flow(name="chris")

    # Check that the state completed happily
    assert tr_state.is_completed()
    task_run = await prefect_client.read_task_run(tr_state.state_details.task_run_id)
    assert task_run.name == "chris-wuz-here"


async def test_task_run_name_is_set_with_function_not_returning_string(prefect_client):
    def generate_task_run_name():
        pass

    @task(task_run_name=generate_task_run_name)
    def my_task(name, where="here"):
        return name

    @flow
    def my_flow(name):
        return my_task(name)

    with pytest.raises(
        TypeError,
        match=(
            r"Callable <function"
            r" test_task_run_name_is_set_with_function_not_returning_string.<locals>.generate_task_run_name"
            r" at .*> for 'task_run_name' returned type NoneType but a string is"
            r" required"
        ),
    ):
        my_flow("anon")


async def test_sets_run_name_once():
    generate_task_run_name = MagicMock(return_value="some-string")
    mocked_task_method = MagicMock(side_effect=RuntimeError("Oh-no!, anyway"))

    decorated_task_method = task(task_run_name=generate_task_run_name, retries=3)(
        mocked_task_method
    )

    @flow
    def my_flow(name):
        return decorated_task_method()

    state = my_flow(name="some-name", return_state=True)

    assert state.type == StateType.FAILED
    assert mocked_task_method.call_count == 4
    assert generate_task_run_name.call_count == 1


async def test_sets_run_name_once_per_call():
    generate_task_run_name = MagicMock(return_value="some-string")
    mocked_task_method = MagicMock()

    decorated_task_method = task(task_run_name=generate_task_run_name)(
        mocked_task_method
    )

    @flow
    def my_flow(name):
        decorated_task_method()
        decorated_task_method()

        return "hi"

    state = my_flow(name="some-name", return_state=True)

    assert state.type == StateType.COMPLETED
    assert mocked_task_method.call_count == 2
    assert generate_task_run_name.call_count == 2


def create_hook(mock_obj):
    def my_hook(task, task_run, state):
        mock_obj()

    return my_hook


def create_async_hook(mock_obj):
    async def my_hook(task, task_run, state):
        mock_obj()

    return my_hook


class TestTaskHooksOnCompletion:
    def test_noniterable_hook_raises(self):
        def completion_hook():
            pass

        with pytest.raises(
            TypeError,
            match=re.escape(
                "Expected iterable for 'on_completion'; got function instead. Please"
                " provide a list of hooks to 'on_completion':\n\n"
                "@flow(on_completion=[hook1, hook2])\ndef my_flow():\n\tpass"
            ),
        ):

            @flow(on_completion=completion_hook)
            def flow1():
                pass

    def test_empty_hook_list_raises(self):
        with pytest.raises(ValueError, match="Empty list passed for 'on_completion'"):

            @flow(on_completion=[])
            def flow2():
                pass

    def test_noncallable_hook_raises(self):
        with pytest.raises(
            TypeError,
            match=re.escape(
                "Expected callables in 'on_completion'; got str instead. Please provide"
                " a list of hooks to 'on_completion':\n\n"
                "@flow(on_completion=[hook1, hook2])\ndef my_flow():\n\tpass"
            ),
        ):

            @flow(on_completion=["test"])
            def flow1():
                pass

    def test_callable_noncallable_hook_raises(self):
        def completion_hook():
            pass

        with pytest.raises(
            TypeError,
            match=re.escape(
                "Expected callables in 'on_completion'; got str instead. Please provide"
                " a list of hooks to 'on_completion':\n\n"
                "@flow(on_completion=[hook1, hook2])\ndef my_flow():\n\tpass"
            ),
        ):

            @flow(on_completion=[completion_hook, "test"])
            def flow2():
                pass

    def test_on_completion_hooks_run_on_completed(self):
        my_mock = MagicMock()

        def completed1(task, task_run, state):
            my_mock("completed1")

        def completed2(task, task_run, state):
            my_mock("completed2")

        @task(on_completion=[completed1, completed2])
        def my_task():
            pass

        @flow
        def my_flow():
            return my_task._run()

        state = my_flow()
        assert state.type == StateType.COMPLETED
        assert my_mock.call_args_list == [call("completed1"), call("completed2")]

    def test_on_completion_hooks_dont_run_on_failure(self):
        my_mock = MagicMock()

        def completed1(task, task_run, state):
            my_mock("completed1")

        def completed2(task, task_run, state):
            my_mock("completed2")

        @task(on_completion=[completed1, completed2])
        def my_task():
            raise Exception("oops")

        @flow
        def my_flow():
            future = my_task.submit()
            return future.wait()

        with pytest.raises(Exception, match="oops"):
            state = my_flow()
            assert state == StateType.FAILED
            assert my_mock.call_args_list == []

    def test_other_completion_hooks_run_if_a_hook_fails(self):
        my_mock = MagicMock()

        def completed1(task, task_run, state):
            my_mock("completed1")

        def exception_hook(task, task_run, state):
            raise Exception("oops")

        def completed2(task, task_run, state):
            my_mock("completed2")

        @task(on_completion=[completed1, exception_hook, completed2])
        def my_task():
            pass

        @flow
        def my_flow():
            return my_task._run()

        state = my_flow()
        assert state.type == StateType.COMPLETED
        assert my_mock.call_args_list == [call("completed1"), call("completed2")]

    @pytest.mark.parametrize(
        "hook1, hook2",
        [
            (create_hook, create_hook),
            (create_hook, create_async_hook),
            (create_async_hook, create_hook),
            (create_async_hook, create_async_hook),
        ],
    )
    def test_on_completion_hooks_work_with_sync_and_async(self, hook1, hook2):
        my_mock = MagicMock()
        hook1_with_mock = hook1(my_mock)
        hook2_with_mock = hook2(my_mock)

        @task(on_completion=[hook1_with_mock, hook2_with_mock])
        def my_task():
            pass

        @flow
        def my_flow():
            return my_task._run()

        state = my_flow()
        assert state.type == StateType.COMPLETED
        assert my_mock.call_args_list == [call(), call()]


class TestTaskHooksOnFailure:
    def test_noniterable_hook_raises(self):
        def failure_hook():
            pass

        with pytest.raises(
            TypeError,
            match=re.escape(
                "Expected iterable for 'on_failure'; got function instead. Please"
                " provide a list of hooks to 'on_failure':\n\n"
                "@flow(on_failure=[hook1, hook2])\ndef my_flow():\n\tpass"
            ),
        ):

            @flow(on_failure=failure_hook)
            def flow1():
                pass

    def test_empty_hook_list_raises(self):
        with pytest.raises(ValueError, match="Empty list passed for 'on_failure'"):

            @flow(on_failure=[])
            def flow2():
                pass

    def test_noncallable_hook_raises(self):
        with pytest.raises(
            TypeError,
            match=re.escape(
                "Expected callables in 'on_failure'; got str instead. Please provide a"
                " list of hooks to 'on_failure':\n\n"
                "@flow(on_failure=[hook1, hook2])\ndef my_flow():\n\tpass"
            ),
        ):

            @flow(on_failure=["test"])
            def flow1():
                pass

    def test_callable_noncallable_hook_raises(self):
        def failure_hook():
            pass

        with pytest.raises(
            TypeError,
            match=re.escape(
                "Expected callables in 'on_failure'; got str instead. Please provide a"
                " list of hooks to 'on_failure':\n\n"
                "@flow(on_failure=[hook1, hook2])\ndef my_flow():\n\tpass"
            ),
        ):

            @flow(on_failure=[failure_hook, "test"])
            def flow2():
                pass

    def test_on_failure_hooks_run_on_failure(self):
        my_mock = MagicMock()

        def failed1(task, task_run, state):
            my_mock("failed1")

        def failed2(task, task_run, state):
            my_mock("failed2")

        @task(on_failure=[failed1, failed2])
        def my_task():
            raise Exception("oops")

        @flow
        def my_flow():
            future = my_task.submit()
            return future.wait()

        with pytest.raises(Exception, match="oops"):
            state = my_flow()
            assert state.type == StateType.FAILED
            assert my_mock.call_args_list == [call("failed1"), call("failed2")]

    def test_on_failure_hooks_dont_run_on_completed(self):
        my_mock = MagicMock()

        def failed1(task, task_run, state):
            my_mock("failed1")

        def failed2(task, task_run, state):
            my_mock("failed2")

        @task(on_failure=[failed1, failed2])
        def my_task():
            pass

        @flow
        def my_flow():
            future = my_task.submit()
            return future.wait()

        state = my_flow()
        assert state.type == StateType.COMPLETED
        assert my_mock.call_args_list == []

    def test_other_failure_hooks_run_if_a_hook_fails(self):
        my_mock = MagicMock()

        def failed1(task, task_run, state):
            my_mock("failed1")

        def exception_hook(task, task_run, state):
            raise Exception("bad hook")

        def failed2(task, task_run, state):
            my_mock("failed2")

        @task(on_failure=[failed1, exception_hook, failed2])
        def my_task():
            raise Exception("oops")

        @flow
        def my_flow():
            future = my_task.submit()
            return future.wait()

        with pytest.raises(Exception, match="oops"):
            state = my_flow()
            assert state.type == StateType.FAILED
            assert my_mock.call_args_list == [call("failed1"), call("failed2")]

    @pytest.mark.parametrize(
        "hook1, hook2",
        [
            (create_hook, create_hook),
            (create_hook, create_async_hook),
            (create_async_hook, create_hook),
            (create_async_hook, create_async_hook),
        ],
    )
    def test_on_failure_hooks_work_with_sync_and_async_functions(self, hook1, hook2):
        my_mock = MagicMock()
        hook1_with_mock = hook1(my_mock)
        hook2_with_mock = hook2(my_mock)

        @task(on_failure=[hook1_with_mock, hook2_with_mock])
        def my_task():
            raise Exception("oops")

        @flow
        def my_flow():
            future = my_task.submit()
            return future.wait()

        with pytest.raises(Exception, match="oops"):
            state = my_flow()
            assert state.type == StateType.FAILED
            assert my_mock.call_args_list == [call(), call()]

    def test_failure_hooks_dont_run_on_retries(self):
        my_mock = MagicMock()

        def failed1(task, task_run, state):
            my_mock("failed1")

        @task(retries=2, on_failure=[failed1])
        def my_task():
            raise Exception("oops")

        @flow
        def my_flow():
            future = my_task.submit()
            return future.wait()

        state = my_flow._run()
        assert state.type == StateType.FAILED
        assert my_mock.call_args_list == [call("failed1")]
