import enum
import inspect
import sys
import time
from textwrap import dedent
from typing import List
from unittest.mock import MagicMock, call

import anyio
import pydantic
import pytest

from prefect import flow, get_run_logger, tags, task
from prefect.blocks.core import Block
from prefect.client.orchestration import PrefectClient
from prefect.context import PrefectObjectRegistry
from prefect.deprecated.data_documents import DataDocument
from prefect.exceptions import (
    CancelledRun,
    InvalidNameError,
    MissingResult,
    ParameterTypeError,
    ReservedArgumentError,
)
from prefect.filesystems import LocalFileSystem
from prefect.flows import Flow, load_flow_from_entrypoint
from prefect.results import PersistedResult
from prefect.server.schemas.core import TaskRunResult
from prefect.server.schemas.filters import FlowFilter, FlowRunFilter
from prefect.server.schemas.sorting import FlowRunSort
from prefect.settings import PREFECT_LOCAL_STORAGE_PATH, temporary_settings
from prefect.states import Cancelled, State, StateType, raise_state_exception
from prefect.task_runners import ConcurrentTaskRunner, SequentialTaskRunner
from prefect.testing.utilities import (
    exceptions_equal,
    flaky_on_windows,
    get_most_recent_flow_run,
)
from prefect.utilities.annotations import allow_failure, quote
from prefect.utilities.callables import parameter_schema
from prefect.utilities.collections import flatdict_to_dict
from prefect.utilities.hashing import file_hash


class TestFlow:
    def test_initializes(self):
        f = Flow(
            name="test",
            fn=lambda **kwargs: 42,
            version="A",
            description="B",
            flow_run_name="hi",
        )
        assert f.name == "test"
        assert f.fn() == 42
        assert f.version == "A"
        assert f.description == "B"
        assert f.flow_run_name == "hi"

    def test_initializes_with_default_version(self):
        f = Flow(name="test", fn=lambda **kwargs: 42)
        assert isinstance(f.version, str)

    @pytest.mark.parametrize(
        "sourcefile", [None, "<stdin>", "<ipython-input-1-d31e8a6792d4>"]
    )
    def test_version_none_if_source_file_cannot_be_determined(
        self, monkeypatch, sourcefile
    ):
        """
        `getsourcefile` will return `None` when functions are defined interactively,
        or other values on Windows.
        """
        monkeypatch.setattr(
            "prefect.flows.inspect.getsourcefile", MagicMock(return_value=sourcefile)
        )

        f = Flow(name="test", fn=lambda **kwargs: 42)
        assert f.version is None

    def test_raises_on_bad_funcs(self):
        with pytest.raises(TypeError):
            Flow(name="test", fn={})

    def test_default_description_is_from_docstring(self):
        def my_fn():
            """
            Hello
            """

        f = Flow(
            name="test",
            fn=my_fn,
        )
        assert f.description == "Hello"

    def test_default_name_is_from_function(self):
        def my_fn():
            pass

        f = Flow(
            fn=my_fn,
        )
        assert f.name == "my-fn"

    def test_raises_clear_error_when_not_compatible_with_validator(self):
        def my_fn(v__args):
            pass

        with pytest.raises(
            ValueError,
            match="Flow function is not compatible with `validate_parameters`",
        ):
            Flow(fn=my_fn)

    @pytest.mark.parametrize(
        "name",
        [
            "my/flow",
            r"my%flow",
            "my<flow",
            "my>flow",
            "my&flow",
        ],
    )
    def test_invalid_name(self, name):
        with pytest.raises(InvalidNameError, match="contains an invalid character"):
            Flow(fn=lambda: 1, name=name)

    def test_using_return_state_in_flow_definition_raises_reserved(self):
        with pytest.raises(
            ReservedArgumentError, match="'return_state' is a reserved argument name"
        ):
            f = Flow(
                name="test", fn=lambda return_state: 42, version="A", description="B"
            )

    def test_param_description_from_docstring(self):
        def my_fn(x):
            """
            Hello

            Args:
                x: description
            """

        f = Flow(fn=my_fn)
        assert parameter_schema(f).properties["x"]["description"] == "description"


class TestDecorator:
    def test_flow_decorator_initializes(self):
        # TODO: We should cover initialization with a task runner once introduced
        @flow(name="foo", version="B", flow_run_name="hi")
        def my_flow():
            return "bar"

        assert isinstance(my_flow, Flow)
        assert my_flow.name == "foo"
        assert my_flow.version == "B"
        assert my_flow.fn() == "bar"
        assert my_flow.flow_run_name == "hi"

    def test_flow_decorator_sets_default_version(self):
        my_flow = flow(flatdict_to_dict)

        assert my_flow.version == file_hash(flatdict_to_dict.__globals__["__file__"])


class TestFlowWithOptions:
    def test_with_options_allows_override_of_flow_settings(self):
        @flow(
            name="Initial flow",
            description="Flow before with options",
            flow_run_name="OG",
            task_runner=ConcurrentTaskRunner,
            timeout_seconds=10,
            validate_parameters=True,
            persist_result=True,
            result_serializer="pickle",
            result_storage=LocalFileSystem(basepath="foo"),
            cache_result_in_memory=False,
            on_completion=[],
            on_failure=[],
        )
        def initial_flow():
            pass

        failure_hook = lambda task, task_run, state: print("Woof!")
        success_hook = lambda task, task_run, state: print("Meow!")

        flow_with_options = initial_flow.with_options(
            name="Copied flow",
            description="A copied flow",
            flow_run_name="new-name",
            task_runner=SequentialTaskRunner,
            retries=3,
            retry_delay_seconds=20,
            timeout_seconds=5,
            validate_parameters=False,
            persist_result=False,
            result_serializer="json",
            result_storage=LocalFileSystem(basepath="bar"),
            cache_result_in_memory=True,
            on_completion=[success_hook],
            on_failure=[failure_hook],
        )

        assert flow_with_options.name == "Copied flow"
        assert flow_with_options.description == "A copied flow"
        assert flow_with_options.flow_run_name == "new-name"
        assert isinstance(flow_with_options.task_runner, SequentialTaskRunner)
        assert flow_with_options.timeout_seconds == 5
        assert flow_with_options.retries == 3
        assert flow_with_options.retry_delay_seconds == 20
        assert flow_with_options.should_validate_parameters is False
        assert flow_with_options.persist_result is False
        assert flow_with_options.result_serializer == "json"
        assert flow_with_options.result_storage == LocalFileSystem(basepath="bar")
        assert flow_with_options.cache_result_in_memory is True
        assert flow_with_options.on_completion == [success_hook]
        assert flow_with_options.on_failure == [failure_hook]

    def test_with_options_uses_existing_settings_when_no_override(self):
        @flow(
            name="Initial flow",
            description="Flow before with options",
            task_runner=SequentialTaskRunner,
            timeout_seconds=10,
            validate_parameters=True,
            retries=3,
            retry_delay_seconds=20,
            persist_result=False,
            result_serializer="json",
            result_storage=LocalFileSystem(),
            cache_result_in_memory=False,
            log_prints=False,
        )
        def initial_flow():
            pass

        flow_with_options = initial_flow.with_options()

        assert flow_with_options is not initial_flow
        assert flow_with_options.name == "Initial flow"
        assert flow_with_options.description == "Flow before with options"
        assert isinstance(flow_with_options.task_runner, SequentialTaskRunner)
        assert flow_with_options.timeout_seconds == 10
        assert flow_with_options.should_validate_parameters is True
        assert flow_with_options.retries == 3
        assert flow_with_options.retry_delay_seconds == 20
        assert flow_with_options.persist_result is False
        assert flow_with_options.result_serializer == "json"
        assert flow_with_options.result_storage == LocalFileSystem()
        assert flow_with_options.cache_result_in_memory is False
        assert flow_with_options.log_prints is False

    def test_with_options_can_unset_timeout_seconds_with_zero(self):
        @flow(timeout_seconds=1)
        def initial_flow():
            pass

        flow_with_options = initial_flow.with_options(timeout_seconds=0)
        assert flow_with_options.timeout_seconds is None

    def test_with_options_can_unset_result_options_with_none(self):
        @flow(
            persist_result=True,
            result_serializer="json",
            result_storage=LocalFileSystem(),
        )
        def initial_flow():
            pass

        flow_with_options = initial_flow.with_options(
            persist_result=None,
            result_serializer=None,
            result_storage=None,
        )
        assert flow_with_options.persist_result is None
        assert flow_with_options.result_serializer is None
        assert flow_with_options.result_storage is None

    def test_with_options_signature_aligns_with_flow_signature(self):
        flow_params = set(inspect.signature(flow).parameters.keys())
        with_options_params = set(
            inspect.signature(Flow.with_options).parameters.keys()
        )
        # `with_options` does not accept a new function
        flow_params.remove("__fn")
        # `self` isn't in flow decorator
        with_options_params.remove("self")

        assert flow_params == with_options_params


