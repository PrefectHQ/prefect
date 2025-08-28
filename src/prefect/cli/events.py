import asyncio
import json
from enum import Enum
from typing import Optional

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
    get_events_client,
    get_events_subscriber,
)

events_app: PrefectTyper = PrefectTyper(name="events", help="Stream events.")
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


async def handle_event(event: Event, format: StreamFormat, output_file: str) -> None:
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


def handle_error(exc: Exception) -> None:
    if isinstance(exc, websockets.exceptions.ConnectionClosedError):
        exit_with_error(f"Connection closed, retrying... ({exc})")
    elif isinstance(exc, (KeyboardInterrupt, asyncio.exceptions.CancelledError)):
        exit_with_error("Exiting...")
    elif isinstance(exc, (PermissionError)):
        exit_with_error(f"Error writing to file: {exc}")
    else:
        exit_with_error(f"An unexpected error occurred: {exc}")


@events_app.command()
async def emit(
    event: str = typer.Argument(help="The name of the event"),
    resource: str = typer.Option(
        None,
        "--resource",
        "-r",
        help="Resource specification as 'key=value' or JSON. Can be used multiple times.",
    ),
    resource_id: str = typer.Option(
        None,
        "--resource-id",
        help="The resource ID (shorthand for --resource prefect.resource.id=<id>)",
    ),
    related: Optional[str] = typer.Option(
        None,
        "--related",
        help="Related resources as JSON string",
    ),
    payload: Optional[str] = typer.Option(
        None,
        "--payload",
        "-p",
        help="Event payload as JSON string",
    ),
):
    """Emit a single event to Prefect.

    Examples:
        # Simple event with resource ID
        prefect event emit user.logged_in --resource-id user-123

        # Event with payload
        prefect event emit order.shipped --resource-id order-456 --payload '{"tracking": "ABC123"}'

        # Event with full resource specification
        prefect event emit customer.subscribed --resource '{"prefect.resource.id": "customer-789", "prefect.resource.name": "ACME Corp"}'
    """
    resource_dict = {}

    if resource:
        try:
            parsed = json.loads(resource)
            if not isinstance(parsed, dict):
                exit_with_error(
                    "Resource must be a JSON object, not an array or string"
                )
            resource_dict = parsed
        except json.JSONDecodeError:
            if "=" in resource:
                key, value = resource.split("=", 1)
                resource_dict[key] = value
            else:
                exit_with_error("Resource must be JSON or 'key=value' format")

    if resource_id:
        resource_dict["prefect.resource.id"] = resource_id

    if "prefect.resource.id" not in resource_dict:
        exit_with_error("Resource must include 'prefect.resource.id'")

    related_list = None
    if related:
        try:
            parsed_related = json.loads(related)
            if isinstance(parsed_related, dict):
                related_list = [parsed_related]
            elif isinstance(parsed_related, list):
                related_list = parsed_related
            else:
                exit_with_error("Related resources must be a JSON object or array")
        except json.JSONDecodeError:
            exit_with_error("Related resources must be valid JSON")

    payload_dict = None
    if payload:
        try:
            parsed_payload = json.loads(payload)
            if not isinstance(parsed_payload, dict):
                exit_with_error("Payload must be a JSON object")
            payload_dict = parsed_payload
        except json.JSONDecodeError:
            exit_with_error("Payload must be valid JSON")

    event_obj = Event(
        event=event,
        resource=resource_dict,
        related=related_list or [],
        payload=payload_dict or {},
    )

    async with get_events_client() as events_client:
        await events_client.emit(event_obj)

    app.console.print(f"Successfully emitted event '{event}' with ID {event_obj.id}")
