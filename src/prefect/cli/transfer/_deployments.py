"""
Deployment transfer utilities for the transfer command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prefect.cli.root import app

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.responses import DeploymentResponse


async def gather_deployments(client: "PrefectClient") -> list["DeploymentResponse"]:
    """
    Gather all deployments from the source profile.
    """
    try:
        deployments = await client.read_deployments()
        return deployments
    except Exception as e:
        app.console.print(f"[yellow]Warning: Could not read deployments: {e}[/yellow]")
        return []


async def transfer_deployments(
    deployments: list["DeploymentResponse"],
    to_client: "PrefectClient",
) -> dict[str, Any]:
    """
    Transfer deployments to the target profile.

    Note: Deployments depend on flows, work pools, and potentially blocks.
    This function assumes those dependencies have already been transferred.

    Returns a dictionary with succeeded, failed, and skipped deployments.
    """
    # TODO: Implement deployment transfer with proper handling of:
    # - Flow references (flows must exist in target)
    # - Work pool references
    # - Block references (infrastructure and storage)
    # - Schedules and parameters
    # See IMPLEMENTATION_NOTES.md for details
    raise NotImplementedError(
        "Deployment transfer not yet implemented. "
        "Requires: flow existence verification, mapping work pool and block references."
    )