class TestFlowCall:
    async def test_call_creates_flow_run_and_runs(self):
        @flow(version="test")
        def foo(x, y=3, z=3):
            return x + y + z

        assert foo(1, 2) == 6

        flow_run = await get_most_recent_flow_run()
        assert flow_run.parameters == {"x": 1, "y": 2, "z": 3}
        assert flow_run.flow_version == foo.version

    async def test_async_call_creates_flow_run_and_runs(self):
        @flow(version="test")
        async def foo(x, y=3, z=3):
            return x + y + z

        assert await foo(1, 2) == 6

        flow_run = await get_most_recent_flow_run()
        assert flow_run.parameters == {"x": 1, "y": 2, "z": 3}
        assert flow_run.flow_version == foo.version

    async def test_call_with_return_state_true(self):
        @flow()
        def foo(x, y=3, z=3):
            return x + y + z

        state = foo(1, 2, return_state=True)

        assert isinstance(state, State)
        assert await state.result() == 6

    def test_call_coerces_parameter_types(self):
        class CustomType(pydantic.BaseModel):
            z: int

        @flow(version="test")
        def foo(x: int, y: List[int], zt: CustomType):
            return x + sum(y) + zt.z

        result = foo(x="1", y=["2", "3"], zt=CustomType(z=4).dict())
        assert result == 10

    def test_call_with_variadic_args(self):
        @flow
        def test_flow(*foo, bar):
            return foo, bar

        assert test_flow(1, 2, 3, bar=4) == ((1, 2, 3), 4)

    def test_call_with_variadic_keyword_args(self):
        @flow
        def test_flow(foo, bar, **foobar):
            return foo, bar, foobar

        assert test_flow(1, 2, x=3, y=4, z=5) == (1, 2, dict(x=3, y=4, z=5))

    def test_fails_but_does_not_raise_on_incompatible_parameter_types(self):
        @flow(version="test")
        def foo(x: int):
            pass

        state = foo._run(x="foo")

        with pytest.raises(
            ParameterTypeError,
            match="value is not a valid integer",
        ):
            state.result()

    def test_call_ignores_incompatible_parameter_types_if_asked(self):
        @flow(version="test", validate_parameters=False)
        def foo(x: int):
            return x

        assert foo(x="foo") == "foo"

    @pytest.mark.parametrize("error", [ValueError("Hello"), None])
    def test_final_state_reflects_exceptions_during_run(self, error):
        @flow(version="test")
        def foo():
            if error:
                raise error

        state = foo._run()

        # Assert the final state is correct
        assert state.is_failed() if error else state.is_completed()
        assert exceptions_equal(state.result(raise_on_failure=False), error)

    def test_final_state_respects_returned_state(sel):
        @flow(version="test")
        def foo():
            return State(
                type=StateType.FAILED,
                message="Test returned state",
                data=DataDocument.encode("json", "hello!"),
            )

        state = foo._run()

        # Assert the final state is correct
        assert state.is_failed()
        assert state.result(raise_on_failure=False) == "hello!"
        assert state.message == "Test returned state"

    def test_flow_state_reflects_returned_task_run_state(self):
        @task
        def fail():
            raise ValueError("Test")

        @flow(version="test")
        def foo():
            return fail._run()

        flow_state = foo._run()

        assert flow_state.is_failed()

        # The task run state is returned as the data of the flow state
        task_run_state = flow_state.result(raise_on_failure=False)
        assert isinstance(task_run_state, State)
        assert task_run_state.is_failed()
        with pytest.raises(ValueError, match="Test"):
            task_run_state.result()

    def test_flow_state_defaults_to_task_states_when_no_return_failure(self):
        @task
        def fail():
            raise ValueError("Test")

        @flow(version="test")
        def foo():
            fail._run()
            fail._run()
            return None

        flow_state = foo._run()

        assert flow_state.is_failed()

        # The task run states are returned as the data of the flow state
        task_run_states = flow_state.result(raise_on_failure=False)
        assert len(task_run_states) == 2
        assert all(isinstance(state, State) for state in task_run_states)
        task_run_state = task_run_states[0]
        assert task_run_state.is_failed()
        with pytest.raises(ValueError, match="Test"):
            raise_state_exception(task_run_states[0])

    def test_flow_state_defaults_to_task_states_when_no_return_completed(self):
        @task
        def succeed():
            return "foo"

        @flow(version="test")
        def foo():
            succeed()
            succeed()
            return None

        flow_state = foo._run()

        # The task run states are returned as the data of the flow state
        task_run_states = flow_state.result()
        assert len(task_run_states) == 2
        assert all(isinstance(state, State) for state in task_run_states)
        assert task_run_states[0].result() == "foo"

    def test_flow_state_default_includes_subflow_states(self):
        @task
        def succeed():
            return "foo"

        @flow
        def fail():
            raise ValueError("bar")

        @flow(version="test")
        def foo():
            succeed._run()
            fail._run()
            return None

        states = foo._run().result(raise_on_failure=False)
        assert len(states) == 2
        assert all(isinstance(state, State) for state in states)
        assert states[0].result() == "foo"
        with pytest.raises(ValueError, match="bar"):
            raise_state_exception(states[1])

    def test_flow_state_default_handles_nested_failures(self):
        @task
        def fail_task():
            raise ValueError("foo")

        @flow
        def fail_flow():
            fail_task._run()

        @flow
        def wrapper_flow():
            fail_flow._run()

        @flow(version="test")
        def foo():
            wrapper_flow._run()
            return None

        states = foo._run().result(raise_on_failure=False)
        assert len(states) == 1
        state = states[0]
        assert isinstance(state, State)
        with pytest.raises(ValueError, match="foo"):
            raise_state_exception(state)

    def test_flow_state_reflects_returned_multiple_task_run_states(self):
        @task
        def fail1():
            raise ValueError("Test 1")

        @task
        def fail2():
            raise ValueError("Test 2")

        @task
        def succeed():
            return True

        @flow(version="test")
        def foo():
            return fail1._run(), fail2._run(), succeed._run()

        flow_state = foo._run()
        assert flow_state.is_failed()
        assert flow_state.message == "2/3 states failed."

        # The task run states are attached as a tuple
        first, second, third = flow_state.result(raise_on_failure=False)
        assert first.is_failed()
        assert second.is_failed()
        assert third.is_completed()

        with pytest.raises(ValueError, match="Test 1"):
            first.result()

        with pytest.raises(ValueError, match="Test 2"):
            second.result()

    async def test_call_execution_blocked_does_not_run_flow(self):
        @flow(version="test")
        def foo(x, y=3, z=3):
            return x + y + z

        with PrefectObjectRegistry(block_code_execution=True):
            state = foo(1, 2)
            assert state is None

    def test_flow_can_end_in_cancelled_state(self):
        @flow
        def my_flow():
            return Cancelled()

        flow_state = my_flow(return_state=True)
        assert flow_state.is_cancelled()

    def test_flow_state_with_cancelled_tasks_has_cancelled_state(self):
        @task
        def cancel():
            return Cancelled()

        @task
        def fail():
            raise ValueError("Fail")

        @task
        def succeed():
            return True

        @flow(version="test")
        def my_flow():
            return cancel.submit(), succeed.submit(), fail.submit()

        flow_state = my_flow(return_state=True)
        assert flow_state.is_cancelled()
        assert flow_state.message == "1/3 states cancelled."

        # The task run states are attached as a tuple
        first, second, third = flow_state.result(raise_on_failure=False)
        assert first.is_cancelled()
        assert second.is_completed()
        assert third.is_failed()

        with pytest.raises(CancelledRun):
            first.result()

    def test_flow_with_cancelled_subflow_has_cancelled_state(self):
        @task
        def cancel():
            return Cancelled()

        @flow(version="test")
        def subflow():
            return cancel.submit()

        @flow
        def my_flow():
            return subflow(return_state=True)

        flow_state = my_flow(return_state=True)
        assert flow_state.is_cancelled()
        assert flow_state.message == "1/1 states cancelled."


