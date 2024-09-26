import uuid
from pathlib import Path

import pytest

from prefect import flow
from prefect.exceptions import CancelledRun, CrashedRun, FailedRun
from prefect.results import (
    PersistedResult,
    ResultRecord,
    ResultRecordMetadata,
    ResultStore,
)
from prefect.serializers import JSONSerializer
from prefect.states import (
    Cancelled,
    Completed,
    Crashed,
    Failed,
    Paused,
    Pending,
    Running,
    State,
    StateGroup,
    is_state_iterable,
    raise_state_exception,
    return_value_to_state,
)
from prefect.utilities.annotations import quote


@pytest.mark.parametrize("iterable_type", [set, list, tuple])
def test_is_state_iterable(iterable_type):
    assert is_state_iterable(iterable_type([Completed(), Completed()]))


def test_is_not_state_iterable_if_unsupported_iterable_type():
    assert not is_state_iterable({Completed(): i for i in range(3)})


@pytest.mark.parametrize("iterable_type", [set, list, tuple])
def test_is_not_state_iterable_if_empty(iterable_type):
    assert not is_state_iterable(iterable_type())


@pytest.mark.parametrize("state_cls", [Failed, Crashed, Cancelled])
class TestRaiseStateException:
    def test_works_in_sync_context(self, state_cls):
        with pytest.raises(ValueError, match="Test"):

            @flow
            def test_flow():
                raise_state_exception(state_cls(data=ValueError("Test")))

            test_flow()

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

    async def test_raises_wrapper_with_message_if_result_is_string(self, state_cls):
        state_to_exception = {
            Failed: FailedRun,
            Crashed: CrashedRun,
            Cancelled: CancelledRun,
        }

        with pytest.raises(state_to_exception[state_cls]):
            await raise_state_exception(state_cls(data="foo"))

    async def test_raises_base_exception(self, state_cls):
        with pytest.raises(BaseException):
            await raise_state_exception(state_cls(data=BaseException("foo")))

    async def test_raises_wrapper_with_state_message_if_result_is_null(self, state_cls):
        state_to_exception = {
            Failed: FailedRun,
            Crashed: CrashedRun,
            Cancelled: CancelledRun,
        }

        with pytest.raises(state_to_exception[state_cls]):
            await raise_state_exception(state_cls(data=None, message="foo"))

    async def test_raises_error_if_failed_state_does_not_contain_exception(
        self, state_cls
    ):
        with pytest.raises(TypeError, match="int cannot be resolved into an exception"):
            await raise_state_exception(state_cls(data=2))

    async def test_quoted_state_does_not_raise_state_exception(self, state_cls):
        @flow
        def test_flow():
            return quote(state_cls())

        actual = test_flow()
        assert isinstance(actual, quote)
        assert isinstance(actual.unquote(), State)


class TestReturnValueToState:
    @pytest.fixture
    async def store(self):
        return ResultStore()

    async def test_returns_single_state_unaltered(self, store):
        state = Completed(data="hello!")
        assert await return_value_to_state(state, store) is state

    async def test_returns_single_state_with_null_data_and_persist_off(self):
        store = ResultStore()
        state = Completed(data=None)
        result_state = await return_value_to_state(state, store)
        assert result_state is state
        assert isinstance(result_state.data, ResultRecord)
        assert not Path(result_state.data.metadata.storage_key).exists()
        assert await result_state.result() is None

    async def test_returns_single_state_with_data_to_persist(self):
        store = ResultStore()
        state = Completed(data=1)
        result_state = await return_value_to_state(state, store, write_result=True)
        assert result_state is state
        assert isinstance(result_state.data, ResultRecord)
        assert Path(result_state.data.metadata.storage_key).exists()
        assert await result_state.result() == 1

    async def test_returns_persisted_results_unaltered(
        self, ignore_prefect_deprecation_warnings
    ):
        # TODO: This test will be removed in a future release when PersistedResult is removed
        store = ResultStore(persist_result=True)
        result = await store.create_result(42)
        result_state = await return_value_to_state(result, store)
        assert result_state.data == result
        assert await result_state.result() == 42

    async def test_returns_persisted_result_records_unaltered(self):
        store = ResultStore()
        record = store.create_result_record(42)
        result_state = await return_value_to_state(record, store)
        assert result_state.data == record
        assert await result_state.result() == 42

    async def test_returns_single_state_unaltered_with_user_created_reference(
        self, store
    ):
        result = store.create_result_record("test")
        state = Completed(data=result)
        result_state = await return_value_to_state(state, store)
        assert result_state is state
        # Pydantic makes a copy of the result type during state so we cannot assert that
        # it is the original `result` object but we can assert there is not a copy in
        # `return_value_to_state`
        assert result_state.data is state.data
        assert result_state.data == result
        assert await result_state.result() == "test"

    async def test_all_completed_states(self, store):
        states = [Completed(message="hi"), Completed(message="bye")]
        result_state = await return_value_to_state(states, store)
        # States have been stored as data
        assert await result_state.result() == states
        # Message explains aggregate
        assert result_state.message == "All states completed."
        # Aggregate type is completed
        assert result_state.is_completed()

    async def test_some_failed_states(self, store):
        states = [
            Completed(message="hi"),
            Failed(message="bye"),
            Failed(message="err"),
        ]
        result_state = await return_value_to_state(states, store)
        # States have been stored as data
        assert await result_state.result(raise_on_failure=False) == states
        # Message explains aggregate
        assert result_state.message == "2/3 states failed."
        # Aggregate type is failed
        assert result_state.is_failed()

    async def test_some_unfinal_states(self, store):
        states = [
            Completed(message="hi"),
            Running(message="bye"),
            Pending(message="err"),
        ]
        result_state = await return_value_to_state(states, store)
        # States have been stored as data
        assert await result_state.result(raise_on_failure=False) == states
        # Message explains aggregate
        assert result_state.message == "2/3 states are not final."
        # Aggregate type is failed
        assert result_state.is_failed()

    @pytest.mark.parametrize("run_identifier", ["task_run_id", "flow_run_id"])
    async def test_single_state_in_future_is_processed(self, run_identifier, store):
        state = Completed(data="test", state_details={run_identifier: uuid.uuid4()})
        # The engine is responsible for resolving the futures
        result_state = await return_value_to_state(state, store)
        assert await result_state.result() == state
        assert result_state.is_completed()
        assert result_state.message == "All states completed."

    async def test_non_prefect_types_return_completed_state(self, store):
        result_state = await return_value_to_state("foo", store)
        assert result_state.is_completed()
        assert await result_state.result() == "foo"


