"""
Block transfer utilities for the transfer command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prefect.cli.root import app

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import BlockDocument


async def gather_blocks(client: "PrefectClient") -> list["BlockDocument"]:
    """
    Gather all blocks from the source profile.
    """
    try:
        blocks = await client.read_block_documents()
        return blocks
    except Exception as e:
        app.console.print(f"[yellow]Warning: Could not read blocks: {e}[/yellow]")
        return []


async def transfer_blocks(
    blocks: list["BlockDocument"],
    to_client: "PrefectClient",
) -> dict[str, Any]:
    """
    Transfer blocks to the target profile.

    Returns a dictionary with succeeded, failed, and skipped blocks.
    """
    # TODO: Implement block transfer with proper dependency resolution
    # See IMPLEMENTATION_NOTES.md for details
    raise NotImplementedError(
        "Block transfer not yet implemented. "
        "Requires: block type mapping, schema mapping, and handling of block-to-block references."
    )
