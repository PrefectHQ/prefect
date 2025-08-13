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
    results = {
        "succeeded": [],
        "failed": [],
        "skipped": [],
    }

    for work_pool in work_pools:
        try:
            # Check if work pool already exists
            existing = None
            try:
                existing = await to_client.read_work_pool(work_pool.name)
            except Exception:
                # Work pool doesn't exist, we can create it
                pass

            if existing:
                results["skipped"].append(
                    {
                        "name": work_pool.name,
                        "type": work_pool.type,
                        "reason": "already exists",
                    }
                )
                continue

            # Create the work pool in the target
            await to_client.create_work_pool(
                work_pool=WorkPool(
                    name=work_pool.name,
                    type=work_pool.type,
                    description=work_pool.description,
                    base_job_template=work_pool.base_job_template,
                    is_paused=work_pool.is_paused,
                    concurrency_limit=work_pool.concurrency_limit,
                )
            )

            results["succeeded"].append(
                {
                    "name": work_pool.name,
                    "type": work_pool.type,
                }
            )

        except Exception as e:
            results["failed"].append(
                {
                    "name": work_pool.name,
                    "type": work_pool.type,
                    "error": str(e),
                }
            )

    return results
