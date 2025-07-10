"""
Task definition management for ECS worker.
"""

import copy
import json
import logging
from typing import Any, Optional, Tuple

from slugify import slugify

from prefect.client.schemas.objects import FlowRun
from prefect.utilities.dockerutils import get_prefect_image_name

from .utils import (
    ECS_DEFAULT_CONTAINER_NAME,
    ECS_DEFAULT_CPU,
    ECS_DEFAULT_FAMILY,
    ECS_DEFAULT_LAUNCH_TYPE,
    ECS_DEFAULT_MEMORY,
    ECS_POST_REGISTRATION_FIELDS,
    _container_name_from_task_definition,
    _drop_empty_keys_from_dict,
    _get_container,
)

# Internal type alias for ECS clients which are generated dynamically in botocore
_ECSClient = Any


def register_task_definition(
    logger: logging.Logger,
    ecs_client: _ECSClient,
    task_definition: dict,
) -> str:
    """
    Register a new task definition with AWS.

    Returns the ARN.
    """
    logger.info("Registering ECS task definition...")
    logger.debug(
        f"Task definition request{json.dumps(task_definition, indent=2, default=str)}"
    )

    response = ecs_client.register_task_definition(**task_definition)
    return response["taskDefinition"]["taskDefinitionArn"]


def retrieve_task_definition(
    logger: logging.Logger,
    ecs_client: _ECSClient,
    task_definition: str,
):
    """
    Retrieve an existing task definition from AWS.
    """
    if task_definition.startswith("arn:aws:ecs:"):
        logger.info(f"Retrieving ECS task definition {task_definition!r}...")
    else:
        logger.info(
            "Retrieving most recent active revision from "
            f"ECS task family {task_definition!r}..."
        )
    response = ecs_client.describe_task_definition(taskDefinition=task_definition)
    return response["taskDefinition"]


def get_or_generate_family(
    task_definition: dict[str, Any], flow_run: FlowRun, work_pool_name: str
) -> str:
    """
    Gets or generate a family for the task definition.
    """
    family = task_definition.get("family")
    if not family:
        family_prefix = f"{ECS_DEFAULT_FAMILY}_{work_pool_name}"
        if flow_run.deployment_id:
            family = f"{family_prefix}_{flow_run.deployment_id}"
        else:
            family = f"{family_prefix}_{flow_run.flow_id}"
    slugify(
        family,
        max_length=255,
        regex_pattern=r"[^a-zA-Z0-9-_]+",
    )
    return family


