from prefect.client.schemas import State
from prefect.orion.schemas.states import StateType


def test_handles_generator_as_data():
    state = State(type=StateType.COMPLETED, data=(i for i in range(5)))
    assert list(state.data) == [0, 1, 2, 3, 4]
