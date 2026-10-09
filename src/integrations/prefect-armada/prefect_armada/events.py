"""Module to define tasks and helpers for observing Armada job set events."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from contextlib import aclosing

import anyio
from armada_client.event import Event

from prefect import task
from prefect_armada.credentials import ArmadaCredentials


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
    async with armada_credentials.get_client() as client:
        event_stream = await client.get_job_events_stream(
            queue=queue,
            job_set_id=job_set_id,
            from_message_id=from_message_id,
        )
        try:
            async for message in event_stream:
                yield client.unmarshal_event_response(message)
        finally:
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
