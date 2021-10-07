import sys
from functools import partial
from unittest.mock import MagicMock

import anyio
import pendulum
import pytest

from prefect import flow, task
from prefect.client import OrionClient
from prefect.engine import (
    begin_flow_run,
    orchestrate_flow_run,
    orchestrate_task_run,
    raise_failed_state,
    resolve_datadoc,
    user_return_value_to_state,
)
from prefect.executors import SequentialExecutor
from prefect.futures import PrefectFuture
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.filters import FlowRunFilter
from prefect.orion.schemas.states import (
    Cancelled,
    Completed,
    Failed,
    Pending,
    Running,
    State,
    StateDetails,
    StateType,
)

if sys.version_info < (3, 8):
    # https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock
    from mock import AsyncMock
else:
    from unittest.mock import AsyncMock


class TestUserReturnValueToState:
    async def test_returns_single_state_unaltered(self):
        state = Completed(data=DataDocument.encode("json", "hello"))
        assert await user_return_value_to_state(state) is state

    async def test_all_completed_states(self):
        states = [Completed(message="hi"), Completed(message="bye")]
        result_state = await user_return_value_to_state(states)
        # States have been stored as data
        assert result_state.data.decode() == states
        # Message explains aggregate
        assert result_state.message == "All states completed."
        # Aggregate type is completed
        assert result_state.is_completed()

    async def test_some_failed_states(self):
        states = [
            Completed(message="hi"),
            Failed(message="bye"),
            Failed(message="err"),
        ]
        result_state = await user_return_value_to_state(states)
        # States have been stored as data
        assert result_state.data.decode() == states
        # Message explains aggregate
        assert result_state.message == "2/3 states failed."
        # Aggregate type is failed
        assert result_state.is_failed()

    async def test_some_unfinal_states(self):
        states = [
            Completed(message="hi"),
            Running(message="bye"),
            Pending(message="err"),
        ]
        result_state = await user_return_value_to_state(states)
        # States have been stored as data
        assert result_state.data.decode() == states
        # Message explains aggregate
        assert result_state.message == "2/3 states are not final."
        # Aggregate type is failed
        assert result_state.is_failed()

    async def test_single_state_in_future_is_processed(self, task_run):
        # Unlike a single state without a future, which represents an override of the
        # return state, this is a child task run that is being used to determine the
        # flow state
        state = Completed(data=DataDocument.encode("json", "hello"))
        future = PrefectFuture(
            task_run=task_run,
            executor=None,
            _final_state=state,
        )
        result_state = await user_return_value_to_state(future)
        assert result_state.data.decode() is state
        assert result_state.is_completed()
        assert result_state.message == "All states completed."

    async def test_non_prefect_types_return_completed_state(self):
        result_state = await user_return_value_to_state("foo")
        assert result_state.is_completed()
        assert result_state.data.decode() == "foo"

    async def test_uses_passed_serializer(self):
        result_state = await user_return_value_to_state("foo", serializer="json")
        assert result_state.data.encoding == "json"


class TestRaiseFailedState:
    failed_state = State(
        type=StateType.FAILED,
        data=DataDocument.encode("cloudpickle", ValueError("Test")),
    )

    def test_works_in_sync_context(self):
        with pytest.raises(ValueError, match="Test"):
            raise_failed_state(self.failed_state)

    async def test_raises_state_exception(self):
        with pytest.raises(ValueError, match="Test"):
            await raise_failed_state(self.failed_state)

    async def test_returns_without_error_for_completed_states(self):
        assert await raise_failed_state(Completed()) is None

    async def test_raises_nested_state_exception(self):
        with pytest.raises(ValueError, match="Test"):
            await raise_failed_state(
                State(
                    type=StateType.FAILED,
                    data=DataDocument.encode("cloudpickle", self.failed_state),
                )
            )

    async def test_raises_first_nested_multistate_exception(self):
        # TODO: We may actually want to raise a "multi-error" here where we have several
        #       exceptions displayed at once
        inner_states = [
            Completed(),
            self.failed_state,
            State(
                type=StateType.FAILED,
                data=DataDocument.encode(
                    "cloudpickle", ValueError("Should not be raised")
                ),
            ),
        ]
        with pytest.raises(ValueError, match="Test"):
            await raise_failed_state(
                State(
                    type=StateType.FAILED,
                    data=DataDocument.encode("cloudpickle", inner_states),
                )
            )

    async def test_raises_error_if_failed_state_does_not_contain_exception(self):
        with pytest.raises(TypeError, match="str cannot be resolved into an exception"):
            await raise_failed_state(
                State(
                    type=StateType.FAILED,
                    data=DataDocument.encode("cloudpickle", "foo"),
                )
            )