def prepare_task_definition(
    configuration: Any,  # ECSJobConfiguration
    region: str,
    flow_run: FlowRun,
    work_pool_name: str,
) -> dict[str, Any]:
    """
    Prepare a task definition by inferring any defaults and merging overrides.
    """
    task_definition = copy.deepcopy(configuration.task_definition)

    # Configure the Prefect runtime container
    task_definition.setdefault("containerDefinitions", [])

    # Remove empty container definitions
    task_definition["containerDefinitions"] = [
        d for d in task_definition["containerDefinitions"] if d
    ]

    container_name = configuration.container_name
    if not container_name:
        container_name = (
            _container_name_from_task_definition(task_definition)
            or ECS_DEFAULT_CONTAINER_NAME
        )

    container = _get_container(task_definition["containerDefinitions"], container_name)
    if container is None:
        if container_name != ECS_DEFAULT_CONTAINER_NAME:
            raise ValueError(
                f"Container {container_name!r} not found in task definition."
            )

        # Look for a container without a name
        for container in task_definition["containerDefinitions"]:
            if "name" not in container:
                container["name"] = container_name
                break
        else:
            container = {"name": container_name}
            task_definition["containerDefinitions"].append(container)

    # Image is required so make sure it's present
    container.setdefault("image", get_prefect_image_name())

    # Remove any keys that have been explicitly "unset"
    unset_keys = {key for key, value in configuration.env.items() if value is None}
    for item in tuple(container.get("environment", [])):
        if item["name"] in unset_keys or item["value"] is None:
            container["environment"].remove(item)

    if configuration.configure_cloudwatch_logs:
        prefix = f"prefect-logs_{work_pool_name}"
        if flow_run.deployment_id:
            prefix = f"{prefix}_{flow_run.deployment_id}"
        else:
            prefix = f"{prefix}_{flow_run.flow_id}"

        container["logConfiguration"] = {
            "logDriver": "awslogs",
            "options": {
                "awslogs-create-group": "true",
                "awslogs-group": "prefect",
                "awslogs-region": region,
                "awslogs-stream-prefix": (
                    configuration.cloudwatch_logs_prefix or prefix
                ),
                **configuration.cloudwatch_logs_options,
            },
        }

    task_definition["family"] = get_or_generate_family(
        task_definition, flow_run, work_pool_name
    )
    # CPU and memory are required in some cases, retrieve the value to use
    cpu = task_definition.get("cpu") or ECS_DEFAULT_CPU
    memory = task_definition.get("memory") or ECS_DEFAULT_MEMORY

    launch_type = configuration.task_run_request.get(
        "launchType", ECS_DEFAULT_LAUNCH_TYPE
    )

    if launch_type == "FARGATE" or launch_type == "FARGATE_SPOT":
        # Task level memory and cpu are required when using fargate
        task_definition["cpu"] = str(cpu)
        task_definition["memory"] = str(memory)

        # The FARGATE compatibility is required if it will be used as as launch type
        requires_compatibilities = task_definition.setdefault(
            "requiresCompatibilities", []
        )
        if "FARGATE" not in requires_compatibilities:
            task_definition["requiresCompatibilities"].append("FARGATE")

        # Only the 'awsvpc' network mode is supported when using FARGATE
        # However, we will not enforce that here if the user has set it
        task_definition.setdefault("networkMode", "awsvpc")

    elif launch_type == "EC2":
        # Container level memory and cpu are required when using ec2
        container.setdefault("cpu", cpu)
        container.setdefault("memory", memory)

        # Ensure set values are cast to integers
        container["cpu"] = int(container["cpu"])
        container["memory"] = int(container["memory"])

    # Ensure set values are cast to strings
    if task_definition.get("cpu"):
        task_definition["cpu"] = str(task_definition["cpu"])
    if task_definition.get("memory"):
        task_definition["memory"] = str(task_definition["memory"])

    _drop_empty_keys_from_dict(task_definition)

    return task_definition


def validate_task_definition(
    task_definition: dict,
    configuration: Any,  # ECSJobConfiguration
) -> None:
    """
    Ensure that the task definition is compatible with the configuration.

    Raises `ValueError` on incompatibility. Returns `None` on success.
    """
    launch_type = configuration.task_run_request.get(
        "launchType", ECS_DEFAULT_LAUNCH_TYPE
    )
    if (
        launch_type != "EC2"
        and "FARGATE" not in task_definition["requiresCompatibilities"]
    ):
        raise ValueError(
            "Task definition does not have 'FARGATE' in 'requiresCompatibilities'"
            f" and cannot be used with launch type {launch_type!r}"
        )

    if launch_type == "FARGATE" or launch_type == "FARGATE_SPOT":
        # Only the 'awsvpc' network mode is supported when using FARGATE
        network_mode = task_definition.get("networkMode")
        if network_mode != "awsvpc":
            raise ValueError(
                f"Found network mode {network_mode!r} which is not compatible with "
                f"launch type {launch_type!r}. Use either the 'EC2' launch "
                "type or the 'awsvpc' network mode."
            )

    if configuration.configure_cloudwatch_logs and not task_definition.get(
        "executionRoleArn"
    ):
        raise ValueError(
            "An execution role arn must be set on the task definition to use "
            "`configure_cloudwatch_logs` or `stream_logs` but no execution role "
            "was found on the task definition."
        )


