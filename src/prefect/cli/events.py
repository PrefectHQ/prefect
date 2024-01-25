import asyncio
from enum import Enum

import orjson
import websockets
from anyio import open_file

from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.events.clients import PrefectCloudEventSubscriber
from prefect.events.filters import EventFilter, EventNameFilter

events_app = PrefectTyper(name="events", help="Commands for working with events.")
app.add_typer(events_app, aliases=["event"])


class StreamFormat(str, Enum):
    json = "json"
    text = "text"


@events_app.command()
async def stream(format: StreamFormat = StreamFormat.json, output_file: str = None):
    """Subscribes to the event stream of a workspace, printing each event
    as it is received. By default, events are printed as JSON, but can be
    printed as text by passing `--format text`.
    """
    EventFilter(event=EventNameFilter(prefix=["prefect.flow-run."]))
    app.console.print("Subscribing to event stream...")
    await process_events(format, output_file)


async def process_events(format, output_file):
    try:
        async with PrefectCloudEventSubscriber() as subscriber:
            async for event in subscriber:
                await handle_event(event, format, output_file)
    except (
        websockets.exceptions.ConnectionClosedError,
        KeyboardInterrupt,
        asyncio.exceptions.CancelledError,
        PermissionError,
        IOError,
    ) as exc:
        handle_error(exc)


async def handle_event(event, format, output_file):
    if format == StreamFormat.json:
        await write_event_json(event, output_file)
    elif format == StreamFormat.text:
        await write_event_text(event, output_file)


async def write_event_json(event, output_file):
    event_data = orjson.dumps(event.dict(), default=str).decode()
    await write_to_output(event_data, output_file)


async def write_event_text(event, output_file):
    event_data = f"{event.occurred.isoformat()} {event.event} {event.resource.id}"
    await write_to_output(event_data, output_file)


async def write_to_output(data, output_file):
    if output_file:
        async with open_file(output_file, "a") as f:
            await f.write(data + "\n")
    else:
        print(data)


def handle_error(exc):
    if isinstance(exc, websockets.exceptions.ConnectionClosedError):
        app.console.print(f"Connection closed, retrying... ({exc})")
    elif isinstance(exc, (KeyboardInterrupt, asyncio.exceptions.CancelledError)):
        app.console.print("Exiting...")
    elif isinstance(exc, (PermissionError)):
        app.console.print(f"Error writing to file: {exc}")
    else:
        app.console.print(f"An unexpected error occurred: {exc}")
