"""
Command line interface for transferring resources between profiles.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client.orchestration import get_client
from prefect.context import use_profile
from prefect.settings import load_profiles

from ._types import ResourceType


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
    from ._blocks import gather_blocks, transfer_blocks
    from ._concurrency import gather_concurrency_limits, transfer_concurrency_limits
    from ._deployments import gather_deployments, transfer_deployments
    from ._utils import (
        display_resource_summary,
        display_transfer_results,
        preview_transfer,
    )
    from ._variables import gather_variables, transfer_variables
    from ._work_pools import gather_work_pools, transfer_work_pools

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

    # Create configuration panel
    config_content = f"""[bold cyan]Source:[/bold cyan] {from_profile}
[bold cyan]Target:[/bold cyan] {to_profile}"""

    if exclude:
        included = sorted(r.value for r in resources_to_transfer)
        excluded = sorted(r.value for r in exclude)
        config_content += f"\n[bold cyan]Including:[/bold cyan] {', '.join(included)}"
        config_content += f"\n[bold cyan]Excluding:[/bold cyan] {', '.join(excluded)}"

    if dry_run:
        title = "[yellow]Transfer Configuration (Dry Run)[/yellow]"
    else:
        title = "Transfer Configuration"

    config_panel = Panel(
        config_content,
        title=title,
        expand=False,
        padding=(1, 2),
    )

    console.print()
    console.print(config_panel)

    # First gather resources to show what will be transferred
    console.print("\n[dim]Analyzing source profile...[/dim]\n")

    with use_profile(from_profile):
        async with get_client() as from_client:
            resources = await _gather_resources(
                from_client,
                resources_to_transfer,
            )

    # Show resource counts
    display_resource_summary(resources, console)

    if dry_run:
        console.print()
        await preview_transfer(resources, console)
        console.print("\n[green]Dry run completed successfully[/green]")
        return

    # Confirmation prompt with resource counts visible
    if not force:
        total_count = sum(len(items) for items in resources.values())
        if total_count == 0:
            console.print("\n[yellow]No resources found to transfer.[/yellow]")
            return

        if not typer.confirm(
            f"\nDo you want to transfer {total_count} resource(s) to {to_profile!r}?"
        ):
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

        except Exception as e:
            exit_with_error(f"Transfer failed: {e}")

        finally:
            progress.stop()

    # Display results after progress is stopped
    display_transfer_results(results, console)

    # Determine exit status based on results
    total_succeeded = sum(len(items) for items in results["succeeded"].values())
    total_failed = sum(len(items) for items in results["failed"].values())
    total_skipped = sum(len(items) for items in results["skipped"].values())

    if total_failed > 0:
        exit_with_error(
            f"Transfer completed with errors: {total_succeeded} succeeded, {total_failed} failed, {total_skipped} skipped"
        )
    elif total_skipped > 0:
        exit_with_success(
            f"Transfer completed: {total_succeeded} succeeded, {total_skipped} already existed"
        )
    else:
        exit_with_success(
            f"Transfer completed successfully: {total_succeeded} resource(s) transferred"
        )


async def _gather_resources(
    client,
    resource_types: set[ResourceType],
) -> dict:
    """
    Gather resources from the source profile.

    Returns a dictionary mapping resource types to lists of resource objects.
    """
    from ._blocks import gather_blocks
    from ._concurrency import gather_concurrency_limits
    from ._deployments import gather_deployments
    from ._variables import gather_variables
    from ._work_pools import gather_work_pools

    resources = {}

    if ResourceType.BLOCKS in resource_types:
        resources[ResourceType.BLOCKS] = await gather_blocks(client)

    if ResourceType.VARIABLES in resource_types:
        resources[ResourceType.VARIABLES] = await gather_variables(client)

    if ResourceType.DEPLOYMENTS in resource_types:
        resources[ResourceType.DEPLOYMENTS] = await gather_deployments(client)

    if ResourceType.WORK_POOLS in resource_types:
        resources[ResourceType.WORK_POOLS] = await gather_work_pools(client)

    if ResourceType.CONCURRENCY_LIMITS in resource_types:
        resources[ResourceType.CONCURRENCY_LIMITS] = await gather_concurrency_limits(
            client
        )

    if ResourceType.AUTOMATIONS in resource_types:
        # Automations are Cloud-only - we'll skip for now
        # TODO: Implement when Cloud API is available
        resources[ResourceType.AUTOMATIONS] = []

    return resources


async def _execute_transfer(
    resources: dict,
    to_client,
    progress: Progress,
) -> dict:
    """
    Execute the actual transfer of resources to the target profile.

    Returns a dictionary with transfer results and statistics.
    """
    from ._blocks import transfer_blocks
    from ._concurrency import transfer_concurrency_limits
    from ._deployments import transfer_deployments
    from ._dependencies import resolve_dependencies
    from ._variables import transfer_variables
    from ._work_pools import transfer_work_pools

    results = {
        "succeeded": {},
        "failed": {},
        "skipped": {},
    }

    # Resolve dependencies and get transfer order
    transfer_order = resolve_dependencies(resources)

    # Transfer resources in dependency order
    for resource_type in transfer_order:
        if resource_type not in resources or not resources[resource_type]:
            continue

        if resource_type == ResourceType.BLOCKS:
            type_results = await transfer_blocks(resources[resource_type], to_client)
        elif resource_type == ResourceType.VARIABLES:
            type_results = await transfer_variables(resources[resource_type], to_client)
        elif resource_type == ResourceType.WORK_POOLS:
            type_results = await transfer_work_pools(
                resources[resource_type], to_client
            )
        elif resource_type == ResourceType.DEPLOYMENTS:
            type_results = await transfer_deployments(
                resources[resource_type], to_client
            )
        elif resource_type == ResourceType.CONCURRENCY_LIMITS:
            type_results = await transfer_concurrency_limits(
                resources[resource_type], to_client
            )
        else:
            # Skip unsupported types
            continue

        # Aggregate results
        for status in ["succeeded", "failed", "skipped"]:
            if status in type_results:
                results[status][resource_type] = type_results[status]

    return results
