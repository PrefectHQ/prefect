import asyncio
from enum import Enum

import orjson
import websockets

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
async def stream(format: StreamFormat = StreamFormat, output_file: str = None):
    """Subscribes to the event stream of a workspace, printing each event
    as it is received. By default, events are printed as JSON, but can be
    printed as text by passing `--format text`.
    Text format is of the form: `2021-01-01T00:00:00.000000+00:00 [event] id`
    format: str, optional (default: "json") Format to print events in. Can be "json" or "text".
    output_file: str, optional (default: None) File to write events to. If not provided, events are printed to stdout.
    """
    EventFilter(event=EventNameFilter(prefix=["prefect.flow-run."]))
    app.console.print("Subscribing to event stream...")
    while True:
        try:
            async with PrefectCloudEventSubscriber() as subscriber:
                async for event in subscriber:
                    if format == "json":
                        if output_file:
                            with open(output_file, "a") as f:
                                f.write(
                                    (orjson.dumps(event.dict(), default=str).decode())
                                )
                        else:
                            print((orjson.dumps(event.dict(), default=str).decode()))
                    if format == "text":
                        if output_file:
                            with open(output_file, "a") as f:
                                f.write(
                                    f"{event.occurred.isoformat()} {event.event} {event.resource.id}"
                                )
                        else:
                            app.console.print(
                                f"{event.occurred.isoformat()} ",
                                f"\\[[bold green]{event.event}[/]]",
                                f" {event.id}",
                            )

        except Exception as exc:
            if isinstance(exc, websockets.exceptions.ConnectionClosedError):
                app.console.print(f"Connection closed, retrying... ({exc})")
            if isinstance(exc, (KeyboardInterrupt, asyncio.exceptions.CancelledError)):
                app.console.print("Exiting...")
                break
            if isinstance(exc, (PermissionError, IOError)):
                app.console.print(f"Error writing to file: {exc}")
                break
            else:
                app.console.print(f"An unexpected error occurred: {exc}")
                break  # Exit the loop on unexpected errors