class TestSubflowCalls:
    async def test_subflow_call_with_no_tasks(self):
        @flow(version="foo")
        def child(x, y, z):
            return x + y + z

        @flow(version="bar")
        def parent(x, y=2, z=3):
            return child(x, y, z)

        assert parent(1, 2) == 6

    def test_subflow_call_with_returned_task(self):
        @task
        def compute(x, y, z):
            return x + y + z

        @flow(version="foo")
        def child(x, y, z):
            return compute(x, y, z)

        @flow(version="bar")
        def parent(x, y=2, z=3):
            return child(x, y, z)

        assert parent(1, 2) == 6

    async def test_async_flow_with_async_subflow_and_async_task(self):
        @task
        async def compute_async(x, y, z):
            return x + y + z

        @flow(version="foo")
        async def child(x, y, z):
            return await compute_async(x, y, z)

        @flow(version="bar")
        async def parent(x, y=2, z=3):
            return await child(x, y, z)

        assert await parent(1, 2) == 6

    async def test_async_flow_with_async_subflow_and_sync_task(self):
        @task
        def compute(x, y, z):
            return x + y + z

        @flow(version="foo")
        async def child(x, y, z):
            return compute(x, y, z)

        @flow(version="bar")
        async def parent(x, y=2, z=3):
            return await child(x, y, z)

        assert await parent(1, 2) == 6

    async def test_async_flow_with_sync_subflow_and_sync_task(self):
        @task
        def compute(x, y, z):
            return x + y + z

        @flow(version="foo")
        def child(x, y, z):
            return compute(x, y, z)

        @flow(version="bar")
        async def parent(x, y=2, z=3):
            return child(x, y, z)

        assert await parent(1, 2) == 6

    def test_sync_flow_with_async_subflow(self):
        result = "a string, not a coroutine"

        @flow
        async def async_child():
            return result

        @flow
        def parent():
            return async_child()

        assert parent() == result

    def test_sync_flow_with_async_subflow_and_async_task(self):
        @task
        async def compute(x, y, z):
            return x + y + z

        @flow(version="foo")
        async def child(x, y, z):
            return await compute(x, y, z)

        @flow(version="bar")
        def parent(x, y=2, z=3):
            return child(x, y, z)

        assert parent(1, 2) == 6

    async def test_subflow_with_invalid_parameters_is_failed(self, orion_client):
        @flow
        def child(x: int):
            return x

        @flow
        def parent(x):
            return child._run(x)

        parent_state = parent._run("foo")

        with pytest.raises(ParameterTypeError, match="not a valid integer"):
            await parent_state.result()

        child_state = await parent_state.result(raise_on_failure=False)
        flow_run = await orion_client.read_flow_run(
            child_state.state_details.flow_run_id
        )
        assert flow_run.state.is_failed()
        assert "invalid parameters" in flow_run.state.message

    async def test_subflow_with_invalid_parameters_is_not_failed_without_validation(
        self,
    ):
        @flow(validate_parameters=False)
        def child(x: int):
            return x

        @flow
        def parent(x):
            return child(x)

        assert parent("foo") == "foo"

    async def test_subflow_relationship_tracking(self, orion_client):
        @flow(version="inner")
        def child(x, y):
            return x + y

        @flow()
        def parent():
            return child._run(1, 2)

        parent_state = parent._run()
        parent_flow_run_id = parent_state.state_details.flow_run_id
        child_state = await parent_state.result()
        child_flow_run_id = child_state.state_details.flow_run_id

        child_flow_run = await orion_client.read_flow_run(child_flow_run_id)

        # This task represents the child flow run in the parent
        parent_flow_run_task = await orion_client.read_task_run(
            child_flow_run.parent_task_run_id
        )

        assert parent_flow_run_task.task_version == "inner"
        assert (
            parent_flow_run_id != child_flow_run_id
        ), "The subflow run and parent flow run are distinct"

        assert (
            child_state.state_details.task_run_id == parent_flow_run_task.id
        ), "The client subflow run state links to the parent task"

        assert all(
            state.state_details.task_run_id == parent_flow_run_task.id
            for state in await orion_client.read_flow_run_states(child_flow_run_id)
        ), "All server subflow run states link to the parent task"

        assert (
            parent_flow_run_task.state.state_details.child_flow_run_id
            == child_flow_run_id
        ), "The parent task links to the subflow run id"

        assert (
            parent_flow_run_task.state.state_details.flow_run_id == parent_flow_run_id
        ), "The parent task belongs to the parent flow"

        assert (
            child_flow_run.parent_task_run_id == parent_flow_run_task.id
        ), "The server subflow run links to the parent task"

        assert (
            child_flow_run.id == child_flow_run_id
        ), "The server subflow run id matches the client"


