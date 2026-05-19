import asyncio
import subprocess
import sys
import time
from threading import Event as ThreadingEvent
from threading import Thread
from typing import List
from uuid import uuid4

import uv

from prefect.events import Event
from prefect.events.clients import get_events_subscriber
from prefect.events.filters import EventFilter, EventNameFilter, EventOccurredFilter
from prefect.types._datetime import now


async def watch_worker_events(events: List[Event], ready: ThreadingEvent):
    """Watch for worker start/stop events and collect them"""
    async with get_events_subscriber(
        filter=EventFilter(
            event=EventNameFilter(prefix=["prefect.worker."]),
            occurred=EventOccurredFilter(since=now()),
        )
    ) as events_subscriber:
        ready.set()
        async for event in events_subscriber:
            events.append(event)


def run_event_listener(
    events: List[Event], ready: ThreadingEvent, errors: List[BaseException]
):
    """Run the async event listener in a thread"""
    try:
        asyncio.run(watch_worker_events(events, ready))
    except BaseException as exc:
        errors.append(exc)
        ready.set()


def _wait_for(predicate, *, timeout: float, message: str, interval: float = 0.5):
    """Poll until predicate returns a truthy value or timeout is reached."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    raise AssertionError(message)


def test_worker():
    WORKER_NAME = f"test-worker-{uuid4()}"  # noqa: F821
    events: List[Event] = []
    listener_errors: List[BaseException] = []
    listener_ready = ThreadingEvent()

    listener_thread = Thread(
        target=run_event_listener,
        args=(events, listener_ready, listener_errors),
        daemon=True,
    )
    listener_thread.start()
    assert listener_ready.wait(timeout=10), "Worker event listener did not start"
    assert not listener_errors, f"Worker event listener failed: {listener_errors[0]!r}"

    # Wait for the websocket subscription to be active before starting the
    # worker, otherwise events emitted before the subscription connects are lost.
    assert listener_ready.wait(timeout=30), "Event listener did not become ready"

    try:
        subprocess.check_output(
            [
                uv.find_uv_bin(),
                "run",
                "--isolated",
                "prefect",
                "work-pool",
                "delete",
                "test-worker-pool",
            ],
        )
    except subprocess.CalledProcessError:
        pass

    try:
        subprocess.check_output(
            [
                uv.find_uv_bin(),
                "run",
                "--isolated",
                "--with",
                "prefect-kubernetes>=0.5.0",
                "prefect",
                "work-pool",
                "create",
                "test-worker-pool",
                "-t",
                "nonsense",
            ],
        )
    except subprocess.CalledProcessError as e:
        # Check that the error message contains kubernetes worker type
        for type in ["process", "kubernetes"]:
            assert type in str(e.output), (
                f"Worker type {type!r} missing from output {e.output}"
            )

    subprocess.check_call(
        [
            uv.find_uv_bin(),
            "run",
            "--isolated",
            "prefect",
            "work-pool",
            "create",
            "test-worker-pool",
            "-t",
            "kubernetes",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    subprocess.check_call(
        [
            uv.find_uv_bin(),
            "run",
            "--isolated",
            "--with",
            "prefect-kubernetes",
            "prefect",
            "worker",
            "start",
            "-p",
            "test-worker-pool",
            "-t",
            "kubernetes",
            "-n",
            WORKER_NAME,
            "--run-once",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    subprocess.check_call(
        [
            uv.find_uv_bin(),
            "run",
            "--isolated",
            "prefect",
            "--no-prompt",
            "work-pool",
            "delete",
            "test-worker-pool",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    def _get_worker_events():
        return [
            e
            for e in events
            if e.event.startswith("prefect.worker.") and e.resource.name == WORKER_NAME
        ]

    deadline = time.monotonic() + 10
    worker_events = []
    while time.monotonic() < deadline:
        assert not listener_errors, (
            f"Worker event listener failed while waiting for events: {listener_errors[0]!r}"
        )
        worker_events = _get_worker_events()
        if len(worker_events) == 2:
            break
        time.sleep(0.1)

    assert len(worker_events) == 2, (
        f"Expected 2 worker events, got {len(worker_events)}"
    )

    # Poll for events — delivery via websocket may lag slightly behind the
    # worker subprocess exiting.
    worker_events = _wait_for(
        lambda: (evts := _get_worker_events()) and len(evts) >= 2 and evts,
        timeout=15,
        message=(
            f"Expected 2 worker events within timeout, got {len(_get_worker_events())}"
        ),
    )

    start_events = [e for e in worker_events if e.event == "prefect.worker.started"]
    stop_events = [e for e in worker_events if e.event == "prefect.worker.stopped"]

    assert len(start_events) == 1, "Expected 1 worker start event"
    assert len(stop_events) == 1, "Expected 1 worker stop event"

    print("Captured expected worker start and stop events!")

    assert stop_events[0].follows == start_events[0].id, (
        "Stop event should follow start event"
    )
