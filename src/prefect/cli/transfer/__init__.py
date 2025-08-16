"""
Command line interface for transferring resources between profiles.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.client.orchestration import get_client
from prefect.context import use_profile
from prefect.logging import get_logger
from prefect.settings import load_profiles

from ._dag import TransferDAG
from ._migratable_resources import (
    MigratableProtocol,
    construct_migratable_resource,
)

logger = get_logger(__name__)


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

    Example:
        Transfer all resources from staging to production:
            $ prefect transfer --from staging --to prod
    """
    console = Console()

    # Load and validate profiles
    profiles = load_profiles(include_defaults=False)

    if from_profile not in profiles:
        exit_with_error(f"Source profile '{from_profile}' not found.")

    if to_profile not in profiles:
        exit_with_error(f"Target profile '{to_profile}' not found.")

    if from_profile == to_profile:
        exit_with_error("Source and target profiles must be different.")

    # Create configuration panel
    config_content = f"""[bold cyan]Source:[/bold cyan] {from_profile}
[bold cyan]Target:[/bold cyan] {to_profile}"""

    config_panel = Panel(
        config_content,
        title="Transfer Configuration",
        expand=False,
        padding=(1, 2),
    )

    console.print()
    console.print(config_panel)

    # Collect resources from source profile
    with use_profile(from_profile):
        async with get_client() as client:
            resources = await _collect_resources(client, console)

        if not resources:
            console.print("\n[yellow]No resources found to transfer.[/yellow]")
            return

        # Find root resources (those that aren't dependencies of others)
        roots = await _find_root_resources(resources)

        # Build DAG
        dag = TransferDAG()
        await dag.build_from_roots(roots)

    stats = dag.get_statistics()

    if stats["has_cycles"]:
        exit_with_error("Cannot transfer resources with circular dependencies.")

    # Confirmation prompt
    console.print()
    if is_interactive() and not typer.confirm(
        f"Transfer {stats['total_nodes']} resource(s) to '{to_profile}'?"
    ):
        exit_with_error("Transfer cancelled.")

    # Execute transfer
    console.print()
    with use_profile(to_profile):
        results = await _execute_transfer(dag, console)

    # Display results
    _display_results(results, dag._nodes, console)


async def _collect_resources(client, console: Console) -> list[MigratableProtocol]:
    """Collect all resources from the source profile."""
    resources = []

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        "[progress.percentage]{task.percentage:>3.0f}%",
        console=console,
    ) as progress:
        # First, count total resources to collect
        task = progress.add_task("Counting resources...", total=None)

        # Collect ALL work pools and queues - we'll skip push/managed during migration
        work_pools = await client.read_work_pools()
        work_queues = await client.read_work_queues()
        deployments = await client.read_deployments()
        block_documents = await client.read_block_documents()
        variables = await client.read_variables()
        limits = await client.read_global_concurrency_limits()

        automations = await client.read_automations()

        total = (
            len(work_pools)
            + len(work_queues)
            + len(deployments)
            + len(block_documents)
            + len(variables)
            + len(limits)
            + len(automations)
        )

        # Now collect with progress
        progress.update(task, description="Discovering resources...", total=total)

        for pool in work_pools:
            resources.append(await construct_migratable_resource(pool))
            progress.advance(task)

        for queue in work_queues:
            resources.append(await construct_migratable_resource(queue))
            progress.advance(task)

        for deployment in deployments:
            resources.append(await construct_migratable_resource(deployment))
            progress.advance(task)

        # Flows are pulled in as dependencies of deployments, not collected directly

        for doc in block_documents:
            resources.append(await construct_migratable_resource(doc))
            progress.advance(task)

        for var in variables:
            resources.append(await construct_migratable_resource(var))
            progress.advance(task)

        for limit in limits:
            resources.append(await construct_migratable_resource(limit))
            progress.advance(task)

        for automation in automations:
            resources.append(await construct_migratable_resource(automation))
            progress.advance(task)

    return resources


