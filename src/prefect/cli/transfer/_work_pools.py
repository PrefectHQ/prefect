"""
Work pool transfer utilities for the transfer command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prefect.cli.root import app

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import WorkPool


async def gather_work_pools(client: "PrefectClient") -> list["WorkPool"]:
    """
    Gather all work pools from the source profile.
    """
    try:
        work_pools = await client.read_work_pools()
        return work_pools
    except Exception as e:
        app.console.print(f"[yellow]Warning: Could not read work pools: {e}[/yellow]")
        return []


async def transfer_work_pools(
    work_pools: list["WorkPool"],
    to_client: "PrefectClient",
) -> dict[str, Any]:
    """
    Transfer work pools to the target profile.

    Note: Work pools may reference infrastructure blocks for their base job template.

    Returns a dictionary with succeeded, failed, and skipped work pools.
    """
    # TODO: Implement work pool transfer with proper handling of:
    # - Block references in job templates
    # - Work queues associated with pools
    # See IMPLEMENTATION_NOTES.md for details
    raise NotImplementedError(
        "Work pool transfer not yet implemented. "
        "Requires: mapping block references in job templates and transferring associated work queues."
    )