class TestFlowRunTags:
    async def test_flow_run_tags_added_at_call(self, orion_client):
        @flow
        def my_flow():
            pass

        with tags("a", "b"):
            state = my_flow._run()

        flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)
        assert set(flow_run.tags) == {"a", "b"}

    async def test_flow_run_tags_added_to_subflows(self, orion_client):
        @flow
        def my_flow():
            with tags("c", "d"):
                return my_subflow._run()

        @flow
        def my_subflow():
            pass

        with tags("a", "b"):
            subflow_state = await my_flow._run().result()

        flow_run = await orion_client.read_flow_run(
            subflow_state.state_details.flow_run_id
        )
        assert set(flow_run.tags) == {"a", "b", "c", "d"}


class TestFlowTimeouts:
    def test_flows_fail_with_timeout(self):
        @flow(timeout_seconds=0.1)
        def my_flow():
            time.sleep(1)

        state = my_flow._run()
        assert state.is_failed()
        assert state.name == "TimedOut"
        with pytest.raises(TimeoutError):
            state.result()
        assert "exceeded timeout of 0.1 seconds" in state.message

    async def test_async_flows_fail_with_timeout(self):
        @flow(timeout_seconds=0.1)
        async def my_flow():
            await anyio.sleep(1)

        state = await my_flow._run()
        assert state.is_failed()
        assert state.name == "TimedOut"
        with pytest.raises(TimeoutError):
            await state.result()
        assert "exceeded timeout of 0.1 seconds" in state.message

    def test_timeout_only_applies_if_exceeded(self):
        @flow(timeout_seconds=1)
        def my_flow():
            time.sleep(0.1)

        state = my_flow._run()
        assert state.is_completed()

    def test_user_timeout_is_not_hidden(self):
        @flow(timeout_seconds=30)
        def my_flow():
            raise TimeoutError("Oh no!")

        state = my_flow(return_state=True)
        assert state.is_failed()
        assert state.name == "Failed"
        with pytest.raises(TimeoutError, match="Oh no!"):
            state.result()
        assert "exceeded timeout" not in state.message

    def test_timeout_does_not_wait_for_completion_for_sync_flows(self, tmp_path):
        """
        Sync flows are cancelled when they change instructions. The flow will return
        immediately when the timeout is reached, but the thread it executes in will
        continue until the next instruction is reached. `time.sleep` will return then
        the thread will be interrupted.
        """
        if sys.version_info[1] == 11:
            pytest.xfail("The engine returns _after_ sleep finishes in Python 3.11")

        canary_file = tmp_path / "canary"

        @flow(timeout_seconds=0.1)
        def my_flow():
            time.sleep(3)
            canary_file.touch()

        t0 = time.perf_counter()
        state = my_flow(return_state=True)
        t1 = time.perf_counter()

        assert state.is_failed()
        assert "exceeded timeout of 0.1 seconds" in state.message
        assert t1 - t0 < 3, f"The engine returns without waiting; took {t1-t0}s"

        time.sleep(3)
        assert not canary_file.exists()

    def test_timeout_stops_execution_at_next_task_for_sync_flows(self, tmp_path):
        """
        Sync flow runs tasks will fail after a timeout which will cause the flow to exit
        """
        canary_file = tmp_path / "canary"
        task_canary_file = tmp_path / "task_canary"

        @task
        def my_task():
            task_canary_file.touch()

        @flow(timeout_seconds=0.1)
        def my_flow():
            time.sleep(0.25)
            my_task()
            canary_file.touch()  # Should not run

        state = my_flow._run()

        assert state.is_failed()
        assert "exceeded timeout of 0.1 seconds" in state.message

        # Wait in case the flow is just sleeping
        time.sleep(0.5)

        assert not canary_file.exists()
        assert not task_canary_file.exists()

    @flaky_on_windows
    async def test_timeout_stops_execution_after_await_for_async_flows(self, tmp_path):
        """
        Async flow runs can be cancelled after a timeout
        """
        canary_file = tmp_path / "canary"
        sleep_time = 5

        @flow(timeout_seconds=0.1)
        async def my_flow():
            # Sleep in intervals to give more chances for interrupt
            for _ in range(sleep_time * 10):
                await anyio.sleep(0.1)
            canary_file.touch()  # Should not run

        t0 = anyio.current_time()
        state = await my_flow._run()
        t1 = anyio.current_time()

        assert state.is_failed()
        assert "exceeded timeout of 0.1 seconds" in state.message

        # Wait in case the flow is just sleeping
        await anyio.sleep(sleep_time)

        assert not canary_file.exists()
        assert (
            t1 - t0 < sleep_time
        ), f"The engine returns without waiting; took {t1-t0}s"

    async def test_timeout_stops_execution_in_async_subflows(self, tmp_path):
        """
        Async flow runs can be cancelled after a timeout
        """
        canary_file = tmp_path / "canary"
        sleep_time = 5

        @flow(timeout_seconds=0.1)
        async def my_subflow():
            # Sleep in intervals to give more chances for interrupt
            for _ in range(sleep_time * 10):
                await anyio.sleep(0.1)
            canary_file.touch()  # Should not run

        @flow
        async def my_flow():
            t0 = anyio.current_time()
            subflow_state = await my_subflow._run()
            t1 = anyio.current_time()
            return t1 - t0, subflow_state

        state = await my_flow._run()

        runtime, subflow_state = await state.result()
        assert "exceeded timeout of 0.1 seconds" in subflow_state.message

        assert not canary_file.exists()
        assert (
            runtime < sleep_time
        ), f"The engine returns without waiting; took {runtime}s"

    async def test_timeout_stops_execution_in_sync_subflows(self, tmp_path):
        """
        Sync flow runs can be cancelled after a timeout once a task is called
        """
        canary_file = tmp_path / "canary"

        @task
        def timeout_noticing_task():
            pass

        @flow(timeout_seconds=0.1)
        def my_subflow():
            time.sleep(0.5)
            timeout_noticing_task()
            time.sleep(10)
            canary_file.touch()  # Should not run

        @flow
        def my_flow():
            t0 = time.perf_counter()
            subflow_state = my_subflow._run()
            t1 = time.perf_counter()
            return t1 - t0, subflow_state

        state = my_flow._run()

        runtime, subflow_state = await state.result()
        assert "exceeded timeout of 0.1 seconds" in subflow_state.message

        # Wait in case the flow is just sleeping and will still create the canary
        time.sleep(1)

        assert not canary_file.exists()
        assert runtime < 5, f"The engine returns without waiting; took {runtime}s"

    async def test_subflow_timeout_waits_until_execution_starts(self, tmp_path):
        """
        Subflow with a timeout shouldn't start their timeout before the subflow is started.
        Fixes: https://github.com/PrefectHQ/prefect/issues/7903.
        """

        canary_file = tmp_path / "canary"

        @flow(timeout_seconds=1)
        def downstream_flow():
            canary_file.touch()

        @task
        def sleep_task(n):
            time.sleep(n)

        @flow
        async def my_flow():
            upstream_sleepers = sleep_task.map(list(range(3)))
            downstream_flow(wait_for=upstream_sleepers)

        t0 = anyio.current_time()
        state = await my_flow._run()
        t1 = anyio.current_time()

        assert state.is_completed()

        # Validate the sleep tasks have ran.
        # Note: t1 - t0 can be less than exactly 3 (i.e., around 2.9). By comparing with 2.7 we have some leeway.
        assert t1 - t0 >= 2.7
        assert canary_file.exists()  # Validate subflow has ran


