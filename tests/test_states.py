import uuid

import pytest

from prefect.exceptions import CrashedRun, FailedRun
from prefect.results import LiteralResult, ResultFactory
from prefect.states import (
    Completed,
    Crashed,
    Failed,
    Pending,
    Running,
    is_state,
    is_state_iterable,
    raise_state_exception,
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


@pytest.mark.parametrize("state_cls", [Failed, Crashed])
class TestRaiseStateException:
    def test_works_in_sync_context(self, state_cls):
        with pytest.raises(ValueError, match="Test"):
            raise_state_exception(state_cls(data=ValueError("Test")))

    async def test_raises_state_exception(self, state_cls):
        with pytest.raises(ValueError, match="Test"):
            await raise_state_exception(state_cls(data=ValueError("Test")))

    async def test_returns_without_error_for_completed_states(self, state_cls):
        assert await raise_state_exception(Completed()) is None

    async def test_raises_nested_state_exception(self, state_cls):
        with pytest.raises(ValueError, match="Test"):
            await raise_state_exception(state_cls(data=Failed(data=ValueError("Test"))))

    async def test_raises_value_error_if_nested_state_is_not_failed(self, state_cls):
        with pytest.raises(
            ValueError, match="Expected failed or crashed state got Completed"
        ):
            await raise_state_exception(state_cls(data=Completed(data="test")))

    async def test_raises_first_nested_multistate_exception(self, state_cls):
        # TODO: We may actually want to raise a "multi-error" here where we have several
        #       exceptions displayed at once
        inner_states = [
            Completed(data="test"),
            Failed(data=ValueError("Test")),
            Failed(data=ValueError("Should not be raised")),
        ]
        with pytest.raises(ValueError, match="Test"):
            await raise_state_exception(state_cls(data=inner_states))

    async def test_value_error_if_all_multistates_are_not_failed(self, state_cls):
        inner_states = [
            Completed(),
            Completed(),
            Completed(data=ValueError("Should not be raised")),
        ]
        with pytest.raises(
            ValueError,
            match="Failed state result was an iterable of states but none were failed",
        ):
            await raise_state_exception(state_cls(data=inner_states))

    @pytest.mark.parametrize("value", ["foo", LiteralResult(value="foo")])
    async def test_raises_wrapper_with_message_if_result_is_string(
        self, state_cls, value
    ):
        with pytest.raises(
            FailedRun if state_cls == Failed else CrashedRun, match="foo"
        ):
            await raise_state_exception(state_cls(data=value))

    async def test_raises_base_exception(self, state_cls):
        with pytest.raises(BaseException):
            await raise_state_exception(state_cls(data=BaseException("foo")))

    async def test_raises_wrapper_with_state_message_if_result_is_null(self, state_cls):
        with pytest.raises(
            FailedRun if state_cls == Failed else CrashedRun, match="foo"
        ):
            await raise_state_exception(state_cls(data=None, message="foo"))

    async def test_raises_error_if_failed_state_does_not_contain_exception(
        self, state_cls
    ):
        with pytest.raises(TypeError, match="int cannot be resolved into an exception"):
            await raise_state_exception(state_cls(data=2))


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

    @pytest.mark.parametrize("run_identifier", ["task_run_id", "flow_run_id"])
    async def test_single_state_in_future_is_processed(self, run_identifier, factory):
        state = Completed(data="test", state_details={run_identifier: uuid.uuid4()})
        # The engine is responsible for resolving the futures
        result_state = await return_value_to_state(state, factory)
        assert await result_state.result() == state
        assert result_state.is_completed()
        assert result_state.message == "All states completed."

    async def test_non_prefect_types_return_completed_state(self, factory):
        result_state = await return_value_to_state("foo", factory)
        assert result_state.is_completed()
        assert await result_state.result() == "foo"
