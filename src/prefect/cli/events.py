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
    """Subscribes to the event stream of a workspace, printing each event"""
    EventFilter(event=EventNameFilter(prefix=["prefect.flow-run."]))

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
                            app.console.print(
                                (orjson.dumps(event.dict(), default=str).decode())
                            )
                    if format == "text":
                        if output_file:
                            with open(output_file, "a") as f:
                                f.write(
                                    f"{event.occurred.isoformat()} {event.event} {event.resource.id}"
                                )
                        else:
                            app.console.print(
                                f"{event.occurred.isoformat()}",
                                f"\\[[bold green]{event.event}[/]]",
                                event.resource.id,
                            )
        except websockets.exceptions.ConnectionClosedError as e:
            app.console.print(f"Connection closed, retrying... ({e})")
        except KeyboardInterrupt:
            app.console.print("Exiting...")
            break
        except Exception as e:
            app.console.print(f"An unexpected error occurred: {e}")
            break  # Exit the loop on unexpected errors