class ParameterTestModel(pydantic.BaseModel):
    data: int


class ParameterTestClass:
    pass


class ParameterTestEnum(enum.Enum):
    X = 1
    Y = 2


class TestFlowParameterTypes:
    def test_flow_parameters_can_be_unserializable_types(self):
        @flow
        def my_flow(x):
            return x

        data = ParameterTestClass()
        assert my_flow(data) == data

    def test_flow_parameters_can_be_pydantic_types(self):
        @flow
        def my_flow(x):
            return x

        assert my_flow(ParameterTestModel(data=1)) == ParameterTestModel(data=1)

    @pytest.mark.parametrize(
        "data", ([1, 2, 3], {"foo": "bar"}, {"x", "y"}, 1, "foo", ParameterTestEnum.X)
    )
    def test_flow_parameters_can_be_jsonable_python_types(self, data):
        @flow
        def my_flow(x):
            return x

        assert my_flow(data) == data

    def test_subflow_parameters_can_be_unserializable_types(self):
        data = ParameterTestClass()

        @flow
        def my_flow():
            return my_subflow(data)

        @flow
        def my_subflow(x):
            return x

        assert my_flow() == data

    def test_flow_parameters_can_be_unserializable_types_that_raise_value_error(self):
        @flow
        def my_flow(x):
            return x

        data = Exception
        # When passing some parameter types, jsonable_encoder will raise a ValueError
        # for a missing a __dict__ attribute instead of a TypeError.
        # This was notably encountered when using numpy arrays as an
        # input type but applies to exception classes as well.
        # See #1638.
        assert my_flow(data) == data

    def test_subflow_parameters_can_be_pydantic_types(self):
        @flow
        def my_flow():
            return my_subflow(ParameterTestModel(data=1))

        @flow
        def my_subflow(x):
            return x

        assert my_flow() == ParameterTestModel(data=1)

    def test_subflow_parameters_from_future_can_be_unserializable_types(self):
        data = ParameterTestClass()

        @flow
        def my_flow():
            return my_subflow(identity(data))

        @task
        def identity(x):
            return x

        @flow
        def my_subflow(x):
            return x

        assert my_flow() == data

    def test_subflow_parameters_can_be_pydantic_types_from_task_future(self):
        @flow
        def my_flow():
            return my_subflow(identity.submit(ParameterTestModel(data=1)))

        @task
        def identity(x):
            return x

        @flow
        def my_subflow(x):
            return x

        assert my_flow() == ParameterTestModel(data=1)


class TestSubflowTaskInputs:
    async def test_subflow_with_one_upstream_task_future(self, orion_client):
        @task
        def child_task(x):
            return x

        @flow
        def child_flow(x):
            return x

        @flow
        def parent_flow():
            task_future = child_task.submit(1)
            flow_state = child_flow._run(x=task_future)
            task_state = task_future.wait()
            return task_state, flow_state

        task_state, flow_state = parent_flow()
        flow_tracking_task_run = await orion_client.read_task_run(
            flow_state.state_details.task_run_id
        )

        assert flow_tracking_task_run.task_inputs == dict(
            x=[TaskRunResult(id=task_state.state_details.task_run_id)],
        )

    async def test_subflow_with_one_upstream_task_state(self, orion_client):
        @task
        def child_task(x):
            return x

        @flow
        def child_flow(x):
            return x

        @flow
        def parent_flow():
            task_state = child_task._run(257)
            flow_state = child_flow._run(x=task_state)
            return task_state, flow_state

        task_state, flow_state = parent_flow()
        flow_tracking_task_run = await orion_client.read_task_run(
            flow_state.state_details.task_run_id
        )

        assert flow_tracking_task_run.task_inputs == dict(
            x=[TaskRunResult(id=task_state.state_details.task_run_id)],
        )

    async def test_subflow_with_one_upstream_task_result(self, orion_client):
        @task
        def child_task(x):
            return x

        @flow
        def child_flow(x):
            return x

        @flow
        def parent_flow():
            task_state = child_task._run(257)
            task_result = task_state.result()
            flow_state = child_flow._run(x=task_result)
            return task_state, flow_state

        task_state, flow_state = parent_flow()
        flow_tracking_task_run = await orion_client.read_task_run(
            flow_state.state_details.task_run_id
        )

        assert flow_tracking_task_run.task_inputs == dict(
            x=[TaskRunResult(id=task_state.state_details.task_run_id)],
        )

    async def test_subflow_with_one_upstream_task_future_and_allow_failure(
        self, orion_client
    ):
        @task
        def child_task():
            raise ValueError()

        @flow
        def child_flow(x):
            return x

        @flow
        def parent_flow():
            future = child_task.submit()
            flow_state = child_flow(x=allow_failure(future), return_state=True)
            return quote((future.wait(), flow_state))

        task_state, flow_state = parent_flow().unquote()
        assert isinstance(await flow_state.result(), ValueError)
        flow_tracking_task_run = await orion_client.read_task_run(
            flow_state.state_details.task_run_id
        )

        assert task_state.is_failed()
        assert flow_tracking_task_run.task_inputs == dict(
            x=[TaskRunResult(id=task_state.state_details.task_run_id)],
        )

    async def test_subflow_with_one_upstream_task_state_and_allow_failure(
        self, orion_client
    ):
        @task
        def child_task():
            raise ValueError()

        @flow
        def child_flow(x):
            return x

        @flow
        def parent_flow():
            task_state = child_task(return_state=True)
            flow_state = child_flow(x=allow_failure(task_state), return_state=True)
            return quote((task_state, flow_state))

        task_state, flow_state = parent_flow().unquote()
        assert isinstance(await flow_state.result(), ValueError)
        flow_tracking_task_run = await orion_client.read_task_run(
            flow_state.state_details.task_run_id
        )

        assert task_state.is_failed()
        assert flow_tracking_task_run.task_inputs == dict(
            x=[TaskRunResult(id=task_state.state_details.task_run_id)],
        )

    async def test_subflow_with_no_upstream_tasks(self, orion_client):
        @flow
        def bar(x, y):
            return x + y

        @flow
        def foo():
            return bar._run(x=2, y=1)

        child_flow_state = foo()
        flow_tracking_task_run = await orion_client.read_task_run(
            child_flow_state.state_details.task_run_id
        )

        assert flow_tracking_task_run.task_inputs == dict(
            x=[],
            y=[],
        )


