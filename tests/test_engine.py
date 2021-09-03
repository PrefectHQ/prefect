import pytest
import pendulum

from prefect import task, flow
from prefect.engine import (
    user_return_value_to_state,
    get_result,
    raise_failed_state,
    resolve_datadoc,
    orchestrate_task_run,
)
from prefect.orion.schemas.states import State, StateType, Completed, StateDetails
from prefect.orion.schemas.data import DataDocument
from prefect.futures import PrefectFuture
from prefect.utilities.testing import exceptions_equal
from prefect.client import OrionClient
from prefect.utilities.compat import AsyncMock


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
            State(type=StateType.FAILED, message="bye"),
            State(type=StateType.FAILED, message="err"),
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
            State(type=StateType.RUNNING, message="bye"),
            State(type=StateType.PENDING, message="err"),
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
            _result=state,
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
                    scheduled_time=pendulum.now().add(minutes=5)
                ),
            ),
        )

        async def cancel_run():
            # TODO: Ensure this will exit the run as expected
            await orion_client.create_task_run_state(
                task_run_id=task_run_id, state=State(type=StateType.COMPLETED)
            )

        sleep = AsyncMock(side_effect=cancel_run)
        monkeypatch.setattr("anyio.sleep", sleep)

        result = await orchestrate_task_run(
            task=foo,
            task_run_id=task_run_id,
            flow_run_id=flow_run_id,
            parameters={},
            client=orion_client,
        )

        sleep.assert_awaited_once()
