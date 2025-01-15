import asyncio
from datetime import datetime
from typing import Any

import asyncpg
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def make_connection_table(connections: list[dict[str, Any]], title: str) -> Table:
    """Create a table for a specific connection type"""
    table = Table(
        show_header=True,
        header_style="bold",
        title=title,
        title_style="bold",
        expand=True,
    )

    table.add_column("PID", style="cyan", justify="right")
    table.add_column("State", style="green")
    table.add_column("Duration", justify="right")
    table.add_column("Wait Event", style="yellow")
    table.add_column("Last Query", max_width=50)

    for conn in sorted(connections, key=lambda x: x["state_duration"], reverse=True):
        # Style the state
        state = conn["state"]
        state_style = {
            "idle": "green",
            "active": "bright_green",
            "idle in transaction": "yellow",
            "idle in transaction (aborted)": "red",
        }.get(state, "white")

        # Format duration with warning colors
        duration = f"{conn['state_duration']:.1f}s"
        if conn["state_duration"] > 30:
            duration = Text(duration, style="red bold")
        elif conn["state_duration"] > 10:
            duration = Text(duration, style="yellow")
        else:
            duration = Text(duration, style="green")

        # Format wait event
        wait_event = (
            f"{conn['wait_event_type']}.{conn['wait_event']}"
            if conn["wait_event_type"]
            else "-"
        )

        # Format query
        query = (
            conn["query"][:50] + "..."
            if conn["query"] and len(conn["query"]) > 50
            else (conn["query"] or "-")
        )

        table.add_row(
            str(conn["pid"]),
            Text(state, style=state_style),
            duration,
            wait_event,
            query,
        )

    return table


def make_summary_panel(by_app: dict[str, list[dict[str, Any]]]) -> Panel:
    """Create a summary panel with connection statistics"""
    stats: list[Text] = []
    total_connections = 0
    long_running = 0
    in_transaction = 0

    # Track pool utilization
    web_pool_size = 10  # Base pool size for web
    service_pool_size = 2  # Base pool size per service

    for app_name, connections in by_app.items():
        total_connections += len(connections)
        long_running += sum(1 for c in connections if c["state_duration"] > 30)
        in_transaction += sum(1 for c in connections if "transaction" in c["state"])

        # Calculate pool utilization
        pool_size = (
            web_pool_size if app_name == "prefect-server-web" else service_pool_size
        )
        utilization = len(connections) / pool_size * 100

        # Color code based on utilization
        if utilization > 90:
            util_color = "red"
        elif utilization > 70:
            util_color = "yellow"
        else:
            util_color = "green"

        stats.append(
            Text.assemble(
                (f"{app_name}: ", "bold cyan"),
                (f"{len(connections)} connections", "white"),
                (f" ({utilization:.1f}% of pool)", util_color),
                (
                    f" ({sum(1 for c in connections if c['state_duration'] > 30)} long-running)",
                    "red"
                    if any(c["state_duration"] > 30 for c in connections)
                    else "green",
                ),
            )
        )

    stats.insert(
        0,
        Text.assemble(
            ("Total: ", "bold"),
            (f"{total_connections} connections ", "white"),
            (f"({long_running} long-running, ", "red" if long_running else "green"),
            (
                f"{in_transaction} in transaction)",
                "yellow" if in_transaction else "green",
            ),
        ),
    )

    return Panel(
        "\n".join([str(s) for s in stats]),
        title="Connection Summary",
        title_align="left",
        border_style="blue",
    )


async def monitor_prefect_connections():
    """Monitor connections grouped by application name with live updates"""
    console = Console()

    conn = await asyncpg.connect(
        "postgresql://postgres:yourTopSecretPassword@localhost:5432/prefect"
    )

    with Live(console=console, refresh_per_second=2) as live:
        while True:
            results = await conn.fetch(
                """
                SELECT 
                    COALESCE(application_name, 'unknown') as app_name,
                    state,
                    wait_event_type,
                    wait_event,
                    query,
                    pid,
                    EXTRACT(EPOCH FROM (now() - state_change)) as state_duration
                FROM pg_stat_activity 
                WHERE datname = 'prefect'
                    AND pid != pg_backend_pid()
                ORDER BY application_name, state_change DESC
            """
            )

            by_app: dict[str, list[dict[str, Any]]] = {}
            for r in results:
                app = r["app_name"]
                if app not in by_app:
                    by_app[app] = []
                by_app[app].append(r)

            # Create layout
            service_conns = []
            web_conns = []
            other_conns = []

            for app_name, conns in by_app.items():
                if "-service" in app_name:  # Match our new service naming convention
                    service_conns.extend(conns)
                elif app_name in [
                    "prefect-server",
                    "prefect-server-web",
                ]:  # Web server names
                    web_conns.extend(conns)
                else:
                    other_conns.extend(conns)

            # Build display
            summary = make_summary_panel(by_app)
            tables = []

            if web_conns:
                tables.append(
                    make_connection_table(web_conns, "Web Server Connections")
                )
            if service_conns:
                tables.append(
                    make_connection_table(
                        service_conns, "Background Service Connections"
                    )
                )
            if other_conns:
                tables.append(make_connection_table(other_conns, "Other Connections"))

            # Update display
            from rich.console import Group

            live.update(
                Group(
                    summary,
                    *tables,
                    Text(
                        f"\nLast updated: {datetime.now().strftime('%H:%M:%S')}",
                        style="dim",
                    ),
                )
            )

            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(monitor_prefect_connections())
    except KeyboardInterrupt:
        print("\nMonitoring stopped")