class TestStateGroup:
    def test_fail_count(self):
        states = [
            Failed(data=ValueError("1")),
            Failed(data=ValueError("2")),
            Failed(data=ValueError("3")),
            Crashed(data=ValueError("4")),
            Crashed(data=ValueError("5")),
        ]

        assert StateGroup(states).fail_count == 5

    def test_all_completed(self):
        states = [
            Completed(data="test"),
            Completed(data="test"),
            Completed(data="test"),
        ]

        assert StateGroup(states).all_completed()

        states = [
            Completed(data="test"),
            Failed(data=ValueError("1")),
        ]

        assert not StateGroup(states).all_completed()

    def test_any_cancelled(self):
        states = [
            Cancelled(),
            Failed(data=ValueError("1")),
        ]

        assert StateGroup(states).any_cancelled()

        states = [
            Completed(data="test"),
            Failed(data=ValueError("1")),
        ]

        assert not StateGroup(states).any_cancelled()

    def test_any_paused(self):
        states = [
            Paused(),
            Failed(data=ValueError("1")),
        ]

        assert StateGroup(states).any_paused()

        states = [
            Completed(data="test"),
            Failed(data=ValueError("1")),
        ]

        assert not StateGroup(states).any_paused()

    def test_any_failed(self):
        states = [
            Completed(data="test"),
            Failed(data=ValueError("1")),
        ]

        assert StateGroup(states).any_failed()

        states = [
            Completed(data="test"),
            Completed(data="test"),
            Completed(data="test"),
        ]

        assert not StateGroup(states).any_failed()

    def test_all_final(self):
        states = [
            Failed(data=ValueError("failed")),
            Crashed(data=ValueError("crashed")),
            Completed(data="complete"),
            Cancelled(data="cancelled"),
        ]

        assert StateGroup(states).all_final()

        states = [
            Failed(data=ValueError("failed")),
            Crashed(data=ValueError("crashed")),
            Completed(data="complete"),
            Cancelled(data="cancelled"),
            Running(),
        ]

        assert not StateGroup(states).all_final()

        states = [
            Failed(data=ValueError("failed")),
            Crashed(data=ValueError("crashed")),
            Completed(data="complete"),
            Paused(data="paused"),
            Running(),
        ]

        assert not StateGroup(states).all_final()

    def test_counts_message_all_final(self):
        states = [
            Failed(data=ValueError("failed")),
            Crashed(data=ValueError("crashed")),
            Completed(data="complete"),
            Cancelled(data="cancelled"),
        ]

        counts_message = StateGroup(states).counts_message()

        assert "total=4" in counts_message
        assert "'FAILED'=1" in counts_message
        assert "'CRASHED'=1" in counts_message
        assert "'COMPLETED'=1" in counts_message
        assert "'CANCELLED'=1" in counts_message

    def test_counts_message_some_non_final(self):
        states = [
            Failed(data=ValueError("failed")),
            Running(),
            Crashed(data=ValueError("crashed")),
            Running(),
        ]

        counts_message = StateGroup(states).counts_message()

        assert "total=4" in counts_message
        assert "not_final=2" in counts_message
        assert "'FAILED'=1" in counts_message
        assert "'CRASHED'=1" in counts_message
        assert "'RUNNING'=2" in counts_message


def test_state_returns_expected_result(ignore_prefect_deprecation_warnings):
    """
    Regression test for https://github.com/PrefectHQ/prefect/issues/14927
    """
    state = Completed(data="test")
    assert state.result() == "test"

    state = Completed(
        data=ResultRecord(
            result="test",
            metadata=ResultRecordMetadata(
                serializer=JSONSerializer(), storage_key="test"
            ),
        )
    )
    assert state.result() == "test"

    # legacy case
    result = PersistedResult(serializer_type="pickle", storage_key="test")
    result._cache = "test"
    state = Completed(data=result)
    assert state.result() == "test"
