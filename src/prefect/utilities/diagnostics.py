import json
import os
from typing import Dict, Any

import prefect
import platform


def system_information() -> dict:
    """
    Get system information

    Returns:
        - dict: a dictionary containing some system information
    """
    return dict(
        system_information=dict(
            platform=platform.platform(),
            python_version=platform.python_version(),
            prefect_version=prefect.__version__,
            prefect_backend=prefect.config.backend,
        )
    )


def config_overrides(include_secret_names: bool = False) -> dict:
    """
    Get user configuration keys that differ from the default configuration. Will only
    return an indication if a key is set and differs from the defaults, values are
    *not* returned.

    Args:
        - include_secret_names (bool, optional): toggle inclusion of secret config keys
            in the output. Note that secret values are never returned, only their names
            when this is `True`. Defaults to `False`.

    Returns:
        - dict: a dictionary containing names of user configuration overrides
    """
    # Replace values with boolean signalling variable presence
    def _replace_values(data: dict) -> Dict[Any, Any]:
        if isinstance(data, dict):
            return {
                k: _replace_values(v)
                if k != "secrets" or include_secret_names
                else False
                for k, v in data.items()
            }
        return True

    # Load the default config to compare values
    default_config = dict()
    default_config_path = prefect.configuration.DEFAULT_CONFIG
    if default_config_path and os.path.isfile(default_config_path):
        default_config = prefect.configuration.load_toml(default_config_path)

    user_config = dict()  # type: ignore
    user_config_path = prefect.configuration.USER_CONFIG
    if user_config_path and os.path.isfile(
        str(prefect.configuration.interpolate_env_vars(user_config_path))
    ):
        user_config = prefect.configuration.load_toml(user_config_path)

    # Create some shorter names for fully specified imports avoiding circular
    # dependencies in the utilities
    dict_to_flatdict = prefect.utilities.collections.dict_to_flatdict
    flatdict_to_dict = prefect.utilities.collections.flatdict_to_dict

    # Drop keys from `user_config` that have values identical to `default_config`
    # converting to flat dictionaries for ease of comparison
    user_config = dict_to_flatdict(user_config)
    default_config = dict_to_flatdict(default_config)

    # Collect keys to drop in a list so we aren't dropping keys during iteration
    keys_to_drop = [
        key
        for key, val in user_config.items()
        if key in default_config and val == default_config[key]
    ]

    for key in keys_to_drop:
        user_config.pop(key)

    # Restore to a nested dictionary then replace values with bools
    user_config = flatdict_to_dict(user_config)
    user_config = _replace_values(user_config)

    return dict(config_overrides=user_config)


def environment_variables() -> dict:
    """
    Get `PREFECT__` specific environment variables

    Returns:
        - dict: a dictionary containing names of set Prefect environment variables
    """
    env_vars = list()
    for env_var, _ in os.environ.items():
        if env_var.startswith(prefect.configuration.ENV_VAR_PREFIX + "__"):
            env_vars.append(env_var)

    return dict(env_vars=env_vars)


def flow_information(flow: "prefect.Flow") -> dict:
    """
    Get flow information

    Args:
        - flow ("prefect.Flow"): the flow whose attributes to retrieve

    Returns:
        - dict: a dictionary of informative flow attributes
    """

    def _replace_values(data: dict) -> Dict[Any, Any]:
        if isinstance(data, dict):
            return {k: _replace_values(v) if v else False for k, v in data.items()}

        return True

    # Check presence of environment attributes
    if flow.environment:
        environment = {
            "type": type(flow.environment).__name__,  # type: ignore
            **_replace_values(flow.environment.__dict__),  # type: ignore
        }
    else:
        environment = False  # type: ignore

    # Check presence of run_config attributes
    if flow.run_config:
        run_config = {
            "type": type(flow.run_config).__name__,
            **_replace_values(flow.run_config.__dict__),
        }
    else:
        run_config = False  # type: ignore

    # Check presence of storage attributes
    if flow.storage:
        storage = {
            "type": type(flow.storage).__name__,
            **_replace_values(flow.storage.__dict__),
        }
    else:
        storage = False  # type: ignore

    # Check presence of a result handler
    if flow.result:
        result = {"type": type(flow.result).__name__}
    else:
        result = False  # type: ignore

    # Check presence of a schedule
    if flow.schedule:
        schedule = {"type": type(flow.schedule).__name__, **flow.schedule.__dict__}
    else:
        schedule = False  # type: ignore

    return dict(
        flow_information=dict(
            environment=environment,
            run_config=run_config,
            storage=storage,
            result=result,
            schedule=schedule,
            task_count=len(flow.tasks),
        )
    )


def diagnostic_info(
    flow: "prefect.Flow" = None, include_secret_names: bool = False
) -> str:
    """
    Get full diagnostic information

    Args:
        - flow ("prefect.Flow", optional): the flow whose attributes to retrieve. If no
            flow is provided then flow information will not be present in output.
        - include_secret_names (bool, optional): toggle output of Secret names, defaults to False.
            Note: Secret values are never returned, only their names.

    Returns:
        - str: a string representation of the full diagnostic information
    """
    aggregate_info = dict()

    aggregate_info.update(system_information())
    aggregate_info.update(config_overrides(include_secret_names))
    aggregate_info.update(environment_variables())

    if flow:
        aggregate_info.update(flow_information(flow))

    return json.dumps(aggregate_info, sort_keys=True, indent=2)