@pytest.mark.enable_api_log_handler
class TestFlowRunLogs:
    async def test_user_logs_are_sent_to_orion(self, orion_client):
        @flow
        def my_flow():
            logger = get_run_logger()
            logger.info("Hello world!")

        my_flow()

        logs = await orion_client.read_logs()
        assert "Hello world!" in {log.message for log in logs}

    async def test_repeated_flow_calls_send_logs_to_orion(self, orion_client):
        @flow
        async def my_flow(i):
            logger = get_run_logger()
            logger.info(f"Hello {i}")

        await my_flow(1)
        await my_flow(2)

        logs = await orion_client.read_logs()
        assert {"Hello 1", "Hello 2"}.issubset({log.message for log in logs})

    async def test_exception_info_is_included_in_log(self, orion_client):
        @flow
        def my_flow():
            logger = get_run_logger()
            try:
                x + y
            except:
                logger.error("There was an issue", exc_info=True)

        my_flow()

        logs = await orion_client.read_logs()
        error_log = [log.message for log in logs if log.level == 40].pop()
        assert "Traceback" in error_log
        assert "NameError" in error_log, "Should reference the exception type"
        assert "x + y" in error_log, "Should reference the line of code"

    async def test_raised_exceptions_include_tracebacks(self, orion_client):
        @flow
        def my_flow():
            raise ValueError("Hello!")

        with pytest.raises(ValueError):
            my_flow()

        logs = await orion_client.read_logs()
        error_log = [
            log.message
            for log in logs
            if log.level == 40 and "Encountered exception" in log.message
        ].pop()
        assert "Traceback" in error_log
        assert "ValueError: Hello!" in error_log, "References the exception"

    async def test_opt_out_logs_are_not_sent_to_orion(self, orion_client):
        @flow
        def my_flow():
            logger = get_run_logger()
            logger.info(
                "Hello world!",
                extra={"send_to_orion": False},
            )

        my_flow()

        logs = await orion_client.read_logs()
        assert "Hello world!" not in {log.message for log in logs}

    async def test_logs_are_given_correct_id(self, orion_client):
        @flow
        def my_flow():
            logger = get_run_logger()
            logger.info("Hello world!")

        state = my_flow._run()
        flow_run_id = state.state_details.flow_run_id

        logs = await orion_client.read_logs()
        assert all([log.flow_run_id == flow_run_id for log in logs])
        assert all([log.task_run_id is None for log in logs])


@pytest.mark.enable_api_log_handler
class TestSubflowRunLogs:
    async def test_subflow_logs_are_written_correctly(self, orion_client):
        @flow
        def my_subflow():
            logger = get_run_logger()
            logger.info("Hello smaller world!")

        @flow
        def my_flow():
            logger = get_run_logger()
            logger.info("Hello world!")
            return my_subflow._run()

        state = my_flow._run()
        flow_run_id = state.state_details.flow_run_id
        subflow_run_id = (await state.result()).state_details.flow_run_id

        logs = await orion_client.read_logs()
        log_messages = [log.message for log in logs]
        assert all([log.task_run_id is None for log in logs])
        assert "Hello world!" in log_messages, "Parent log message is present"
        assert (
            logs[log_messages.index("Hello world!")].flow_run_id == flow_run_id
        ), "Parent log message has correct id"
        assert "Hello smaller world!" in log_messages, "Child log message is present"
        assert (
            logs[log_messages.index("Hello smaller world!")].flow_run_id
            == subflow_run_id
        ), "Child log message has correct id"

    async def test_subflow_logs_are_written_correctly_with_tasks(self, orion_client):
        @task
        def a_log_task():
            logger = get_run_logger()
            logger.info("Task log")

        @flow
        def my_subflow():
            a_log_task()
            logger = get_run_logger()
            logger.info("Hello smaller world!")

        @flow
        def my_flow():
            logger = get_run_logger()
            logger.info("Hello world!")
            return my_subflow(return_state=True)

        subflow_state = my_flow()
        subflow_run_id = subflow_state.state_details.flow_run_id

        logs = await orion_client.read_logs()
        log_messages = [log.message for log in logs]
        task_run_logs = [log for log in logs if log.task_run_id is not None]
        assert all([log.flow_run_id == subflow_run_id for log in task_run_logs])
        assert "Hello smaller world!" in log_messages
        assert (
            logs[log_messages.index("Hello smaller world!")].flow_run_id
            == subflow_run_id
        )


class TestFlowResults:
    """
    See `tests/results/test_flow_results.py` instead please.

    These tests were retained during the results rewrite but new tests should be added
    in the dedicated file.
    """

    async def test_flow_results_are_not_stored_by_default(self, orion_client):
        @flow
        def foo():
            return 6

        state = foo(return_state=True)

        # Available in local cache
        assert await state.result() == 6

        # Data is not a reference
        assert state.data == 6

        flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)
        assert flow_run.state.data is None

        with pytest.raises(MissingResult, match="State data is missing"):
            await flow_run.state.result()

    async def test_flow_results_are_stored_locally_if_enabled(self, orion_client):
        @flow(persist_result=True)
        def foo():
            return 6

        state = foo(return_state=True)

        # Available from memory cache
        assert await state.result() == 6

        # Check that the storage block uses local path
        reference = state.result(fetch=False)
        assert isinstance(reference, PersistedResult)
        storage_block = Block._from_block_document(
            await orion_client.read_block_document(reference.storage_block_id)
        )
        assert storage_block.basepath == str(PREFECT_LOCAL_STORAGE_PATH.value())

        flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)
        # The result can be fetched using the API state
        assert await flow_run.state.result() == 6

    async def test_subflow_results_use_parent_flow_run_storage_block_by_default(
        self, orion_client, tmp_path
    ):
        @flow(persist_result=True)
        async def foo():
            with temporary_settings({PREFECT_LOCAL_STORAGE_PATH: tmp_path / "foo"}):
                return bar(return_state=True)

        @flow(persist_result=True)
        def bar():
            return 6

        parent_state = await foo(return_state=True)
        child_state = await parent_state.result()

        parent_flow_run = await orion_client.read_flow_run(
            parent_state.state_details.flow_run_id
        )
        child_flow_run = await orion_client.read_flow_run(
            child_state.state_details.flow_run_id
        )

        parent_result_ref = parent_flow_run.state.result(fetch=False)
        child_result_ref = child_flow_run.state.result(fetch=False)
        assert parent_result_ref.storage_block_id == child_result_ref.storage_block_id

        # The result can be fetched using the API state
        assert await child_flow_run.state.result() == 6


