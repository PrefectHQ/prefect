import json
import os
from typing import Dict, Any

import prefect
import platform


def system_information() -> dict:
    """
    Get system information

    Return:
        - dict: a dictionary containing some system information
    """
    return dict(
        system_information=dict(
            platform=platform.platform(),
            python_version=platform.python_version(),
            prefect_version=prefect.__version__,
        )
    )


def config_overrides(secrets: bool = True) -> dict:
    """
    Get user configuration overrides

    Args:
        - secrets (bool, optional): toggle output of Secret names, defaults to True.
            Note: Secret values are never returned, only their names.

    Returns:
        - dict: a dictionary containing names of user configuration overrides
    """
    # Replace values with boolean signalling variable presence
    def _replace_values(data: dict) -> Dict[Any, Any]:
        if isinstance(data, dict):
            return {
                k: _replace_values(v) if k != "secrets" or secrets else False
                for k, v in data.items()
            }
        return True

    user_config: Dict[Any, Any] = dict()
    user_config_path = prefect.configuration.USER_CONFIG
    if user_config_path and os.path.isfile(
        str(prefect.configuration.interpolate_env_vars(user_config_path))
    ):
        user_config = prefect.configuration.load_toml(user_config_path)
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
    environment: Dict[Any, Any] = dict()
    if flow.environment:
        environment = {
            "type": type(flow.environment).__name__,
        }
        environment.update(_replace_values(flow.environment.__dict__))

    # Check presence of storage attributes
    storage: Dict[Any, Any] = dict()
    if flow.storage:
        storage = {
            "type": type(flow.storage).__name__,
        }
        storage.update(_replace_values(flow.storage.__dict__))

    # Check presence of a result handler
    result_handler: Dict[Any, Any] = dict()
    if flow.result_handler:
        result_handler = {"type": type(flow.result_handler).__name__}

    # Check presence of a schedule
    schedule: Dict[Any, Any] = dict()
    if flow.schedule:
        schedule = {"type": type(flow.schedule).__name__}
        schedule.update(flow.schedule.__dict__)

    return dict(
        flow_information=dict(
            environment=environment,
            storage=storage,
            result_handler=result_handler,
            schedule=schedule,
            task_count=len(flow.tasks),
        )
    )


def diagnostic_info(flow: "prefect.Flow" = None, secrets: bool = True) -> str:
    """
    Get full diagnostic information

    Args:
        - flow ("prefect.Flow", optional): the flow whose attributes to retrieve. If no
            flow is provided then flow information will not be present in output.
        - secrets (bool, optional): toggle output of Secret names, defaults to True.
            Note: Secret values are never returned, only their names.

    Returns:
        - str: a string representation of the full diagnostic information
    """
    aggregate_info = dict()

    aggregate_info.update(system_information())
    aggregate_info.update(config_overrides(secrets))
    aggregate_info.update(environment_variables())

    if flow:
        aggregate_info.update(flow_information(flow))

    return json.dumps(aggregate_info, sort_keys=True, indent=2)
