"""
Command line interface for transferring resources between profiles.
"""

from __future__ import annotations

from enum import Enum

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client.orchestration import get_client
from prefect.context import use_profile
from prefect.settings import load_profiles


class ResourceType(str, Enum):
    """Supported resource types for transfer operations."""

    BLOCKS = "blocks"
    DEPLOYMENTS = "deployments"
    WORK_POOLS = "work-pools"
    VARIABLES = "variables"
    CONCURRENCY_LIMITS = "concurrency-limits"
    AUTOMATIONS = "automations"


@app.command()
async def transfer(
    from_profile: str = typer.Option(
        ..., "--from", help="Source profile to transfer resources from"
    ),
    to_profile: str = typer.Option(
        ..., "--to", help="Target profile to transfer resources to"
    ),
    exclude: list[ResourceType] = typer.Option(
        [],
        "--exclude",
        help="Resource types to exclude from transfer",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview what would be transferred without making changes",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompts",
    ),
):
    """
    Transfer resources from one Prefect profile to another.

    By default, all supported resource types are transferred. Use --exclude
    to omit specific resource types.

    Examples:
        Transfer all resources from staging to production:
            $ prefect transfer --from staging --to prod

        Transfer everything except blocks and deployments:
            $ prefect transfer --from staging --to prod --exclude blocks --exclude deployments

        Preview transfer without making changes:
            $ prefect transfer --from staging --to prod --dry-run
    """
    console = app.console

    # Load and validate profiles
    profiles = load_profiles(include_defaults=False)

    if from_profile not in profiles:
        exit_with_error(f"Source profile '{from_profile}' not found.")

    if to_profile not in profiles:
        exit_with_error(f"Target profile '{to_profile}' not found.")

    if from_profile == to_profile:
        exit_with_error("Source and target profiles must be different.")

    # Determine which resource types to transfer
    all_resources = set(ResourceType)
    resources_to_transfer = all_resources - set(exclude)

    if not resources_to_transfer:
        exit_with_error("All resource types have been excluded. Nothing to transfer.")

    # Create a nice summary table
    summary_table = Table(title="Transfer Configuration", show_header=False)
    summary_table.add_column(style="bold cyan")
    summary_table.add_column()

    summary_table.add_row("Source Profile", from_profile)
    summary_table.add_row("Target Profile", to_profile)

    # Format resource types
    transfer_list = ", ".join(sorted(r.value for r in resources_to_transfer))
    summary_table.add_row("Resources to Transfer", transfer_list)

    if exclude:
        exclude_list = ", ".join(sorted(r.value for r in exclude))
        summary_table.add_row("Excluded Resources", exclude_list)

    if dry_run:
        summary_table.add_row(
            "Mode", "[yellow]DRY RUN - No changes will be made[/yellow]"
        )

    console.print()
    console.print(summary_table)
    console.print()

    # First gather resources to show what will be transferred
    console.print("Analyzing source profile...")

    with use_profile(from_profile):
        async with get_client() as from_client:
            resources = await _gather_resources(
                from_client,
                resources_to_transfer,
                Progress(),  # Silent progress for gathering
            )

    # Show resource counts
    _display_resource_summary(resources, console)

    if dry_run:
        console.print("\n[yellow]DRY RUN MODE - No changes will be made[/yellow]")
        console.print("\nResources that would be transferred:")
        await _preview_transfer(resources, console)
        console.print("\n[green]Dry run completed successfully.[/green]")
        return

    # Confirmation prompt with resource counts visible
    if not force:
        total_count = sum(len(items) for items in resources.values())
        if total_count == 0:
            console.print("\n[yellow]No resources found to transfer.[/yellow]")
            return

        if not typer.confirm(f"\nDo you want to transfer {total_count} resource(s)?"):
            exit_with_error("Transfer cancelled.")

    # Execute actual transfer
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Transferring resources...", total=None)

        try:
            with use_profile(to_profile):
                async with get_client() as to_client:
                    results = await _execute_transfer(
                        resources,
                        to_client,
                        progress,
                    )

                    # Display results
                    _display_transfer_results(results, console)

        except Exception as e:
            exit_with_error(f"Transfer failed: {e}")

        finally:
            progress.stop()

    exit_with_success("Transfer completed successfully.")


def _display_resource_summary(resources: dict, console: Console):
    """Display a summary table of resources found."""
    if not any(resources.values()):
        return

    summary = Table(title="Resources Found", show_header=True)
    summary.add_column("Resource Type", style="cyan")
    summary.add_column("Count", justify="right", style="green")

    total = 0
    for resource_type, items in sorted(resources.items()):
        if items:
            count = len(items)
            total += count
            summary.add_row(resource_type.value.title(), str(count))

    if total > 0:
        summary.add_section()
        summary.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")

    console.print(summary)


