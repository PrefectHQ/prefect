import asyncio
from typing import Any

import asyncpg
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def make_table(connections: list[dict[str, Any]]) -> tuple[Table, list[str]]:
    table = Table(show_header=True, expand=True)

    table.add_column("PID", style="cyan")
    table.add_column("State", style="green")
    table.add_column("Duration", justify="right")
    table.add_column("Wait Event")
    table.add_column("Query", max_width=60)

    # Track problem states
    stuck_reads: list[int] = []
    long_transactions: list[int] = []
    blocked_queries: list[int] = []

    for conn in sorted(
        connections, key=lambda c: c["state_duration"] or 0, reverse=True
    ):
        pid = conn["pid"]
        state = conn["state"]
        duration = f"{conn['state_duration']:.1f}s"
        wait_event = (
            f"{conn['wait_event_type']}.{conn['wait_event']}"
            if conn["wait_event_type"]
            else "-"
        )
        query = conn["query"] or "-"

        # Track issues
        if (
            state == "idle"
            and wait_event == "Client.ClientRead"
            and conn["state_duration"] > 5
        ):
            stuck_reads.append(pid)
            duration = Text(duration, style="red")

        if "transaction" in state and conn["state_duration"] > 10:
            long_transactions.append(pid)
            state = Text(state, style="red")

        if wait_event.startswith("Lock"):
            blocked_queries.append(pid)
            wait_event = Text(wait_event, style="red")

        table.add_row(str(pid), str(state), str(duration), wait_event, query)

    summary: list[str] = []
    if stuck_reads:
        summary.append(
            f"[red]PIDs stuck in ClientRead > 5s: {', '.join(str(p) for p in stuck_reads)}[/]"
        )
    if long_transactions:
        summary.append(
            f"[red]PIDs in transaction > 10s: {', '.join(str(p) for p in long_transactions)}[/]"
        )
    if blocked_queries:
        summary.append(
            f"[red]PIDs waiting on locks: {', '.join(str(p) for p in blocked_queries)}[/]"
        )

    return table, summary


async def monitor_connections():
    console = Console()

    conn = await asyncpg.connect(
        "postgresql://postgres:yourTopSecretPassword@localhost:5432/prefect"
    )

    with Live(console=console, refresh_per_second=1) as live:
        while True:
            results = await conn.fetch(
                """
                SELECT 
                    pid,
                    state,
                    wait_event_type,
                    wait_event,
                    query,
                    xact_start,
                    EXTRACT(EPOCH FROM (now() - state_change)) as state_duration,
                    EXTRACT(EPOCH FROM (now() - xact_start)) as transaction_duration
                FROM pg_stat_activity 
                WHERE datname = 'prefect'
                    AND pid != pg_backend_pid()
            """
            )

            conns = [dict(r) for r in results]

            table, issues = make_table(conns)
            total_active = sum(1 for c in conns if c["state"] == "active")
            total_idle = sum(1 for c in conns if c["state"] == "idle")
            # Only count actual blocking wait states like locks
            total_waiting = sum(
                1
                for c in conns
                if c["wait_event_type"] == "Lock"
                or (c["wait_event_type"] == "Client" and c["state"] != "idle")
            )

            status = f"Total: {len(conns)} connections ({total_active} active, {total_idle} idle, {total_waiting} waiting)"
            if issues:
                status += "\n" + "\n".join(issues)

            live.update(Panel(table, title=status))
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(monitor_connections())
    except KeyboardInterrupt:
        print("\nStopped monitoring")
