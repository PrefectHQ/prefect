"""
Command line interface for transferring resources between profiles.
"""

from __future__ import annotations

from enum import Enum

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

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

    # Display transfer summary
    console.print("\n[bold]Transfer Summary[/bold]")
    console.print(f"  Source profile: [cyan]{from_profile}[/cyan]")
    console.print(f"  Target profile: [cyan]{to_profile}[/cyan]")
    console.print("  Resource types to transfer:")
    for resource in sorted(resources_to_transfer):
        console.print(f"    • {resource.value}")

    if exclude:
        console.print("  Excluded resource types:")
        for resource in sorted(exclude):
            console.print(f"    • {resource.value}")

    if dry_run:
        console.print("\n[yellow]DRY RUN MODE - No changes will be made[/yellow]")

    # Confirmation prompt
    if not force and not dry_run:
        if not typer.confirm("\nDo you want to proceed with the transfer?"):
            exit_with_error("Transfer cancelled.")

    # Execute transfer
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Initialize transfer orchestrator
        task = progress.add_task("Initializing transfer...", total=None)

        try:
            # Create transfer context with both profiles
            with use_profile(from_profile):
                async with get_client() as from_client:
                    # Gather resources from source
                    progress.update(
                        task, description="Gathering resources from source profile..."
                    )
                    resources = await _gather_resources(
                        from_client,
                        resources_to_transfer,
                        progress,
                    )

                    # Switch to target profile
                    with use_profile(to_profile):
                        async with get_client() as to_client:
                            # Transfer resources to target
                            progress.update(
                                task,
                                description="Transferring resources to target profile...",
                            )

                            if dry_run:
                                # In dry run mode, just display what would be transferred
                                await _preview_transfer(resources, console)
                            else:
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

    if dry_run:
        console.print("\n[green]Dry run completed successfully.[/green]")
    else:
        exit_with_success("Transfer completed successfully.")


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

    # TODO: Implement resource gathering for each type
    # This will involve calling the appropriate client methods to list resources

    if ResourceType.BLOCKS in resource_types:
        # blocks = await client.read_block_documents()
        # resources[ResourceType.BLOCKS] = blocks
        pass

    if ResourceType.DEPLOYMENTS in resource_types:
        # deployments = await client.read_deployments()
        # resources[ResourceType.DEPLOYMENTS] = deployments
        pass

    if ResourceType.WORK_POOLS in resource_types:
        # work_pools = await client.read_work_pools()
        # resources[ResourceType.WORK_POOLS] = work_pools
        pass

    if ResourceType.VARIABLES in resource_types:
        # variables = await client.read_variables()
        # resources[ResourceType.VARIABLES] = variables
        pass

    if ResourceType.CONCURRENCY_LIMITS in resource_types:
        # limits = await client.read_concurrency_limits()
        # resources[ResourceType.CONCURRENCY_LIMITS] = limits
        pass

    if ResourceType.AUTOMATIONS in resource_types:
        # Check if automations are available (Cloud only)
        # automations = await client.read_automations()
        # resources[ResourceType.AUTOMATIONS] = automations
        pass

    return resources


async def _preview_transfer(resources: dict, console: Console):
    """
    Display a preview of what would be transferred in dry run mode.
    """
    console.print("\n[bold]Resources to be transferred:[/bold]\n")

    for resource_type, items in resources.items():
        if items:
            console.print(f"[cyan]{resource_type.value}[/cyan]: {len(items)} item(s)")
            # TODO: Display more details about each resource

    if not resources:
        console.print("[yellow]No resources found to transfer.[/yellow]")


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
