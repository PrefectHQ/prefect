import enum
import inspect
import time
from typing import List
from unittest.mock import MagicMock

import anyio
import pydantic
import pytest

from prefect import flow, get_run_logger, tags, task
from prefect.blocks.storage import TempStorageBlock
from prefect.client import get_client
from prefect.exceptions import InvalidNameError, ParameterTypeError
from prefect.flows import Flow
from prefect.orion.schemas.core import TaskRunResult
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import State, StateType
from prefect.states import raise_failed_state
from prefect.task_runners import ConcurrentTaskRunner, SequentialTaskRunner
from prefect.testing.utilities import exceptions_equal, flaky_on_windows
from prefect.utilities.collections import flatdict_to_dict
from prefect.utilities.hashing import file_hash


class TestFlow:
    def test_initializes(self):
        f = Flow(name="test", fn=lambda **kwargs: 42, version="A", description="B")
        assert f.name == "test"
        assert f.fn() == 42
        assert f.version == "A"
        assert f.description == "B"

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


class TestDecorator:
    def test_flow_decorator_initializes(self):
        # TODO: We should cover initialization with a task runner once introduced
        @flow(name="foo", version="B")
        def my_flow():
            return "bar"

        assert isinstance(my_flow, Flow)
        assert my_flow.name == "foo"
        assert my_flow.version == "B"
        assert my_flow.fn() == "bar"

    def test_flow_decorator_sets_default_version(self):
        my_flow = flow(flatdict_to_dict)

        assert my_flow.version == file_hash(flatdict_to_dict.__globals__["__file__"])