class TestFlowRetries:
    def test_flow_retry_with_error_in_flow(self):
        run_count = 0

        @flow(retries=1)
        def foo():
            nonlocal run_count
            run_count += 1
            if run_count == 1:
                raise ValueError()
            return "hello"

        assert foo() == "hello"
        assert run_count == 2

    async def test_flow_retry_with_error_in_flow_and_successful_task(self):
        task_run_count = 0
        flow_run_count = 0

        @task
        def my_task():
            nonlocal task_run_count
            task_run_count += 1
            return "hello"

        @flow(retries=1)
        def foo():
            nonlocal flow_run_count
            flow_run_count += 1

            fut = my_task()

            if flow_run_count == 1:
                raise ValueError()

            return fut

        assert foo() == "hello"
        assert flow_run_count == 2
        assert task_run_count == 1

    def test_flow_retry_with_no_error_in_flow_and_one_failed_task(self):
        task_run_count = 0
        flow_run_count = 0

        @task
        def my_task():
            nonlocal task_run_count
            task_run_count += 1

            # Fail on the first flow run but not the retry
            if flow_run_count == 1:
                raise ValueError()

            return "hello"

        @flow(retries=1)
        def foo():
            nonlocal flow_run_count
            flow_run_count += 1
            return my_task()

        assert foo() == "hello"
        assert flow_run_count == 2
        assert task_run_count == 2, "Task should be reset and run again"

    def test_flow_retry_with_error_in_flow_and_one_failed_task(self):
        task_run_count = 0
        flow_run_count = 0

        @task
        def my_task():
            nonlocal task_run_count
            task_run_count += 1

            # Fail on the first flow run but not the retry
            if flow_run_count == 1:
                raise ValueError()

            return "hello"

        @flow(retries=1)
        def my_flow():
            nonlocal flow_run_count
            flow_run_count += 1

            fut = my_task()

            # It is important that the flow run fails after the task run is created
            if flow_run_count == 1:
                raise ValueError()

            return fut

        assert my_flow() == "hello"
        assert flow_run_count == 2
        assert task_run_count == 2, "Task should be reset and run again"

    @pytest.mark.xfail
    async def test_flow_retry_with_branched_tasks(self, orion_client):
        flow_run_count = 0

        @task
        def identity(value):
            return value

        @flow(retries=1)
        def my_flow():
            nonlocal flow_run_count
            flow_run_count += 1

            # Raise on the first run but use 'foo'
            if flow_run_count == 1:
                identity("foo")
                raise ValueError()
            else:
                # On the second run, switch to 'bar'
                result = identity("bar")

            return result

        my_flow()

        assert flow_run_count == 2

        # The state is pulled from the API and needs to be decoded
        document = await (await my_flow().result()).result()
        result = await orion_client.retrieve_data(document)

        assert result == "bar"
        # AssertionError: assert 'foo' == 'bar'
        # Wait, what? Because tasks are identified by dynamic key which is a simple
        # increment each time the task is called, if there branching is different
        # after a flow run retry, the stale value will be pulled from the cache.

    async def test_flow_retry_with_no_error_in_flow_and_one_failed_child_flow(
        self, orion_client: PrefectClient
    ):
        child_run_count = 0
        flow_run_count = 0

        @flow
        def child_flow():
            nonlocal child_run_count
            child_run_count += 1

            # Fail on the first flow run but not the retry
            if flow_run_count == 1:
                raise ValueError()

            return "hello"

        @flow(retries=1)
        def parent_flow():
            nonlocal flow_run_count
            flow_run_count += 1
            return child_flow()

        state = parent_flow._run()
        assert await state.result() == "hello"
        assert flow_run_count == 2
        assert child_run_count == 2, "Child flow should be reset and run again"

        # Ensure that the tracking task run for the subflow is reset and tracked
        task_runs = await orion_client.read_task_runs(
            flow_run_filter=FlowRunFilter(
                id={"any_": [state.state_details.flow_run_id]}
            )
        )
        state_types = {task_run.state_type for task_run in task_runs}
        assert state_types == {StateType.COMPLETED}

        # There should only be the child flow run's task
        assert len(task_runs) == 1

    async def test_flow_retry_with_error_in_flow_and_one_successful_child_flow(self):
        child_run_count = 0
        flow_run_count = 0

        @flow
        def child_flow():
            nonlocal child_run_count
            child_run_count += 1
            return "hello"

        @flow(retries=1)
        def parent_flow():
            nonlocal flow_run_count
            flow_run_count += 1
            child_result = child_flow()

            # Fail on the first flow run but not the retry
            if flow_run_count == 1:
                raise ValueError()

            return child_result

        assert parent_flow() == "hello"
        assert flow_run_count == 2
        assert child_run_count == 1, "Child flow should not run again"

    async def test_flow_retry_with_error_in_flow_and_one_failed_child_flow(
        self, orion_client: PrefectClient
    ):
        child_flow_run_count = 0
        flow_run_count = 0

        @flow
        def child_flow():
            nonlocal child_flow_run_count
            child_flow_run_count += 1

            # Fail on the first flow run but not the retry
            if flow_run_count == 1:
                raise ValueError()

            return "hello"

        @flow(retries=1)
        def parent_flow():
            nonlocal flow_run_count
            flow_run_count += 1

            state = child_flow._run()

            # It is important that the flow run fails after the child flow run is created
            if flow_run_count == 1:
                raise ValueError()

            return state

        parent_state = parent_flow._run()
        child_state = await parent_state.result()
        assert await child_state.result() == "hello"
        assert flow_run_count == 2
        assert child_flow_run_count == 2, "Child flow should run again"

        child_flow_run = await orion_client.read_flow_run(
            child_state.state_details.flow_run_id
        )
        child_flow_runs = await orion_client.read_flow_runs(
            flow_filter=FlowFilter(id={"any_": [child_flow_run.flow_id]}),
            sort=FlowRunSort.EXPECTED_START_TIME_ASC,
        )

        assert len(child_flow_runs) == 2

        # The original flow run has its failed state preserved
        assert child_flow_runs[0].state.is_failed()

        # The final flow run is the one returned by the parent flow
        assert child_flow_runs[-1] == child_flow_run

    async def test_flow_retry_with_failed_child_flow_with_failed_task(self):
        child_task_run_count = 0
        child_flow_run_count = 0
        flow_run_count = 0

        @task
        def child_task():
            nonlocal child_task_run_count
            child_task_run_count += 1

            # Fail on the first task run but not the retry
            if child_task_run_count == 1:
                raise ValueError()

            return "hello"

        @flow
        def child_flow():
            nonlocal child_flow_run_count
            child_flow_run_count += 1
            return child_task()

        @flow(retries=1)
        def parent_flow():
            nonlocal flow_run_count
            flow_run_count += 1

            state = child_flow()

            return state

        assert parent_flow() == "hello"
        assert flow_run_count == 2
        assert child_flow_run_count == 2, "Child flow should run again"
        assert child_task_run_count == 2, "Child taks should run again with child flow"

    def test_flow_retry_with_error_in_flow_and_one_failed_task_with_retries(self):
        task_run_retry_count = 0
        task_run_count = 0
        flow_run_count = 0

        @task(retries=1)
        def my_task():
            nonlocal task_run_count, task_run_retry_count
            task_run_count += 1
            task_run_retry_count += 1

            # Always fail on the first flow run
            if flow_run_count == 1:
                raise ValueError("Fail on first flow run")

            # Only fail the first time this task is called within a given flow run
            # This ensures that we will always retry this task so we can ensure
            # retry logic is preserved
            if task_run_retry_count == 1:
                raise ValueError("Fail on first task run")

            return "hello"

        @flow(retries=1)
        def foo():
            nonlocal flow_run_count, task_run_retry_count
            task_run_retry_count = 0
            flow_run_count += 1

            fut = my_task()

            # It is important that the flow run fails after the task run is created
            if flow_run_count == 1:
                raise ValueError()

            return fut

        assert foo() == "hello"
        assert flow_run_count == 2
        assert task_run_count == 4, "Task should use all of its retries every time"

    def test_flow_retry_with_error_in_flow_and_one_failed_task_with_retries_cannot_exceed_retries(
        self,
    ):
        task_run_count = 0
        flow_run_count = 0

        @task(retries=2)
        def my_task():
            nonlocal task_run_count
            task_run_count += 1
            raise ValueError("This task always fails")

        @flow(retries=1)
        def my_flow():
            nonlocal flow_run_count
            flow_run_count += 1

            fut = my_task()

            # It is important that the flow run fails after the task run is created
            if flow_run_count == 1:
                raise ValueError()

            return fut

        with pytest.raises(ValueError, match="This task always fails"):
            my_flow().result().result()

        assert flow_run_count == 2
        assert task_run_count == 6, "Task should use all of its retries every time"

    async def test_flow_with_failed_child_flow_with_retries(self):
        child_flow_run_count = 0
        flow_run_count = 0

        @flow(retries=1)
        def child_flow():
            nonlocal child_flow_run_count
            child_flow_run_count += 1

            # Fail on first try.
            if child_flow_run_count == 1:
                raise ValueError()

            return "hello"

        @flow
        def parent_flow():
            nonlocal flow_run_count
            flow_run_count += 1

            state = child_flow()

            return state

        assert parent_flow() == "hello"
        assert flow_run_count == 1, "Parent flow should only run once"
        assert child_flow_run_count == 2, "Child flow should run again"

    async def test_parent_flow_retries_failed_child_flow_with_retries(self):
        child_flow_retry_count = 0
        child_flow_run_count = 0
        flow_run_count = 0

        @flow(retries=1)
        def child_flow():
            nonlocal child_flow_run_count, child_flow_retry_count
            child_flow_run_count += 1
            child_flow_retry_count += 1

            # Fail during first parent flow run, but not on parent retry.
            if flow_run_count == 1:
                raise ValueError()

            # Fail on first try after parent retry.
            if child_flow_retry_count == 1:
                raise ValueError()

            return "hello"

        @flow(retries=1)
        def parent_flow():
            nonlocal flow_run_count, child_flow_retry_count
            child_flow_retry_count = 0
            flow_run_count += 1

            state = child_flow()

            return state

        assert parent_flow() == "hello"
        assert flow_run_count == 2, "Parent flow should exhaust retries"
        assert (
            child_flow_run_count == 4
        ), "Child flow should run 2 times for each parent run"


