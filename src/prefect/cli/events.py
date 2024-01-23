import pendulum
import websockets

from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.events.clients import PrefectCloudEventSubscriber
from prefect.events.filters import EventFilter, EventNameFilter

events_app = PrefectTyper(name="events", help="Commands for working with events.")
app.add_typer(events_app, aliases=["event"])


@events_app.command()
async def stream():
    """Subscribes to the event stream of a workspace, printing each event"""
    EventFilter(event=EventNameFilter(prefix=["prefect.flow-run."]))

    while True:
        try:
            async with PrefectCloudEventSubscriber() as subscriber:
                async for event in subscriber:
                    pendulum.now("UTC")
                    app.console.print(event.json())
        except websockets.exceptions.ConnectionClosedError as e:
            app.console.print(f"Connection closed, retrying... ({e})")
        except Exception as e:
            app.console.print(f"An unexpected error occurred: {e}")
            break  # Exit the loop on unexpected errors
