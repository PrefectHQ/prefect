"""
Shared types for the transfer command.
"""

from enum import Enum


class ResourceType(str, Enum):
    """Supported resource types for transfer operations."""

    BLOCKS = "blocks"
    DEPLOYMENTS = "deployments"
    WORK_POOLS = "work-pools"
    VARIABLES = "variables"
    CONCURRENCY_LIMITS = "concurrency-limits"
    AUTOMATIONS = "automations"
