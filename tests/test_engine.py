from unittest.mock import MagicMock

import pendulum
import pytest

from prefect import flow, task
from prefect.client import OrionClient
from prefect.engine import (
    get_result,
    orchestrate_flow_run,
    orchestrate_task_run,
    raise_failed_state,
    resolve_datadoc,
    user_return_value_to_state,
)
from prefect.executors import BaseExecutor
from prefect.futures import PrefectFuture
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import (
    Completed,
    State,
    StateDetails,
    StateType,
    Failed,
    Running,
    Pending,
)
from prefect.utilities.compat import AsyncMock
from prefect.utilities.testing import exceptions_equal


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

    async def test_single_state_in_future_is_processed(self):
        # Unlike a single state without a future, which represents an override of the
        # return state, this is a child task run that is being used to determine the
        # flow state
        state = Completed(data=DataDocument.encode("json", "hello"))
        future = PrefectFuture(
            flow_run_id=None,
            client=None,
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


class TestGetResult:
    async def test_decodes_state_data(self):
        assert (
            await get_result(Completed(data=DataDocument.encode("json", "hello")))
            == "hello"
        )

    async def test_waits_for_futures(self):
        assert (
            await get_result(
                PrefectFuture(
                    flow_run_id=None,
                    client=None,
                    executor=None,
                    _final_state=Completed(data=DataDocument.encode("json", "hello")),
                )
            )
            == "hello"
        )

    def test_works_in_sync_context(self):
        assert (
            get_result(Completed(data=DataDocument.encode("json", "hello"))) == "hello"
        )

    async def test_raises_failure_states(self):
        with pytest.raises(ValueError, match="Test"):
            await get_result(
                State(
                    type=StateType.FAILED,
                    data=DataDocument.encode("cloudpickle", ValueError("Test")),
                )
            )

    async def test_returns_exceptions_from_failure_states_when_requested(self):
        result = await get_result(
            State(
                type=StateType.FAILED,
                data=DataDocument.encode("cloudpickle", ValueError("Test")),
            ),
            raise_failures=False,
        )
        assert exceptions_equal(result, ValueError("Test"))

    async def test_decodes_nested_data_documents(self):
        assert (
            await get_result(
                Completed(
                    data=DataDocument.encode(
                        "cloudpickle", DataDocument.encode("json", "hello")
                    )
                )
            )
            == "hello"
        )

    async def test_decodes_persisted_data_documents(self):
        async with OrionClient() as client:
            assert (
                await get_result(
                    Completed(
                        data=await client.persist_data(
                            DataDocument.encode("json", "hello").json().encode()
                        )
                    )
                )
                == "hello"
            )

    async def test_decodes_using_cached_data_if_available(self):
        async with OrionClient() as client:
            orion_doc = await client.persist_data(
                DataDocument.encode("json", "hello").json().encode()
            )
            # Corrupt the blob so that if we try to retrieve the data from the API
            # it will fail
            orion_doc.blob = b"BROKEN!"
            assert await get_result(Completed(data=orion_doc)) == "hello"


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
    @pytest.fixture
    async def flow_run_id(self, orion_client: OrionClient):
        @flow
        def foo():
            pass

        return await orion_client.create_flow_run(flow=foo)

    async def test_waits_until_scheduled_start_time(
        self, orion_client, flow_run_id, monkeypatch
    ):
        @task
        def foo():
            return 1

        task_run_id = await orion_client.create_task_run(
            task=foo,
            flow_run_id=flow_run_id,
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
                task_run_id=task_run_id,
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
            task_run_id=task_run_id,
            flow_run_id=flow_run_id,
            parameters={},
            client=orion_client,
        )

        sleep.assert_awaited_once()
        assert state.is_completed()
        assert await get_result(state) == 1

    async def test_does_not_wait_for_scheduled_time_in_past(
        self, orion_client, flow_run_id, monkeypatch
    ):
        @task
        def foo():
            return 1

        task_run_id = await orion_client.create_task_run(
            task=foo,
            flow_run_id=flow_run_id,
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
            task_run_id=task_run_id,
            flow_run_id=flow_run_id,
            parameters={},
            client=orion_client,
        )

        sleep.assert_not_called()
        assert state.is_completed()
        assert await get_result(state) == 1

    async def test_waits_for_awaiting_retry_scheduled_time(
        self, monkeypatch, orion_client, flow_run_id
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
        task_run_id = await orion_client.create_task_run(
            task=flaky_function,
            flow_run_id=flow_run_id,
            state=Pending(),
        )

        # Mock sleep for a fast test; force transition into a new scheduled state so we
        # don't repeatedly propose the state
        async def reset_scheduled_time(*_):
            await orion_client.set_task_run_state(
                task_run_id=task_run_id,
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
            task_run_id=task_run_id,
            flow_run_id=flow_run_id,
            parameters={},
            client=orion_client,
        )

        # Check for a proper final result
        assert await get_result(state) == 1

        # Assert that the sleep was called
        # due to network time and rounding, the expected sleep time will be less than
        # 43 seconds so we test a window
        sleep.assert_awaited_once()
        assert 40 < sleep.call_args[0][0] < 43

        # Check expected state transitions
        states = await orion_client.read_task_run_states(task_run_id)
        state_names = [state.name for state in states]
        assert state_names == [
            "Pending",
            "Running",
            "Awaiting Retry",
            "Scheduled",  # This is a forced state change to speedup the test
            "Running",
            "Completed",
        ]


class TestOrchestrateFlowRun:
    async def test_waits_until_scheduled_start_time(self, orion_client, monkeypatch):
        @flow
        def foo():
            return 1

        flow_run_id = await orion_client.create_flow_run(
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
                flow_run_id=flow_run_id,
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
            flow_run_id=flow_run_id,
            parameters={},
            executor=BaseExecutor(),
            sync_portal=None,
            client=orion_client,
        )

        sleep.assert_awaited_once()
        assert await get_result(state) == 1

    async def test_does_not_wait_for_scheduled_time_in_past(
        self, orion_client, monkeypatch
    ):
        @flow
        def foo():
            return 1

        flow_run_id = await orion_client.create_flow_run(
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
            flow_run_id=flow_run_id,
            parameters={},
            executor=BaseExecutor(),
            sync_portal=None,
            client=orion_client,
        )

        sleep.assert_not_called()
        assert await get_result(state) == 1
