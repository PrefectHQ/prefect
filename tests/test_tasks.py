import asyncio
import datetime
import inspect
import json
import time
from asyncio import Event, sleep
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import ANY, MagicMock, call
from uuid import UUID, uuid4

import anyio
import pydantic
import pytest
import regex as re

import prefect
from prefect import flow, tags
from prefect.blocks.core import Block
from prefect.cache_policies import (
    DEFAULT,
    INPUTS,
    NONE,
    TASK_SOURCE,
    CachePolicy,
    Inputs,
)
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import LogFilter, LogFilterFlowRunId
from prefect.client.schemas.objects import StateType, TaskRunResult
from prefect.context import FlowRunContext, TaskRunContext
from prefect.exceptions import (
    ConfigurationError,
    MappingLengthMismatch,
    MappingMissingIterable,
    ParameterBindError,
    ReservedArgumentError,
)
from prefect.filesystems import LocalFileSystem
from prefect.futures import PrefectDistributedFuture, PrefectFuture
from prefect.locking.filesystem import FileSystemLockManager
from prefect.locking.memory import MemoryLockManager
from prefect.logging import get_run_logger
from prefect.results import (
    ResultStore,
    get_or_create_default_task_scheduling_storage,
)
from prefect.runtime import task_run as task_run_ctx
from prefect.server import models
from prefect.settings import (
    PREFECT_DEBUG_MODE,
    PREFECT_LOCAL_STORAGE_PATH,
    PREFECT_TASK_DEFAULT_RETRIES,
    PREFECT_TASKS_REFRESH_CACHE,
    PREFECT_UI_URL,
    temporary_settings,
)
from prefect.states import State
from prefect.tasks import Task, task, task_input_hash
from prefect.testing.utilities import exceptions_equal
from prefect.transactions import (
    CommitMode,
    IsolationLevel,
    Transaction,
    get_transaction,
    transaction,
)
from prefect.utilities.annotations import allow_failure, unmapped
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.collections import quote
from prefect.utilities.engine import get_state_for_result


def comparable_inputs(d):
    return {k: set(v) for k, v in d.items()}


@pytest.fixture
def timeout_test_flow():
    @task(timeout_seconds=0.1)
    def times_out(x):
        time.sleep(2)
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


async def get_background_task_run_parameters(task, parameters_id):
    store = await ResultStore(
        result_storage=await get_or_create_default_task_scheduling_storage()
    ).update_for_task(task)
    return await store.read_parameters(parameters_id)


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


class TestTaskKey:
    def test_task_key_typical_case(self):
        @task
        def my_task():
            pass

        assert my_task.task_key.startswith("my_task-")

    def test_task_key_after_import(self):
        from tests.generic_tasks import noop

        assert noop.task_key.startswith("noop-")

    def test_task_key_with_funky_class(self):
        class Funky:
            def __call__(self, x):
                return x

        # set up class to trigger certain code path
        # see https://github.com/PrefectHQ/prefect/issues/15058
        funky = Funky()
        funky.__qualname__ = "__main__.Funky"
        if hasattr(funky, "__code__"):
            del funky.__code__

        tt = task(funky)
        assert tt.task_key.startswith("Funky-")


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

    def test_task_call_with_debug_mode(self):
        @task
        def foo(x):
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

    def test_task_doesnt_modify_args(self):
        @task
        def identity(x):
            return x

        @task
        def appender(x):
            x.append(3)
            return x

        val = [1, 2]
        assert identity(val) is val
        assert val == [1, 2]
        assert appender(val) is val
        assert val == [1, 2, 3]

    async def test_task_failure_raises_in_flow(self):
        @task
        def foo():
            raise ValueError("Test")

        @flow
        def bar():
            foo()
            return "bar"

        state = bar(return_state=True)
        assert state.is_failed()
        with pytest.raises(ValueError, match="Test"):
            await state.result()

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

    class BaseFooModel(pydantic.BaseModel):
        model_config = pydantic.ConfigDict(ignored_types=(Task,))
        x: int

    class BaseFoo:
        def __init__(self, x):
            self.x = x

    @pytest.mark.parametrize("T", [BaseFoo, BaseFooModel])
    def test_task_supports_instance_methods(self, T):
        class Foo(T):
            @task
            def instance_method(self):
                return self.x

        f = Foo(x=1)
        assert Foo(x=5).instance_method() == 5
        # ensure the instance binding is not global
        assert f.instance_method() == 1

        assert isinstance(Foo(x=10).instance_method, Task)

    @pytest.mark.parametrize("T", [BaseFoo, BaseFooModel])
    def test_task_supports_class_methods(self, T):
        class Foo(T):
            @classmethod
            @task
            def class_method(cls):
                return cls.__name__

        assert Foo.class_method() == "Foo"
        assert isinstance(Foo.class_method, Task)

    @pytest.mark.parametrize("T", [BaseFoo, BaseFooModel])
    def test_task_supports_static_methods(self, T):
        class Foo(T):
            @staticmethod
            @task
            def static_method():
                return "static"

        assert Foo.static_method() == "static"
        assert isinstance(Foo.static_method, Task)

    def test_instance_method_doesnt_create_copy_of_self(self):
        class Foo(pydantic.BaseModel):
            model_config = dict(
                ignored_types=(prefect.Flow, prefect.Task),
            )

            @task
            def get_x(self):
                return self

        f = Foo()

        # assert that the value is equal to the original
        assert f.get_x() == f
        # assert that the value IS the original and was never copied
        assert f.get_x() is f

    def test_instance_method_doesnt_create_copy_of_args(self):
        class Foo(pydantic.BaseModel):
            model_config = dict(
                ignored_types=(prefect.Flow, prefect.Task),
            )
            x: dict

            @task
            def get_x(self):
                return self.x

        val = dict(a=1)
        f = Foo(x=val)

        # this is surprising but pydantic sometimes copies values during
        # construction/validation (it doesn't for nested basemodels, by default)
        # Therefore this assert is to set a baseline for the test, because if
        # you try to write the test as `assert f.get_x() is val` it will fail
        # and it's not Prefect's fault.
        assert f.x is not val

        # assert that the value is equal to the original
        assert f.get_x() == f.x
        # assert that the value IS the original and was never copied
        assert f.get_x() is f.x

    def test_task_run_name_can_access_self_arg_for_instance_methods(self):
        class Foo:
            a = 10

            @task(task_run_name="{self.a}|{x}")
            def instance_method(self, x):
                return TaskRunContext.get()

        f = Foo()
        context = f.instance_method(x=5)
        assert context.task_run.name == "10|5"

    @pytest.mark.parametrize("T", [BaseFoo, BaseFooModel])
    async def test_task_supports_async_instance_methods(self, T):
        class Foo(T):
            @task
            async def instance_method(self):
                return self.x

        f = Foo(x=1)
        assert await Foo(x=5).instance_method() == 5
        # ensure the instance binding is not global
        assert await f.instance_method() == 1

        assert isinstance(Foo(x=10).instance_method, Task)

    @pytest.mark.parametrize("T", [BaseFoo, BaseFooModel])
    async def test_task_supports_async_class_methods(self, T):
        class Foo(T):
            @classmethod
            @task
            async def class_method(cls):
                return cls.__name__

        assert await Foo.class_method() == "Foo"
        assert isinstance(Foo.class_method, Task)

    @pytest.mark.parametrize("T", [BaseFoo, BaseFooModel])
    async def test_task_supports_async_static_methods(self, T):
        class Foo(T):
            @staticmethod
            @task
            async def static_method():
                return "static"

        assert await Foo.static_method() == "static"
        assert isinstance(Foo.static_method, Task)

    def test_error_message_if_decorate_classmethod(self):
        with pytest.raises(
            TypeError, match="@classmethod should be applied on top of @task"
        ):

            class Foo:
                @task
                @classmethod
                def bar():
                    pass

    def test_error_message_if_decorate_staticmethod(self):
        with pytest.raises(
            TypeError, match="@staticmethod should be applied on top of @task"
        ):

            class Foo:
                @task
                @staticmethod
                def bar():
                    pass

    def test_returns_when_cache_result_in_memory_is_false_sync_task(self):
        @task(cache_result_in_memory=False)
        def my_task():
            return 42

        assert my_task() == 42

    async def test_returns_when_cache_result_in_memory_is_false_async_task(self):
        @task(cache_result_in_memory=False)
        async def my_task():
            return 42

        assert await my_task() == 42

    def test_raises_correct_error_when_cache_result_in_memory_is_false_sync_task(self):
        @task(cache_result_in_memory=False)
        def my_task():
            raise ValueError("Test")

        with pytest.raises(ValueError, match="Test"):
            my_task()

    async def test_raises_correct_error_when_cache_result_in_memory_is_false_async_task(
        self,
    ):
        @task(cache_result_in_memory=False)
        async def my_task():
            raise ValueError("Test")

        with pytest.raises(ValueError, match="Test"):
            await my_task()


class TestTaskRun:
    async def test_sync_task_run_inside_sync_flow(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1, return_state=True)

        task_state = bar()
        assert isinstance(task_state, State)
        assert await task_state.result() == 1

    async def test_async_task_run_inside_async_flow(self):
        @task
        async def foo(x):
            return x

        @flow
        async def bar():
            return await foo(1, return_state=True)

        task_state = await bar()
        assert isinstance(task_state, State)
        assert await task_state.result() == 1

    async def test_sync_task_run_inside_async_flow(self):
        @task
        def foo(x):
            return x

        @flow
        async def bar():
            return foo(1, return_state=True)

        task_state = await bar()
        assert isinstance(task_state, State)
        assert await task_state.result() == 1

    def test_task_failure_does_not_affect_flow(self):
        @task
        def foo():
            raise ValueError("Test")

        @flow
        def bar():
            foo(return_state=True)
            return "bar"

        assert bar() == "bar"

    async def test_task_with_return_state_true(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1, return_state=True)

        task_state = bar()
        assert isinstance(task_state, State)
        assert await task_state.result() == 1


