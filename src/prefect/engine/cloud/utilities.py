from prefect.engine.state import State, Failed


def prepare_state_for_cloud(state: State) -> State:
    """
    Prepares a Prefect State for being sent to Cloud; this ensures that any data attributes
    are properly handled prior to being shipped off to a database.

    Args:
        - state (State): the Prefect State to prepare

    Returns:
        - State: a sanitized copy of the original state
    """
    if state.is_cached():
        state._result.store_safe_value()

    if (
        isinstance(state, Failed)
        and state.cached_inputs is not None
        and all(r.result_handler is not None for k, r in state.cached_inputs.items())
    ):  # type: ignore
        for res in state.cached_inputs.values():
            res.store_safe_value()
    elif (
        hasattr(state, "cached_inputs")
        and state.cached_inputs is not None  # type: ignore
        and not state.is_failed()
    ):
        for res in state.cached_inputs.values():  # type: ignore
            res.store_safe_value()

    return state
