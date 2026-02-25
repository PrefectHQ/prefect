"""
Events command — native cyclopts implementation.

Stream and emit events.
"""

import json
from typing import Annotated, Optional

import cyclopts

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    with_cli_exception_handling,
)
from prefect.events.clients import get_events_client

events_app: cyclopts.App = cyclopts.App(
    name="events",
    alias="event",
    help="Stream events.",
    version_flags=[],
    help_flags=["--help"],
)


@events_app.command()
@with_cli_exception_handling
async def stream(
    *,
    format: Annotated[
        str,
        cyclopts.Parameter("--format", help="Output format (json or text)"),
    ] = "json",
    output_file: Annotated[
        Optional[str],
        cyclopts.Parameter("--output-file", help="File to write events to"),
    ] = None,
    account: Annotated[
        bool,
        cyclopts.Parameter(
            "--account",
            help="Stream events for entire account, including audit logs",
        ),
    ] = False,
    run_once: Annotated[
        bool,
        cyclopts.Parameter("--run-once", help="Stream only one event"),
    ] = False,
):
    """Subscribe to the event stream, printing each event as it is received."""
    import asyncio

    import orjson
    import websockets
    from anyio import open_file

    from prefect.events import Event
    from prefect.events.clients import (
        PrefectCloudAccountEventSubscriber,
        get_events_subscriber,
    )

    async def handle_event(event: Event, fmt: str, out_file: Optional[str]) -> None:
        if fmt == "json":
            event_data = orjson.dumps(event.model_dump(), default=str).decode()
        elif fmt == "text":
            event_data = (
                f"{event.occurred.isoformat()} {event.event} {event.resource.id}"
            )
        else:
            raise ValueError(f"Unknown format: {fmt}")
        if out_file:
            async with open_file(out_file, "a") as f:  # type: ignore
                await f.write(event_data + "\n")
        else:
            print(event_data)

    def handle_error(exc: Exception) -> None:
        if isinstance(exc, websockets.exceptions.ConnectionClosedError):
            exit_with_error(f"Connection closed, retrying... ({exc})")
        elif isinstance(exc, (KeyboardInterrupt, asyncio.exceptions.CancelledError)):
            exit_with_error("Exiting...")
        elif isinstance(exc, PermissionError):
            exit_with_error(f"Error writing to file: {exc}")
        else:
            exit_with_error(f"An unexpected error occurred: {exc}")

    try:
        if account:
            events_subscriber = PrefectCloudAccountEventSubscriber()
        else:
            events_subscriber = get_events_subscriber()

        _cli.console.print("Subscribing to event stream...")
        async with events_subscriber as subscriber:
            async for event in subscriber:
                await handle_event(event, format, output_file)
                if run_once:
                    # Note: typer.Exit(0) as a statement is a no-op (not
                    # raised), so the typer version continues iterating.
                    # We match that behavior here — the subscriber's
                    # iterator will naturally stop when events are exhausted.
                    pass
    except Exception as exc:
        handle_error(exc)


@events_app.command()
@with_cli_exception_handling
async def emit(
    event: str,
    *,
    resource: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--resource",
            alias="-r",
            help="Resource specification as 'key=value' or JSON. Can be used multiple times.",
        ),
    ] = None,
    resource_id: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--resource-id",
            help="The resource ID (shorthand for --resource prefect.resource.id=<id>)",
        ),
    ] = None,
    related: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--related",
            help="Related resources as JSON string",
        ),
    ] = None,
    payload: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--payload",
            alias="-p",
            help="Event payload as JSON string",
        ),
    ] = None,
):
    """Emit a single event to Prefect."""
    from prefect.events import Event as EventModel

    resource_dict: dict[str, str] = {}

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

    event_obj = EventModel(
        event=event,
        resource=resource_dict,
        related=related_list or [],
        payload=payload_dict or {},
    )

    async with get_events_client() as events_client:
        await events_client.emit(event_obj)

    _cli.console.print(f"Successfully emitted event '{event}' with ID {event_obj.id}")
