import asyncio
from enum import Enum

import orjson
import typer
import websockets
from anyio import open_file

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.events import Event
from prefect.events.clients import (
    PrefectCloudAccountEventSubscriber,
    get_events_subscriber,
)

events_app = PrefectTyper(name="events", help="Stream events.")
app.add_typer(events_app, aliases=["event"])


class StreamFormat(str, Enum):
    json = "json"
    text = "text"


@events_app.command()
async def stream(
    format: StreamFormat = typer.Option(
        StreamFormat.json, "--format", help="Output format (json or text)"
    ),
    output_file: str = typer.Option(
        None, "--output-file", help="File to write events to"
    ),
    account: bool = typer.Option(
        False,
        "--account",
        help="Stream events for entire account, including audit logs",
    ),
    run_once: bool = typer.Option(False, "--run-once", help="Stream only one event"),
):
    """Subscribes to the event stream of a workspace, printing each event
    as it is received. By default, events are printed as JSON, but can be
    printed as text by passing `--format text`.
    """

    try:
        if account:
            events_subscriber = PrefectCloudAccountEventSubscriber()
        else:
            events_subscriber = get_events_subscriber()

        app.console.print("Subscribing to event stream...")
        async with events_subscriber as subscriber:
            async for event in subscriber:
                await handle_event(event, format, output_file)
                if run_once:
                    typer.Exit(0)
    except Exception as exc:
        handle_error(exc)


async def handle_event(event: Event, format: StreamFormat, output_file: str):
    if format == StreamFormat.json:
        event_data = orjson.dumps(event.model_dump(), default=str).decode()
    elif format == StreamFormat.text:
        event_data = f"{event.occurred.isoformat()} {event.event} {event.resource.id}"
    else:
        raise ValueError(f"Unknown format: {format}")
    if output_file:
        async with open_file(output_file, "a") as f:  # type: ignore
            await f.write(event_data + "\n")
    else:
        print(event_data)


def handle_error(exc):
    if isinstance(exc, websockets.exceptions.ConnectionClosedError):
        exit_with_error(f"Connection closed, retrying... ({exc})")
    elif isinstance(exc, (KeyboardInterrupt, asyncio.exceptions.CancelledError)):
        exit_with_error("Exiting...")
    elif isinstance(exc, (PermissionError)):
        exit_with_error(f"Error writing to file: {exc}")
    else:
        exit_with_error(f"An unexpected error occurred: {exc}")