class TestResolveDataDoc:
    async def test_does_not_allow_other_types(self):
        with pytest.raises(TypeError, match="invalid type str"):
            await resolve_datadoc("foo")

    async def test_resolves_data_document(self):
        assert (
            await resolve_datadoc(DataDocument.encode("cloudpickle", "hello"))
            == "hello"
        )

    async def test_resolves_nested_data_documents(self):
        assert (
            await resolve_datadoc(
                DataDocument.encode("cloudpickle", DataDocument.encode("json", "hello"))
            )
            == "hello"
        )

    async def test_resolves_persisted_data_documents(self):
        async with OrionClient() as client:
            assert (
                await resolve_datadoc(
                    await client.persist_data(
                        DataDocument.encode("json", "hello").json().encode()
                    ),
                    client=client,
                )
                == "hello"
            )


class TestOrchestrateTaskRun:
    async def test_waits_until_scheduled_start_time(
        self, orion_client, flow_run, monkeypatch
    ):
        @task
        def foo():
            return 1

        task_run = await orion_client.create_task_run(
            task=foo,
            flow_run_id=flow_run.id,
            dynamic_key="0",
            state=State(
                type=StateType.SCHEDULED,
                state_details=StateDetails(
                    scheduled_time=pendulum.now("utc").add(minutes=5)
                ),
            ),
        )

        # Mock sleep for a fast test; force transition into a new scheduled state so we
        # don't repeatedly propose the state
        async def reset_scheduled_time(*_):
            await orion_client.set_task_run_state(
                task_run_id=task_run.id,
                state=State(
                    type=StateType.SCHEDULED,
                    state_details=StateDetails(scheduled_time=pendulum.now("utc")),
                ),
                force=True,
            )

        sleep = AsyncMock(side_effect=reset_scheduled_time)
        monkeypatch.setattr("anyio.sleep", sleep)

        state = await orchestrate_task_run(
            task=foo,
            task_run=task_run,
            parameters={},
            wait_for=None,
            client=orion_client,
        )

        sleep.assert_awaited_once()
        assert state.is_completed()
        assert state.result() == 1

    async def test_does_not_wait_for_scheduled_time_in_past(
        self, orion_client, flow_run, monkeypatch
    ):
        @task
        def foo():
            return 1

        task_run = await orion_client.create_task_run(
            task=foo,
            flow_run_id=flow_run.id,
            dynamic_key="0",
            state=State(
                type=StateType.SCHEDULED,
                state_details=StateDetails(
                    scheduled_time=pendulum.now("utc").subtract(minutes=5)
                ),
            ),
        )

        sleep = AsyncMock()
        monkeypatch.setattr("anyio.sleep", sleep)

        state = await orchestrate_task_run(
            task=foo,
            task_run=task_run,
            parameters={},
            wait_for=None,
            client=orion_client,
        )

        sleep.assert_not_called()
        assert state.is_completed()
        assert state.result() == 1

    async def test_waits_for_awaiting_retry_scheduled_time(
        self, monkeypatch, orion_client, flow_run
    ):
        # Define a task that fails once and then succeeds
        mock = MagicMock()

        @task(retries=1, retry_delay_seconds=43)
        def flaky_function():
            mock()

            if mock.call_count == 2:
                return 1

            raise ValueError("try again, but only once")

        # Create a task run to test
        task_run = await orion_client.create_task_run(
            task=flaky_function,
            flow_run_id=flow_run.id,
            state=Pending(),
            dynamic_key="0",
        )

        # Mock sleep for a fast test; force transition into a new scheduled state so we
        # don't repeatedly propose the state
        async def reset_scheduled_time(*_):
            await orion_client.set_task_run_state(
                task_run_id=task_run.id,
                state=State(
                    type=StateType.SCHEDULED,
                    state_details=StateDetails(scheduled_time=pendulum.now("utc")),
                ),
                force=True,
            )

        sleep = AsyncMock(side_effect=reset_scheduled_time)
        monkeypatch.setattr("anyio.sleep", sleep)

        # Actually run the task
        state = await orchestrate_task_run(
            task=flaky_function,
            task_run=task_run,
            parameters={},
            wait_for=None,
            client=orion_client,
        )

        # Check for a proper final result
        assert state.result() == 1

        # Assert that the sleep was called
        # due to network time and rounding, the expected sleep time will be less than
        # 43 seconds so we test a window
        sleep.assert_awaited_once()
        assert 40 < sleep.call_args[0][0] < 43

        # Check expected state transitions
        states = await orion_client.read_task_run_states(task_run.id)
        state_names = [state.type for state in states]
        assert state_names == [
            StateType.PENDING,
            StateType.RUNNING,
            StateType.SCHEDULED,
            StateType.SCHEDULED,  # This is a forced state change to speedup the test
            StateType.RUNNING,
            StateType.COMPLETED,
        ]

    @pytest.mark.parametrize(
        "upstream_task_state", [Pending(), Running(), Cancelled(), Failed()]
    )
    async def test_returns_not_ready_when_any_upstream_futures_resolve_to_incomplete(
        self, orion_client, flow_run, upstream_task_state
    ):
        # Define a mock to ensure the task was not run
        mock = MagicMock()

        @task
        def my_task(x):
            mock()

        # Create an upstream task run
        upstream_task_run = await orion_client.create_task_run(
            task=my_task,
            flow_run_id=flow_run.id,
            state=upstream_task_state,
            dynamic_key="upstream",
        )
        upstream_task_state.state_details.task_run_id = upstream_task_run.id

        # Create a future to wrap the upstream task, have it resolve to the given
        # incomplete state
        future = PrefectFuture(
            task_run=upstream_task_run,
            executor=None,
            _final_state=upstream_task_state,
        )

        # Create a task run to test
        task_run = await orion_client.create_task_run(
            task=my_task,
            flow_run_id=flow_run.id,
            state=Pending(),
            dynamic_key="downstream",
        )

        # Actually run the task
        state = await orchestrate_task_run(
            task=my_task,
            task_run=task_run,
            # Nest the future in a collection to ensure that it is found
            parameters={"x": {"nested": [future]}},
            wait_for=None,
            client=orion_client,
        )

        # The task did not run
        mock.assert_not_called()

        # Check that the state is 'NotReady'
        assert state.is_pending()
        assert state.name == "NotReady"
        assert (
            state.message
            == f"Upstream task run '{upstream_task_run.id}' did not reach a 'COMPLETED' state."
        )

    @pytest.mark.parametrize(
        "upstream_task_state", [Pending(), Running(), Cancelled(), Failed()]
    )
    async def test_states_in_parameters_can_be_incomplete(
        self, orion_client, flow_run, upstream_task_state
    ):
        # Define a mock to ensure the task was not run
        mock = MagicMock()

        @task
        def my_task(x):
            mock(x)

        # Create a task run to test
        task_run = await orion_client.create_task_run(
            task=my_task,
            flow_run_id=flow_run.id,
            state=Pending(),
            dynamic_key="downstream",
        )

        # Actually run the task
        state = await orchestrate_task_run(
            task=my_task,
            task_run=task_run,
            # Nest the future in a collection to ensure that it is found
            parameters={"x": upstream_task_state},
            wait_for=None,
            client=orion_client,
        )

        # The task ran with the state as its input
        mock.assert_called_once_with(upstream_task_state)

        # Check that the state completed happily
        assert state.is_completed()


