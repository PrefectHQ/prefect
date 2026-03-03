"""Shared transfer utilities used by both typer and cyclopts CLI implementations."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any, Callable, Sequence

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
)

if TYPE_CHECKING:
    from prefect.cli.transfer._migratable_resources import MigratableProtocol


async def collect_resources(client: Any) -> Sequence["MigratableProtocol"]:
    """Collect all resources from the source profile."""
    from prefect.cli.transfer._migratable_resources import construct_migratable_resource

    collections = await asyncio.gather(
        client.read_work_pools(),
        client.read_work_queues(),
        client.read_deployments(),
        client.read_block_documents(),
        client.read_variables(),
        client.read_global_concurrency_limits(),
        client.read_automations(),
    )

    resources = await asyncio.gather(
        *[
            construct_migratable_resource(item)
            for collection in collections
            for item in collection
        ]
    )

    return resources


async def find_root_resources(
    resources: Sequence["MigratableProtocol"],
) -> Sequence["MigratableProtocol"]:
    """Find resources that aren't dependencies of any other resource."""
    all_ids = {r.source_id for r in resources}
    dependency_ids: set[uuid.UUID] = set()

    for resource in resources:
        deps = await resource.get_dependencies()
        dependency_ids.update(d.source_id for d in deps)

    root_ids = all_ids - dependency_ids
    return (
        resources if not root_ids else [r for r in resources if r.source_id in root_ids]
    )


async def execute_transfer(dag: Any, console: Console) -> dict[uuid.UUID, Any]:
    """Execute the transfer with progress reporting."""
    total = len(dag.nodes)

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Transferring resources...", total=total)

        async def migrate_with_progress(resource: "MigratableProtocol"):
            try:
                await resource.migrate()
                progress.update(task, advance=1)
                return None
            except Exception as e:
                progress.update(task, advance=1)
                raise e

        results = await dag.execute_concurrent(
            migrate_with_progress,
            max_workers=5,
            skip_on_failure=True,
        )

    return results


def get_resource_display_name(resource: "MigratableProtocol") -> str:
    """Get a display name for a resource."""
    mappings: list[tuple[str, Callable[["MigratableProtocol"], str]]] = [
        ("source_work_pool", lambda r: f"work-pool/{r.source_work_pool.name}"),
        ("source_work_queue", lambda r: f"work-queue/{r.source_work_queue.name}"),
        ("source_deployment", lambda r: f"deployment/{r.source_deployment.name}"),
        ("source_flow", lambda r: f"flow/{r.source_flow.name}"),
        (
            "source_block_document",
            lambda r: f"block-document/{r.source_block_document.name}",
        ),
        ("source_block_type", lambda r: f"block-type/{r.source_block_type.slug}"),
        (
            "source_block_schema",
            lambda r: f"block-schema/{str(r.source_block_schema.id)[:8]}",
        ),
        ("source_variable", lambda r: f"variable/{r.source_variable.name}"),
        ("source_automation", lambda r: f"automation/{r.source_automation.name}"),
        (
            "source_global_concurrency_limit",
            lambda r: f"concurrency-limit/{r.source_global_concurrency_limit.name}",
        ),
    ]

    for attr, formatter in mappings:
        if hasattr(resource, attr):
            return formatter(resource)

    return str(resource)
