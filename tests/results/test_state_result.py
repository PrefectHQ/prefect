"""
Generic tests for `State.result`
"""

import time
from unittest import mock

import pytest

import prefect.states
from prefect.exceptions import UnfinishedRun
from prefect.filesystems import LocalFileSystem, WritableFileSystem
from prefect.results import PersistedResult, PersistedResultBlob, UnpersistedResult
from prefect.serializers import JSONSerializer
from prefect.states import State, StateType
from prefect.utilities.annotations import NotSet


@pytest.mark.parametrize(
    "state_type",
    [StateType.PENDING, StateType.RUNNING, StateType.SCHEDULED, StateType.CANCELLING],
)
@pytest.mark.parametrize("raise_on_failure", [True, False])
async def test_unfinished_states_raise_on_result_retrieval(
    state_type: StateType, raise_on_failure: bool
):
    # We'll even attach a result to the state, but it shouldn't matter
    state = State(type=state_type, data=await UnpersistedResult.create("test"))

    with pytest.raises(UnfinishedRun):
        # raise_on_failure should have no effect here
        await state.result(raise_on_failure=raise_on_failure)


@pytest.mark.parametrize(
    "state_type",
    [StateType.CRASHED, StateType.COMPLETED, StateType.FAILED, StateType.CANCELLED],
)
async def test_finished_states_allow_result_retrieval(state_type: StateType):
    state = State(type=state_type, data=await UnpersistedResult.create("test"))

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
async def a_real_result(storage_block: WritableFileSystem) -> PersistedResult:
    return await PersistedResult.create(
        "test-graceful-retry",
        storage_block_id=storage_block._block_document_id,
        storage_block=storage_block,
        storage_key_fn=lambda: "test-graceful-retry-path",
        serializer=JSONSerializer(),
        defer_persistence=True,
    )


@pytest.fixture
def completed_state(a_real_result: PersistedResult) -> State[str]:
    assert a_real_result.has_cached_object()

    result_copy = a_real_result.model_copy()
    result_copy._cache = NotSet
    assert not result_copy.has_cached_object()

    return State(type=StateType.COMPLETED, data=result_copy)


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
        prefect.states.RESULT_READ_MAXIMUM_ATTEMPTS
        * prefect.states.RESULT_READ_RETRY_DELAY
    )
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
        prefect.states.RESULT_READ_MAXIMUM_ATTEMPTS
        * prefect.states.RESULT_READ_RETRY_DELAY
    )
    elapsed = time.monotonic() - now
    assert elapsed >= expected_sleep


async def test_graceful_retries_eventually_succeed_while(
    shorter_result_retries: None,
    a_real_result: PersistedResult,
    completed_state: State[str],
):
    # now write the result so it's available
    await a_real_result.write()
    expected_blob = await a_real_result._read_blob()
    assert isinstance(expected_blob, PersistedResultBlob)

    # even if it misses a couple times, it will eventually return the data
    now = time.monotonic()
    with mock.patch(
        "prefect.filesystems.LocalFileSystem.read_path",
        new=mock.AsyncMock(
            side_effect=[
                FileNotFoundError,
                TimeoutError,
                expected_blob.model_dump_json().encode(),
            ]
        ),
    ) as m:
        assert await completed_state.result() == "test-graceful-retry"

    # the loop should have failed twice, then succeeded, sleeping 0.01s per failure
    assert m.call_count == prefect.states.RESULT_READ_MAXIMUM_ATTEMPTS
    expected_sleep = 2 * prefect.states.RESULT_READ_RETRY_DELAY
    elapsed = time.monotonic() - now
    assert elapsed >= expected_sleep
