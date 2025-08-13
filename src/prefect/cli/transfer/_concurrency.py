"""
Concurrency limit transfer utilities for the transfer command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prefect.cli.root import app

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.responses import GlobalConcurrencyLimitResponse


async def gather_concurrency_limits(
    client: "PrefectClient",
) -> list["GlobalConcurrencyLimitResponse"]:
    """
    Gather all global concurrency limits from the source profile.
    """
    try:
        limits = await client.read_global_concurrency_limits()
        return limits
    except Exception as e:
        app.console.print(
            f"[yellow]Warning: Could not read concurrency limits: {e}[/yellow]"
        )
        return []


async def transfer_concurrency_limits(
    limits: list["GlobalConcurrencyLimitResponse"],
    to_client: "PrefectClient",
) -> dict[str, Any]:
    """
    Transfer global concurrency limits to the target profile.

    Returns a dictionary with succeeded, failed, and skipped limits.
    """
    results = {
        "succeeded": [],
        "failed": [],
        "skipped": [],
    }

    for limit in limits:
        try:
            # Check if limit already exists
            existing = None
            try:
                existing = await to_client.read_global_concurrency_limit_by_name(
                    limit.name
                )
            except Exception:
                # Limit doesn't exist, we can create it
                pass

            if existing:
                results["skipped"].append(
                    {
                        "name": limit.name,
                        "reason": "already exists",
                    }
                )
                continue

            # Create the limit in the target
            from prefect.client.schemas.actions import GlobalConcurrencyLimitCreate

            await to_client.create_global_concurrency_limit(
                concurrency_limit=GlobalConcurrencyLimitCreate(
                    name=limit.name,
                    limit=limit.limit,
                    active=limit.active,
                    active_slots=0,  # Start with no active slots
                    slot_decay_per_second=limit.slot_decay_per_second,
                )
            )

            results["succeeded"].append(
                {
                    "name": limit.name,
                    "limit": limit.limit,
                }
            )

        except Exception as e:
            results["failed"].append(
                {
                    "name": limit.name,
                    "error": str(e),
                }
            )

    return results