class TestTaskSubmit:
    def test_raises_outside_of_flow(self):
        @task
        def foo(x):
            return x

        with pytest.raises(RuntimeError):
            foo.submit(1)

    async def test_sync_task_submitted_inside_sync_flow(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            future = foo.submit(1)
            assert isinstance(future, PrefectFuture)
            return future

        task_state = bar()
        assert await task_state.result() == 1

    async def test_sync_task_with_return_state_true(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            state = foo.submit(1, return_state=True)
            assert isinstance(state, State)
            return state

        task_state = bar()
        assert await task_state.result() == 1

    async def test_async_task_with_return_state_true(self):
        @task
        async def foo(x):
            return x

        @flow
        async def bar():
            state = foo.submit(1, return_state=True)
            assert isinstance(state, State)
            return state

        task_state = await bar()
        assert await task_state.result() == 1

    async def test_async_task_submitted_inside_async_flow(self):
        @task
        async def foo(x):
            return x

        @flow
        async def bar():
            future = foo.submit(1)
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

    async def test_async_task_submitted_inside_sync_flow(self):
        @task
        async def foo(x):
            return x

        @flow
        def bar():
            future = foo.submit(1)
            assert isinstance(future, PrefectFuture)
            return future

        task_state = bar()
        assert await task_state.result() == 1

    def test_task_failure_does_not_affect_flow(self):
        @task
        def foo():
            raise ValueError("Test")

        @flow
        def bar():
            foo.submit()
            return "bar"

        assert bar() == "bar"

    async def test_downstream_does_not_run_if_upstream_fails(self):
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
        task_state = await flow_state.result(raise_on_failure=False)
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

    async def test_allow_failure_chained_mapped_tasks(
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

        assert await states[0].result(), await states[2].result() == [1, 3]

        assert states[1].is_completed()
        assert exceptions_equal(await states[1].result(), ValueError("Fail task"))

    async def test_allow_failure_mapped_with_noniterable_upstream(
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
            y, z = await state.result()
            assert y == i + 1
            assert exceptions_equal(z, ValueError("Fail task"))

    async def test_raises_if_depends_on_itself(self):
        @task
        def say_hello(name):
            return f"Hello {name}!"

        @flow
        def my_flow():
            greeting_queue = []
            for i in range(3):
                if greeting_queue:
                    wait_for = greeting_queue
                else:
                    wait_for = []
                future = say_hello.submit(name=f"Person {i}", wait_for=wait_for)
                greeting_queue.append(future)

            for fut in greeting_queue:
                print(fut.result())

        with pytest.raises(ValueError, match="deadlock"):
            my_flow()

    @pytest.mark.skip(
        reason="This test is not compatible with the current state of client side task orchestration"
    )
    def test_logs_message_when_submitted_tasks_end_in_pending(self, caplog):
        """
        If submitted tasks aren't waited on before a flow exits, they may fail to run
        because they're transition from PENDING to RUNNING is denied. This test ensures
        that a message is logged when this happens.
        """

        @task
        def find_palindromes():
            """This is a computationally expensive task that never ends,
            allowing the flow to exit before the task is completed."""
            num = 10
            while True:
                _ = str(num) == str(num)[::-1]
                num += 1

        @flow
        def test_flow():
            find_palindromes.submit()

        test_flow()
        assert (
            "Please wait for all submitted tasks to complete before exiting your flow"
            in caplog.text
        )


class TestTaskStates:
    @pytest.mark.parametrize("error", [ValueError("Hello"), None])
    async def test_final_state_reflects_exceptions_during_run(self, error):
        @task
        def bar():
            if error:
                raise error

        @flow(version="test")
        def foo():
            return quote(bar(return_state=True))

        task_state = foo().unquote()

        # Assert the final state is correct
        assert task_state.is_failed() if error else task_state.is_completed()
        assert exceptions_equal(await task_state.result(raise_on_failure=False), error)

    async def test_final_task_state_respects_returned_state(self):
        @task
        def bar():
            return State(
                type=StateType.FAILED,
                message="Test returned state",
                data=True,
            )

        @flow(version="test")
        def foo():
            return quote(bar(return_state=True))

        task_state = foo().unquote()

        # Assert the final state is correct
        assert task_state.is_failed()
        assert await task_state.result(raise_on_failure=False) is True
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

    async def test_task_version_is_set_in_backend(
        self, prefect_client, events_pipeline
    ):
        @task(version="test-dev-experimental")
        def my_task():
            pass

        @flow
        def test():
            return my_task(return_state=True)

        task_state = test()

        await events_pipeline.process_events()

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
            future = foo.submit()
            future.wait()
            state = future.state

            assert state.is_completed()

            # TODO: The ids are not equal here, why?
            # task_run = await prefect_client.read_task_run(state.state_details.task_run_id)
            # assert task_run.state.model_dump(exclude={"data"}) == state.model_dump(exclude={"data"})

        await my_flow()

    async def test_wait_returns_none_with_timeout_exceeded(self):
        @task
        async def foo():
            await anyio.sleep(0.1)
            return 1

        @flow
        async def my_flow():
            future = foo.submit()
            future.wait(0.01)
            state = future.state
            assert not state.is_completed()

        await my_flow()

    async def test_wait_returns_final_state_with_timeout_not_exceeded(self):
        @task
        async def foo():
            return 1

        @flow
        async def my_flow():
            future = foo.submit()
            future.wait(5)
            state = future.state

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
            future = foo.submit()
            with pytest.raises(TimeoutError):
                future.result(timeout=0.01)

        await my_flow()

    async def test_result_returns_data_with_timeout_not_exceeded(self):
        @task
        async def foo():
            return 1

        @flow
        async def my_flow():
            future = foo.submit()
            result = future.result(timeout=5)
            assert result == 1

        await my_flow()

    async def test_result_returns_data_without_timeout(self):
        @task
        async def foo():
            return 1

        @flow
        async def my_flow():
            future = foo.submit()
            result = future.result()
            assert result == 1

        await my_flow()

    async def test_result_raises_exception_from_task(self):
        @task
        async def foo():
            raise ValueError("Test")

        @flow
        async def my_flow():
            future = foo.submit()
            with pytest.raises(ValueError, match="Test"):
                future.result()
            return True  # Ignore failed tasks

        await my_flow()

    async def test_result_returns_exception_from_task_if_asked(self):
        @task
        async def foo():
            raise ValueError("Test")

        @flow
        async def my_flow():
            future = foo.submit()
            result = future.result(raise_on_failure=False)
            assert isinstance(result, ValueError) and str(result) == "Test"
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
    async def test_task_respects_retry_count(
        self, always_fail, prefect_client, events_pipeline
    ):
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
            future.wait()
            return future.state, ...

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

        await events_pipeline.process_events()

        states = await prefect_client.read_task_run_states(task_run_id)

        state_names = [state.name for state in states]
        # task retries are client-side in the new engine
        assert state_names == [
            "Pending",
            "Running",
            "Retrying",
            "Retrying",
            "Retrying",
            "Failed" if always_fail else "Completed",
        ]

    async def test_task_only_uses_necessary_retries(
        self, prefect_client, events_pipeline
    ):
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
            future.wait()
            return future.state

        task_run_state = test_flow()
        task_run_id = task_run_state.state_details.task_run_id

        assert task_run_state.is_completed()
        assert await task_run_state.result() is True
        assert mock.call_count == 2

        await events_pipeline.process_events()

        states = await prefect_client.read_task_run_states(task_run_id)
        state_names = [state.name for state in states]
        # task retries are client side in the new engine
        assert state_names == [
            "Pending",
            "Running",
            "Retrying",
            "Completed",
        ]

    async def test_task_retries_receive_latest_task_run_in_context(
        self, events_pipeline
    ):
        state_names: List[str] = []
        run_counts = []
        start_times = []

        # Added retry_delay_seconds as a regression check for https://github.com/PrefectHQ/prefect/issues/15422
        @task(retries=3, retry_delay_seconds=1)
        def flaky_function():
            ctx = TaskRunContext.get()
            state_names.append(ctx.task_run.state_name)
            run_counts.append(ctx.task_run.run_count)
            start_times.append(ctx.start_time)
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
        assert len(state_names) == len(expected_state_names) == len(run_counts)
        for i in range(len(state_names)):
            assert run_counts[i] == i + 1
            assert state_names[i] == expected_state_names[i]

            if i > 0:
                last_start_time = start_times[i - 1]
                assert (
                    last_start_time < start_times[i]
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


class TestResultPersistence:
    @pytest.mark.parametrize("persist_result", [True, False])
    def test_persist_result_set_to_bool(self, persist_result):
        @task(persist_result=persist_result)
        def my_task():
            pass

        @task
        def base():
            pass

        new_task = base.with_options(persist_result=persist_result)

        assert my_task.persist_result is persist_result
        assert new_task.persist_result is persist_result

    @pytest.mark.parametrize(
        "cache_policy",
        [policy for policy in CachePolicy.__subclasses__() if policy != NONE],
    )
    def test_setting_cache_policy_sets_persist_result_to_true(self, cache_policy):
        @task(cache_policy=cache_policy)
        def my_task():
            pass

        @task
        def base():
            pass

        new_task = base.with_options(cache_policy=cache_policy)

        assert my_task.persist_result is True
        assert new_task.persist_result is True

    def test_setting_cache_key_fn_sets_persist_result_to_true(self):
        @task(cache_key_fn=lambda *_: "test-key")
        def my_task():
            pass

        @task
        def base():
            pass

        new_task = base.with_options(cache_key_fn=lambda *_: "test-key")

        assert my_task.persist_result is True
        assert new_task.persist_result is True

    def test_setting_result_storage_sets_persist_result_to_true(self, tmpdir):
        block = LocalFileSystem(basepath=str(tmpdir))
        block.save("test-name", _sync=True)

        @task(result_storage=block)
        def my_task():
            pass

        @task
        def base():
            pass

        new_task = base.with_options(result_storage=block)

        assert my_task.persist_result is True
        assert new_task.persist_result is True

    def test_setting_result_serializer_sets_persist_result_to_true(self):
        @task(result_serializer="json")
        def my_task():
            pass

        @task
        def base():
            pass

        new_task = base.with_options(result_serializer="json")

        assert my_task.persist_result is True
        assert new_task.persist_result is True

    def test_setting_result_storage_key_sets_persist_result_to_true(self):
        @task(result_storage_key="test-key")
        def my_task():
            pass

        @task
        def base():
            pass

        new_task = base.with_options(result_storage_key="test-key")

        assert my_task.persist_result is True
        assert new_task.persist_result is True

    def test_logs_warning_on_serialization_error(self, caplog):
        @task(result_serializer="json")
        def my_task():
            return lambda: 1

        my_task()

        record = next(
            (
                record
                for record in caplog.records
                if "Encountered an error while serializing result" in record.message
            ),
            None,
        )
        assert record is not None
        assert record.levelname == "WARNING"


class TestTaskCaching:
    async def test_repeated_task_call_within_flow_is_cached_by_default(self):
        @task(persist_result=True)
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1, return_state=True), foo(1, return_state=True)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert await second_state.result() == await first_state.result()

    async def test_cache_hits_within_flows_are_cached(
        self,
    ):
        @task(
            cache_key_fn=lambda *_: "cache_hit-1",
            persist_result=True,
        )
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1, return_state=True), foo(2, return_state=True)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert await second_state.result() == await first_state.result()

    def test_many_repeated_cache_hits_within_flows_cached(
        self,
    ):
        @task(
            cache_key_fn=lambda *_: "cache_hit-2",
            persist_result=True,
        )
        def foo(x):
            return x

        @flow
        def bar():
            foo(1, return_state=True)  # populate the cache
            return [foo(i, return_state=True) for i in range(5)]

        states = bar()
        assert all(state.name == "Cached" for state in states), states

    async def test_cache_hits_between_flows_are_cached(
        self,
    ):
        @task(
            cache_key_fn=lambda *_: "cache_hit-3",
            persist_result=True,
        )
        def foo(x):
            return x

        @flow
        def bar(x):
            return foo(x, return_state=True)

        first_state = bar(1)
        second_state = bar(2)
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert await second_state.result() == await first_state.result() == 1

    def test_cache_misses_arent_cached(
        self,
    ):
        # this hash fn won't return the same value twice
        def mutating_key(*_, tally=[]):
            tally.append("x")
            return "call tally:" + "".join(tally)

        @task(cache_key_fn=mutating_key, persist_result=True)
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1, return_state=True), foo(1, return_state=True)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"

    async def test_cache_key_fn_receives_context(self):
        def get_flow_run_id(context, args):
            return str(context.task_run.flow_run_id)

        @task(cache_key_fn=get_flow_run_id, persist_result=True)
        def foo(x):
            return x

        @flow
        def bar():
            return foo("something", return_state=True), foo(
                "different", return_state=True
            )

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert await first_state.result() == "something"

        assert second_state.name == "Cached"
        assert await second_state.result() == "something"

        third_state, fourth_state = bar()
        assert third_state.name == "Completed"
        assert fourth_state.name == "Cached"
        assert await third_state.result() == "something"
        assert await fourth_state.result() == "something"

    async def test_cache_key_fn_receives_resolved_futures(
        self,
    ):
        def check_args(context, params):
            assert params["x"] == "something"
            assert len(params) == 1
            return params["x"]

        @task
        def foo(x):
            return x

        @task(cache_key_fn=check_args, persist_result=True)
        def bar(x):
            return x

        @flow
        def my_flow():
            future = foo.submit("something")
            # Mix run/submit to cover both cases
            return bar(future, return_state=True), bar.submit(future, return_state=True)

        first_state, second_state = my_flow()
        assert first_state.name == "Completed"
        assert await first_state.result() == "something"

        assert second_state.name == "Cached"
        assert await second_state.result() == "something"

    async def test_cache_key_fn_arg_inputs_are_stable(
        self,
    ):
        def stringed_inputs(context, args):
            return str(args)

        @task(cache_key_fn=stringed_inputs, persist_result=True)
        def foo(a, b, c=3):
            return a + b + c

        @flow
        def bar():
            return (
                foo(1, 2, 3, return_state=True),
                foo(1, b=2, return_state=True),
                foo(c=3, a=1, b=2, return_state=True),
            )

        first_state, second_state, third_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert third_state.name == "Cached"

        # same output
        assert await first_state.result() == 6
        assert await second_state.result() == 6
        assert await third_state.result() == 6

    async def test_cache_key_hits_with_future_expiration_are_cached(
        self,
    ):
        @task(
            cache_key_fn=lambda *_: "cache-hit-4",
            cache_expiration=datetime.timedelta(seconds=5),
            persist_result=True,
        )
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1, return_state=True), foo(2, return_state=True)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert await second_state.result() == 1

    async def test_cache_key_hits_with_past_expiration_are_not_cached(self):
        @task(
            cache_key_fn=lambda *_: "cache-hit-5",
            cache_expiration=datetime.timedelta(seconds=-5),
            persist_result=True,
        )
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1, return_state=True), foo(2, return_state=True)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert await second_state.result() != await first_state.result()

    async def test_cache_misses_w_refresh_cache(self):
        @task(
            cache_key_fn=lambda *_: "cache-hit-6",
            refresh_cache=True,
            persist_result=True,
        )
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1, return_state=True), foo(2, return_state=True)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert await second_state.result() != await first_state.result()

    async def test_cache_hits_wo_refresh_cache(
        self,
    ):
        @task(
            cache_key_fn=lambda *_: "cache-hit-7",
            refresh_cache=False,
            persist_result=True,
        )
        def foo(x):
            return x

        @flow
        def bar():
            return foo(1, return_state=True), foo(2, return_state=True)

        first_state, second_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert await second_state.result() == await first_state.result()

    async def test_tasks_refresh_cache_setting(self):
        @task(cache_key_fn=lambda *_: "cache-hit-8", persist_result=True)
        def foo(x):
            return x

        @task(
            cache_key_fn=lambda *_: "cache-hit-8",
            refresh_cache=True,
            persist_result=True,
        )
        def refresh_task(x):
            return x

        @task(
            cache_key_fn=lambda *_: "cache-hit-8",
            refresh_cache=False,
            persist_result=True,
        )
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
            assert await second_state.result() != await first_state.result()
            assert await third_state.result() == await second_state.result()

    async def test_cache_key_fn_receives_self_if_method(self):
        """
        The `self` argument of a bound method is implicitly passed as a parameter to the decorated
        function. This test ensures that it is passed to the cache key function by checking that
        two instances of the same class do not share a cache (both instances yield COMPLETED states
        the first time they run and CACHED states the second time).
        """

        cache_args = []

        def stringed_inputs(context, args):
            cache_args.append(args)
            return str(args)

        class Foo:
            def __init__(self, x):
                self.x = x

            @task(cache_key_fn=stringed_inputs, persist_result=True)
            def add(self, a):
                return a + self.x

        # create an instance that adds 1 and another that adds 100
        f1 = Foo(1)
        f2 = Foo(100)

        @flow
        def bar():
            return (
                f1.add(5, return_state=True),
                f1.add(5, return_state=True),
                f2.add(5, return_state=True),
                f2.add(5, return_state=True),
            )

        s1, s2, s3, s4 = bar()
        # the first two calls are completed / cached
        assert s1.name == "Completed"
        assert s2.name == "Cached"
        # the second two calls are completed / cached because it's a different instance
        assert s3.name == "Completed"
        assert s4.name == "Cached"

        # check that the cache key function received the self arg
        assert cache_args[0] == dict(self=f1, a=5)
        assert cache_args[1] == dict(self=f1, a=5)
        assert cache_args[2] == dict(self=f2, a=5)
        assert cache_args[3] == dict(self=f2, a=5)

        assert await s1.result() == 6
        assert await s2.result() == 6
        assert await s3.result() == 105
        assert await s4.result() == 105

    async def test_instance_methods_can_share_a_cache(
        self,
    ):
        """
        Test that instance methods can share a cache by using a cache key function that
        ignores the bound instance argument
        """

        def stringed_inputs(context, args):
            # remove the self arg from the cache key
            cache_args = args.copy()
            cache_args.pop("self")
            return str(cache_args)

        class Foo:
            def __init__(self, x):
                self.x = x

            @task(cache_key_fn=stringed_inputs, persist_result=True)
            def add(self, a):
                return a + self.x

        # create an instance that adds 1 and another that adds 100
        f1 = Foo(1)
        f2 = Foo(100)

        @flow
        def bar():
            return (
                f1.add(5, return_state=True),
                f1.add(5, return_state=True),
                f2.add(5, return_state=True),
                f2.add(5, return_state=True),
            )

        s1, s2, s3, s4 = bar()
        # all subsequent calls are cached because the instance is not part of the cache key
        assert s1.name == "Completed"
        assert s2.name == "Cached"
        assert s3.name == "Cached"
        assert s4.name == "Cached"

        assert await s1.result() == 6
        assert await s2.result() == 6
        assert await s3.result() == 6
        assert await s4.result() == 6

    async def test_cache_key_fn_takes_precedence_over_cache_policy(
        self, caplog, tmpdir
    ):
        block = LocalFileSystem(basepath=str(tmpdir))

        await block.save("test-cache-key-fn-takes-precedence-over-cache-policy")

        @task(
            cache_key_fn=lambda *_: "cache-hit-9",
            cache_policy=INPUTS,
            result_storage=block,
            persist_result=True,
        )
        def foo(x):
            return x

        first_state = foo(1, return_state=True)
        second_state = foo(2, return_state=True)
        assert first_state.name == "Completed"
        assert second_state.name == "Cached"
        assert await second_state.result() == await first_state.result()
        assert "`cache_key_fn` will be used" in caplog.text

    async def test_changing_result_storage_key_busts_cache(
        self,
    ):
        @task(
            cache_key_fn=lambda *_: "cache-hit-10",
            result_storage_key="before",
            persist_result=True,
        )
        def foo(x):
            return x

        first_state = foo(1, return_state=True)
        second_state = foo.with_options(result_storage_key="after")(
            2, return_state=True
        )
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert await first_state.result() == 1
        assert await second_state.result() == 2

    async def test_false_persist_results_sets_cache_policy_to_none(self, caplog):
        @task(persist_result=False)
        def foo(x):
            return x

        assert foo.cache_policy == NONE
        assert (
            "Ignoring `cache_policy` because `persist_result` is False"
            not in caplog.text
        )

    async def test_warns_went_false_persist_result_and_cache_policy(self, caplog):
        @task(persist_result=False, cache_policy=INPUTS)
        def foo(x):
            return x

        assert foo.cache_policy == NONE

        assert (
            "Ignoring `cache_policy` because `persist_result` is False" in caplog.text
        )

    @pytest.mark.parametrize("cache_policy", [NONE, None])
    async def test_does_not_warn_went_false_persist_result_and_none_cache_policy(
        self, caplog, cache_policy
    ):
        @task(persist_result=False, cache_policy=cache_policy)
        def foo(x):
            return x

        assert foo.cache_policy == cache_policy

        assert (
            "Ignoring `cache_policy` because `persist_result` is False"
            not in caplog.text
        )

    def test_cache_policy_storage_path(self, tmp_path):
        cache_policy = Inputs().configure(key_storage=tmp_path)
        expected_cache_key = cache_policy.compute_key(
            task_ctx=None, inputs={"x": 1}, flow_parameters=None
        )

        @task(cache_policy=cache_policy)
        def foo(x):
            return x

        foo(1)
        assert (tmp_path / expected_cache_key).exists()

    def test_cache_policy_storage_str(self, tmp_path):
        cache_policy = Inputs().configure(key_storage=str(tmp_path))
        expected_cache_key = cache_policy.compute_key(
            task_ctx=None, inputs={"x": 1}, flow_parameters=None
        )

        @task(cache_policy=cache_policy)
        def foo(x):
            return x

        foo(1)
        assert (tmp_path / expected_cache_key).exists()

    def test_cache_policy_storage_storage_block(self, tmp_path):
        cache_policy = Inputs().configure(
            key_storage=LocalFileSystem(basepath=str(tmp_path))
        )
        expected_cache_key = cache_policy.compute_key(
            task_ctx=None, inputs={"x": 1}, flow_parameters=None
        )

        @task(cache_policy=cache_policy)
        def foo(x):
            return x

        foo(1)
        # make sure cache key file and result file are both created
        assert (tmp_path / expected_cache_key).exists()
        assert "prefect_version" in json.loads(
            (tmp_path / expected_cache_key).read_text()
        )
        assert (PREFECT_LOCAL_STORAGE_PATH.value() / expected_cache_key).exists()

    @pytest.mark.parametrize(
        "isolation_level", [IsolationLevel.SERIALIZABLE, "SERIALIZABLE"]
    )
    def test_cache_policy_lock_manager(self, tmp_path, isolation_level):
        cache_policy = Inputs().configure(
            lock_manager=FileSystemLockManager(lock_files_directory=tmp_path),
            isolation_level=IsolationLevel.SERIALIZABLE,
        )
        expected_cache_key = cache_policy.compute_key(
            task_ctx=None, inputs={"x": 1}, flow_parameters=None
        )

        @task(cache_policy=cache_policy)
        def foo(x):
            assert (tmp_path / f"{expected_cache_key}.lock").exists()
            return x

        assert foo(1) == 1

    def test_cache_policy_serializable_isolation_level_with_no_manager(self):
        cache_policy = Inputs().configure(isolation_level=IsolationLevel.SERIALIZABLE)

        @task(cache_policy=cache_policy)
        def foo(x):
            return x

        with pytest.raises(
            ConfigurationError, match="not supported by provided configuration"
        ):
            foo(1)


