"""Module to define tasks and helpers for observing Armada job set events."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import aclosing

import anyio
import grpc
from armada_client.event import Event

from prefect import task
from prefect.logging.loggers import get_logger
from prefect_armada.credentials import ArmadaCredentials

logger = get_logger("prefect_armada.events")


async def stream_job_set_events(
    armada_credentials: ArmadaCredentials,
    queue: str,
    job_set_id: str,
    from_message_id: str | None = None,
) -> AsyncGenerator[Event, None]:
    """Yields events for an Armada job set as they occur.

    The stream begins at the start of the job set's history unless
    `from_message_id` is provided, and it does not end on its own, because
    Armada keeps the stream open in case more jobs are added to the job set.
    Callers are responsible for deciding when to stop consuming it, and should
    wrap this generator in `contextlib.aclosing` so that the underlying gRPC
    stream is cancelled as soon as they stop rather than whenever the generator
    is garbage collected.

    Events that cannot be decoded, such as event types newer than the installed
    `armada_client`, are skipped with a warning.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        queue: The name of the Armada queue the job set was submitted to.
        job_set_id: The name of the Armada job set to watch.
        from_message_id: If provided, the stream resumes after this message ID.

    Yields:
        An `Event` for each message in the job set's event stream.

    Example:
        Print each event for a job set until the job set finishes:
        ```python
        from contextlib import aclosing

        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.events import stream_job_set_events

        async with aclosing(
            stream_job_set_events(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                queue="prefect",
                job_set_id="my-job-set",
            )
        ) as events:
            async for event in events:
                print(event.type, event.message.job_id)
                if event.type.value in ("succeeded", "failed"):
                    break
        ```
    """
    async with aclosing(
        _stream_job_set_events(
            armada_credentials=armada_credentials,
            queue=queue,
            job_set_id=job_set_id,
            from_message_id=from_message_id,
        )
    ) as events:
        async for event in events:
            yield event


async def _stream_job_set_events(
    armada_credentials: ArmadaCredentials,
    queue: str,
    job_set_id: str,
    from_message_id: str | None = None,
    on_connected: Callable[[], None] | None = None,
) -> AsyncGenerator[Event, None]:
    """
    Yields events for an Armada job set as `stream_job_set_events` does.

    Args:
        on_connected: Called once a connection to Armada has been established,
            which for a stream with no new events is before any event arrives.
    """
    connected = False

    def notify_connected() -> None:
        nonlocal connected
        if not connected and on_connected is not None:
            connected = True
            on_connected()

    async def notify_when_ready(channel: grpc.aio.Channel) -> None:
        await channel.channel_ready()
        notify_connected()

    async with armada_credentials.get_client() as client:
        event_stream = await client.get_job_events_stream(
            queue=queue,
            job_set_id=job_set_id,
            from_message_id=from_message_id,
        )
        # Runs alongside the stream rather than before it, so that waiting for
        # the connection never delays or replaces the stream's own errors.
        channel = getattr(client, "channel", None)
        ready_task = (
            asyncio.create_task(notify_when_ready(channel))
            if on_connected is not None and channel is not None
            else None
        )
        try:
            async for message in event_stream:
                notify_connected()
                try:
                    event = client.unmarshal_event_response(message)
                except ValueError:
                    # An event type this version of `armada_client` does not
                    # know, e.g. from a newer Armada server. Skipping it keeps
                    # the rest of the stream readable.
                    logger.warning(
                        "Skipping Armada event %r in job set %r that could not "
                        "be decoded",
                        message.id,
                        job_set_id,
                        exc_info=True,
                    )
                    continue
                yield event
        finally:
            if ready_task is not None:
                ready_task.cancel()
            client.unwatch_events(event_stream)


@task
async def get_job_set_events(
    armada_credentials: ArmadaCredentials,
    queue: str,
    job_set_id: str,
    from_message_id: str | None = None,
    max_events: int | None = None,
    event_types: Sequence[str] | None = None,
    timeout_seconds: float | None = 30,
) -> list[Event]:
    """Task for collecting events from an Armada job set's event stream.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        queue: The name of the Armada queue the job set was submitted to.
        job_set_id: The name of the Armada job set to read events for.
        from_message_id: If provided, collection resumes after this message ID.
        max_events: If provided, collection stops after this many matching events.
        event_types: If provided, only events of these types are collected,
            for example `["running", "succeeded"]`.
        timeout_seconds: How long to collect events for. Armada job set streams
            stay open indefinitely, so collection is bounded by either this
            timeout or `max_events`.

    Returns:
        A list of `Event` objects.

    Example:
        Collect the events emitted for a job set in the last 10 seconds:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.events import get_job_set_events

        @flow
        def armada_orchestrator():
            events = get_job_set_events(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                queue="prefect",
                job_set_id="my-job-set",
                timeout_seconds=10,
            )
        ```
    """
    wanted_types = set(event_types) if event_types else None
    events: list[Event] = []

    with anyio.move_on_after(timeout_seconds):
        async with aclosing(
            stream_job_set_events(
                armada_credentials=armada_credentials,
                queue=queue,
                job_set_id=job_set_id,
                from_message_id=from_message_id,
            )
        ) as event_stream:
            async for event in event_stream:
                if wanted_types is not None and event.type.value not in wanted_types:
                    continue
                events.append(event)
                if max_events is not None and len(events) >= max_events:
                    break

    return events


@task
async def wait_for_job_event(
    armada_credentials: ArmadaCredentials,
    queue: str,
    job_set_id: str,
    job_id: str,
    event_types: Sequence[str],
    timeout_seconds: float | None = None,
) -> Event | None:
    """Task for waiting until a specific Armada job emits one of several events.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        queue: The name of the Armada queue the job was submitted to.
        job_set_id: The name of the Armada job set the job belongs to.
        job_id: The ID of the job to wait for.
        event_types: The event types to wait for, for example
            `["succeeded", "failed", "cancelled"]`.
        timeout_seconds: How long to wait before giving up. If not provided, the
            task waits indefinitely.

    Returns:
        The matching `Event`, or `None` if the timeout elapsed first.

    Example:
        Wait for a job to succeed or fail:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.events import wait_for_job_event

        @flow
        def armada_orchestrator():
            event = wait_for_job_event(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                queue="prefect",
                job_set_id="my-job-set",
                job_id="01hqk8m0z6z9jz3q0k9pz9x5nb",
                event_types=["succeeded", "failed"],
                timeout_seconds=600,
            )
        ```
    """
    wanted_types = set(event_types)
    matched: Event | None = None

    with anyio.move_on_after(timeout_seconds):
        async with aclosing(
            stream_job_set_events(
                armada_credentials=armada_credentials,
                queue=queue,
                job_set_id=job_set_id,
            )
        ) as event_stream:
            async for event in event_stream:
                if getattr(event.message, "job_id", None) != job_id:
                    continue
                if event.type.value in wanted_types:
                    matched = event
                    break

    return matched