def test_load_flow_from_entrypoint(tmp_path):
    flow_code = """
    from prefect import flow

    @flow
    def dog():
        return "woof!"
    """
    fpath = tmp_path / "f.py"
    fpath.write_text(dedent(flow_code))

    flow = load_flow_from_entrypoint(f"{fpath}:dog")
    assert flow.fn() == "woof!"


async def test_handling_script_with_unprotected_call_in_flow_script(
    tmp_path,
    caplog,
    orion_client,
):
    flow_code_with_call = """
    from prefect import flow, get_run_logger

    @flow
    def dog():
        get_run_logger().warning("meow!")
        return "woof!"

    dog()
    """
    fpath = tmp_path / "f.py"
    fpath.write_text(dedent(flow_code_with_call))
    with caplog.at_level("WARNING"):
        flow = load_flow_from_entrypoint(f"{fpath}:dog")

        # Make sure that warning is raised
        assert (
            "Script loading is in progress, flow 'dog' will not be executed. "
            "Consider updating the script to only call the flow"
            in caplog.text
        )

    flow_runs = await orion_client.read_flows()
    assert len(flow_runs) == 0

    # Make sure that flow runs when called
    res = flow()
    assert res == "woof!"
    flow_runs = await orion_client.read_flows()
    assert len(flow_runs) == 1


async def test_sets_run_name_when_provided(orion_client):
    @flow(flow_run_name="hi")
    def flow_with_name(foo: str = "bar", bar: int = 1):
        pass

    state = flow_with_name(return_state=True)

    assert state.type == StateType.COMPLETED
    flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)
    assert flow_run.name == "hi"


async def test_sets_run_name_with_params_including_defaults(orion_client):
    @flow(flow_run_name="hi-{foo}-{bar}")
    def flow_with_name(foo: str = "one", bar: str = "1"):
        pass

    state = flow_with_name(bar="two", return_state=True)

    assert state.type == StateType.COMPLETED
    flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)
    assert flow_run.name == "hi-one-two"


def create_hook(mock_obj):
    def my_hook(flow, flow_run, state):
        mock_obj()

    return my_hook


def create_async_hook(mock_obj):
    async def my_hook(flow, flow_run, state):
        mock_obj()

    return my_hook


class TestFlowHooksOnCompletion:
    def test_on_completion_hooks_run_on_completed(self):
        my_mock = MagicMock()

        def completed1(flow, flow_run, state):
            my_mock("completed1")

        def completed2(flow, flow_run, state):
            my_mock("completed2")

        @flow(on_completion=[completed1, completed2])
        def my_flow():
            pass

        state = my_flow._run()
        assert state.type == StateType.COMPLETED
        assert my_mock.call_args_list == [call("completed1"), call("completed2")]

    def test_on_completion_hooks_dont_run_on_failure(self):
        my_mock = MagicMock()

        def completed1(flow, flow_run, state):
            my_mock("completed1")

        def completed2(flow, flow_run, state):
            my_mock("completed2")

        @flow(on_completion=[completed1, completed2])
        def my_flow():
            raise Exception("oops")

        state = my_flow._run()
        assert state.type == StateType.FAILED
        assert my_mock.call_args_list == []

    def test_other_completion_hooks_run_if_a_hook_fails(self):
        my_mock = MagicMock()

        def completed1(flow, flow_run, state):
            my_mock("completed1")

        def exception_hook(flow, flow_run, state):
            raise Exception("oops")

        def completed2(flow, flow_run, state):
            my_mock("completed2")

        @flow(on_completion=[completed1, exception_hook, completed2])
        def my_flow():
            pass

        state = my_flow._run()
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

        @flow(on_completion=[hook1_with_mock, hook2_with_mock])
        def my_flow():
            pass

        state = my_flow._run()
        assert state.type == StateType.COMPLETED
        assert my_mock.call_args_list == [call(), call()]


class TestFlowHooksOnFailure:
    def test_on_failure_hooks_run_on_failure(self):
        my_mock = MagicMock()

        def failed1(flow, flow_run, state):
            my_mock("failed1")

        def failed2(flow, flow_run, state):
            my_mock("failed2")

        @flow(on_failure=[failed1, failed2])
        def my_flow():
            raise Exception("oops")

        state = my_flow._run()
        assert state.type == StateType.FAILED
        assert my_mock.call_args_list == [call("failed1"), call("failed2")]

    def test_on_failure_hooks_dont_run_on_completed(self):
        my_mock = MagicMock()

        def failed1(flow, flow_run, state):
            my_mock("failed1")

        def failed2(flow, flow_run, state):
            my_mock("failed2")

        @flow(on_failure=[failed1, failed2])
        def my_flow():
            pass

        state = my_flow._run()
        assert state.type == StateType.COMPLETED
        assert my_mock.call_args_list == []

    def test_other_failure_hooks_run_if_a_hook_fails(self):
        my_mock = MagicMock()

        def failed1(flow, flow_run, state):
            my_mock("failed1")

        def exception_hook(flow, flow_run, state):
            raise Exception("oops")

        def failed2(flow, flow_run, state):
            my_mock("failed2")

        @flow(on_failure=[failed1, exception_hook, failed2])
        def my_flow():
            raise Exception("oops")

        state = my_flow._run()
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
    def test_on_failure_hooks_work_with_sync_and_async(self, hook1, hook2):
        my_mock = MagicMock()
        hook1_with_mock = hook1(my_mock)
        hook2_with_mock = hook2(my_mock)

        @flow(on_failure=[hook1_with_mock, hook2_with_mock])
        def my_flow():
            raise Exception("oops")

        state = my_flow._run()
        assert state.type == StateType.FAILED
        assert my_mock.call_args_list == [call(), call()]
