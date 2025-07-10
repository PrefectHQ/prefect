"""
Utility functions for ECS worker.
"""

from typing import List, Optional

# Constants
ECS_DEFAULT_CONTAINER_NAME = "prefect"
ECS_DEFAULT_CPU = 1024
ECS_DEFAULT_COMMAND = "python -m prefect.engine"
ECS_DEFAULT_MEMORY = 2048
ECS_DEFAULT_LAUNCH_TYPE = "FARGATE"
ECS_DEFAULT_FAMILY = "prefect"
ECS_POST_REGISTRATION_FIELDS = [
    "compatibilities",
    "taskDefinitionArn",
    "revision",
    "status",
    "requiresAttributes",
    "registeredAt",
    "registeredBy",
    "deregisteredAt",
]

# Create task run retry settings
MAX_CREATE_TASK_RUN_ATTEMPTS = 3
CREATE_TASK_RUN_MIN_DELAY_SECONDS = 1
CREATE_TASK_RUN_MIN_DELAY_JITTER_SECONDS = 0
CREATE_TASK_RUN_MAX_DELAY_JITTER_SECONDS = 3

_TAG_REGEX = r"[^a-zA-Z0-9_./=+:@-]"


def _drop_empty_keys_from_dict(taskdef: dict):
    """
    Recursively drop keys with 'empty' values from a task definition dict.

    Mutates the task definition in place. Only supports recursion into dicts and lists.
    """
    for key, value in tuple(taskdef.items()):
        if not value:
            taskdef.pop(key)
        if isinstance(value, dict):
            _drop_empty_keys_from_dict(value)
        if isinstance(value, list) and key != "capacity_provider_strategy":
            for v in value:
                if isinstance(v, dict):
                    _drop_empty_keys_from_dict(v)


def _get_container(containers: List[dict], name: str) -> Optional[dict]:
    """
    Extract a container from a list of containers or container definitions.
    If not found, `None` is returned.
    """
    for container in containers:
        if container.get("name") == name:
            return container
    return None


def _container_name_from_task_definition(task_definition: dict) -> Optional[str]:
    """
    Attempt to infer the container name from a task definition.

    If not found, `None` is returned.
    """
    if task_definition:
        container_definitions = task_definition.get("containerDefinitions", [])
    else:
        container_definitions = []

    if _get_container(container_definitions, ECS_DEFAULT_CONTAINER_NAME):
        # Use the default container name if present
        return ECS_DEFAULT_CONTAINER_NAME
    elif container_definitions:
        # Otherwise, if there's at least one container definition try to get the
        # name from that
        return container_definitions[0].get("name")

    return None