async def _gather_resources(
    client,
    resource_types: set[ResourceType],
    progress: Progress,
) -> dict:
    """
    Gather resources from the source profile.

    Returns a dictionary mapping resource types to lists of resource objects.
    """
    resources = {}

    if ResourceType.BLOCKS in resource_types:
        try:
            blocks = await client.read_block_documents()
            resources[ResourceType.BLOCKS] = blocks
        except Exception as e:
            # Log but don't fail - some resources might not be available
            app.console.print(f"[yellow]Warning: Could not read blocks: {e}[/yellow]")
            resources[ResourceType.BLOCKS] = []

    if ResourceType.VARIABLES in resource_types:
        try:
            variables = await client.read_variables()
            resources[ResourceType.VARIABLES] = variables
        except Exception as e:
            app.console.print(
                f"[yellow]Warning: Could not read variables: {e}[/yellow]"
            )
            resources[ResourceType.VARIABLES] = []

    if ResourceType.DEPLOYMENTS in resource_types:
        try:
            deployments = await client.read_deployments()
            resources[ResourceType.DEPLOYMENTS] = deployments
        except Exception as e:
            app.console.print(
                f"[yellow]Warning: Could not read deployments: {e}[/yellow]"
            )
            resources[ResourceType.DEPLOYMENTS] = []

    if ResourceType.WORK_POOLS in resource_types:
        try:
            work_pools = await client.read_work_pools()
            resources[ResourceType.WORK_POOLS] = work_pools
        except Exception as e:
            app.console.print(
                f"[yellow]Warning: Could not read work pools: {e}[/yellow]"
            )
            resources[ResourceType.WORK_POOLS] = []

    if ResourceType.CONCURRENCY_LIMITS in resource_types:
        try:
            # Try global concurrency limits
            limits = await client.read_global_concurrency_limits()
            resources[ResourceType.CONCURRENCY_LIMITS] = limits
        except Exception as e:
            app.console.print(
                f"[yellow]Warning: Could not read concurrency limits: {e}[/yellow]"
            )
            resources[ResourceType.CONCURRENCY_LIMITS] = []

    if ResourceType.AUTOMATIONS in resource_types:
        # Automations are Cloud-only - we'll skip for now
        # TODO: Implement when Cloud API is available
        resources[ResourceType.AUTOMATIONS] = []

    return resources


async def _preview_transfer(resources: dict, console: Console):
    """
    Display a detailed preview of what would be transferred.
    """
    for resource_type, items in sorted(resources.items()):
        if not items:
            continue

        # Create a panel for each resource type
        content = []
        for i, item in enumerate(items[:5]):  # Show up to 5 examples
            if resource_type == ResourceType.BLOCKS:
                name = getattr(item, "name", "unknown")
                block_type = (
                    getattr(item.block_type, "slug", "unknown")
                    if hasattr(item, "block_type")
                    else "unknown"
                )
                content.append(f"• {name} [dim]({block_type})[/dim]")
            elif resource_type == ResourceType.VARIABLES:
                name = getattr(item, "name", "unknown")
                value = getattr(item, "value", "unknown")
                # Truncate long values
                if isinstance(value, str) and len(value) > 50:
                    value = value[:47] + "..."
                content.append(f"• {name} = [dim]{value}[/dim]")
            elif resource_type == ResourceType.DEPLOYMENTS:
                name = getattr(item, "name", "unknown")
                content.append(f"• {name}")
            elif resource_type == ResourceType.WORK_POOLS:
                name = getattr(item, "name", "unknown")
                work_pool_type = getattr(item, "type", "unknown")
                content.append(f"• {name} [dim]({work_pool_type})[/dim]")
            elif resource_type == ResourceType.CONCURRENCY_LIMITS:
                name = getattr(item, "name", "unknown")
                limit = getattr(item, "limit", "unknown")
                content.append(f"• {name} [dim](limit: {limit})[/dim]")

        if len(items) > 5:
            content.append(f"[dim]... and {len(items) - 5} more[/dim]")

        panel_content = "\n".join(content) if content else "[dim]None[/dim]"
        panel = Panel(
            panel_content,
            title=f"[bold cyan]{resource_type.value.title()}[/bold cyan] ({len(items)} items)",
            expand=False,
        )
        console.print(panel)


async def _execute_transfer(
    resources: dict,
    to_client,
    progress: Progress,
) -> dict:
    """
    Execute the actual transfer of resources to the target profile.

    Returns a dictionary with transfer results and statistics.
    """
    results = {
        "succeeded": {},
        "failed": {},
        "skipped": {},
    }

    # TODO: Implement actual transfer logic for each resource type
    # This will involve:
    # 1. Checking for conflicts/duplicates
    # 2. Resolving dependencies
    # 3. Creating resources in the target profile
    # 4. Handling errors gracefully

    return results


def _display_transfer_results(results: dict, console: Console):
    """
    Display a summary of the transfer results.
    """
    console.print("\n[bold]Transfer Results:[/bold]\n")

    # Display success counts
    total_succeeded = sum(len(items) for items in results["succeeded"].values())
    if total_succeeded > 0:
        console.print(
            f"[green]✓ Successfully transferred: {total_succeeded} resource(s)[/green]"
        )

    # Display failure counts
    total_failed = sum(len(items) for items in results["failed"].values())
    if total_failed > 0:
        console.print(f"[red]✗ Failed to transfer: {total_failed} resource(s)[/red]")

    # Display skipped counts
    total_skipped = sum(len(items) for items in results["skipped"].values())
    if total_skipped > 0:
        console.print(
            f"[yellow]⊝ Skipped (already exists): {total_skipped} resource(s)[/yellow]"
        )

    # TODO: Display detailed breakdown by resource type if needed
