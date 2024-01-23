import pendulum

from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.events.clients import PrefectCloudEventSubscriber
from prefect.events.filters import EventFilter, EventNameFilter

events_app = PrefectTyper(name="events", help="Commands for working with events.")
app.add_typer(events_app, aliases=["event"])


@events_app.command()
async def subscribe():
    """Subscribes to the event stream of a workspace, printing each event"""
    EventFilter(event=EventNameFilter(prefix=["prefect.flow-run."]))

    async with PrefectCloudEventSubscriber() as subscriber:
        async for event in subscriber:
            now = pendulum.now("UTC")
            app.console.print(
                str(event.id).partition("-")[0],
                f"{event.occurred.isoformat()}",
                f" ({(event.occurred - now).total_seconds():>6,.2f})",
                f"\\[[bold green]{event.event}[/]]",
                event.resource.id,
            )
