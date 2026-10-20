from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from prefect.client.schemas.objects import FlowRun

console = Console()


def print_flow_run_created(flow_run: FlowRun) -> None:
    """Display information about a created flow run."""
    console.print(
        Panel(
            f"[bold]Flow Run ID:[/bold] {flow_run.id}\n"
            f"[bold]Flow Run Name:[/bold] {flow_run.name}",
            title="Created Flow Run",
            style="cyan",
        )
    )


def print_flow_run_result(flow_run: FlowRun) -> None:
    """Display the final state of a flow run."""
    result_table = Table(title="Flow Run Final State")
    result_table.add_column("Property", style="cyan")
    result_table.add_column("Value", style="green")

    result_table.add_row(
        "State", flow_run.state.type.name if flow_run.state else "None"
    )
    result_table.add_row(
        "State Message", flow_run.state.message if flow_run.state else "None"
    )
    result_table.add_row("Infrastructure PID", flow_run.infrastructure_pid)
    result_table.add_row("Start Time", str(flow_run.start_time))
    result_table.add_row("End Time", str(flow_run.end_time))
    result_table.add_row("Total Run Time", str(flow_run.total_run_time))

    console.print(result_table)