async def _find_root_resources(
    resources: list[MigratableProtocol],
) -> list[MigratableProtocol]:
    """Find resources that aren't dependencies of any other resource."""
    all_ids = {r.source_id for r in resources}
    dependency_ids = set()

    # Collect all dependency IDs
    for resource in resources:
        deps = await resource.get_dependencies()
        dependency_ids.update(d.source_id for d in deps)

    # Roots are resources that aren't dependencies
    root_ids = all_ids - dependency_ids

    # If no roots found (circular deps), just return all resources
    # The DAG will detect the cycle
    if not root_ids:
        return resources

    return [r for r in resources if r.source_id in root_ids]


async def _execute_transfer(dag: TransferDAG, console: Console) -> dict:
    """Execute the transfer with progress reporting."""
    results = {}
    completed = 0
    total = len(dag._nodes)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        "[progress.percentage]{task.percentage:>3.0f}%",
        console=console,
    ) as progress:
        task = progress.add_task("Transferring resources...", total=total)

        async def migrate_with_progress(resource: MigratableProtocol):
            nonlocal completed
            resource_name = _get_resource_display_name(resource)
            progress.update(
                task,
                description=f"Transferring {resource_name}...",
            )

            try:
                await resource.migrate()
                completed += 1
                progress.update(
                    task,
                    advance=1,
                )
                return None  # Success
            except Exception as e:
                completed += 1
                progress.update(
                    task,
                    advance=1,
                )
                raise e

        # Execute DAG
        results = await dag.execute_concurrent(
            migrate_with_progress,
            max_workers=5,  # Limit concurrency to avoid overwhelming the API
            skip_on_failure=True,
        )

    return results


def _get_resource_display_name(resource: MigratableProtocol) -> str:
    """Get a display name for a resource."""
    # Try to get a name attribute from the source object
    if hasattr(resource, "source_work_pool"):
        return f"work-pool/{resource.source_work_pool.name}"
    elif hasattr(resource, "source_work_queue"):
        return f"work-queue/{resource.source_work_queue.name}"
    elif hasattr(resource, "source_deployment"):
        return f"deployment/{resource.source_deployment.name}"
    elif hasattr(resource, "source_flow"):
        return f"flow/{resource.source_flow.name}"
    elif hasattr(resource, "source_block_document"):
        return f"block/{resource.source_block_document.name}"
    elif hasattr(resource, "source_block_type"):
        return f"{resource.source_block_type.slug} (type)"
    elif hasattr(resource, "source_block_schema"):
        # Show a shortened version of the schema ID
        schema_id = str(resource.source_block_schema.id)
        return f"schema:{schema_id[:8]}"
    elif hasattr(resource, "source_variable"):
        return f"variable/{resource.source_variable.name}"
    elif hasattr(resource, "source_automation"):
        return f"automation/{resource.source_automation.name}"
    elif hasattr(resource, "source_global_concurrency_limit"):
        return f"concurrency-limit/{resource.source_global_concurrency_limit.name}"
    else:
        return str(resource)


def _display_results(results: dict, nodes: dict, console: Console):
    """Display transfer results."""
    succeeded = []
    failed = []
    skipped = []

    for node_id, result in results.items():
        resource = nodes[node_id]
        resource_name = _get_resource_display_name(resource)

        if result is None:
            succeeded.append(resource_name)
        elif isinstance(result, RuntimeError) and "Skipped" in str(result):
            skipped.append((resource_name, str(result)))
        else:
            failed.append((resource_name, str(result)))

    # Create results table
    if succeeded or failed or skipped:
        results_table = Table(title="Transfer Results", show_header=True)
        results_table.add_column("Resource", style="cyan")
        results_table.add_column("Status", style="white")
        results_table.add_column("Details", style="dim")

        for name in succeeded:
            results_table.add_row(name, "[green]✓ Success[/green]", "")

        for name, error in failed:
            results_table.add_row(name, "[red]✗ Failed[/red]", str(error)[:50])

        for name, reason in skipped:
            results_table.add_row(name, "[yellow]⊘ Skipped[/yellow]", reason[:50])

        console.print()
        console.print(results_table)

    # Summary
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
