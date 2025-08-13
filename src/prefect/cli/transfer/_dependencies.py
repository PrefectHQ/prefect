"""
Dependency resolution utilities for the transfer command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._types import ResourceType

if TYPE_CHECKING:
    pass


def resolve_dependencies(resources: dict) -> list[ResourceType]:
    """
    Resolve dependencies between resource types and return the order
    in which they should be transferred.

    Dependencies:
    - Variables: No dependencies
    - Blocks: May reference other blocks
    - Work Pools: May reference blocks for infrastructure
    - Concurrency Limits: No dependencies
    - Deployments: Depend on flows, work pools, and blocks
    - Automations: Depend on deployments, work pools

    Returns a list of ResourceType in the order they should be transferred.
    """

    # Define the dependency order
    # Items with no dependencies come first
    transfer_order = [
        ResourceType.VARIABLES,  # No dependencies
        ResourceType.CONCURRENCY_LIMITS,  # No dependencies
        ResourceType.BLOCKS,  # May have internal dependencies
        ResourceType.WORK_POOLS,  # Depends on blocks
        ResourceType.DEPLOYMENTS,  # Depends on flows, work pools, blocks
        ResourceType.AUTOMATIONS,  # Depends on deployments
    ]

    # Filter to only include resource types that have data
    return [rt for rt in transfer_order if rt in resources and resources.get(rt)]


def resolve_block_dependencies(blocks: list) -> list:
    """
    Resolve dependencies between blocks.

    Some blocks reference other blocks (e.g., a Docker block might reference
    a credentials block). This function determines the order in which blocks
    should be transferred.

    Args:
        blocks: List of block documents

    Returns:
        List of blocks in dependency order
    """
    # TODO: Implement topological sort based on block references
    # For now, return blocks as-is
    return blocks


def resolve_deployment_dependencies(deployments: list, resources: dict) -> dict:
    """
    Group deployments by their dependencies.

    Returns a dictionary mapping deployments to their required resources:
    - work_pool_name: Name of the work pool (if any)
    - infrastructure_block: Block ID for infrastructure (if any)
    - storage_block: Block ID for storage (if any)
    """
    dependencies = {}

    for deployment in deployments:
        deps = {
            "work_pool_name": getattr(deployment, "work_pool_name", None),
            "infrastructure_document_id": getattr(
                deployment, "infrastructure_document_id", None
            ),
            "storage_document_id": getattr(deployment, "storage_document_id", None),
        }
        dependencies[deployment.name] = deps

    return dependencies
