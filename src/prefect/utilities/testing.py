""""
Internal utilities for tests.
"""
import os
import sys
import warnings
from abc import ABC, abstractmethod
from contextlib import contextmanager

import pytest

import prefect.context
import prefect.settings
from prefect.task_runners import BaseTaskRunner, TaskConcurrencyType


def exceptions_equal(a, b):
    """
    Exceptions cannot be compared by `==`. They can be compared using `is` but this
    will fail if the exception is serialized/deserialized so this utility does its
    best to assert equality using the type and args used to initialize the exception
    """
    if a == b:
        return True
    return type(a) == type(b) and getattr(a, "args", None) == getattr(b, "args", None)


# AsyncMock has a new import path in Python 3.8+

if sys.version_info < (3, 8):
    # https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock
    from mock import AsyncMock
else:
    from unittest.mock import AsyncMock


@contextmanager
def temporary_settings(**kwargs):
    """
    Temporarily override setting values by updating the current os.environ and changing
    the profile context.

    This will _not_ mutate values that have been already been accessed at module
    load time.

    This function should only be used for testing.

    Example:
        >>> from prefect.settings import PREFECT_API_URL
        >>> with temporary_settings(PREFECT_API_URL="foo"):
        >>>    assert PREFECT_API_URL.value() == "foo"
        >>> assert PREFECT_API_URL.value() is None
    """
    old_env = os.environ.copy()

    # Cast to strings
    variables = {key: str(value) for key, value in kwargs.items()}

    try:
        for key in variables:
            os.environ[key] = str(variables[key])

        new_settings = prefect.settings.get_settings_from_env()

        with prefect.context.ProfileContext(
            name="temporary", settings=new_settings, env=variables
        ):
            yield new_settings

    finally:
        for key in variables:
            if old_env.get(key):
                os.environ[key] = old_env[key]
            else:
                os.environ.pop(key, None)


