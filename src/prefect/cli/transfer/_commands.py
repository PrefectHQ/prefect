"""
Transfer command — native cyclopts implementation.

Transfer resources between workspaces.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Annotated, Any

import cyclopts
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
)
from rich.table import Table

import prefect.cli._app as _cli
from prefect.cli._transfer_utils import (
    collect_resources,
    execute_transfer,
    find_root_resources,
    get_resource_display_name,
)
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

if TYPE_CHECKING:
    from prefect.cli.transfer._migratable_resources import MigratableProtocol

transfer_app: cyclopts.App = cyclopts.App(
    name="transfer",
    help="Transfer resources from one Prefect profile to another.\n\nAutomatically handles dependencies between resources and transfers them in the correct order.",
    version_flags=[],
    help_flags=["--help"],
)


@transfer_app.default
@with_cli_exception_handling
async def transfer(
    *,
    from_profile: Annotated[
        str,
        cyclopts.Parameter("--from", help="Source profile to transfer resources from"),
    ],
    to_profile: Annotated[
        str,
        cyclopts.Parameter("--to", help="Target profile to transfer resources to"),
    ],
):
    """Transfer resources from one Prefect profile to another.

    Automatically handles dependencies between resources and transfers them
    in the correct order.
    """
    from prefect.cli._prompts import confirm
    from prefect.cli.transfer._dag import TransferDAG
    from prefect.cli.transfer._exceptions import TransferSkipped
    from prefect.client.orchestration import get_client
    from prefect.context import use_profile
    from prefect.events import get_events_client
    from prefect.events.schemas.events import Event, Resource
    from prefect.settings import load_profiles

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
                resources = await collect_resources(client)

            if not resources:
                console.print("\n[yellow]No resources found to transfer.[/yellow]")
                return

            progress.update(task, description="Building dependency graph...")
            roots = await find_root_resources(resources)
            dag = TransferDAG()
            await dag.build_from_roots(roots)

    stats = dag.get_statistics()

    if stats["has_cycles"]:
        exit_with_error("Cannot transfer resources with circular dependencies.")

    console.print()
    if _cli.is_interactive() and not confirm(
        f"Transfer {stats['total_nodes']} resource(s) from '{from_profile}' to '{to_profile}'?",
        console=console,
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
                results = await execute_transfer(dag, console)

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


def _display_results(
    results: dict[uuid.UUID, Any],
    nodes: dict[uuid.UUID, "MigratableProtocol"],
    console: Console,
):
    """Display transfer results."""
    from prefect.cli.transfer._exceptions import TransferSkipped

    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []

    for node_id, result in results.items():
        resource = nodes[node_id]
        resource_name = get_resource_display_name(resource)

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
