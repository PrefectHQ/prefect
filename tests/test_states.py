import pytest

from prefect.client.schemas import Completed, Failed, Pending, Running, State
from prefect.deprecated.data_documents import DataDocument
from prefect.futures import PrefectFuture
from prefect.orion.schemas.states import StateType
from prefect.results import ResultFactory
from prefect.states import (
    is_state,
    is_state_iterable,
    raise_failed_state,
    return_value_to_state,
)


def test_is_state():
    assert is_state(Completed())


def test_is_not_state():
    assert not is_state(None)
    assert not is_state("test")


def test_is_state_requires_instance():
    assert not is_state(Completed)


@pytest.mark.parametrize("iterable_type", [set, list, tuple])
def test_is_state_iterable(iterable_type):
    assert is_state_iterable(iterable_type([Completed(), Completed()]))


def test_is_not_state_iterable_if_unsupported_iterable_type():
    assert not is_state_iterable({Completed(): i for i in range(3)})


@pytest.mark.parametrize("iterable_type", [set, list, tuple])
def test_is_not_state_iterable_if_empty(iterable_type):
    assert not is_state_iterable(iterable_type())


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


class TestReturnValueToState:
    @pytest.fixture
    async def factory(orion_client):
        return await ResultFactory.default_factory(client=orion_client)

    async def test_returns_single_state_unaltered(self, factory):
        state = Completed(data="hello!")
        assert await return_value_to_state(state, factory) is state

    async def test_returns_single_state_unaltered_with_user_created_reference(
        self, factory
    ):
        state = Completed(data=await factory.create_result("test"))
        result_state = await return_value_to_state(state, factory)
        assert result_state is state
        assert await result_state.result() == "test"

    async def test_all_completed_states(self, factory):
        states = [Completed(message="hi"), Completed(message="bye")]
        result_state = await return_value_to_state(states, factory)
        # States have been stored as data
        assert await result_state.result() == states
        # Message explains aggregate
        assert result_state.message == "All states completed."
        # Aggregate type is completed
        assert result_state.is_completed()

    async def test_some_failed_states(self, factory):
        states = [
            Completed(message="hi"),
            Failed(message="bye"),
            Failed(message="err"),
        ]
        result_state = await return_value_to_state(states, factory)
        # States have been stored as data
        assert await result_state.result(raise_on_failure=False) == states
        # Message explains aggregate
        assert result_state.message == "2/3 states failed."
        # Aggregate type is failed
        assert result_state.is_failed()

    async def test_some_unfinal_states(self, factory):
        states = [
            Completed(message="hi"),
            Running(message="bye"),
            Pending(message="err"),
        ]
        result_state = await return_value_to_state(states, factory)
        # States have been stored as data
        assert await result_state.result(raise_on_failure=False) == states
        # Message explains aggregate
        assert result_state.message == "2/3 states are not final."
        # Aggregate type is failed
        assert result_state.is_failed()

    async def test_single_state_in_future_is_processed(self, task_run, factory):
        # Unlike a single state without a future, which represents an override of the
        # return state, this is a child task run that is being used to determine the
        # flow state
        state = Completed(data="test")
        future = PrefectFuture(
            key=str(task_run.id),
            name="hello",
            task_runner=None,
            _final_state=state,
        )
        future.task_run = task_run
        future._submitted.set()
        result_state = await return_value_to_state(future, factory)
        assert await result_state.result() == state
        assert result_state.is_completed()
        assert result_state.message == "All states completed."

    async def test_non_prefect_types_return_completed_state(self, factory):
        result_state = await return_value_to_state("foo", factory)
        assert result_state.is_completed()
        assert await result_state.result() == "foo"