@contextmanager
def assert_does_not_warn():
    """
    Converts warnings to errors within this context to assert warnings are not raised.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        try:
            yield
        except Warning as warning:
            raise AssertionError(f"Warning was raised. {warning!r}") from warning


def parameterize_with_fixtures(name: str, *values):
    """
    Create a parameterized fixture from a collection of fixtures.

    Generates a `pytest.mark.parametrize` instance from a collection of fixtures.

    Passes marks from the fixtures to the parameter.

    Example:

        >>> @pytest.fixture
        >>> @pytest.mark.foo
        >>> def foo():
        >>>     return "foo"
        >>>
        >>>
        >>> @pytest.fixture
        >>> @pytest.mark.bar
        >>> def bar():
        >>>     return "bar"
        >>>
        >>> @parameterize_with_fixtures("foobar", foo, bar)
        >>> def test_foo_or_bar(foobar)
        >>>     assert foobar == "foo" or foobar == "bar"
    """

    def add_marks(item):
        return pytest.param(
            item, marks=[mark for mark in getattr(item, "pytestmark", [])]
        )

    values = [add_marks(value) for value in values]

    return pytest.mark.parametrize(
        name,
        values,
        indirect=True,
    )


import time
from uuid import uuid4

import anyio
import cloudpickle

from prefect import flow, task
from prefect.futures import PrefectFuture
from prefect.orion.schemas.core import TaskRun
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import State, StateType


class TaskRunnerTests(ABC):
    """
    Run the test suite for a given task runner.

    Implementations must define a `task_runner` fixture.
    """

    @pytest.fixture
    def task_runner(self) -> BaseTaskRunner:
        """
        Yield a task runner to run tests with
        """
        if getattr(self, "parameterized_task_runner", None):
            yield self.parameterized_task_runner
        else:
            raise NotImplementedError("You must provide a `task_runner` fixture.")

    def get_sleep_time(self) -> float:
        """
        Return an amount of time to sleep for concurrency tests
        """
        return 0.5

    async def test_successful_flow_run(self, task_runner):
        @task
        def task_a():
            return "a"

        @task
        def task_b():
            return "b"

        @task
        def task_c(b):
            return b + "c"

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            a = task_a()
            b = task_b()
            c = task_c(b)
            return a, b, c

        a, b, c = test_flow().result()

        assert (a.result(), b.result(), c.result()) == (
            "a",
            "b",
            "bc",
        )

    def test_failing_flow_run(self, task_runner):
        @task
        def task_a():
            raise RuntimeError("This task fails!")

        @task
        def task_b():
            raise ValueError("This task fails and passes data downstream!")

        @task
        def task_c(b):
            # This task attempts to use the upstream data and should fail too
            return b + "c"

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            a = task_a()
            b = task_b()
            c = task_c(b)
            d = task_c(c)

            return a, b, c, d

        state = test_flow()

        assert state.is_failed()
        a, b, c, d = state.result(raise_on_failure=False)
        with pytest.raises(RuntimeError, match="This task fails!"):
            a.result()
        with pytest.raises(
            ValueError, match="This task fails and passes data downstream"
        ):
            b.result()

        assert c.is_pending()
        assert c.name == "NotReady"
        assert (
            f"Upstream task run '{b.state_details.task_run_id}' did not reach a 'COMPLETED' state"
            in c.message
        )

        assert d.is_pending()
        assert d.name == "NotReady"
        assert (
            f"Upstream task run '{c.state_details.task_run_id}' did not reach a 'COMPLETED' state"
            in d.message
        )

    @pytest.fixture
    def tmp_file(self, tmp_path):
        tmp_file = tmp_path / "canary.txt"
        tmp_file.touch()
        return tmp_file

    def test_sync_tasks_run_sequentially_with_sequential_concurrency_type(
        self, task_runner, tmp_file
    ):
        if task_runner.concurrency_type != TaskConcurrencyType.SEQUENTIAL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task runners."
            )

        @task
        def foo():
            time.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            foo()
            bar()

        test_flow().result()

        assert tmp_file.read_text() == "bar"

    def test_sync_tasks_run_concurrently_with_nonsequential_concurrency_type(
        self, task_runner, tmp_file
    ):
        if task_runner.concurrency_type == TaskConcurrencyType.SEQUENTIAL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task runners."
            )

        @task
        def foo():
            # This test is prone to flaking
            time.sleep(self.get_sleep_time() + 0.5)
            tmp_file.write_text("foo")

        @task
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            foo()
            bar()

        test_flow().result()

        assert tmp_file.read_text() == "foo"

    async def test_async_tasks_run_sequentially_with_sequential_concurrency_type(
        self, task_runner, tmp_file
    ):
        if task_runner.concurrency_type != TaskConcurrencyType.SEQUENTIAL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task runners."
            )

        @task
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            await foo()
            await bar()

        (await test_flow()).result()

        assert tmp_file.read_text() == "bar"

    async def test_async_tasks_run_concurrently_with_nonsequential_concurrency_type(
        self, task_runner, tmp_file
    ):
        if task_runner.concurrency_type == TaskConcurrencyType.SEQUENTIAL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task runners."
            )

        @task
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            await foo()
            await bar()

        (await test_flow()).result()

        assert tmp_file.read_text() == "foo"

    async def test_async_tasks_run_concurrently_with_task_group_with_all_concurrency_types(
        self, task_runner, tmp_file
    ):
        @task
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            async with anyio.create_task_group() as tg:
                tg.start_soon(foo)
                tg.start_soon(bar)

        (await test_flow()).result()

        assert tmp_file.read_text() == "foo"

    def test_sync_subflows_run_sequentially_with_all_concurrency_types(
        self, task_runner, tmp_file
    ):
        @flow
        def foo():
            time.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @flow
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            foo()
            bar()

        test_flow().result()

        assert tmp_file.read_text() == "bar"

    async def test_async_subflows_run_sequentially_with_all_concurrency_types(
        self, task_runner, tmp_file
    ):
        @flow
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @flow
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            await foo()
            await bar()

        (await test_flow()).result()

        assert tmp_file.read_text() == "bar"

    async def test_async_subflows_run_concurrently_with_task_group_with_all_concurrency_types(
        self, task_runner, tmp_file
    ):
        @flow
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @flow
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            async with anyio.create_task_group() as tg:
                tg.start_soon(foo)
                tg.start_soon(bar)

        (await test_flow()).result()

        assert tmp_file.read_text() == "foo"

    async def test_is_pickleable_after_start(self, task_runner):
        """
        The task_runner must be picklable as it is attached to `PrefectFuture` objects
        """
        async with task_runner.start():
            pickled = cloudpickle.dumps(task_runner)
            unpickled = cloudpickle.loads(pickled)
            assert isinstance(unpickled, type(task_runner))

    async def test_submit_and_wait(self, task_runner):
        task_run = TaskRun(flow_run_id=uuid4(), task_key="foo", dynamic_key="bar")

        async def fake_orchestrate_task_run(example_kwarg):
            return State(
                type=StateType.COMPLETED,
                data=DataDocument.encode("json", example_kwarg),
            )

        async with task_runner.start():
            fut = await task_runner.submit(
                task_run=task_run,
                run_fn=fake_orchestrate_task_run,
                run_kwargs=dict(example_kwarg=1),
            )
            assert isinstance(fut, PrefectFuture), "submit should return a future"
            assert fut.task_run == task_run, "the future should have the same task run"
            assert fut.asynchronous == True

            state = await task_runner.wait(fut, 5)
            assert state is not None, "wait timed out"
            assert isinstance(state, State), "wait should return a state"
            assert state.result() == 1

    @pytest.mark.parametrize("exception", [KeyboardInterrupt(), ValueError("test")])
    async def test_wait_captures_exceptions_as_crashed_state(
        self, task_runner, exception
    ):
        task_run = TaskRun(flow_run_id=uuid4(), task_key="foo", dynamic_key="bar")

        async def fake_orchestrate_task_run():
            raise exception

        async with task_runner.start():
            future = await task_runner.submit(
                task_run=task_run, run_fn=fake_orchestrate_task_run, run_kwargs={}
            )

            state = await task_runner.wait(future, 5)
            assert state is not None, "wait timed out"
            assert isinstance(state, State), "wait should return a state"
            assert state.name == "Crashed"
            result = state.result(raise_on_failure=False)

        assert exceptions_equal(result, exception)