class TestCacheFunctionBuiltins:
    async def test_task_input_hash_within_flows(
        self,
    ):
        @task(
            cache_key_fn=task_input_hash,
            persist_result=True,
        )
        def foo(x):
            return x

        @flow
        def bar():
            return (
                foo(1, return_state=True),
                foo(2, return_state=True),
                foo(1, return_state=True),
            )

        first_state, second_state, third_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"

        assert await first_state.result() != await second_state.result()
        assert await first_state.result() == await third_state.result()
        assert await first_state.result() == 1

    async def test_task_input_hash_between_flows(
        self,
    ):
        @task(
            cache_key_fn=task_input_hash,
            persist_result=True,
        )
        def foo(x):
            return x

        @flow
        def bar(x):
            return foo(x, return_state=True)

        first_state = bar(1)
        second_state = bar(2)
        third_state = bar(1)
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"
        assert await first_state.result() != await second_state.result()
        assert await first_state.result() == await third_state.result() == 1

    async def test_task_input_hash_works_with_object_return_types(
        self,
    ):
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

        @task(
            cache_key_fn=task_input_hash,
            persist_result=True,
        )
        def foo(x):
            return TestClass(x)

        @flow
        def bar():
            return (
                foo(1, return_state=True),
                foo(2, return_state=True),
                foo(1, return_state=True),
            )

        first_state, second_state, third_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"

        assert await first_state.result() != await second_state.result()
        assert await first_state.result() == await third_state.result()

    async def test_task_input_hash_works_with_object_input_types(
        self,
    ):
        class TestClass:
            def __init__(self, x):
                self.x = x

            def __eq__(self, other) -> bool:
                return type(self) == type(other) and self.x == other.x

        @task(
            cache_key_fn=task_input_hash,
            persist_result=True,
        )
        def foo(instance):
            return instance.x

        @flow
        def bar():
            return (
                foo(TestClass(1), return_state=True),
                foo(TestClass(2), return_state=True),
                foo(TestClass(1), return_state=True),
            )

        first_state, second_state, third_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"

        assert await first_state.result() != await second_state.result()
        assert await first_state.result() == await third_state.result() == 1

    async def test_task_input_hash_works_with_block_input_types(
        self,
    ):
        class TestBlock(Block):
            x: int
            y: int
            z: int

        @task(
            cache_key_fn=task_input_hash,
            persist_result=True,
        )
        def foo(instance):
            return instance.x

        @flow
        def bar():
            return (
                foo(TestBlock(x=1, y=2, z=3), return_state=True),
                foo(TestBlock(x=4, y=2, z=3), return_state=True),
                foo(TestBlock(x=1, y=2, z=3), return_state=True),
            )

        first_state, second_state, third_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"

        assert await first_state.result() != await second_state.result()
        assert await first_state.result() == await third_state.result() == 1

    async def test_task_input_hash_depends_on_task_key_and_code(
        self,
    ):
        @task(
            cache_key_fn=task_input_hash,
            persist_result=True,
        )
        def foo(x):
            return x

        def foo_new_code(x):
            return x + 1

        def foo_same_code(x):
            return x

        @task(
            cache_key_fn=task_input_hash,
            persist_result=True,
        )
        def bar(x):
            return x

        @flow
        def my_flow():
            first = foo(1, return_state=True)
            foo.fn = foo_same_code
            second = foo(1, return_state=True)
            foo.fn = foo_new_code
            third = foo(1, return_state=True)
            fourth = bar(1, return_state=True)
            fifth = bar(1, return_state=True)
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

        assert await first_state.result() == await second_state.result() == 1
        assert await first_state.result() != await third_state.result()
        assert await fourth_state.result() == await fifth_state.result() == 1

    async def test_task_input_hash_works_with_block_input_types_and_bytes(
        self,
    ):
        class TestBlock(Block):
            x: int
            y: int
            z: bytes

        @task(
            cache_key_fn=task_input_hash,
            persist_result=True,
        )
        def foo(instance):
            return instance.x

        @flow
        def bar():
            return (
                foo(
                    TestBlock(x=1, y=2, z="dog".encode("utf-8")), return_state=True
                ),  # same
                foo(
                    TestBlock(x=4, y=2, z="dog".encode("utf-8")), return_state=True
                ),  # different x
                foo(
                    TestBlock(x=1, y=2, z="dog".encode("utf-8")), return_state=True
                ),  # same
                foo(
                    TestBlock(x=1, y=2, z="dog".encode("latin-1")), return_state=True
                ),  # same
                foo(
                    TestBlock(x=1, y=2, z="cat".encode("utf-8")), return_state=True
                ),  # different z
            )

        first_state, second_state, third_state, fourth_state, fifth_state = bar()
        assert first_state.name == "Completed"
        assert second_state.name == "Completed"
        assert third_state.name == "Cached"
        assert fourth_state.name == "Cached"
        assert fifth_state.name == "Completed"

        assert await first_state.result() != await second_state.result()
        assert (
            await first_state.result()
            == await third_state.result()
            == await fourth_state.result()
            == 1
        )