class TestFlowWithOptions:
    def test_with_options_allows_override_of_flow_settings(self):
        @flow(
            name="Initial flow",
            description="Flow before with options",
            task_runner=ConcurrentTaskRunner,
            timeout_seconds=10,
            validate_parameters=True,
        )
        def initial_flow():
            pass

        flow_with_options = initial_flow.with_options(
            name="Copied flow",
            description="A copied flow",
            task_runner=SequentialTaskRunner,
            timeout_seconds=5,
            validate_parameters=False,
        )

        assert flow_with_options.name == "Copied flow"
        assert flow_with_options.description == "A copied flow"
        assert isinstance(flow_with_options.task_runner, SequentialTaskRunner)
        assert flow_with_options.timeout_seconds == 5
        assert flow_with_options.should_validate_parameters is False

    def test_with_options_uses_existing_settings_when_no_override(self):
        @flow(
            name="Initial flow",
            description="Flow before with options",
            task_runner=SequentialTaskRunner,
            timeout_seconds=10,
            validate_parameters=True,
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

    def test_with_options_can_unset_timeout_seconds_with_zero(self):
        @flow(timeout_seconds=1)
        def initial_flow():
            pass

        flow_with_options = initial_flow.with_options(timeout_seconds=0)
        assert flow_with_options.timeout_seconds is None

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

        state = foo(1, 2)
        assert isinstance(state, State)
        assert state.result() == 6
        assert state.state_details.flow_run_id is not None

        async with get_client() as client:
            flow_run = await client.read_flow_run(state.state_details.flow_run_id)
        assert flow_run.id == state.state_details.flow_run_id
        assert flow_run.parameters == {"x": 1, "y": 2, "z": 3}
        assert flow_run.flow_version == foo.version

    async def test_async_call_creates_flow_run_and_runs(self):
        @flow(version="test")
        async def foo(x, y=3, z=3):
            return x + y + z

        state = await foo(1, 2)
        assert isinstance(state, State)
        assert state.result() == 6
        assert state.state_details.flow_run_id is not None

        async with get_client() as client:
            flow_run = await client.read_flow_run(state.state_details.flow_run_id)
        assert flow_run.id == state.state_details.flow_run_id
        assert flow_run.parameters == {"x": 1, "y": 2, "z": 3}
        assert flow_run.flow_version == foo.version

    def test_call_coerces_parameter_types(self):
        class CustomType(pydantic.BaseModel):
            z: int

        @flow(version="test")
        def foo(x: int, y: List[int], zt: CustomType):
            return x + sum(y) + zt.z

        state = foo(x="1", y=["2", "3"], zt=CustomType(z=4).dict())
        assert state.result() == 10

    def test_call_with_variadic_args(self):
        @flow
        def test_flow(*foo, bar):
            return foo, bar

        assert test_flow(1, 2, 3, bar=4).result() == ((1, 2, 3), 4)

    def test_call_with_variadic_keyword_args(self):
        @flow
        def test_flow(foo, bar, **foobar):
            return foo, bar, foobar

        assert test_flow(1, 2, x=3, y=4, z=5).result() == (1, 2, dict(x=3, y=4, z=5))

    def test_fails_but_does_not_raise_on_incompatible_parameter_types(self):
        @flow(version="test")
        def foo(x: int):
            pass

        state = foo(x="foo")

        with pytest.raises(
            ParameterTypeError,
            match="value is not a valid integer",
        ):
            state.result()

    def test_call_ignores_incompatible_parameter_types_if_asked(self):
        @flow(version="test", validate_parameters=False)
        def foo(x: int):
            return x

        assert foo(x="foo").result() == "foo"

    @pytest.mark.parametrize("error", [ValueError("Hello"), None])
    def test_final_state_reflects_exceptions_during_run(self, error):
        @flow(version="test")
        def foo():
            if error:
                raise error

        state = foo()

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

        state = foo()

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
            return fail()

        flow_state = foo()

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
            fail()
            fail()
            return None

        flow_state = foo()

        assert flow_state.is_failed()

        # The task run states are returned as the data of the flow state
        task_run_states = flow_state.result(raise_on_failure=False)
        assert len(task_run_states) == 2
        assert all(isinstance(state, State) for state in task_run_states)
        task_run_state = task_run_states[0]
        assert task_run_state.is_failed()
        with pytest.raises(ValueError, match="Test"):
            raise_failed_state(task_run_states[0])

    def test_flow_state_defaults_to_task_states_when_no_return_completed(self):
        @task
        def succeed():
            return "foo"

        @flow(version="test")
        def foo():
            succeed()
            succeed()
            return None

        flow_state = foo()

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
            succeed()
            fail()
            return None

        states = foo().result(raise_on_failure=False)
        assert len(states) == 2
        assert all(isinstance(state, State) for state in states)
        assert states[0].result() == "foo"
        with pytest.raises(ValueError, match="bar"):
            raise_failed_state(states[1])

    def test_flow_state_default_handles_nested_failures(self):
        @task
        def fail_task():
            raise ValueError("foo")

        @flow
        def fail_flow():
            fail_task()

        @flow
        def wrapper_flow():
            fail_flow()

        @flow(version="test")
        def foo():
            wrapper_flow()
            return None

        states = foo().result(raise_on_failure=False)
        assert len(states) == 1
        state = states[0]
        assert isinstance(state, State)
        with pytest.raises(ValueError, match="foo"):
            raise_failed_state(state)

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
            return fail1(), fail2(), succeed()

        flow_state = foo()
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

        from prefect.context import PrefectObjectRegistry

        registry = PrefectObjectRegistry.get()

        with registry.block_code_execution():
            state = foo(1, 2)
            assert state is None


class TestSubflowCalls:
    async def test_subflow_call_with_no_tasks(self):
        @flow(version="foo")
        def child(x, y, z):
            return x + y + z

        @flow(version="bar")
        def parent(x, y=2, z=3):
            subflow_state = child(x, y, z)
            return subflow_state

        parent_state = parent(1, 2)
        assert isinstance(parent_state, State)

        child_state = parent_state.result()
        assert child_state.result() == 6

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

        parent_state = parent(1, 2)
        assert isinstance(parent_state, State)
        child_state = parent_state.result()
        assert child_state.result().result() == 6

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

        parent_state = await parent(1, 2)
        assert isinstance(parent_state, State)
        child_state = parent_state.result()
        assert child_state.result().result() == 6

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

        parent_state = await parent(1, 2)
        assert isinstance(parent_state, State)
        child_state = parent_state.result()
        assert child_state.result().result() == 6

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

        parent_state = await parent(1, 2)
        assert isinstance(parent_state, State)
        child_state = parent_state.result()
        assert child_state.result().result() == 6

    async def test_subflow_with_invalid_parameters_is_failed(self, orion_client):
        @flow
        def child(x: int):
            return x

        @flow
        def parent(x):
            subflow_state = child(x)
            return subflow_state

        parent_state = parent("foo")

        with pytest.raises(ParameterTypeError, match="not a valid integer"):
            parent_state.result()

        child_state = parent_state.result(raise_on_failure=False)
        flow_run = await orion_client.read_flow_run(
            child_state.state_details.flow_run_id
        )
        assert flow_run.state.is_failed()
        assert "invalid parameters" in flow_run.state.message

    async def test_subflow_with_invalid_parameters_is_not_failed_without_validation(
        self, orion_client
    ):
        @flow(validate_parameters=False)
        def child(x: int):
            return x

        @flow
        def parent(x):
            subflow_state = child(x)
            return subflow_state

        assert parent("foo").result().result() == "foo"

    async def test_subflow_relationship_tracking(self, orion_client):
        @flow(version="inner")
        def child(x, y):
            return x + y

        @flow()
        def parent():
            subflow_state = child(1, 2)
            return subflow_state

        parent_state = parent()
        parent_flow_run_id = parent_state.state_details.flow_run_id
        child_state = parent_state.result()
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
            state = my_flow()

        flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)
        assert set(flow_run.tags) == {"a", "b"}

    async def test_flow_run_tags_added_to_subflows(self, orion_client):
        @flow
        def my_flow():
            with tags("c", "d"):
                return my_subflow()

        @flow
        def my_subflow():
            pass

        with tags("a", "b"):
            subflow_state = my_flow().result()

        flow_run = await orion_client.read_flow_run(
            subflow_state.state_details.flow_run_id
        )
        assert set(flow_run.tags) == {"a", "b", "c", "d"}