def get_or_register_task_definition(
    logger: logging.Logger,
    ecs_client: _ECSClient,
    configuration: Any,  # ECSJobConfiguration
    flow_run: FlowRun,
    task_definition: dict[str, Any],
    cached_task_definition_arn: Optional[str],
) -> Tuple[str, bool]:
    """Get or register a task definition for the given flow run.

    Returns a tuple of the task definition ARN and a bool indicating if the task
    definition is newly registered.
    """
    new_task_definition_registered = False

    if cached_task_definition_arn:
        try:
            cached_task_definition = retrieve_task_definition(
                logger, ecs_client, cached_task_definition_arn
            )
            if not cached_task_definition[
                "status"
            ] == "ACTIVE" or not task_definitions_equal(
                task_definition, cached_task_definition, logger
            ):
                cached_task_definition_arn = None
        except Exception as e:
            logger.warning(
                f"Failed to retrieve task definition for cached arn {cached_task_definition_arn!r}. "
                f"Error: {e}"
            )
            cached_task_definition_arn = None

    if not cached_task_definition_arn and configuration.match_latest_revision_in_family:
        family_name = task_definition.get("family", ECS_DEFAULT_FAMILY)
        try:
            task_definition_from_family = retrieve_task_definition(
                logger, ecs_client, family_name
            )
            if task_definition_from_family and task_definitions_equal(
                task_definition, task_definition_from_family, logger
            ):
                cached_task_definition_arn = task_definition_from_family[
                    "taskDefinitionArn"
                ]
        except Exception as e:
            logger.warning(
                f"Failed to retrieve task definition for family {family_name!r}. "
                f"Error: {e}"
            )
            cached_task_definition_arn = None

    if not cached_task_definition_arn:
        task_definition_arn = register_task_definition(
            logger, ecs_client, task_definition
        )
        new_task_definition_registered = True
    else:
        task_definition_arn = cached_task_definition_arn

    return task_definition_arn, new_task_definition_registered


def task_definitions_equal(taskdef_1, taskdef_2, logger: logging.Logger) -> bool:
    """
    Compare two task definitions.

    Since one may come from the AWS API and have populated defaults, we do our best
    to homogenize the definitions without changing their meaning.
    """
    if taskdef_1 == taskdef_2:
        return True

    if taskdef_1 is None or taskdef_2 is None:
        return False

    taskdef_1 = copy.deepcopy(taskdef_1)
    taskdef_2 = copy.deepcopy(taskdef_2)

    for taskdef in (taskdef_1, taskdef_2):
        # Set defaults that AWS would set after registration
        container_definitions = taskdef.get("containerDefinitions", [])
        essential = any(
            container.get("essential") for container in container_definitions
        )
        if not essential:
            container_definitions[0].setdefault("essential", True)

        taskdef.setdefault("networkMode", "bridge")

        # Normalize ordering of lists that ECS considers unordered
        # ECS stores these in unordered data structures, so order shouldn't matter for comparison
        for container in container_definitions:
            # Sort environment variables by name for consistent comparison
            if "environment" in container:
                container["environment"] = sorted(
                    container["environment"], key=lambda x: x.get("name", "")
                )

            # Sort secrets by name for consistent comparison
            if "secrets" in container:
                container["secrets"] = sorted(
                    container["secrets"], key=lambda x: x.get("name", "")
                )

            # Sort environmentFiles by value as they don't have names
            if "environmentFiles" in container:
                container["environmentFiles"] = sorted(
                    container["environmentFiles"], key=lambda x: x.get("value", "")
                )

    _drop_empty_keys_from_dict(taskdef_1)
    _drop_empty_keys_from_dict(taskdef_2)

    # Clear fields that change on registration for comparison
    for field in ECS_POST_REGISTRATION_FIELDS:
        taskdef_1.pop(field, None)
        taskdef_2.pop(field, None)

    # Log differences between task definitions for debugging
    if taskdef_1 != taskdef_2:
        logger.debug(
            "The generated task definition and the retrieved task definition are not equal."
        )
        # Find and log differences in keys
        keys1 = set(taskdef_1.keys())
        keys2 = set(taskdef_2.keys())

        if keys1 != keys2:
            keys_only_in_1 = keys1 - keys2
            keys_only_in_2 = keys2 - keys1
            if keys_only_in_1:
                logger.debug(
                    f"Keys only in generated task definition: {keys_only_in_1}"
                )
            if keys_only_in_2:
                logger.debug(
                    f"Keys only in retrieved task definition: {keys_only_in_2}"
                )

        # Find and log differences in values for common keys
        common_keys = keys1.intersection(keys2)
        for key in common_keys:
            if taskdef_1[key] != taskdef_2[key]:
                logger.debug(f"Value differs for key '{key}':")
                logger.debug(f" Generated:  {taskdef_1[key]}")
                logger.debug(f" Retrieved: {taskdef_2[key]}")

    return taskdef_1 == taskdef_2
