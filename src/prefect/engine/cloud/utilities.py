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
    if cloud_state.is_cached():
        cloud_state._result.store_safe_value()
    else:
        cloud_state._result = NoResult

    if (
        hasattr(cloud_state, "cached_inputs")
        and cloud_state.cached_inputs is not None  # type: ignore
    ):
        for res in cloud_state.cached_inputs.values():  # type: ignore
            res.store_safe_value()
    return cloud_state
