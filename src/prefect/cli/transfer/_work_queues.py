"""
Work queue transfer utilities for the transfer command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prefect.cli.root import app

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import WorkQueue


async def gather_work_queues(client: "PrefectClient") -> list["WorkQueue"]:
    """
    Gather all work queues from the source profile.

    Note: Work queues are associated with work pools, so we need to
    gather them from all work pools.
    """
    try:
        work_queues = []
        work_pools = await client.read_work_pools()

        for work_pool in work_pools:
            # Get work queues for this work pool
            pool_queues = await client.read_work_queues(work_pool_name=work_pool.name)
            work_queues.extend(pool_queues)

        return work_queues
    except Exception as e:
        app.console.print(f"[yellow]Warning: Could not read work queues: {e}[/yellow]")
        return []


async def transfer_work_queues(
    work_queues: list["WorkQueue"],
    to_client: "PrefectClient",
) -> dict[str, Any]:
    """
    Transfer work queues to the target profile.

    Note: Work queues belong to work pools, so work pools must be
    transferred first.

    Returns a dictionary with succeeded, failed, and skipped work queues.
    """
    # TODO: Implement work queue transfer with proper handling of:
    # - Work pool parent relationship
    # - Priority ordering
    # - Concurrency limits
    # See IMPLEMENTATION_NOTES.md for details
    raise NotImplementedError(
        "Work queue transfer not yet implemented. "
        "Requires: work pools to be transferred first, maintaining parent-child relationships."
    )