class TestFlowTimeouts:
    def test_flows_fail_with_timeout(self):
        @flow(timeout_seconds=0.1)
        def my_flow():
            time.sleep(1)

        state = my_flow()
        assert state.is_failed()
        assert state.name == "TimedOut"
        assert "exceeded timeout of 0.1 seconds" in state.message

    async def test_async_flows_fail_with_timeout(self):
        @flow(timeout_seconds=0.1)
        async def my_flow():
            await anyio.sleep(1)

        state = await my_flow()
        assert state.is_failed()
        assert state.name == "TimedOut"
        assert "exceeded timeout of 0.1 seconds" in state.message

    def test_timeout_only_applies_if_exceeded(self):
        @flow(timeout_seconds=0.5)
        def my_flow():
            time.sleep(0.1)

        state = my_flow()
        assert state.is_completed()

    def test_timeout_does_not_wait_for_completion_for_sync_flows(self, tmp_path):
        """
        Sync flows are cancelled when they change instructions. The flow will return
        immediately when the timeout is reached, but the thread it executes in will
        continue until the next instruction is reached. `time.sleep` will return then
        the thread will be interrupted.
        """
        canary_file = tmp_path / "canary"

        @flow(timeout_seconds=0.1)
        def my_flow():
            time.sleep(2)
            canary_file.touch()

        t0 = time.perf_counter()
        state = my_flow()
        t1 = time.perf_counter()

        assert state.is_failed()
        assert "exceeded timeout of 0.1 seconds" in state.message
        assert t1 - t0 < 2, f"The engine returns without waiting; took {t1-t0}s"

        time.sleep(2)
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

        state = my_flow()

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
        state = await my_flow()
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
            subflow_state = await my_subflow()
            t1 = anyio.current_time()
            return t1 - t0, subflow_state

        state = await my_flow()

        runtime, subflow_state = state.result()
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
            subflow_state = my_subflow()
            t1 = time.perf_counter()
            return t1 - t0, subflow_state

        state = my_flow()

        runtime, subflow_state = state.result()
        assert "exceeded timeout of 0.1 seconds" in subflow_state.message

        # Wait in case the flow is just sleeping and will still create the canary
        time.sleep(1)

        assert not canary_file.exists()
        assert runtime < 5, f"The engine returns without waiting; took {runtime}s"


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
        assert my_flow(data).result() == data

    def test_flow_parameters_can_be_pydantic_types(self):
        @flow
        def my_flow(x):
            return x

        assert my_flow(ParameterTestModel(data=1)).result() == ParameterTestModel(
            data=1
        )

    @pytest.mark.parametrize(
        "data", ([1, 2, 3], {"foo": "bar"}, {"x", "y"}, 1, "foo", ParameterTestEnum.X)
    )
    def test_flow_parameters_can_be_jsonable_python_types(self, data):
        @flow
        def my_flow(x):
            return x

        assert my_flow(data).result() == data

    def test_subflow_parameters_can_be_unserializable_types(self):
        data = ParameterTestClass()

        @flow
        def my_flow():
            return my_subflow(data).result()

        @flow
        def my_subflow(x):
            return x

        assert my_flow().result() == data

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
        assert my_flow(data).result() == data

    def test_subflow_parameters_can_be_pydantic_types(self):
        @flow
        def my_flow():
            return my_subflow(ParameterTestModel(data=1)).result()

        @flow
        def my_subflow(x):
            return x

        assert my_flow().result() == ParameterTestModel(data=1)

    def test_subflow_parameters_from_future_can_be_unserializable_types(self):
        data = ParameterTestClass()

        @flow
        def my_flow():
            return my_subflow(identity(data)).result()

        @task
        def identity(x):
            return x

        @flow
        def my_subflow(x):
            return x

        assert my_flow().result() == data

    def test_subflow_parameters_can_be_pydantic_types(self):
        @flow
        def my_flow():
            return my_subflow(identity(ParameterTestModel(data=1)))

        @task
        def identity(x):
            return x

        @flow
        def my_subflow(x):
            return x

        assert my_flow().result().result() == ParameterTestModel(data=1)