class TestOrchestrateFlowRun:
    async def test_waits_until_scheduled_start_time(self, orion_client, monkeypatch):
        @flow
        def foo():
            return 1

        flow_run = await orion_client.create_flow_run(
            flow=foo,
            state=State(
                type=StateType.SCHEDULED,
                state_details=StateDetails(
                    scheduled_time=pendulum.now("utc").add(minutes=5)
                ),
            ),
        )

        # Mock sleep for a fast test; force transition into a new scheduled state so we
        # don't repeatedly propose the state
        async def reset_scheduled_time(*_):
            await orion_client.set_flow_run_state(
                flow_run_id=flow_run.id,
                state=State(
                    type=StateType.SCHEDULED,
                    state_details=StateDetails(scheduled_time=pendulum.now("utc")),
                ),
                force=True,
            )

        sleep = AsyncMock(side_effect=reset_scheduled_time)
        monkeypatch.setattr("anyio.sleep", sleep)

        state = await orchestrate_flow_run(
            flow=foo,
            flow_run=flow_run,
            executor=SequentialExecutor(),
            sync_portal=None,
            client=orion_client,
        )

        sleep.assert_awaited_once()
        assert state.result() == 1

    async def test_does_not_wait_for_scheduled_time_in_past(
        self, orion_client, monkeypatch
    ):
        @flow
        def foo():
            return 1

        flow_run = await orion_client.create_flow_run(
            flow=foo,
            state=State(
                type=StateType.SCHEDULED,
                state_details=StateDetails(
                    scheduled_time=pendulum.now("utc").subtract(minutes=5)
                ),
            ),
        )

        sleep = AsyncMock()
        monkeypatch.setattr("anyio.sleep", sleep)

        state = await orchestrate_flow_run(
            flow=foo,
            flow_run=flow_run,
            executor=SequentialExecutor(),
            sync_portal=None,
            client=orion_client,
        )

        sleep.assert_not_called()
        assert state.result() == 1


