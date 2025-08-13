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

    # First, ensure all block types are available in the target
    block_type_map = {}  # Maps source block type ID to target block type ID
    block_schema_map = {}  # Maps source schema ID to target schema ID

    for block in blocks:
        if block.block_type.id not in block_type_map:
            try:
                # Try to get the block type in the target by slug
                target_block_type = await to_client.read_block_type_by_slug(
                    block.block_type.slug
                )
                block_type_map[block.block_type.id] = target_block_type.id

                # Get the most recent schema for this block type in the target
                target_schema = (
                    await to_client.get_most_recent_block_schema_for_block_type(
                        target_block_type.id
                    )
                )
                if target_schema and block.block_schema_id:
                    block_schema_map[block.block_schema_id] = target_schema.id

            except Exception:
                # Block type doesn't exist in target - we can't transfer this block
                app.console.print(
                    f"[yellow]Warning: Block type '{block.block_type.slug}' not found in target. "
                    f"Blocks of this type will be skipped.[/yellow]"
                )
                block_type_map[block.block_type.id] = None

    for block in blocks:
        try:
            # Skip if block type doesn't exist in target
            if block_type_map.get(block.block_type.id) is None:
                results["skipped"].append(
                    {
                        "name": block.name,
                        "type": block.block_type.slug,
                        "reason": "block type not available in target",
                    }
                )
                continue

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

            # Create the block in the target with mapped IDs
            block_data = block.data.copy() if block.data else {}

            # TODO: Handle block references (blocks that reference other blocks)
            # TODO: Handle encrypted secrets properly

            await to_client.create_block_document(
                block_document=BlockDocument(
                    name=block.name,
                    data=block_data,
                    block_type_id=block_type_map[block.block_type.id],
                    block_schema_id=block_schema_map.get(block.block_schema_id),
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
