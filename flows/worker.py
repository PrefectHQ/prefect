import asyncio
import subprocess
import sys
from threading import Thread
from typing import List

from prefect.events import Event
from prefect.events.clients import get_events_subscriber
from prefect.events.filters import EventFilter, EventNameFilter, EventOccurredFilter
from prefect.types._datetime import now


async def watch_worker_events(events: List[Event]):
    """Watch for worker start/stop events and collect them"""
    async with get_events_subscriber(
        filter=EventFilter(
            event=EventNameFilter(prefix=["prefect.worker."]),
            occurred=EventOccurredFilter(since=now()),
        )
    ) as events_subscriber:
        async for event in events_subscriber:
            events.append(event)


def run_event_listener(events: List[Event]):
    """Run the async event listener in a thread"""
    asyncio.run(watch_worker_events(events))


def main():
    events: List[Event] = []

    listener_thread = Thread(target=run_event_listener, args=(events,), daemon=True)
    listener_thread.start()

    subprocess.check_call(
        ["python", "-m", "pip", "install", "prefect-kubernetes>=0.5.0"],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    try:
        subprocess.check_output(
            ["prefect", "work-pool", "delete", "test-worker-pool"],
        )
    except subprocess.CalledProcessError:
        pass

    try:
        subprocess.check_output(
            ["prefect", "work-pool", "create", "test-worker-pool", "-t", "nonsense"],
        )
    except subprocess.CalledProcessError as e:
        # Check that the error message contains kubernetes worker type
        for type in ["process", "kubernetes"]:
            assert type in str(e.output), (
                f"Worker type {type!r} missing from output {e.output}"
            )

    subprocess.check_call(
        ["prefect", "work-pool", "create", "test-worker-pool", "-t", "kubernetes"],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    subprocess.check_call(
        [
            "prefect",
            "worker",
            "start",
            "-p",
            "test-worker-pool",
            "-t",
            "kubernetes",
            "--run-once",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    subprocess.check_call(
        ["python", "-m", "pip", "uninstall", "prefect-kubernetes", "-y"],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    subprocess.check_call(
        ["prefect", "--no-prompt", "work-pool", "delete", "test-worker-pool"],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    worker_events = [e for e in events if e.event.startswith("prefect.worker.")]
    assert len(worker_events) == 2, (
        f"Expected 2 worker events, got {len(worker_events)}"
    )

    start_events = [e for e in worker_events if e.event == "prefect.worker.started"]
    stop_events = [e for e in worker_events if e.event == "prefect.worker.stopped"]

    assert len(start_events) == 1, "Expected 1 worker start event"
    assert len(stop_events) == 1, "Expected 1 worker stop event"

    print("Captured expected worker start and stop events!")

    assert stop_events[0].follows == start_events[0].id, (
        "Stop event should follow start event"
    )


if __name__ == "__main__":
    main()
