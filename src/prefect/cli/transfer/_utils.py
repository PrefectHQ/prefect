"""
Shared utilities for the transfer command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

if TYPE_CHECKING:
    pass


def display_resource_summary(resources: dict, console: Console):
    """Display a summary of resources found."""
    total = sum(len(items) for items in resources.values() if items)

    if total == 0:
        console.print("[yellow]No resources found in source profile[/yellow]")
        return

    # Build summary text
    summary_lines = []
    for resource_type, items in sorted(resources.items()):
        if items:
            count = len(items)
            summary_lines.append(
                f"[cyan]{resource_type.value.title()}:[/cyan] [bold green]{count}[/bold green]"
            )

    summary_content = "\n".join(summary_lines)
    summary_content += (
        f"\n\n[bold]Total: {total} resource{'s' if total != 1 else ''}[/bold]"
    )

    summary_panel = Panel(
        summary_content,
        title="Resources Found",
        expand=False,
        padding=(1, 2),
    )

    console.print(summary_panel)


async def preview_transfer(resources: dict, console: Console):
    """
    Display a detailed preview of what would be transferred.
    """
    from ._types import ResourceType

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
            elif resource_type == ResourceType.WORK_QUEUES:
                name = getattr(item, "name", "unknown")
                pool = getattr(item, "work_pool_name", "unknown")
                content.append(f"• {name} [dim](pool: {pool})[/dim]")
            elif resource_type == ResourceType.CONCURRENCY_LIMITS:
                name = getattr(item, "name", "unknown")
                limit = getattr(item, "limit", "unknown")
                content.append(f"• {name} [dim](limit: {limit})[/dim]")

        if len(items) > 5:
            content.append(f"[dim]... and {len(items) - 5} more[/dim]")

        panel_content = "\n".join(content) if content else "[dim]None[/dim]"

        # Use simpler display without panels for cleaner look
        console.print(
            f"\n[bold cyan]{resource_type.value.title()}[/bold cyan] [dim]({len(items)} items)[/dim]"
        )
        console.print(panel_content)


def display_transfer_results(results: dict, console: Console):
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

    # Display detailed breakdown by resource type if there were failures
    if total_failed > 0:
        console.print("\n[bold]Failed Resources:[/bold]")
        for resource_type, failures in results["failed"].items():
            if failures:
                console.print(
                    f"\n[bold cyan]{resource_type.value.title()}:[/bold cyan]"
                )
                for failure in failures[:5]:  # Show up to 5 failures
                    name = failure.get("name", "unknown")
                    error = failure.get("error", "unknown error")
                    console.print(f"  • {name}: [red]{error}[/red]")
                if len(failures) > 5:
                    console.print(f"  [dim]... and {len(failures) - 5} more[/dim]")