class TestSubflowTaskInputs:
    async def test_subflow_with_one_upstream_kwarg(self, orion_client):
        @task
        def foo(x):
            return x

        @flow
        def bar(x, y):
            return x + y

        @flow
        def test_flow():
            a = foo(1)
            b = bar(x=a, y=1)
            return a, b

        flow_state = test_flow()
        a, b = flow_state.result()

        task_run = await orion_client.read_task_run(b.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[TaskRunResult(id=a.state_details.task_run_id)],
            y=[],
        )

    async def test_subflow_with_no_upstream_tasks(self, orion_client):
        @flow
        def bar(x, y):
            return x + y

        @flow
        def test_flow():
            return bar(x=2, y=1)

        flow_state = test_flow()
        state = flow_state.result()

        task_run = await orion_client.read_task_run(state.state_details.task_run_id)

        assert task_run.task_inputs == dict(
            x=[],
            y=[],
        )


@pytest.mark.enable_orion_handler
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
        def my_flow(i):
            logger = get_run_logger()
            logger.info(f"Hello {i}")

        my_flow(1)
        my_flow(2)

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
        assert "NameError" in error_log, "References the exception type"
        assert "x + y" in error_log, "References the line of code"

    async def test_raised_exceptions_include_tracebacks(self, orion_client):
        @flow
        def my_flow():
            raise ValueError("Hello!")

        my_flow()

        logs = await orion_client.read_logs()
        error_log = [log.message for log in logs if log.level == 40].pop()
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

        state = my_flow()
        flow_run_id = state.state_details.flow_run_id

        logs = await orion_client.read_logs()
        assert all([log.flow_run_id == flow_run_id for log in logs])
        assert all([log.task_run_id is None for log in logs])


@pytest.mark.enable_orion_handler
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
            return my_subflow()

        state = my_flow()
        flow_run_id = state.state_details.flow_run_id
        subflow_run_id = state.result().state_details.flow_run_id

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
            return my_subflow()

        state = my_flow()
        flow_run_id = state.state_details.flow_run_id
        subflow_run_id = state.result().state_details.flow_run_id

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
    async def test_flow_results_default_to_temporary_directory(self, orion_client):
        @flow
        def foo():
            return 6

        state = foo()

        flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)

        server_state = flow_run.state
        assert isinstance(server_state.data, DataDocument)
        document = server_state.data.decode()
        assert document["block_document_id"] is None
        assert document["data"].startswith(str(TempStorageBlock().basepath()))

        retrieved_result = await orion_client.resolve_datadoc(flow_run.state.data)
        assert retrieved_result == state.result()

    async def test_flow_results_use_server_default(
        self, local_storage_block, orion_client
    ):
        @flow
        def foo():
            return 6

        await orion_client.set_default_storage_block_document(
            local_storage_block._block_document_id
        )

        state = foo()
        assert state.result() == 6

        flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)

        server_state = flow_run.state
        assert isinstance(server_state.data, DataDocument)
        document = server_state.data.decode()
        assert document["block_document_id"] == local_storage_block._block_document_id
        assert document["data"].startswith(str(local_storage_block.basepath()))

        retrieved_result = await orion_client.resolve_datadoc(flow_run.state.data)
        assert retrieved_result == state.result()

    async def test_subflow_results_use_parent_flow_run_value_by_default(
        self, local_storage_block, orion_client
    ):
        @flow
        async def foo():
            # Change the default storage on the server, bar() will not use it
            await orion_client.set_default_storage_block_document(
                local_storage_block._block_document_id
            )
            return bar()

        @flow
        def bar():
            return 6

        parent_state = await foo()
        child_state = parent_state.result()

        parent_flow_run = await orion_client.read_flow_run(
            parent_state.state_details.flow_run_id
        )
        child_flow_run = await orion_client.read_flow_run(
            child_state.state_details.flow_run_id
        )

        parent_document = parent_flow_run.state.data.decode()
        child_document = child_flow_run.state.data.decode()
        assert (
            parent_document["block_document_id"] == child_document["block_document_id"]
        ), "Parent and child used the same block"
        assert (
            child_document["block_document_id"]
            != local_storage_block._block_document_id
        ), "Storage block to use is determined at flow start time"

        retrieved_result = await orion_client.resolve_datadoc(child_flow_run.state.data)
        assert retrieved_result == child_state.result()