class TestFlowRunCrashes:
    async def test_anyio_cancellation_crashes_flow(self, flow_run, orion_client):
        @flow
        async def my_flow():
            await anyio.sleep_forever()

        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(
                    partial(
                        begin_flow_run,
                        flow=my_flow,
                        flow_run=flow_run,
                        client=orion_client,
                    )
                )
                await anyio.sleep(0.2)  # Give the flow time to start
                tg.cancel_scope.cancel()
        except BaseException:
            # In python 3.8+ cancellation raises a `BaseException` that will not
            # be captured by `orchestrate_flow_run` and needs to be trapped here to
            # prevent the test from failing before we can assert things are 'Crashed'
            pass

        flow_run = await orion_client.read_flow_run(flow_run.id)

        assert flow_run.state.is_failed()
        assert flow_run.state.name == "Crashed"
        assert (
            "Execution was interrupted by the async runtime" in flow_run.state.message
        )

    async def test_anyio_cancellation_crashes_subflow(self, flow_run, orion_client):
        @flow
        async def child_flow():
            await anyio.sleep_forever()

        @flow
        async def parent_flow():
            await child_flow()

        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(
                    partial(
                        begin_flow_run,
                        flow=parent_flow,
                        flow_run=flow_run,
                        client=orion_client,
                    )
                )
                await anyio.sleep(0.5)  # Give the subflow time to start
                tg.cancel_scope.cancel()
        except BaseException:
            # In python 3.8+ cancellation raises a `BaseException` that will not
            # be captured by `orchestrate_flow_run` and needs to be trapped here to
            # prevent the test from failing before we can assert things are 'Crashed'
            pass

        parent_flow_run = await orion_client.read_flow_run(flow_run.id)
        assert parent_flow_run.state.is_failed()
        assert parent_flow_run.state.name == "Crashed"

        child_runs = await orion_client.read_flow_runs(
            flow_run_filter=FlowRunFilter(parent_task_run_id=dict(is_null_=False))
        )
        assert len(child_runs) == 1
        child_run = child_runs[0]
        assert child_run.state.is_failed()
        assert child_run.state.name == "Crashed"
        assert (
            "Execution was interrupted by the async runtime" in child_run.state.message
        )

    async def test_keyboard_interrupt_crashes_flow(self, flow_run, orion_client):
        @flow
        async def my_flow():
            raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            await begin_flow_run(flow=my_flow, flow_run=flow_run, client=orion_client)

        flow_run = await orion_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_failed()
        assert flow_run.state.name == "Crashed"
        assert "Execution was interrupted by the system" in flow_run.state.message

    async def test_flow_timeouts_are_not_crashes(self, flow_run, orion_client):
        """
        Since timeouts use anyio cancellation scopes, we want to ensure that they are
        not marked as crashes
        """

        @flow(timeout_seconds=0.1)
        async def my_flow():
            await anyio.sleep_forever()

        await begin_flow_run(
            flow=my_flow,
            flow_run=flow_run,
            client=orion_client,
        )
        flow_run = await orion_client.read_flow_run(flow_run.id)

        assert flow_run.state.is_failed()
        assert flow_run.state.name != "Crashed"
        assert "timed out" in flow_run.state.message

    async def test_timeouts_do_not_hide_crashes(self, flow_run, orion_client):
        """
        Since timeouts capture anyio cancellations, we want to ensure that something
        still ends up in a 'Crashed' state if it is cancelled independently from our
        timeout cancellation.
        """

        @flow(timeout_seconds=100)
        async def my_flow():
            await anyio.sleep_forever()

        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(
                    partial(
                        begin_flow_run,
                        flow=my_flow,
                        flow_run=flow_run,
                        client=orion_client,
                    )
                )
                await anyio.sleep(0.2)  # Give the flow time to start
                tg.cancel_scope.cancel()
        except BaseException:
            # In python 3.8+ cancellation raises a `BaseException` that will not
            # be captured by `orchestrate_flow_run` and needs to be trapped here to
            # prevent the test from failing before we can assert things are 'Crashed'
            pass

        flow_run = await orion_client.read_flow_run(flow_run.id)

        assert flow_run.state.is_failed()
        assert flow_run.state.name == "Crashed"
        assert (
            "Execution was interrupted by the async runtime" in flow_run.state.message
        )
