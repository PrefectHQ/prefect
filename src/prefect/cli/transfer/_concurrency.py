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
    # TODO: Implement concurrency limit transfer
    # See IMPLEMENTATION_NOTES.md for details
    raise NotImplementedError(
        "Concurrency limit transfer not yet implemented. "
        "This should be straightforward as concurrency limits have no dependencies."
    )
