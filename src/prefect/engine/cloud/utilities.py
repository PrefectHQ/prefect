import copy

from prefect.engine.result import NoResult
from prefect.engine.state import State


def prepare_state_for_cloud(state: State) -> State:
    """
    Prepares a Prefect State for being sent to Cloud; this ensures that any data attributes
    are properly handled prior to being shipped off to a database.

    Args:
        - state (State): the Prefect State to prepare

    Returns:
        - State: a sanitized copy of the original state
    """
    res = state._result
    cloud_state = copy.copy(state)
    cloud_state._result = res.write() if cloud_state.is_cached() else NoResult
    if (
        hasattr(cloud_state, "cached_inputs")
        and cloud_state.cached_inputs is not None  # type: ignore
    ):
        cloud_state.cached_inputs = {  # type: ignore
            k: r.write() for k, r in cloud_state.cached_inputs.items()  # type: ignore
        }
    return cloud_state
