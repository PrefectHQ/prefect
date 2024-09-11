"""
Generic tests for `State.result`
"""

import time
from unittest import mock

import pytest

import prefect.states
from prefect.exceptions import UnfinishedRun
from prefect.filesystems import LocalFileSystem, WritableFileSystem
from prefect.results import (
    ResultRecord,
    ResultRecordMetadata,
    ResultStore,
)
from prefect.serializers import JSONSerializer
from prefect.states import State, StateType


@pytest.mark.parametrize(
    "state_type",
    [StateType.PENDING, StateType.RUNNING, StateType.SCHEDULED, StateType.CANCELLING],
)
@pytest.mark.parametrize("raise_on_failure", [True, False])
async def test_unfinished_states_raise_on_result_retrieval(
    state_type: StateType, raise_on_failure: bool
):
    state = State(type=state_type)

    with pytest.raises(UnfinishedRun):
        # raise_on_failure should have no effect here
        await state.result(raise_on_failure=raise_on_failure)


@pytest.mark.parametrize(
    "state_type",
    [StateType.CRASHED, StateType.COMPLETED, StateType.FAILED, StateType.CANCELLED],
)
async def test_finished_states_allow_result_retrieval(state_type: StateType):
    store = ResultStore()
    state = State(type=state_type, data=store.create_result_record("test"))

    assert await state.result(raise_on_failure=False) == "test"


@pytest.fixture
def shorter_result_retries(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(prefect.states, "RESULT_READ_MAXIMUM_ATTEMPTS", 3)
    monkeypatch.setattr(prefect.states, "RESULT_READ_RETRY_DELAY", 0.01)


@pytest.fixture
async def storage_block(tmp_path):
    block = LocalFileSystem(basepath=tmp_path)
    await block._save(is_anonymous=True)
    return block


@pytest.fixture
def store(storage_block: WritableFileSystem) -> ResultStore:
    return ResultStore(
        result_storage=storage_block,
        serializer=JSONSerializer(),
        storage_key_fn=lambda: "test-graceful-retry-path",
    )


@pytest.fixture
async def a_real_result(store) -> ResultRecord:
    return store.create_result_record(
        "test-graceful-retry",
    )


@pytest.fixture
def completed_state(a_real_result: ResultRecord) -> State[str]:
    return State(type=StateType.COMPLETED, data=a_real_result.metadata)


async def test_graceful_retries_are_finite_while_retrieving_missing_results(
    shorter_result_retries: None,
    completed_state: State[str],
):
    now = time.monotonic()

    # it should raise if the result has not been written
    with pytest.raises(ValueError, match="does not exist"):
        await completed_state.result()

    # it should have taken ~3 retries for this to raise
    expected_sleep = (
        prefect.states.RESULT_READ_MAXIMUM_ATTEMPTS - 1
    ) * prefect.states.RESULT_READ_RETRY_DELAY
    elapsed = time.monotonic() - now
    assert elapsed >= expected_sleep


async def test_graceful_retries_reraise_last_error_while_retrieving_missing_results(
    shorter_result_retries: None,
    completed_state: State[str],
):
    # if it strikes out 3 times, we should re-raise
    now = time.monotonic()
    with pytest.raises(FileNotFoundError):
        with mock.patch(
            "prefect.filesystems.LocalFileSystem.read_path",
            new=mock.AsyncMock(
                side_effect=[
                    OSError,
                    TimeoutError,
                    FileNotFoundError,
                ]
            ),
        ) as m:
            await completed_state.result()

    # the loop should have failed three times, sleeping 0.01s per error
    assert m.call_count == prefect.states.RESULT_READ_MAXIMUM_ATTEMPTS
    expected_sleep = (
        prefect.states.RESULT_READ_MAXIMUM_ATTEMPTS - 1
    ) * prefect.states.RESULT_READ_RETRY_DELAY
    elapsed = time.monotonic() - now
    assert elapsed >= expected_sleep


async def test_graceful_retries_eventually_succeed_while(
    shorter_result_retries: None,
    a_real_result: ResultRecord,
    completed_state: State[str],
    store: ResultStore,
):
    # now write the result so it's available
    await store.apersist_result_record(a_real_result)
    expected_record = ResultRecord(
        result="test-graceful-retry",
        metadata=ResultRecordMetadata(
            storage_key=a_real_result.metadata.storage_key,
            expiration=a_real_result.metadata.expiration,
            serializer=JSONSerializer(),
        ),
    )

    # even if it misses a couple times, it will eventually return the data
    now = time.monotonic()
    with mock.patch(
        "prefect.filesystems.LocalFileSystem.read_path",
        new=mock.AsyncMock(
            side_effect=[
                FileNotFoundError,
                TimeoutError,
                expected_record.serialize(),
            ]
        ),
    ) as m:
        assert await completed_state.result() == "test-graceful-retry"

    # the loop should have failed twice, then succeeded, sleeping 0.01s per failure
    assert m.call_count == prefect.states.RESULT_READ_MAXIMUM_ATTEMPTS
    expected_sleep = 2 * prefect.states.RESULT_READ_RETRY_DELAY
    elapsed = time.monotonic() - now
    assert elapsed >= expected_sleep