class TestTaskTimeouts:
    async def test_task_timeouts_actually_timeout(self, timeout_test_flow):
        flow_state = timeout_test_flow(return_state=True)
        timed_out, _, _ = await flow_state.result(raise_on_failure=False)
        assert timed_out.name == "TimedOut"
        assert timed_out.is_failed()

    async def test_task_timeouts_are_not_task_crashes(self, timeout_test_flow):
        flow_state = timeout_test_flow(return_state=True)
        timed_out, _, _ = await flow_state.result(raise_on_failure=False)
        assert timed_out.is_crashed() is False

    async def test_task_timeouts_do_not_crash_flow_runs(self, timeout_test_flow):
        flow_state = timeout_test_flow(return_state=True)
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

        flow_state = my_flow(return_state=True)
        assert flow_state.type == StateType.COMPLETED

        task_res = await flow_state.result()
        assert task_res.type == StateType.COMPLETED


class TestTaskRunTags:
    async def test_task_run_tags_added_at_submission(
        self, prefect_client, events_pipeline
    ):
        @flow
        def my_flow():
            with tags("a", "b"):
                future = my_task.submit()

            return future

        @task
        def my_task():
            pass

        task_state = my_flow()
        await events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b"}

    async def test_task_run_tags_added_at_run(self, prefect_client, events_pipeline):
        @flow
        def my_flow():
            with tags("a", "b"):
                state = my_task(return_state=True)

            return state

        @task
        def my_task():
            pass

        task_state = my_flow()
        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b"}

    async def test_task_run_tags_added_at_call(self, prefect_client, events_pipeline):
        @flow
        def my_flow():
            with tags("a", "b"):
                result = my_task()

            return get_state_for_result(result)

        @task
        def my_task():
            return "foo"

        task_state = my_flow()
        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b"}

    async def test_task_run_tags_include_tags_on_task_object(
        self, prefect_client, events_pipeline
    ):
        @flow
        def my_flow():
            with tags("c", "d"):
                state = my_task(return_state=True)

            return state

        @task(tags={"a", "b"})
        def my_task():
            pass

        task_state = my_flow()
        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b", "c", "d"}

    async def test_task_run_tags_include_flow_run_tags(
        self, prefect_client, events_pipeline
    ):
        @flow
        def my_flow():
            with tags("c", "d"):
                state = my_task(return_state=True)

            return state

        @task
        def my_task():
            pass

        with tags("a", "b"):
            task_state = my_flow()

        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert set(task_run.tags) == {"a", "b", "c", "d"}

    async def test_task_run_tags_not_added_outside_context(
        self, prefect_client, events_pipeline
    ):
        @flow
        def my_flow():
            with tags("a", "b"):
                my_task()
            state = my_task(return_state=True)

            return state

        @task
        def my_task():
            pass

        task_state = my_flow()
        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )
        assert not task_run.tags

    async def test_task_run_tags_respects_nesting(
        self, prefect_client, events_pipeline
    ):
        @flow
        def my_flow():
            with tags("a", "b"):
                with tags("c", "d"):
                    state = my_task(return_state=True)

            return state

        @task
        def my_task():
            pass

        task_state = my_flow()
        await events_pipeline.process_events()
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
            upstream_state = upstream(result, return_state=True)
            # TODO: Running with the new engine causes the result call to return a coroutine
            # because it runs on the main thread with an active event loop. We need to update
            # result retrieval to be sync.
            result = upstream_state.result()
            if asyncio.iscoroutine(result):
                result = run_coro_as_sync(result)
            downstream_state = downstream(result, return_state=True)
            return upstream_state, downstream_state

        return upstream_downstream_flow

    async def test_task_inputs_populated_with_no_upstreams(
        self, prefect_client, events_pipeline
    ):
        @task
        def foo(x):
            return x

        @flow
        def test_flow():
            return foo.submit(1)

        flow_state = test_flow(return_state=True)
        x = await flow_state.result()
        await events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(x.state_details.task_run_id)

        assert task_run.task_inputs == dict(x=[])

    async def test_task_inputs_populated_with_no_upstreams_and_multiple_parameters(
        self, prefect_client, events_pipeline
    ):
        @task
        def foo(x, *a, **k):
            return x

        @flow
        def test_flow():
            return foo.submit(1)

        flow_state = test_flow(return_state=True)
        x = await flow_state.result()
        await events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(x.state_details.task_run_id)

        assert task_run.task_inputs == dict(x=[], a=[], k=[])

    async def test_task_inputs_populated_with_one_upstream_positional_future(
        self, prefect_client, events_pipeline
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
            c = bar(a, 1, return_state=True)
            return a, b, c

        flow_state = test_flow(return_state=True)
        a, b, c = await flow_state.result()

        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[],
        )

    async def test_task_inputs_populated_with_one_upstream_keyword_future(
        self, prefect_client, events_pipeline
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
            c = bar(x=a, y=1, return_state=True)
            return a, b, c

        flow_state = test_flow(return_state=True)
        a, b, c = await flow_state.result()

        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[],
        )

    async def test_task_inputs_populated_with_two_upstream_futures(
        self, prefect_client, events_pipeline
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
            c = bar(a, b, return_state=True)
            return a, b, c

        flow_state = test_flow(return_state=True)
        a, b, c = await flow_state.result()
        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[TaskRunResult(id=b.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_two_upstream_futures_from_same_task(
        self, prefect_client, events_pipeline
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
            c = bar(a, a, return_state=True)
            return a, c

        flow_state = test_flow(return_state=True)
        a, c = await flow_state.result()

        await events_pipeline.process_events()
        task_run = await prefect_client.read_task_run(c.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[TaskRunResult(id=a.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_nested_upstream_futures(
        self, prefect_client, events_pipeline
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
            d = bar([a, a, b], {3: b, 4: {5: {c, 4}}}, return_state=True)
            return a, b, c, d

        flow_state = test_flow(return_state=True)

        a, b, c, d = await flow_state.result()

        await events_pipeline.process_events()

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

    async def test_task_inputs_populated_with_subflow_upstream(
        self, prefect_client, events_pipeline
    ):
        @task
        def foo(x):
            return x

        @flow
        def child(x):
            return x

        @flow
        def parent():
            child_state = child(1, return_state=True)
            return child_state, foo.submit(child_state)

        parent_state = parent(return_state=True)
        child_state, task_state = await parent_state.result()

        await events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(
            task_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=child_state.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_result_upstream(
        self, sync_prefect_client, events_pipeline
    ):
        @task
        def name():
            return "Fred"

        @task
        def say_hi(name):
            return f"Hi {name}"

        @flow
        def test_flow():
            my_name = name(return_state=True)
            hi = say_hi(my_name.result(), return_state=True)
            return my_name, hi

        flow_state = test_flow(return_state=True)
        name_state, hi_state = await flow_state.result()

        await events_pipeline.process_events()

        task_run = sync_prefect_client.read_task_run(hi_state.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            name=[TaskRunResult(id=name_state.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_result_upstream_from_future(
        self, prefect_client, events_pipeline
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
            downstream_state = downstream(upstream_future, return_state=True)
            upstream_future.wait()
            upstream_state = upstream_future.state
            return upstream_state, downstream_state

        upstream_state, downstream_state = test_flow()

        await events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_result_upstream_from_state(
        self, prefect_client, events_pipeline
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
            upstream_result = upstream_state.result()
            downstream_state = downstream(upstream_result, return_state=True)
            return upstream_state, downstream_state

        upstream_state, downstream_state = test_flow()

        await events_pipeline.process_events()

        await prefect_client.read_task_run(downstream_state.state_details.task_run_id)

    async def test_task_inputs_populated_with_state_upstream(
        self, prefect_client, events_pipeline
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
            downstream_state = downstream(upstream_state, return_state=True)
            return upstream_state, downstream_state

        upstream_state, downstream_state = test_flow()

        await events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    async def test_task_inputs_populated_with_state_upstream_wrapped_with_allow_failure(
        self, prefect_client, events_pipeline
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

        await events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    @pytest.mark.parametrize("result", [["Fred"], {"one": 1}, {1, 2, 2}, (1, 2)])
    async def test_task_inputs_populated_with_collection_result_upstream(
        self, result, prefect_client, flow_with_upstream_downstream, events_pipeline
    ):
        flow_state = flow_with_upstream_downstream(result, return_state=True)
        upstream_state, downstream_state = await flow_state.result()

        await events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(
            value=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    @pytest.mark.parametrize("result", ["Fred", 5.1])
    async def test_task_inputs_populated_with_basic_result_types_upstream(
        self, result, prefect_client, flow_with_upstream_downstream, events_pipeline
    ):
        flow_state = flow_with_upstream_downstream(result, return_state=True)
        upstream_state, downstream_state = await flow_state.result()

        await events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(
            downstream_state.state_details.task_run_id
        )
        assert task_run.task_inputs == dict(
            value=[TaskRunResult(id=upstream_state.state_details.task_run_id)],
        )

    @pytest.mark.parametrize("result", [True, False, None, ..., NotImplemented])
    async def test_task_inputs_not_populated_with_singleton_results_upstream(
        self, result, prefect_client, flow_with_upstream_downstream, events_pipeline
    ):
        flow_state = flow_with_upstream_downstream(result, return_state=True)
        _, downstream_state = await flow_state.result()

        await events_pipeline.process_events()

        task_run = await prefect_client.read_task_run(
            downstream_state.state_details.task_run_id
        )

        assert task_run.task_inputs == dict(value=[])

    async def test_task_inputs_populated_with_result_upstream_from_state_with_unpacking_trackables(
        self, prefect_client, events_pipeline
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
            t1_state = task_1(return_state=True)
            t1_res_1, t1_res_2 = t1_state.result()
            t2_state = task_2(t1_res_1, return_state=True)
            t3_state = task_3(t1_res_2, return_state=True)
            return t1_state, t2_state, t3_state

        t1_state, t2_state, t3_state = unpacking_flow()

        await events_pipeline.process_events()

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
        self, prefect_client, events_pipeline
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
            t1_state = task_1(return_state=True)
            t1_res_1, t1_res_2 = t1_state.result()
            t2_state = task_2(t1_res_1, return_state=True)
            t3_state = task_3(t1_res_2, return_state=True)
            return t1_state, t2_state, t3_state

        t1_state, t2_state, t3_state = unpacking_flow()

        await events_pipeline.process_events()

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
        self, prefect_client, events_pipeline
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
            t1_state = task_1(return_state=True)
            t1_res_1, t1_res_2 = t1_state.result()
            t2_state = task_2(t1_res_1, return_state=True)
            t3_state = task_3(t1_res_2, return_state=True)
            return t1_state, t2_state, t3_state

        t1_state, t2_state, t3_state = unpacking_flow()

        await events_pipeline.process_events()

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
    async def test_downstream_does_not_run_if_upstream_fails(self):
        @task
        def fails():
            raise ValueError("Fail task!")

        @flow
        def bar(y):
            return y

        @flow
        def test_flow():
            f = fails.submit()
            b = bar(2, wait_for=[f], return_state=True)
            return b

        flow_state = test_flow(return_state=True)
        subflow_state = await flow_state.result(raise_on_failure=False)
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
            waiter_task.submit(e, 1)
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
            f = waiter_task.submit(e, 1)
            b = await setter_flow(e, wait_for=[f])
            return b

        flow_state = await test_flow(return_state=True)
        assert flow_state.is_failed()
        assert "UnfinishedRun" in flow_state.message

    def test_using_wait_for_in_task_definition_raises_reserved(self):
        with pytest.raises(
            ReservedArgumentError, match="'wait_for' is a reserved argument name"
        ):

            @flow
            def foo(wait_for):
                pass

    async def test_downstream_runs_if_upstream_fails_with_allow_failure_annotation(
        self,
    ):
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
        subflow_state = await flow_state.result(raise_on_failure=False)
        assert await subflow_state.result() == 2


class TestTaskWaitFor:
    async def test_downstream_does_not_run_if_upstream_fails(self):
        @task
        def fails():
            raise ValueError("Fail task!")

        @task
        def bar(y):
            return y

        @flow
        def test_flow():
            f = fails.submit()
            b = bar(2, wait_for=[f], return_state=True)
            return b

        flow_state = test_flow(return_state=True)
        task_state = await flow_state.result(raise_on_failure=False)
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

    async def test_backend_task_inputs_includes_wait_for_tasks(
        self, prefect_client, events_pipeline
    ):
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
        await events_pipeline.process_events()
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

    async def test_downstream_runs_if_upstream_fails_with_allow_failure_annotation(
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
            b = bar(2, wait_for=[allow_failure(f)], return_state=True)
            return b

        flow_state = test_flow(return_state=True)
        task_state = await flow_state.result(raise_on_failure=False)
        assert await task_state.result() == 2


async def _wait_for_logs(
    prefect_client: PrefectClient, flow_run_id: Optional[UUID] = None
):
    logs = []
    log_filter = (
        LogFilter(flow_run_id=LogFilterFlowRunId(any_=[flow_run_id]))
        if flow_run_id
        else None
    )
    while True:
        logs = await prefect_client.read_logs(log_filter=log_filter)
        if logs:
            break
        await asyncio.sleep(1)
    return logs


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

        # Logs don't always show up immediately with the new engine
        logs = await _wait_for_logs(prefect_client)
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

        logs = await _wait_for_logs(prefect_client)
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

        logs = await _wait_for_logs(prefect_client)
        assert "Hello world!" not in {log.message for log in logs}

    async def test_logs_are_given_correct_ids(self, prefect_client):
        @task
        def my_task():
            logger = get_run_logger()
            logger.info("Hello world!")

        @flow
        def my_flow():
            return my_task(return_state=True)

        task_state = my_flow()
        flow_run_id = task_state.state_details.flow_run_id
        task_run_id = task_state.state_details.task_run_id

        logs = await _wait_for_logs(prefect_client, flow_run_id=flow_run_id)
        assert logs, "There should be logs"
        assert all([log.flow_run_id == flow_run_id for log in logs]), str(
            [log for log in logs]
        )
        task_run_logs = [log for log in logs if log.task_run_id is not None]
        assert task_run_logs, f"There should be task run logs in {logs}"
        assert all([log.task_run_id == task_run_id for log in task_run_logs])


class TestTaskWithOptions:
    def test_with_options_allows_override_of_task_settings(self):
        def first_cache_key_fn(*_):
            return "first cache hit"

        def second_cache_key_fn(*_):
            return "second cache hit"

        block = LocalFileSystem(basepath="foo")
        block.save("foo-test", _sync=True)

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
            result_storage=block,
            cache_result_in_memory=False,
            timeout_seconds=None,
            refresh_cache=False,
            result_storage_key="foo",
        )
        def initial_task():
            pass

        new_block = LocalFileSystem(basepath="bar")
        new_block.save("bar-test", _sync=True)

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
            result_storage=new_block,
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
        assert task_with_options.result_storage == new_block
        assert task_with_options.cache_result_in_memory is True
        assert task_with_options.timeout_seconds == 42
        assert task_with_options.refresh_cache is True
        assert task_with_options.result_storage_key == "bar"

    def test_with_options_uses_existing_settings_when_no_override(self, tmp_path: Path):
        def cache_key_fn(*_):
            return "cache hit"

        storage = LocalFileSystem(basepath=tmp_path)
        storage.save("another-passthrough", _sync=True)

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
            result_storage=storage,
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
        assert task_with_options.result_storage == storage
        assert task_with_options.cache_result_in_memory is False
        assert task_with_options.timeout_seconds == 42
        assert task_with_options.refresh_cache is True
        assert task_with_options.result_storage_key == "test"

    def test_with_options_can_unset_result_options_with_none(self, tmp_path: Path):
        result_storage = LocalFileSystem(basepath=tmp_path)
        result_storage.save("test-yet-again", _sync=True)

        @task(
            result_serializer="json",
            result_storage=result_storage,
            refresh_cache=True,
            result_storage_key="test",
        )
        def initial_task():
            pass

        task_with_options = initial_task.with_options(
            result_serializer=None,
            result_storage=None,
            refresh_cache=None,
            result_storage_key=None,
        )
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

    async def test_with_options_refresh_cache(
        self,
    ):
        @task(
            cache_key_fn=lambda *_: "cache hit",
            persist_result=True,
        )
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

        assert await first.result() == await second.result()
        assert await second.result() != await third.result()
        assert await third.result() == await fourth.result()
        assert await fourth.result() != await first.result()


class TestTaskMap:
    @staticmethod
    @task
    async def add_one(x):
        return x + 1

    @staticmethod
    @task
    def add_together(x, y):
        return x + y

    async def test_simple_map(self):
        @flow
        def my_flow():
            futures = TestTaskMap.add_one.map([1, 2, 3])
            assert all(isinstance(f, PrefectFuture) for f in futures)
            return futures

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [2, 3, 4]

    async def test_simple_map_return_state_true(self):
        @flow
        def my_flow():
            states = TestTaskMap.add_one.map([1, 2, 3], return_state=True)
            assert all(isinstance(s, State) for s in states)
            return states

        states = my_flow()
        assert [await state.result() for state in states] == [2, 3, 4]

    async def test_map_can_take_tuple_as_input(self):
        @flow
        def my_flow():
            futures = TestTaskMap.add_one.map((1, 2, 3))
            assert all(isinstance(f, PrefectFuture) for f in futures)
            return futures

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [2, 3, 4]

    async def test_map_can_take_generator_as_input(self):
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
        assert [await state.result() for state in task_states] == [2, 3, 4]

    async def test_map_can_take_state_as_input(self):
        @task
        def some_numbers():
            return [1, 2, 3]

        @flow
        def my_flow():
            numbers_state = some_numbers(return_state=True)
            return TestTaskMap.add_one.map(numbers_state)

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [2, 3, 4]

    async def test_can_take_quoted_iterable_as_input(self):
        @flow
        def my_flow():
            futures = TestTaskMap.add_together.map(quote(1), [1, 2, 3])
            assert all(isinstance(f, PrefectFuture) for f in futures)
            return futures

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [2, 3, 4]

    async def test_does_not_treat_quote_as_iterable(self):
        @flow
        def my_flow():
            futures = TestTaskMap.add_one.map(quote([1, 2, 3]))
            assert all(isinstance(f, PrefectFuture) for f in futures)
            return futures

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [2, 3, 4]

    async def test_map_can_take_future_as_input(self):
        @task
        def some_numbers():
            return [1, 2, 3]

        @flow
        def my_flow():
            numbers_future = some_numbers.submit()
            return TestTaskMap.add_one.map(numbers_future)

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [2, 3, 4]

    @staticmethod
    @task
    def echo(x):
        return x

    @staticmethod
    @task
    def numbers():
        return [1, 2, 3]

    async def get_dependency_ids(self, session, flow_run_id) -> Dict[UUID, List[UUID]]:
        graph = await models.flow_runs.read_task_run_dependencies(
            session=session, flow_run_id=flow_run_id
        )

        return {x.id: [d.id for d in x.upstream_dependencies] for x in graph}

    async def test_map_preserves_dependencies_between_futures_all_mapped_children(
        self, session, events_pipeline
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
        await events_pipeline.process_events()

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
        self, session, events_pipeline
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
        await events_pipeline.process_events()
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
        self, session, events_pipeline
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
        await events_pipeline.process_events()
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

    async def test_map_preserves_dependencies_between_futures_static_arg(
        self, session, events_pipeline
    ):
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
        await events_pipeline.process_events()

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

    async def test_map_preserves_dependencies_between_futures_mixed_map(
        self, session, events_pipeline
    ):
        @flow
        def my_flow():
            """
            x─►add_together
               add_together
            """

            x = TestTaskMap.echo.submit(1)
            return x, TestTaskMap.add_together.map([x, 2], y=1)

        echo_future, add_task_states = my_flow()
        await events_pipeline.process_events()
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
        self, session, events_pipeline
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

        echo_futures, add_task_futures = my_flow()
        await events_pipeline.process_events()
        dependency_ids = await self.get_dependency_ids(
            session, echo_futures[0].state_details.flow_run_id
        )

        assert [await a.result() for a in add_task_futures] == [[1, 2, 3], [1, 2, 4]]

        assert all(
            dependency_ids[e.state_details.task_run_id] == [] for e in echo_futures
        )
        assert all(
            set(dependency_ids[a.state_details.task_run_id])
            == {e.state_details.task_run_id for e in echo_futures}
            and len(dependency_ids[a.state_details.task_run_id]) == 2
            for a in add_task_futures
        )

    async def test_map_can_take_flow_state_as_input(self):
        @flow
        def child_flow():
            return [1, 2, 3]

        @flow
        def my_flow():
            numbers_state = child_flow(return_state=True)
            return TestTaskMap.add_one.map(numbers_state)

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [2, 3, 4]

    async def test_multiple_inputs(self):
        @flow
        def my_flow():
            numbers = [1, 2, 3]
            others = [4, 5, 6]
            return TestTaskMap.add_together.map(numbers, others)

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [5, 7, 9]

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
            return TestTaskMap.add_one.map(await some_numbers())

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
    async def test_unmapped_int(self, explicit):
        @flow
        def my_flow():
            numbers = [1, 2, 3]
            other = unmapped(5) if explicit else 5
            return TestTaskMap.add_together.map(numbers, other)

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [6, 7, 8]

    @pytest.mark.parametrize("explicit", [True, False])
    async def test_unmapped_str(self, explicit):
        @flow
        def my_flow():
            letters = ["a", "b", "c"]
            other = unmapped("test") if explicit else "test"
            return TestTaskMap.add_together.map(letters, other)

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [
            "atest",
            "btest",
            "ctest",
        ]

    async def test_unmapped_iterable(self):
        @flow
        def my_flow():
            numbers = [[], [], []]
            others = [4, 5, 6, 7]  # Different length!
            return TestTaskMap.add_together.map(numbers, unmapped(others))

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [
            [4, 5, 6, 7],
            [4, 5, 6, 7],
            [4, 5, 6, 7],
        ]

    async def test_with_keyword_with_default(self):
        @task
        def add_some(x, y=5):
            return x + y

        @flow
        def my_flow():
            numbers = [1, 2, 3]
            return add_some.map(numbers)

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [6, 7, 8]

    async def test_with_keyword_with_iterable_default(self):
        @task
        def add_some(x, y=[1, 4]):
            return x + sum(y)

        @flow
        def my_flow():
            numbers = [1, 2, 3]
            return add_some.map(numbers)

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [6, 7, 8]

    async def test_with_variadic_keywords_and_iterable(self):
        @task
        def add_some(x, **kwargs):
            return x + kwargs["y"]

        @flow
        def my_flow():
            numbers = [1, 2, 3]
            return add_some.map(numbers, y=[4, 5, 6])

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [5, 7, 9]

    async def test_with_variadic_keywords_and_noniterable(self):
        @task
        def add_some(x, **kwargs):
            return x + kwargs["y"]

        @flow
        def my_flow():
            numbers = [1, 2, 3]
            return add_some.map(numbers, y=1)

        task_states = my_flow()
        assert [await state.result() for state in task_states] == [2, 3, 4]

    def test_map_raises_outside_of_flow_when_not_deferred(self):
        @task
        def test_task(x):
            print(x)

        with pytest.raises(RuntimeError):
            test_task.map([1, 2, 3])

    async def test_deferred_map_outside_flow(self):
        @task
        def test_task(x):
            print(x)

        mock_task_run_id = uuid4()
        mock_future = PrefectDistributedFuture(task_run_id=mock_task_run_id)
        mapped_args = [1, 2, 3]

        futures = test_task.map(x=mapped_args, wait_for=[mock_future], deferred=True)
        assert all(isinstance(future, PrefectDistributedFuture) for future in futures)
        for future, parameter_value in zip(futures, mapped_args):
            assert await get_background_task_run_parameters(
                test_task, future.state.state_details.task_parameters_id
            ) == {
                "parameters": {"x": parameter_value},
                "wait_for": [mock_future],
                "context": ANY,
            }

    async def test_deferred_map_inside_flow(self):
        @task
        def test_task(x):
            print(x)

        @flow
        async def test_flow():
            mock_task_run_id = uuid4()
            mock_future = PrefectDistributedFuture(task_run_id=mock_task_run_id)
            mapped_args = [1, 2, 3]

            flow_run_context = FlowRunContext.get()
            flow_run_id = flow_run_context.flow_run.id
            futures = test_task.map(
                x=mapped_args, wait_for=[mock_future], deferred=True
            )
            for future, parameter_value in zip(futures, mapped_args):
                saved_data = await get_background_task_run_parameters(
                    test_task, future.state.state_details.task_parameters_id
                )
                assert saved_data == {
                    "parameters": {"x": parameter_value},
                    "wait_for": [mock_future],
                    "context": ANY,
                }
                # Context should contain the current flow run ID
                assert (
                    saved_data["context"]["flow_run_context"]["flow_run"]["id"]
                    == flow_run_id
                )

        await test_flow()

    async def test_wait_mapped_tasks(self):
        @task
        def add_one(x):
            return x + 1

        @flow
        def my_flow():
            futures = add_one.map([1, 2, 3])
            futures.wait()
            for future in futures:
                assert future.state.is_completed()

        my_flow()

    async def test_get_results_all_mapped_tasks(self):
        @task
        def add_one(x):
            return x + 1

        @flow
        def my_flow():
            futures = add_one.map([1, 2, 3])
            results = futures.result()
            assert results == [2, 3, 4]

        my_flow()


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


async def test_task_run_name_is_set(prefect_client, events_pipeline):
    @task(task_run_name="fixed-name")
    def my_task(name):
        return name

    @flow
    def my_flow(name):
        return my_task(name, return_state=True)

    tr_state = my_flow(name="chris")
    await events_pipeline.process_events()

    # Check that the state completed happily
    assert tr_state.is_completed()
    task_run = await prefect_client.read_task_run(tr_state.state_details.task_run_id)
    assert task_run.name == "fixed-name"


async def test_task_run_name_is_set_with_kwargs_including_defaults(
    prefect_client, events_pipeline
):
    @task(task_run_name="{name}-wuz-{where}")
    def my_task(name, where="here"):
        return name

    @flow
    def my_flow(name):
        return my_task(name, return_state=True)

    tr_state = my_flow(name="chris")
    await events_pipeline.process_events()

    # Check that the state completed happily
    assert tr_state.is_completed()
    task_run = await prefect_client.read_task_run(tr_state.state_details.task_run_id)
    assert task_run.name == "chris-wuz-here"


async def test_task_run_name_is_set_with_function(prefect_client, events_pipeline):
    def generate_task_run_name():
        return "is-this-a-bird"

    @task(task_run_name=generate_task_run_name)
    def my_task(name, where="here"):
        return name

    @flow
    def my_flow(name):
        return my_task(name, return_state=True)

    tr_state = my_flow(name="butterfly")
    await events_pipeline.process_events()

    # Check that the state completed happily
    assert tr_state.is_completed()
    task_run = await prefect_client.read_task_run(tr_state.state_details.task_run_id)
    assert task_run.name == "is-this-a-bird"


async def test_task_run_name_is_set_with_function_using_runtime_context(
    prefect_client, events_pipeline
):
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
    await events_pipeline.process_events()

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
    task_calls = 0
    generate_task_run_name = MagicMock(return_value="some-string")

    def test_task(x: str):
        nonlocal task_calls
        task_calls += 1

    decorated_task_method = task(task_run_name=generate_task_run_name)(test_task)

    @flow
    def my_flow(name):
        decorated_task_method("a")
        decorated_task_method("b")

        return "hi"

    state = my_flow(name="some-name", return_state=True)

    assert state.type == StateType.COMPLETED
    assert task_calls == 2
    assert generate_task_run_name.call_count == 2


def test_task_parameter_annotations_can_be_non_pydantic_classes():
    class Test:
        pass

    @task
    def my_task(instance: Test):
        return instance

    @flow
    def my_flow(instance: Test):
        return my_task(instance)

    instance = my_flow(Test())
    assert isinstance(instance, Test)


def create_hook(mock_obj):
    def my_hook(task, task_run, state):
        mock_obj()

    return my_hook


def create_async_hook(mock_obj):
    async def my_hook(task, task_run, state):
        mock_obj()

    return my_hook


class TestTaskHooksWithKwargs:
    def test_hook_with_extra_default_arg(self):
        data = {}

        def hook(task, task_run, state, foo=42):
            data.update(name=hook.__name__, state=state, foo=foo)

        @task(on_completion=[hook])
        def foo_task():
            pass

        @flow
        def foo_flow():
            return foo_task(return_state=True)

        state = foo_flow()

        assert data == dict(name="hook", state=state, foo=42)

    def test_hook_with_bound_kwargs(self):
        data = {}

        def hook(task, task_run, state, **kwargs):
            data.update(name=hook.__name__, state=state, kwargs=kwargs)

        hook_with_kwargs = partial(hook, foo=42)

        @task(on_completion=[hook_with_kwargs])
        def foo_task():
            pass

        @flow
        def foo_flow():
            return foo_task(return_state=True)

        state = foo_flow()

        assert data == dict(name="hook", state=state, kwargs={"foo": 42})


class TestTaskHooksOnCompletion:
    def test_noniterable_hook_raises(self):
        def completion_hook():
            pass

        with pytest.raises(
            TypeError,
            match=re.escape(
                "Expected iterable for 'on_completion'; got function instead. Please"
                " provide a list of hooks to 'on_completion':\n\n"
                "@task(on_completion=[hook1, hook2])\ndef my_task():\n\tpass"
            ),
        ):

            @task(on_completion=completion_hook)
            def task1():
                pass

    def test_decorated_on_completion_hooks_run_on_completed(self):
        my_mock = MagicMock()

        @task
        def my_task():
            pass

        @my_task.on_completion
        def completed1(task, task_run, state):
            my_mock("completed1")

        @my_task.on_completion
        def completed2(task, task_run, state):
            my_mock("completed2")

        @flow
        def my_flow():
            return my_task(return_state=True)

        state = my_flow()
        assert state.type == StateType.COMPLETED
        assert my_mock.call_args_list == [call("completed1"), call("completed2")]

    def test_noncallable_hook_raises(self):
        with pytest.raises(
            TypeError,
            match=re.escape(
                "Expected callables in 'on_completion'; got str instead. Please provide"
                " a list of hooks to 'on_completion':\n\n"
                "@task(on_completion=[hook1, hook2])\ndef my_task():\n\tpass"
            ),
        ):

            @task(on_completion=["test"])
            def task1():
                pass

    def test_callable_noncallable_hook_raises(self):
        def completion_hook():
            pass

        with pytest.raises(
            TypeError,
            match=re.escape(
                "Expected callables in 'on_completion'; got str instead. Please provide"
                " a list of hooks to 'on_completion':\n\n"
                "@task(on_completion=[hook1, hook2])\ndef my_task():\n\tpass"
            ),
        ):

            @task(on_completion=[completion_hook, "test"])
            def task2():
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
            return my_task(return_state=True)

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
            future.wait()
            return future.state

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
            return my_task(return_state=True)

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
            return my_task(return_state=True)

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

    def test_decorated_on_failure_hooks_run_on_failure(self):
        my_mock = MagicMock()

        @task
        def my_task():
            raise Exception("oops")

        @my_task.on_failure
        def failed1(task, task_run, state):
            my_mock("failed1")

        @my_task.on_failure
        def failed2(task, task_run, state):
            my_mock("failed2")

        @flow
        def my_flow():
            future = my_task.submit()
            future.wait()
            return future.state

        with pytest.raises(Exception, match="oops"):
            state = my_flow()
            assert state.type == StateType.FAILED
            assert my_mock.call_args_list == [call("failed1"), call("failed2")]

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
            future.wait()
            return future.state

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
            future.wait()
            return future.state

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
            future.wait()
            return future.state

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
            future.wait()
            return future.state

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
            future.wait()
            return future.state

        state = my_flow(return_state=True)
        assert state.type == StateType.FAILED
        assert my_mock.call_args_list == [call("failed1")]

    async def test_task_condition_fn_raises_when_not_a_callable(self):
        with pytest.raises(TypeError):

            @task(retry_condition_fn="not a callable")
            def my_task():
                ...


class TestNestedTasks:
    def test_nested_task(self):
        @task
        def inner_task():
            return 42

        @task
        def outer_task():
            return inner_task()

        @flow
        def my_flow():
            return outer_task()

        result = my_flow()
        assert result == 42

    async def test_nested_async_task(self):
        @task
        async def inner_task():
            return 42

        @task
        async def outer_task():
            return await inner_task()

        @flow
        async def my_flow():
            return await outer_task()

        result = await my_flow()
        assert result == 42

    def test_nested_submitted_task(self):
        @task
        def inner_task():
            return 42

        @task
        def outer_task():
            future = inner_task.submit()
            return future.result()

        @flow
        def my_flow():
            return outer_task()

        result = my_flow()
        assert result == 42

    async def test_nested_submitted_async_task(self):
        @task
        async def inner_task():
            return 42

        @task
        async def outer_task():
            future = inner_task.submit()
            return future.result()

        @flow
        async def my_flow():
            return await outer_task()

        result = await my_flow()
        assert result == 42

    def test_nested_submitted_task_that_also_is_submitted(self):
        @task
        def inner_task():
            return 42

        @task
        def outer_task():
            future = inner_task.submit()
            return future.result()

        @flow
        def my_flow():
            future = outer_task.submit()
            return future.result()

        result = my_flow()
        assert result == 42

    async def test_nested_submitted_async_task_that_also_is_submitted(self):
        @task
        async def inner_task():
            return 42

        @task
        async def outer_task():
            future = inner_task.submit()
            return future.result()

        @flow
        async def my_flow():
            future = outer_task.submit()
            return future.result()

        result = await my_flow()
        assert result == 42

    def test_nested_map(self):
        @task
        def inner_task(x):
            return x * 2

        @task
        def outer_task(x):
            futures = inner_task.map(x)
            return sum(future.result() for future in futures)

        @flow
        def my_flow():
            result = outer_task([1, 2, 3])
            return result

        assert my_flow() == 12

    async def test_nested_async_map(self):
        @task
        async def inner_task(x):
            return x * 2

        @task
        async def outer_task(x):
            futures = inner_task.map(x)
            return sum([future.result() for future in futures])

        @flow
        async def my_flow():
            result = await outer_task([1, 2, 3])
            return result

        assert await my_flow() == 12

    def test_nested_wait_for(self):
        @task
        def inner_task(x):
            return x * 2

        @task
        def outer_task(x, y):
            future = inner_task.submit(x)
            return future.result() + y

        @flow
        def my_flow():
            f1 = inner_task.submit(2)
            f2 = outer_task.submit(3, 4, wait_for=[f1])
            return f2.result()

        assert my_flow() == 10

    async def test_nested_async_wait_for(self):
        @task
        async def inner_task(x):
            return x * 2

        @task
        async def outer_task(x, y):
            future = inner_task.submit(x)
            return future.result() + y

        @flow
        async def my_flow():
            f1 = inner_task.submit(2)
            f2 = outer_task.submit(3, 4, wait_for=[f1])
            return f2.result()

        assert await my_flow() == 10

    async def test_nested_cache_key_fn(
        self,
    ):
        @task
        def inner_task(x):
            return x * 2

        @task(
            cache_key_fn=task_input_hash,
            persist_result=True,
        )
        def outer_task(x):
            return inner_task(x)

        @flow
        def my_flow():
            state1 = outer_task(2, return_state=True)
            state2 = outer_task(2, return_state=True)

            return state1, state2

        state1, state2 = my_flow()

        assert state1.name == "Completed"
        assert state2.name == "Cached"

        assert await state1.result() == 4
        assert await state2.result() == 4

    async def test_nested_async_cache_key_fn(
        self,
    ):
        @task
        async def inner_task(x):
            return x * 2

        @task(
            cache_key_fn=task_input_hash,
            persist_result=True,
        )
        async def outer_task(x):
            return await inner_task(x)

        @flow
        async def my_flow():
            state1 = await outer_task(2, return_state=True)
            state2 = await outer_task(2, return_state=True)

            return state1, state2

        state1, state2 = await my_flow()

        assert state1.name == "Completed"
        assert state2.name == "Cached"

        assert await state1.result() == 4
        assert await state2.result() == 4

    async def test_nested_cache_key_fn_inner_task_cached_default(
        self,
    ):
        """
        By default, task transactions are LAZY committed and therefore
        inner tasks do not persist data (i.e., create a cache) until
        the outer task is complete.
        """

        @task(
            cache_key_fn=task_input_hash,
        )
        def inner_task(x):
            return x * 2

        @task
        def outer_task(x):
            state1 = inner_task(x, return_state=True)
            state2 = inner_task(x, return_state=True)
            return state1, state2

        @flow
        def my_flow():
            state = outer_task(2, return_state=True)
            return state

        state = my_flow()
        assert state.name == "Completed"
        inner_state1, inner_state2 = await state.result()
        assert inner_state1.name == "Completed"
        assert inner_state2.name == "Completed"

        assert await inner_state1.result() == 4
        assert await inner_state2.result() == 4

    async def test_nested_cache_key_fn_inner_task_cached_eager(
        self,
    ):
        """
        By default, task transactions are LAZY committed and therefore
        inner tasks do not persist data (i.e., create a cache) until
        the outer task is complete.

        This behavior can be modified by using a transaction context manager.
        """

        @task(
            cache_key_fn=task_input_hash,
            persist_result=True,
        )
        def inner_task(x):
            return x * 2

        @task
        def outer_task(x):
            with transaction(commit_mode=CommitMode.EAGER):
                state1 = inner_task(x, return_state=True)
                state2 = inner_task(x, return_state=True)
                return state1, state2

        @flow
        def my_flow():
            state = outer_task(4, return_state=True)
            return state

        state = my_flow()
        assert state.name == "Completed"
        inner_state1, inner_state2 = await state.result()
        assert inner_state1.name == "Completed"
        assert inner_state2.name == "Cached"

        assert await inner_state1.result() == 8
        assert await inner_state2.result() == 8

    async def test_nested_async_cache_key_fn_inner_task_cached_default(
        self,
    ):
        """
        By default, task transactions are LAZY committed and therefore
        inner tasks do not persist data (i.e., create a cache) until
        the outer task is complete.

        This behavior can be modified by using a transaction context manager.
        """

        @task(
            cache_key_fn=task_input_hash,
        )
        async def inner_task(x):
            return x * 2

        @task
        async def outer_task(x):
            state1 = await inner_task(x, return_state=True)
            state2 = await inner_task(x, return_state=True)
            return state1, state2

        @flow
        async def my_flow():
            state = await outer_task(2, return_state=True)
            return state

        state = await my_flow()
        assert state.name == "Completed"
        inner_state1, inner_state2 = await state.result()
        assert inner_state1.name == "Completed"
        assert inner_state2.name == "Completed"

        assert await inner_state1.result() == 4
        assert await inner_state2.result() == 4

    async def test_nested_async_cache_key_fn_inner_task_cached_eager(
        self,
    ):
        """
        By default, task transactions are LAZY committed and therefore
        inner tasks do not persist data (i.e., create a cache) until
        the outer task is complete.

        This behavior can be modified by using a transaction context manager.
        """

        @task(
            cache_key_fn=task_input_hash,
            persist_result=True,
        )
        async def inner_task(x):
            return x * 2

        @task
        async def outer_task(x):
            with transaction(commit_mode=CommitMode.EAGER):
                state1 = await inner_task(x, return_state=True)
                state2 = await inner_task(x, return_state=True)
                return state1, state2

        @flow
        async def my_flow():
            state = await outer_task(2, return_state=True)
            return state

        state = await my_flow()
        assert state.name == "Completed"
        inner_state1, inner_state2 = await state.result()
        assert inner_state1.name == "Completed"
        assert inner_state2.name == "Cached"

        assert await inner_state1.result() == 4
        assert await inner_state2.result() == 4

    def test_nested_task_with_retries(self):
        count = 0

        @task(retries=1)
        def inner_task():
            nonlocal count
            count += 1
            raise Exception("oops")

        @task
        def outer_task():
            state = inner_task(return_state=True)
            return state.name

        @flow
        def my_flow():
            return outer_task()

        result = my_flow()
        assert result == "Failed"
        assert count == 2

    def test_nested_task_with_retries_on_inner_and_outer_task(self):
        count = 0

        @task(retries=1)
        def inner_task():
            nonlocal count
            count += 1
            raise Exception("oops")

        @task(retries=1)
        def outer_task():
            inner_task()

        @flow
        def my_flow():
            state = outer_task(return_state=True)
            return state.name

        result = my_flow()
        assert result == "Failed"
        assert count == 4

    async def test_nested_async_task_without_parent_flow(self):
        @task
        async def inner_task():
            return 42

        @task
        async def outer_task():
            return await inner_task()

        result = await outer_task()
        assert result == 42


class TestCachePolicies:
    def test_cache_policy_init_to_none_when_not_persisting_results(self):
        @task(persist_result=False)
        def my_task():
            pass

        assert my_task.cache_policy is NONE

    def test_cache_policy_init_to_default_when_persisting_results(self):
        @task(persist_result=True)
        def my_task():
            pass

        assert my_task.cache_policy is DEFAULT

    def test_cache_policy_init_to_none_if_result_storage_key(self):
        @task(result_storage_key="foo", persist_result=True)
        def my_task():
            pass

        assert my_task.cache_policy is None
        assert my_task.result_storage_key == "foo"

    def test_cache_policy_inits_as_expected(self):
        @task(cache_policy=TASK_SOURCE, persist_result=True)
        def my_task():
            pass

        assert my_task.cache_policy is TASK_SOURCE


class TestTransactions:
    def test_commit_hook_is_called_on_commit(self):
        data = {}

        @task
        def my_task():
            pass

        @my_task.on_commit
        def commit(txn):
            data["txn"] = txn

        state = my_task(return_state=True)

        assert state.is_completed()
        assert state.name == "Completed"
        assert isinstance(data["txn"], Transaction)

    def test_does_not_log_rollback_when_no_user_defined_rollback_hooks(self, caplog):
        @task
        def my_task():
            pass

        @my_task.on_commit
        def commit(txn):
            raise Exception("oops")

        my_task()

        assert "Running rollback hook" not in caplog.text

    def test_run_task_in_serializable_transaction(self):
        """
        Regression test for https://github.com/PrefectHQ/prefect/issues/15503
        """

        @task
        def my_task():
            return get_transaction()

        with transaction(
            isolation_level=IsolationLevel.SERIALIZABLE,
            store=ResultStore(lock_manager=MemoryLockManager()),
        ):
            task_txn = my_task()

        assert task_txn is not None
        assert isinstance(task_txn.store, ResultStore)
        # make sure the task's result store gets the lock manager from the parent transaction
        assert task_txn.store.lock_manager == MemoryLockManager()
        assert task_txn.isolation_level == IsolationLevel.SERIALIZABLE


class TestApplyAsync:
    @pytest.mark.parametrize(
        "args, kwargs",
        [
            ((42, 42), {}),
            ([42, 42], {}),
            ((), {"x": 42, "y": 42}),
            ([42], {"y": 42}),
        ],
    )
    async def test_with_args_kwargs(self, args, kwargs):
        @task
        def multiply(x, y):
            return x * y

        future = multiply.apply_async(args, kwargs)

        assert await get_background_task_run_parameters(
            multiply, future.state.state_details.task_parameters_id
        ) == {"parameters": {"x": 42, "y": 42}, "context": ANY}

    def test_with_duplicate_values(self):
        @task
        def add(x, y):
            return x + y

        with pytest.raises(
            ParameterBindError, match="multiple values for argument 'x'"
        ):
            add.apply_async((42,), {"x": 42})

    def test_missing_values(self):
        @task
        def add(x, y):
            return x + y

        with pytest.raises(
            ParameterBindError, match="missing a required argument: 'y'"
        ):
            add.apply_async((42,))

    async def test_handles_default_values(self):
        @task
        def add(x, y=42):
            return x + y

        future = add.apply_async((42,))

        assert await get_background_task_run_parameters(
            add, future.state.state_details.task_parameters_id
        ) == {"parameters": {"x": 42, "y": 42}, "context": ANY}

    async def test_overrides_defaults(self):
        @task
        def add(x, y=42):
            return x + y

        future = add.apply_async((42,), {"y": 100})

        assert await get_background_task_run_parameters(
            add, future.state.state_details.task_parameters_id
        ) == {"parameters": {"x": 42, "y": 100}, "context": ANY}

    async def test_with_variadic_args(self):
        @task
        def add_em_up(*args):
            return sum(args)

        future = add_em_up.apply_async((42, 42))

        assert await get_background_task_run_parameters(
            add_em_up, future.state.state_details.task_parameters_id
        ) == {"parameters": {"args": (42, 42)}, "context": ANY}

    async def test_with_variadic_kwargs(self):
        @task
        def add_em_up(**kwargs):
            return sum(kwargs.values())

        future = add_em_up.apply_async(kwargs={"x": 42, "y": 42})

        assert await get_background_task_run_parameters(
            add_em_up, future.state.state_details.task_parameters_id
        ) == {"parameters": {"kwargs": {"x": 42, "y": 42}}, "context": ANY}

    async def test_with_variadic_args_and_kwargs(self):
        @task
        def add_em_up(*args, **kwargs):
            return sum(args) + sum(kwargs.values())

        future = add_em_up.apply_async((42,), {"y": 42})

        assert await get_background_task_run_parameters(
            add_em_up, future.state.state_details.task_parameters_id
        ) == {"parameters": {"args": (42,), "kwargs": {"y": 42}}, "context": ANY}

    async def test_with_wait_for(self):
        task_run_id = uuid4()
        wait_for_future = PrefectDistributedFuture(task_run_id=task_run_id)

        @task
        def multiply(x, y):
            return x * y

        future = multiply.apply_async((42, 42), wait_for=[wait_for_future])

        assert await get_background_task_run_parameters(
            multiply, future.state.state_details.task_parameters_id
        ) == {
            "parameters": {"x": 42, "y": 42},
            "wait_for": [wait_for_future],
            "context": ANY,
        }

    async def test_with_only_wait_for(self):
        task_run_id = uuid4()
        wait_for_future = PrefectDistributedFuture(task_run_id=task_run_id)

        @task
        def the_answer():
            return 42

        future = the_answer.apply_async(wait_for=[wait_for_future])

        assert await get_background_task_run_parameters(
            the_answer, future.state.state_details.task_parameters_id
        ) == {"wait_for": [wait_for_future], "context": ANY}

    async def test_with_dependencies(self, prefect_client):
        task_run_id = uuid4()

        @task
        def add(x, y):
            return x + y

        future = add.apply_async(
            (42, 42), dependencies={"x": {TaskRunResult(id=task_run_id)}}
        )
        task_run = await prefect_client.read_task_run(future.task_run_id)

        assert task_run.task_inputs == {
            "x": [TaskRunResult(id=task_run_id)],
            "y": [],
        }

    def test_apply_async_emits_run_ui_url(self, caplog):
        @task
        def add(x, y):
            return x + y

        with temporary_settings({PREFECT_UI_URL: "http://test/api"}):
            add.apply_async((42, 42))

        assert "in the UI at 'http://test/api/runs/task-run/" in caplog.text


class TestDelay:
    @pytest.mark.parametrize(
        "args, kwargs",
        [
            ((42, 42), {}),
            ([42, 42], {}),
            ((), {"x": 42, "y": 42}),
            ([42], {"y": 42}),
        ],
    )
    async def test_delay_with_args_kwargs(self, args, kwargs):
        @task
        def multiply(x, y):
            return x * y

        future = multiply.delay(*args, **kwargs)

        assert await get_background_task_run_parameters(
            multiply, future.state.state_details.task_parameters_id
        ) == {"parameters": {"x": 42, "y": 42}, "context": ANY}

    def test_delay_with_duplicate_values(self):
        @task
        def add(x, y):
            return x + y

        with pytest.raises(
            ParameterBindError, match="multiple values for argument 'x'"
        ):
            add.delay(42, x=42)

    def test_delay_missing_values(self):
        @task
        def add(x, y):
            return x + y

        with pytest.raises(
            ParameterBindError, match="missing a required argument: 'y'"
        ):
            add.delay(42)

    async def test_delay_handles_default_values(self):
        @task
        def add(x, y=42):
            return x + y

        future = add.delay(42)

        assert await get_background_task_run_parameters(
            add, future.state.state_details.task_parameters_id
        ) == {"parameters": {"x": 42, "y": 42}, "context": ANY}

    async def test_delay_overrides_defaults(self):
        @task
        def add(x, y=42):
            return x + y

        future = add.delay(42, y=100)

        assert await get_background_task_run_parameters(
            add, future.state.state_details.task_parameters_id
        ) == {"parameters": {"x": 42, "y": 100}, "context": ANY}

    async def test_delay_with_variadic_args(self):
        @task
        def add_em_up(*args):
            return sum(args)

        future = add_em_up.delay(42, 42)

        assert await get_background_task_run_parameters(
            add_em_up, future.state.state_details.task_parameters_id
        ) == {"parameters": {"args": (42, 42)}, "context": ANY}

    async def test_delay_with_variadic_kwargs(self):
        @task
        def add_em_up(**kwargs):
            return sum(kwargs.values())

        future = add_em_up.delay(x=42, y=42)

        assert await get_background_task_run_parameters(
            add_em_up, future.state.state_details.task_parameters_id
        ) == {"parameters": {"kwargs": {"x": 42, "y": 42}}, "context": ANY}

    async def test_delay_with_variadic_args_and_kwargs(self):
        @task
        def add_em_up(*args, **kwargs):
            return sum(args) + sum(kwargs.values())

        future = add_em_up.delay(42, y=42)

        assert await get_background_task_run_parameters(
            add_em_up, future.state.state_details.task_parameters_id
        ) == {"parameters": {"args": (42,), "kwargs": {"y": 42}}, "context": ANY}
