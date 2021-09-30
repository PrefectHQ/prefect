import datetime
from itertools import repeat
from unittest.mock import MagicMock

import pytest

from prefect import flow, tags
from prefect.orion.schemas.core import TaskRunResult
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import State, StateType
from prefect.tasks import task, task_input_hash
from prefect.utilities.testing import exceptions_equal
from prefect.utilities.collections import quote


def comparable_inputs(d):
    return {k: set(v) for k, v in d.items()}


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
        task_state = flow_state.result()
        assert isinstance(task_state, State)
        assert task_state.result() == 1

    async def test_async_task_called_inside_async_flow(self):
        @task
        async def foo(x):
            return x

        @flow
        async def bar():
            return await foo(1)

        flow_state = await bar()
        task_state = flow_state.result()
        assert isinstance(task_state, State)
        assert task_state.result() == 1

    async def test_sync_task_called_inside_async_flow(self):
        @task
        def foo(x):
            return x

        @flow
        async def bar():
            return foo(1)

        flow_state = await bar()
        task_state = flow_state.result()
        assert isinstance(task_state, State)
        assert task_state.result() == 1

    def test_async_task_called_inside_sync_flow_raises_clear_error(self):
        @task
        async def foo(x):
            return x

        @flow
        def bar():
            return foo(1)

        state = bar()
        with pytest.raises(
            RuntimeError, match="Your task is async, but your flow is sync"
        ):
            state.result()

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
        task_state = flow_state.result(raise_on_failure=False)

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
            return bar()

        flow_state = foo()
        task_state = flow_state.result(raise_on_failure=False)

        # Assert the final state is correct
        assert task_state.is_failed()
        assert task_state.result(raise_on_failure=False) is True
        assert task_state.message == "Test returned state"

    async def test_task_runs_correctly_populate_dynamic_keys(self):
        @task
        def bar():
            return "foo"

        @flow(version="test")
        def foo():
            return bar().run_id, bar().run_id

        flow_state = foo()
        task_run_ids = flow_state.result()

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
        task_state = flow_state.result()
        assert task_state.result() == 2

    def test_task_with_variadic_args(self):
        @task
        def foo(*foo, bar):
            return foo, bar

        @flow
        def test_flow():
            return foo(1, 2, 3, bar=4)

        flow_state = test_flow()
        task_state = flow_state.result()
        assert task_state.result() == ((1, 2, 3), 4)

    def test_task_with_variadic_keyword_args(self):
        @task
        def foo(foo, bar, **foobar):
            return foo, bar, foobar

        @flow
        def test_flow():
            return foo(1, 2, x=3, y=4, z=5)

        flow_state = test_flow()
        task_state = flow_state.result()
        assert task_state.result() == (1, 2, dict(x=3, y=4, z=5))


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
        task_run_id, task_run_state = flow_state.result()

        if always_fail:
            assert task_run_state.is_failed()
            assert exceptions_equal(task_run_state.result(raise_on_failure=False), exc)
            assert mock.call_count == 4
        else:
            assert task_run_state.is_completed()
            assert task_run_state.result() is True
            assert mock.call_count == 4

        async with OrionClient() as client:
            states = await client.read_task_run_states(task_run_id)

        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Awaiting Retry",
            "Retrying",
            "Awaiting Retry",
            "Retrying",
            "Awaiting Retry",
            "Retrying",
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
        task_run_id, task_run_state = flow_state.result()

        assert task_run_state.is_completed()
        assert task_run_state.result() is True
        assert mock.call_count == 2

        async with OrionClient() as client:
            states = await client.read_task_run_states(task_run_id)
        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Awaiting Retry",
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
            return foo(1).wait(), foo(1).wait()

        flow_state = bar()
        first_state, second_state = flow_state.result()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert second_state.result() == first_state.result()

    def test_cache_hits_within_flows_are_cached(self):
        @task(cache_key_fn=lambda *_: "cache hit")
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1).wait(), foo(2).wait()

        flow_state = bar()
        first_state, second_state = flow_state.result()
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert second_state.result() == first_state.result()

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
        states = flow_state.result()
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
            return foo(1).wait(), foo(1).wait()

        flow_state = bar()
        first_state, second_state = flow_state.result()
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

        first_state, second_state = bar().result()
        assert first_state.name == "Completed"
        assert first_state.result() == "something"

        assert second_state.name == "Cached"
        assert second_state.result() == "something"

        third_state, fourth_state = bar().result()
        assert third_state.name == "Completed"
        assert fourth_state.name == "Cached"
        assert third_state.result() == "something"
        assert fourth_state.result() == "something"

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
        first_state, second_state, third_state = flow_state.result()
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert third_state.name == "Cached"

        # same output
        assert first_state.result() == 6
        assert second_state.result() == 6
        assert third_state.result() == 6

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
        first_state, second_state = flow_state.result()
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
            return foo(1).wait(), foo(2).wait()

        flow_state = bar()
        first_state, second_state = flow_state.result()
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
            return foo(1).wait(), foo(2).wait(), foo(1).wait()

        flow_state = bar()
        first_state, second_state, third_state = flow_state.result()
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
            return foo(x).wait()

        first_state = bar(1)
        second_state = bar(2)
        third_state = bar(1)
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"
        assert first_state.result() != second_state.result()
        assert first_state.result() == third_state.result() == 1


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

        task_state = my_flow().result()
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

        task_state = my_flow().result()
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
            task_state = my_flow().result()

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

        task_state = my_flow().result()
        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert not task_run.tags

    async def test_task_run_tags_respects_nesting(self, orion_client):
        @flow
        def my_flow():
            with tags("a", "b"):
                with tags("c", "d"):
                    future = my_task()

            return future

        @task
        def my_task():
            pass

        task_state = my_flow().result()
        task_run = await orion_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b", "c", "d"}


