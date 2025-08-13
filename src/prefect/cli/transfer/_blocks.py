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
    results = {
        "succeeded": [],
        "failed": [],
        "skipped": [],
    }

    for block in blocks:
        try:
            # Check if block already exists
            existing = None
            try:
                existing = await to_client.read_block_document_by_name(
                    block.name,
                    block.block_type.slug,
                    include_secrets=False,
                )
            except Exception:
                # Block doesn't exist, we can create it
                pass

            if existing:
                results["skipped"].append(
                    {
                        "name": block.name,
                        "type": block.block_type.slug,
                        "reason": "already exists",
                    }
                )
                continue

            # Create the block in the target
            # Note: We need to handle block data carefully, especially references
            block_data = block.data.copy() if block.data else {}

            # TODO: Handle block references (blocks that reference other blocks)
            # TODO: Handle encrypted secrets properly

            await to_client.create_block_document(
                block_document=BlockDocument(
                    name=block.name,
                    data=block_data,
                    block_type_id=block.block_type.id,
                    block_schema_id=block.block_schema_id,
                )
            )

            results["succeeded"].append(
                {
                    "name": block.name,
                    "type": block.block_type.slug,
                }
            )

        except Exception as e:
            results["failed"].append(
                {
                    "name": block.name,
                    "type": block.block_type.slug,
                    "error": str(e),
                }
            )

    return results
