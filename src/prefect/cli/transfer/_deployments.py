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
    results = {
        "succeeded": [],
        "failed": [],
        "skipped": [],
    }

    for deployment in deployments:
        try:
            # Check if deployment already exists
            existing = None
            try:
                # We need to check by flow and deployment name
                existing_deployments = await to_client.read_deployments(
                    flow_filter={"id": {"any_": [deployment.flow_id]}},
                    deployment_filter={"name": {"any_": [deployment.name]}},
                )
                if existing_deployments:
                    existing = existing_deployments[0]
            except Exception:
                # Deployment doesn't exist, we can create it
                pass

            if existing:
                results["skipped"].append(
                    {
                        "name": deployment.name,
                        "reason": "already exists",
                    }
                )
                continue

            # TODO: Create the deployment in the target
            # This is complex because deployments reference:
            # - Flows (need to be created/transferred first)
            # - Work pools (optional, should be transferred first)
            # - Infrastructure blocks (optional, should be transferred first)
            # - Storage blocks (optional, should be transferred first)

            # For now, we'll skip actual creation and mark as failed
            results["failed"].append(
                {
                    "name": deployment.name,
                    "error": "Deployment transfer not yet implemented - requires flow transfer",
                }
            )

        except Exception as e:
            results["failed"].append(
                {
                    "name": deployment.name,
                    "error": str(e),
                }
            )

    return results
