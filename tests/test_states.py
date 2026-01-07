import signal
import uuid
from pathlib import Path

import pytest

from prefect import flow
from prefect._states import (
    exception_to_crashed_state_sync,
    exception_to_failed_state_sync,
    return_value_to_state_sync,
)
from prefect.exceptions import CancelledRun, CrashedRun, FailedRun, TerminationSignal
from prefect.results import (
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
    aget_state_exception,
    araise_state_exception,
    get_state_exception,
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

    async def test_aget_state_exception_from_result_record_metadata(self, state_cls):
        store = ResultStore()
        exception = ValueError("persisted error")
        record = store.create_result_record(exception)
        await store.apersist_result_record(record)
        state = state_cls(data=record.metadata)

        result = await aget_state_exception(state)
        assert isinstance(result, ValueError)
        assert str(result) == "persisted error"

    def test_get_state_exception_from_result_record_metadata(self, state_cls):
        store = ResultStore()
        exception = ValueError("persisted error")
        record = store.create_result_record(exception)
        store.persist_result_record(record)
        state = state_cls(data=record.metadata)

        result = get_state_exception(state)
        assert isinstance(result, ValueError)
        assert str(result) == "persisted error"

    async def test_araise_state_exception_from_result_record_metadata(self, state_cls):
        store = ResultStore()
        exception = ValueError("persisted error")
        record = store.create_result_record(exception)
        await store.apersist_result_record(record)
        state = state_cls(data=record.metadata)

        with pytest.raises(ValueError, match="persisted error"):
            await araise_state_exception(state)

    def test_raise_state_exception_from_result_record_metadata(self, state_cls):
        store = ResultStore()
        exception = ValueError("persisted error")
        record = store.create_result_record(exception)
        store.persist_result_record(record)
        state = state_cls(data=record.metadata)

        with pytest.raises(ValueError, match="persisted error"):
            raise_state_exception(state)


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


class TestExceptionToCrashedStateSync:
    """Tests for exception_to_crashed_state_sync.

    These tests verify that exception_to_crashed_state_sync works correctly
    in both sync and async contexts. The function is designed for use in
    sync code paths but previously required an async backend due to calling
    anyio.get_cancelled_exc_class().

    See: https://github.com/PrefectHQ/prefect/issues/20135
    """

    def test_works_without_async_backend(self):
        """Test that the function works in a pure sync context without async backend.

        This is a regression test for https://github.com/PrefectHQ/prefect/issues/20135

        The bug was that exception_to_crashed_state_sync called
        anyio.get_cancelled_exc_class() which requires an active async backend.
        When called from sync-only code (like sync task crash handling), this
        would raise NoEventLoopError/NoCurrentAsyncBackend.
        """
        exc = RuntimeError("test error")
        # This should work without any async context
        state = exception_to_crashed_state_sync(exc)
        assert state.is_crashed()
        assert "RuntimeError: test error" in state.message

    def test_handles_termination_signal_without_async_backend(self):
        """Test TerminationSignal handling works without async backend.

        TerminationSignal is commonly raised during flow/task cancellation
        and must be handleable in sync contexts.
        """
        exc = TerminationSignal(signal=signal.SIGTERM)
        state = exception_to_crashed_state_sync(exc)
        assert state.is_crashed()
        assert (
            "terminated" in state.message.lower()
            or "termination" in state.message.lower()
        )

    def test_handles_keyboard_interrupt_without_async_backend(self):
        """Test KeyboardInterrupt handling works without async backend."""
        exc = KeyboardInterrupt()
        state = exception_to_crashed_state_sync(exc)
        assert state.is_crashed()
        assert "interrupt" in state.message.lower()

    def test_handles_system_exit_without_async_backend(self):
        """Test SystemExit handling works without async backend."""
        exc = SystemExit(1)
        state = exception_to_crashed_state_sync(exc)
        assert state.is_crashed()
        assert "system exit" in state.message.lower()

    async def test_returns_crashed_state_for_generic_exception(self):
        # Run in async context because anyio.get_cancelled_exc_class() requires it
        exc = RuntimeError("something went wrong")
        state = exception_to_crashed_state_sync(exc)
        assert state.is_crashed()
        assert "Execution was interrupted by an unexpected exception" in state.message
        assert "RuntimeError: something went wrong" in state.message
        assert state.data is exc

    async def test_returns_crashed_state_for_keyboard_interrupt(self):
        exc = KeyboardInterrupt()
        state = exception_to_crashed_state_sync(exc)
        assert state.is_crashed()
        assert "Execution was aborted by an interrupt signal" in state.message

    async def test_returns_crashed_state_for_system_exit(self):
        exc = SystemExit(1)
        state = exception_to_crashed_state_sync(exc)
        assert state.is_crashed()
        assert "Execution was aborted by Python system exit call" in state.message

    async def test_stores_exception_in_result_store_when_provided(self):
        exc = ValueError("test error")
        store = ResultStore()
        state = exception_to_crashed_state_sync(exc, result_store=store)
        assert state.is_crashed()
        assert isinstance(state.data, ResultRecord)
        result = await state.result(raise_on_failure=False)
        assert isinstance(result, ValueError)
        assert str(result) == "test error"


class TestExceptionToFailedStateSync:
    def test_returns_failed_state_with_passed_exception(self):
        exc = ValueError("test error")
        state = exception_to_failed_state_sync(exc)
        assert state.is_failed()
        assert "ValueError: test error" in state.message
        assert state.data is exc
        assert state.state_details.retriable is False

    def test_raises_if_no_exception_and_no_active_exception(self):
        with pytest.raises(ValueError, match="no active exception"):
            exception_to_failed_state_sync()

    def test_captures_active_exception(self):
        try:
            raise RuntimeError("active error")
        except RuntimeError:
            state = exception_to_failed_state_sync()
            assert state.is_failed()
            assert "RuntimeError: active error" in state.message

    async def test_stores_exception_in_result_store_when_provided(self):
        exc = ValueError("test error")
        store = ResultStore()
        state = exception_to_failed_state_sync(exc, result_store=store)
        assert state.is_failed()
        assert isinstance(state.data, ResultRecord)
        result = await state.result(raise_on_failure=False)
        assert isinstance(result, ValueError)
        assert str(result) == "test error"

    def test_persists_result_when_write_result_is_true(self):
        exc = ValueError("test error")
        store = ResultStore()
        state = exception_to_failed_state_sync(
            exc, result_store=store, write_result=True
        )
        assert state.is_failed()
        assert isinstance(state.data, ResultRecord)
        assert Path(state.data.metadata.storage_key).exists()

    def test_prepends_existing_message(self):
        exc = ValueError("test error")
        state = exception_to_failed_state_sync(exc, message="Context:")
        assert state.message == "Context: ValueError: test error"


class TestReturnValueToStateSync:
    @pytest.fixture
    def store(self):
        return ResultStore()

    def test_returns_single_state_unaltered(self, store):
        state = Completed(data="hello!")
        result = return_value_to_state_sync(state, store)
        assert result is state

    def test_returns_single_state_with_null_data(self, store):
        state = Completed(data=None)
        result_state = return_value_to_state_sync(state, store)
        assert result_state is state
        assert isinstance(result_state.data, ResultRecord)
        assert result_state.result() is None

    def test_returns_single_state_with_data_to_persist(self, store):
        state = Completed(data=1)
        result_state = return_value_to_state_sync(state, store, write_result=True)
        assert result_state is state
        assert isinstance(result_state.data, ResultRecord)
        assert Path(result_state.data.metadata.storage_key).exists()
        assert result_state.result() == 1

    def test_returns_persisted_result_records_unaltered(self, store):
        record = store.create_result_record(42)
        result_state = return_value_to_state_sync(record, store)
        assert result_state.data == record
        assert result_state.result() == 42

    def test_returns_single_state_unaltered_with_user_created_reference(self, store):
        result = store.create_result_record("test")
        state = Completed(data=result)
        result_state = return_value_to_state_sync(state, store)
        assert result_state is state
        assert result_state.data is state.data
        assert result_state.data == result
        assert result_state.result() == "test"

    def test_all_completed_states(self, store):
        states = [Completed(message="hi"), Completed(message="bye")]
        result_state = return_value_to_state_sync(states, store)
        assert result_state.result() == states
        assert result_state.message == "All states completed."
        assert result_state.is_completed()

    def test_some_failed_states(self, store):
        states = [
            Completed(message="hi"),
            Failed(message="bye"),
            Failed(message="err"),
        ]
        result_state = return_value_to_state_sync(states, store)
        assert result_state.result(raise_on_failure=False) == states
        assert result_state.message == "2/3 states failed."
        assert result_state.is_failed()

    def test_some_unfinal_states(self, store):
        states = [
            Completed(message="hi"),
            Running(message="bye"),
            Pending(message="err"),
        ]
        result_state = return_value_to_state_sync(states, store)
        assert result_state.result(raise_on_failure=False) == states
        assert result_state.message == "2/3 states are not final."
        assert result_state.is_failed()

    @pytest.mark.parametrize("run_identifier", ["task_run_id", "flow_run_id"])
    def test_single_state_in_future_is_processed(self, run_identifier, store):
        state = Completed(data="test", state_details={run_identifier: uuid.uuid4()})
        result_state = return_value_to_state_sync(state, store)
        assert result_state.result() == state
        assert result_state.is_completed()
        assert result_state.message == "All states completed."

    def test_non_prefect_types_return_completed_state(self, store):
        result_state = return_value_to_state_sync("foo", store)
        assert result_state.is_completed()
        assert result_state.result() == "foo"

    def test_some_cancelled_states(self, store):
        states = [Completed(message="hi"), Cancelled(message="bye")]
        result_state = return_value_to_state_sync(states, store)
        assert result_state.result(raise_on_failure=False) == states
        assert result_state.message == "1/2 states cancelled."
        assert result_state.is_cancelled()

    def test_some_paused_states(self, store):
        states = [Completed(message="hi"), Paused(message="bye")]
        result_state = return_value_to_state_sync(states, store)
        # Paused states cannot have their result retrieved
        assert result_state.message == "1/2 states paused."
        assert result_state.is_paused()
        assert isinstance(result_state.data, ResultRecord)

    def test_generator_converted_to_list(self, store):
        def gen():
            yield 1
            yield 2
            yield 3

        result_state = return_value_to_state_sync(gen(), store)
        assert result_state.is_completed()
        assert result_state.result() == [1, 2, 3]
