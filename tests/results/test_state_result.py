"""
Generic tests for `State.result`
"""

import pytest

from prefect.exceptions import UnfinishedRun
from prefect.results import UnpersistedResult
from prefect.states import State, StateType


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