class TestTaskInputs:
    async def test_task_with_no_upstreams(self, orion_client):
        @task
        def foo(x):
            return x

        @flow
        def test_flow():
            return foo(1)

        flow_state = test_flow()
        x = flow_state.result()

        task_run = await orion_client.read_task_run(x.state_details.task_run_id)

        assert task_run.task_inputs == dict(x=[])

    async def test_task_with_multiple_args_no_upstreams(self, orion_client):
        @task
        def foo(x, *a, **k):
            return x

        @flow
        def test_flow():
            return foo(1)

        flow_state = test_flow()
        x = flow_state.result()

        task_run = await orion_client.read_task_run(x.state_details.task_run_id)

        assert task_run.task_inputs == dict(x=[], a=[], k=[])

    async def test_task_with_one_upstream(self, orion_client):
        @task
        def foo(x):
            return x

        @task
        def bar(x, y):
            return x + y

        @flow
        def test_flow():
            a = foo(1)
            b = foo(2)
            c = bar(a, 1)
            return a, b, c

        flow_state = test_flow()
        a, b, c = flow_state.result()

        task_run = await orion_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[],
        )

    async def test_task_with_one_upstream_kwarg(self, orion_client):
        @task
        def foo(x):
            return x

        @task
        def bar(x, y):
            return x + y

        @flow
        def test_flow():
            a = foo(1)
            b = foo(2)
            c = bar(x=a, y=1)
            return a, b, c

        flow_state = test_flow()
        a, b, c = flow_state.result()

        task_run = await orion_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[],
        )

    async def test_task_with_two_upstream(self, orion_client):
        @task
        def foo(x):
            return x

        @task
        def bar(x, y):
            return x + y

        @flow
        def test_flow():
            a = foo(1)
            b = foo(2)
            c = bar(a, b)
            return a, b, c

        flow_state = test_flow()
        a, b, c = flow_state.result()

        task_run = await orion_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[TaskRunResult(id=b.state_details.task_run_id)],
        )

    async def test_task_with_two_upstream_from_same_task(self, orion_client):
        @task
        def foo(x):
            return x

        @task
        def bar(x, y):
            return x + y

        @flow
        def test_flow():
            a = foo(1)
            c = bar(a, a)
            return a, c

        flow_state = test_flow()
        a, c = flow_state.result()

        task_run = await orion_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[TaskRunResult(id=a.state_details.task_run_id)],
        )

    async def test_task_with_complex_upstream_structure(self, orion_client):
        @task
        def foo(x):
            return x

        @task
        def bar(x, y):
            return x, y

        @flow
        def test_flow():
            a = foo(1)
            b = foo(2)
            c = foo(3)
            d = bar([a, a, b], {3: b, 4: {5: {c, 4}}})
            return a, b, c, d

        flow_state = test_flow()

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
            f = fails()
            b = bar(2, wait_for=[f])
            return quote(b)

        flow_state = test_flow()
        task_state = flow_state.result().unquote()
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
            return quote(b)

        flow_state = test_flow()
        task_state = flow_state.result().unquote()
        assert task_state.result() == 2

    async def test_backend_task_inputs_includes_wait_for_tasks(self, orion_client):
        @task
        def foo(x):
            return x

        @flow
        def test_flow():
            a, b = foo(1), foo(2)
            c = foo(3)
            d = foo(c, wait_for=[a, b])
            return quote((a, b, c, d))

        flow_state = test_flow()
        a, b, c, d = flow_state.result().unquote()
        d_task_run = await orion_client.read_task_run(d.state_details.task_run_id)
        assert d_task_run.task_inputs == {
            "x": [TaskRunResult(id=c.state_details.task_run_id)],
            "wait_for": [
                TaskRunResult(id=a.state_details.task_run_id),
                TaskRunResult(id=b.state_details.task_run_id),
            ],
        }
