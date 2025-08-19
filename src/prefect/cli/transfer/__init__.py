"""
Command line interface for transferring resources between profiles.
"""

from __future__ import annotations

import asyncio
from logging import Logger
from typing import TYPE_CHECKING, Any, Callable, Sequence
import uuid

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources import MigratableType
from prefect.client.orchestration import PrefectClient, get_client
from prefect.context import use_profile
from prefect.events.schemas.events import Event, Resource
from prefect.logging import get_logger
from prefect.settings import load_profiles
from prefect.events import get_events_client

from ._dag import TransferDAG

if TYPE_CHECKING:
    # we use the forward ref and defer this import because that module imports
    # a ton of schemas that we don't want to import here at module load time
    from prefect.cli.transfer._migratable_resources import MigratableProtocol

logger: Logger = get_logger(__name__)


@app.command()
async def transfer(
    from_profile: str = typer.Option(
        ..., "--from", help="Source profile to transfer resources from"
    ),
    to_profile: str = typer.Option(
        ..., "--to", help="Target profile to transfer resources to"
    ),
):
    """
    Transfer resources from one Prefect profile to another.

    Automatically handles dependencies between resources and transfers them
    in the correct order.

    \b
    Examples:
        \b
        Transfer all resources from staging to production:
        \b
        $ prefect transfer --from staging --to prod
    """
    console = Console()

    profiles = load_profiles(include_defaults=False)

    if from_profile not in profiles:
        exit_with_error(f"Source profile '{from_profile}' not found.")

    if to_profile not in profiles:
        exit_with_error(f"Target profile '{to_profile}' not found.")

    if from_profile == to_profile:
        exit_with_error("Source and target profiles must be different.")

    console.print()
    console.print(
        Panel(
            f"[bold cyan]Source:[/bold cyan] {from_profile}\n"
            f"[bold cyan]Target:[/bold cyan] {to_profile}",
            title="Transfer Configuration",
            expand=False,
            padding=(1, 2),
        )
    )

    with use_profile(from_profile):
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Collecting resources...", total=None)
            async with get_client() as client:
                from_url = client.api_url
                resources = await _collect_resources(client)

            if not resources:
                console.print("\n[yellow]No resources found to transfer.[/yellow]")
                return

            progress.update(task, description="Building dependency graph...")
            roots = await _find_root_resources(resources)
            dag = TransferDAG()
            await dag.build_from_roots(roots)

    stats = dag.get_statistics()

    if stats["has_cycles"]:
        exit_with_error("Cannot transfer resources with circular dependencies.")

    console.print()
    if is_interactive() and not typer.confirm(
        f"Transfer {stats['total_nodes']} resource(s) from '{from_profile}' to '{to_profile}'?"
    ):
        exit_with_error("Transfer cancelled.")

    console.print()
    with use_profile(to_profile):
        async with get_client() as client:
            to_url = client.api_url
            async with get_events_client() as events_client:
                transfer_id = uuid.uuid4()
                await events_client.emit(
                    event=Event(
                        event="prefect.workspace.transfer.started",
                        resource=Resource.model_validate(
                            {
                                "prefect.resource.id": f"prefect.workspace.transfer.{transfer_id}",
                                "prefect.resource.name": f"{from_profile} -> {to_profile} transfer",
                                "prefect.resource.role": "transfer",
                            }
                        ),
                        payload=dict(
                            source_profile=from_profile,
                            target_profile=to_profile,
                            source_url=str(from_url),
                            target_url=str(to_url),
                            total_resources=stats["total_nodes"],
                        ),
                    )
                )
                results = await _execute_transfer(dag, console)

                succeeded: int = 0
                failed: int = 0
                skipped: int = 0

                for result in results.values():
                    if result is None:
                        succeeded += 1
                    elif isinstance(result, TransferSkipped):
                        skipped += 1
                    else:
                        failed += 1

                await events_client.emit(
                    event=Event(
                        event="prefect.workspace.transfer.completed",
                        resource=Resource.model_validate(
                            {
                                "prefect.resource.id": f"prefect.workspace.transfer.{transfer_id}",
                                "prefect.resource.name": f"{from_profile} -> {to_profile} transfer",
                                "prefect.resource.role": "transfer",
                            }
                        ),
                        payload=dict(
                            source_profile=from_profile,
                            target_profile=to_profile,
                            source_url=str(from_url),
                            target_url=str(to_url),
                            total_resources=stats["total_nodes"],
                            succeeded=succeeded,
                            failed=failed,
                            skipped=skipped,
                        ),
                    )
                )

    _display_results(results, dag.nodes, console)


async def _collect_resources(client: PrefectClient) -> Sequence["MigratableProtocol"]:
    """Collect all resources from the source profile."""
    from ._migratable_resources import construct_migratable_resource

    resources = []

    collections: list[Sequence[MigratableType]] = await asyncio.gather(
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


async def _find_root_resources(
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


async def _execute_transfer(dag: TransferDAG, console: Console) -> dict[uuid.UUID, Any]:
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


def _get_resource_display_name(resource: "MigratableProtocol") -> str:
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


def _display_results(
    results: dict[uuid.UUID, Any],
    nodes: dict[uuid.UUID, "MigratableProtocol"],
    console: Console,
):
    """Display transfer results."""
    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []

    for node_id, result in results.items():
        resource = nodes[node_id]
        resource_name = _get_resource_display_name(resource)

        if result is None:
            succeeded.append(resource_name)
        elif isinstance(result, TransferSkipped):
            skipped.append((resource_name, str(result)))
        else:
            failed.append((resource_name, str(result)))

    if succeeded or failed or skipped:
        results_table = Table(title="Transfer Results", show_header=True)
        results_table.add_column("Resource", style="cyan")
        results_table.add_column("Status", style="white")
        results_table.add_column("Details", style="dim", no_wrap=False)

        for name in succeeded:
            results_table.add_row(name, "[green]✓ Success[/green]", "")

        for name, error in failed:
            results_table.add_row(name, "[red]✗ Failed[/red]", str(error))

        for name, reason in skipped:
            results_table.add_row(name, "[yellow]⊘ Skipped[/yellow]", reason)

        console.print()
        console.print(results_table)

    console.print()
    if failed:
        exit_with_error(
            f"Transfer completed with errors: {len(succeeded)} succeeded, "
            f"{len(failed)} failed, {len(skipped)} skipped"
        )
    elif skipped:
        exit_with_success(
            f"Transfer completed: {len(succeeded)} succeeded, {len(skipped)} skipped"
        )
    else:
        exit_with_success(
            f"Transfer completed successfully: {len(succeeded)} resource(s) transferred"
        )
