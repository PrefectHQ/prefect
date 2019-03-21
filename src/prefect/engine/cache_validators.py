"""
Cache validators are functions that determine if a task's output cache
is still valid, or whether that task should be re-run; they are provided at
Task creation via the `cache_validator` keyword argument (for more information
on instantiating Tasks see the [Task documentation](../core/task.html)).

Task caches are created at Task runtime if and only if the `cache_for` keyword
argument is provided to the Task, which specifies how long the output cache will be valid for
after its creation.  Cache validators come into play when a cached Task is re-run,
and are used to determine whether to re-run the Task or use the cache.

Note that _all_ validators take into account cache expiration.

A cache validator returns `True` if the cache is still valid, and `False` otherwise.
"""
from typing import Any, Dict, Iterable

import pendulum
from toolz import curry

import prefect


def never_use(
    state: "prefect.engine.state.Cached",
    inputs: Dict[str, Any],
    parameters: Dict[str, Any],
) -> bool:
    """
    Never uses the cache.

    Args:
        - state (State): a `Success` state from the last successful Task run which contains the cache
        - inputs (dict): a `dict` of inputs which were available on the last
            successful run of the cached Task
        - parameters (dict): a `dict` of parameters which were available on the
            last successful run of the cached Task

    Returns:
        - boolean specifying whether or not the cache should be used
    """
    return False


def duration_only(
    state: "prefect.engine.state.Cached",
    inputs: Dict[str, Any],
    parameters: Dict[str, Any],
) -> bool:
    """
    Validates the cache based only on cache expiration.

    Args:
        - state (State): a `Success` state from the last successful Task run which contains the cache
        - inputs (dict): a `dict` of inputs which were available on the last
            successful run of the cached Task
        - parameters (dict): a `dict` of parameters which were available on the
            last successful run of the cached Task

    Returns:
        - boolean specifying whether or not the cache should be used
    """
    if state.cached_result_expiration is None:
        return True
    elif state.cached_result_expiration > pendulum.now("utc"):
        return True
    else:
        return False


def all_inputs(
    state: "prefect.engine.state.Cached",
    inputs: Dict[str, Any],
    parameters: Dict[str, Any],
) -> bool:
    """
    Validates the cache based on cache expiration _and_ all inputs which were provided
    on the last successful run.

    Args:
        - state (State): a `Success` state from the last successful Task run which contains the cache
        - inputs (dict): a `dict` of inputs which were available on the last
            successful run of the cached Task
        - parameters (dict): a `dict` of parameters which were available on the
            last successful run of the cached Task

    Returns:
        - boolean specifying whether or not the cache should be used
    """
    if duration_only(state, inputs, parameters) is False:
        return False
    elif state.cached_inputs == inputs:
        return True
    else:
        return False


def all_parameters(
    state: "prefect.engine.state.Cached",
    inputs: Dict[str, Any],
    parameters: Dict[str, Any],
) -> bool:
    """
    Validates the cache based on cache expiration _and_ all parameters which were provided
    on the last successful run.

    Args:
        - state (State): a `Success` state from the last successful Task run which contains the cache
        - inputs (dict): a `dict` of inputs which were available on the last
            successful run of the cached Task
        - parameters (dict): a `dict` of parameters which were available on the
            last successful run of the cached Task

    Returns:
        - boolean specifying whether or not the cache should be used
    """
    if duration_only(state, inputs, parameters) is False:
        return False
    elif state.cached_parameters == parameters:
        return True
    else:
        return False


@curry
def partial_parameters_only(
    state: "prefect.engine.state.Cached",
    inputs: Dict[str, Any],
    parameters: Dict[str, Any],
    validate_on: Iterable[str] = None,
) -> bool:
    """
    Validates the cache based on cache expiration _and_ a subset of parameters (determined by the
    `validate_on` keyword) which were provided on the last successful run.

    Args:
        - state (State): a `Success` state from the last successful Task run which contains the cache
        - inputs (dict): a `dict` of inputs which were available on the last
            successful run of the cached Task
        - parameters (dict): a `dict` of parameters which were available on the
            last successful run of the cached Task
        - validate_on (list): a `list` of strings specifying the parameter names
            to validate against

    Returns:
        - boolean specifying whether or not the cache should be used

    Example:
    ```python
    from datetime import timedelta
    import pendulum
    from prefect import Flow, Parameter, task
    from prefect.engine.cache_validators import partial_parameters_only

    @task(cache_for=timedelta(days=1),
          cache_validator=partial_parameters_only(validate_on=['nrows']))
    def daily_db_refresh(nrows, runtime):
        pass

    with Flow("My Flow") as f:
        nrows = Parameter("nrows", default=500)
        runtime = Parameter("runtime")
        db_state = daily_db_refresh(nrows, runtime)

    state1 = f.run(parameters=dict(nrows=1000, runtime=pendulum.now('utc')))

    ## the second run will use the cache contained within state1.result[db_state]
    ## even though `runtime` has changed
    state2 = f.run(parameters=dict(nrows=1000, runtime=pendulum.now('utc')),
                   task_states={result: state1.result[db_state]})
    ```
    """
    parameters = parameters or {}
    if duration_only(state, inputs, parameters) is False:
        return False
    elif validate_on is None:
        return True  # if you dont want to validate on anything, then the cache is valid
    else:
        cached = state.cached_parameters or {}
        partial_provided = {
            key: value for key, value in parameters.items() if key in validate_on
        }
        partial_needed = {
            key: value for key, value in cached.items() if key in validate_on
        }
        return partial_provided == partial_needed


@curry
def partial_inputs_only(
    state: "prefect.engine.state.Cached",
    inputs: Dict[str, Any],
    parameters: Dict[str, Any],
    validate_on: Iterable[str] = None,
) -> bool:
    """
    Validates the cache based on cache expiration _and_ a subset of inputs (determined by the
    `validate_on` keyword) which were provided on the last successful run.

    Args:
        - state (State): a `Success` state from the last successful Task run which contains the cache
        - inputs (dict): a `dict` of inputs which were available on the last
            successful run of the cached Task
        - parameters (dict): a `dict` of parameters which were available on the
            last successful run of the cached Task
        - validate_on (list): a `list` of strings specifying the input names
            to validate against

    Returns:
        - boolean specifying whether or not the cache should be used

    Example:
    ```python
    import random
    from datetime import timedelta
    from prefect import Flow, task
    from prefect.engine.cache_validators import partial_inputs_only

    @task(cache_for=timedelta(days=1),
          cache_validator=partial_inputs_only(validate_on=['x', 'y']))
    def add(x, y, as_string=False):
        if as_string:
            return '{0} + {1}'.format(x, y)
        return x + y

    @task
    def rand_bool():
        return random.random() > 0.5

    with Flow("My Flow") as f:
        ans = add(1, 2, rand_bool())

    state1 = f.run()
    ## the second run will use the cache contained within state1.result[ans]
    ## even though `rand_bool` might change
    state2 = f.run(task_states={result: state1.result[ans]})
    ```
    """
    inputs = inputs or {}
    if duration_only(state, inputs, parameters) is False:
        return False
    elif validate_on is None:
        return True  # if you dont want to validate on anything, then the cache is valid
    else:
        cached = state.cached_inputs or {}
        partial_provided = {
            key: value for key, value in inputs.items() if key in validate_on
        }
        partial_needed = {
            key: value for key, value in cached.items() if key in validate_on
        }
        return partial_provided == partial_needed
