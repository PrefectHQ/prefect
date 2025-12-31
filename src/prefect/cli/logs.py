"""
Command line interface for sending logs to Prefect.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional
from uuid import UUID

import typer

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import LogCreate
from prefect.types._datetime import now, parse_datetime

logs_app: PrefectTyper = PrefectTyper(name="logs", help="Send logs to Prefect.")
app.add_typer(logs_app)

LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


@logs_app.command()
async def send(
    file: Optional[Path] = typer.Argument(
        None,
        help="Path to file containing log content. If omitted, reads from stdin or --message.",
    ),
    message: Optional[str] = typer.Option(
        None,
        "--message",
        "-m",
        help="Log message to send directly. If provided, file and stdin are ignored.",
    ),
    level: str = typer.Option(
        "info",
        "--level",
        "-l",
        help="Log level: debug, info, warning, error, critical",
    ),
    name: str = typer.Option(
        "prefect.logs.send",
        "--name",
        "-n",
        help="Logger name for the log record.",
    ),
    flow_run_id: Optional[UUID] = typer.Option(
        None,
        "--flow-run-id",
        "-f",
        help="Flow run ID to associate logs with. Auto-detects from PREFECT__FLOW_RUN_ID env var if not provided.",
    ),
    timestamp: Optional[str] = typer.Option(
        None,
        "--timestamp",
        "-t",
        help="Timestamp for the log record (ISO format). Defaults to current time.",
    ),
    per_line: bool = typer.Option(
        False,
        "--per-line",
        help="Send each line as a separate log entry instead of a single entry.",
    ),
    silent: bool = typer.Option(
        False,
        "--silent",
        help="Suppress errors and exit successfully if sending logs fails.",
    ),
):
    """
    Send log messages to Prefect.

    Reads log content from --message, a file, or stdin and sends it to Prefect
    Cloud/Server. Useful for capturing and forwarding output from failed commands.

    Examples:
        # Send a message directly
        prefect logs send -m "Build failed" --level error

        # Pipe output to Prefect
        some_command 2>&1 | prefect logs send

        # From file with error level
        prefect logs send --level error /tmp/output.log

        # Line-by-line mode
        cat multiline.log | prefect logs send --per-line
    """
    level_lower = level.lower()
    if level_lower not in LOG_LEVELS:
        exit_with_error(
            f"Invalid log level '{level}'. Must be one of: {', '.join(LOG_LEVELS)}"
        )
    log_level = LOG_LEVELS[level_lower]

    # Auto-detect flow_run_id from environment if not provided
    if flow_run_id is None:
        env_val = os.environ.get("PREFECT__FLOW_RUN_ID")
        if env_val:
            try:
                flow_run_id = UUID(env_val)
            except ValueError:
                pass

    # Get content from message, file, or stdin
    if message is not None:
        content = message
    elif file is not None:
        content = file.read_text()
    elif not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        return

    if not content.strip():
        return

    log_timestamp = parse_datetime(timestamp) if timestamp else now("UTC")

    # Build log records
    messages = (
        [line for line in content.splitlines() if line.strip()]
        if per_line
        else [content]
    )
    if not messages:
        return

    logs = [
        LogCreate(
            name=name,
            level=log_level,
            message=msg,
            timestamp=log_timestamp,
            flow_run_id=flow_run_id,
        )
        for msg in messages
    ]

    try:
        async with get_client() as client:
            await client.create_logs(logs)
    except Exception as e:
        if not silent:
            app.console.print(f"Could not send logs to Prefect: {e}", style="red")
            raise
    else:
        if not silent:
            count = len(logs)
            app.console.print(
                f"Successfully sent {count} log{'s' if count != 1 else ''}"
            )
