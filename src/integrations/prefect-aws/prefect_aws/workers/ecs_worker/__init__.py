"""
ECS Worker for executing flow runs as ECS tasks.
"""

from prefect_aws.workers.ecs_worker.logging import mask_sensitive_env_values
from prefect_aws.workers.ecs_worker.task_execution import create_task_run
from prefect_aws.workers.ecs_worker.utils import (
    _TAG_REGEX,
    ECS_DEFAULT_CONTAINER_NAME,
    ECS_DEFAULT_CPU,
    ECS_DEFAULT_FAMILY,
    ECS_DEFAULT_MEMORY,
    _get_container,
)
from prefect_aws.workers.ecs_worker.worker import (
    _TASK_DEFINITION_CACHE,
    ECSWorker,
    ECSJobConfiguration,
    ECSVariables,
    ECSWorkerResult,
    ECSIdentifier,
    CapacityProvider,
    parse_identifier,
)

# Re-export for backward compatibility (used by tests)
from prefect_aws.credentials import AwsCredentials
from prefect.utilities.dockerutils import get_prefect_image_name

__all__ = [
    "ECSWorker",
    "ECSJobConfiguration",
    "ECSVariables",
    "ECSWorkerResult",
    "ECSIdentifier",
    "CapacityProvider",
    # Private exports for tests
    "_TAG_REGEX",
    "_TASK_DEFINITION_CACHE",
    "ECS_DEFAULT_CONTAINER_NAME",
    "ECS_DEFAULT_CPU",
    "ECS_DEFAULT_FAMILY",
    "ECS_DEFAULT_MEMORY",
    "_get_container",
    "AwsCredentials",
    "get_prefect_image_name",
    "mask_sensitive_env_values",
    "parse_identifier",
]
