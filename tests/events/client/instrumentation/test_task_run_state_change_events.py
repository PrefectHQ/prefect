from pathlib import Path
from typing import Any

import pytest

from prefect import flow, task
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import State
from prefect.events.clients import AssertingEventsClient
from prefect.events.schemas.events import Resource
from prefect.events.worker import EventsWorker
from prefect.filesystems import LocalFileSystem
from prefect.task_worker import TaskWorker
from prefect.types._datetime import parse_datetime


@pytest.mark.usefixtures("reset_worker_events")
async def test_task_state_change_happy_path(
    asserting_events_worker: EventsWorker,
    prefect_client: PrefectClient,
    events_pipeline: Any,
):
    @task
    def happy_little_tree():
        return "🌳"

    @flow
    def happy_path():
        return happy_little_tree(return_state=True)

    flow_state: State[State[str]] = happy_path(return_state=True)

    await events_pipeline.process_events(dequeue_events=False)

    task_state: State[str] = await flow_state.result()
    task_run_id = task_state.state_details.task_run_id

    task_run = await prefect_client.read_task_run(task_run_id)
    task_run_states = await prefect_client.read_task_run_states(task_run_id)

    await asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    events = [
        event
        for event in asserting_events_worker._client.events
        if event.event.startswith("prefect.task-run.")
    ]
    assert len(task_run_states) == len(events) == 3

    pending, running, completed = events

    assert pending.event == "prefect.task-run.Pending"
    assert pending.id == task_run_states[0].id
    assert pending.occurred == task_run_states[0].timestamp
    assert pending.resource == Resource(
        {
            "prefect.resource.id": f"prefect.task-run.{task_run.id}",
            "prefect.resource.name": task_run.name,
            "prefect.run-count": "0",
            "prefect.state-message": "",
            "prefect.state-type": "PENDING",
            "prefect.state-name": "Pending",
            "prefect.state-timestamp": task_run_states[0].timestamp.isoformat(),
            "prefect.orchestration": "client",
        }
    )
    assert (
        parse_datetime(pending.payload["task_run"].pop("expected_start_time"))
        == task_run.expected_start_time
    )
    assert pending.payload["task_run"].pop("task_key").startswith("happy_little_tree")
    assert pending.payload == {
        "initial_state": None,
        "intended": {"from": None, "to": "PENDING"},
        "validated_state": {
            "type": "PENDING",
            "name": "Pending",
            "message": "",
            "state_details": {},
            "data": None,
        },
        "task_run": {
            "dynamic_key": task_run.dynamic_key,
            "empirical_policy": {
                "max_retries": 0,
                "retries": 0,
                "retry_delay": 0,
                "retry_delay_seconds": 0.0,
            },
            "flow_run_run_count": 0,
            "name": task_run.name,
            "run_count": 0,
            "tags": [],
            "labels": {},
            "task_inputs": {},
            "total_run_time": 0.0,
        },
    }

    assert running.event == "prefect.task-run.Running"
    assert running.id == task_run_states[1].id
    assert running.occurred == task_run_states[1].timestamp
    assert running.resource == Resource(
        {
            "prefect.resource.id": f"prefect.task-run.{task_run.id}",
            "prefect.resource.name": task_run.name,
            "prefect.run-count": "1",
            "prefect.state-message": "",
            "prefect.state-type": "RUNNING",
            "prefect.state-name": "Running",
            "prefect.state-timestamp": task_run_states[1].timestamp.isoformat(),
            "prefect.orchestration": "client",
        }
    )
    assert (
        parse_datetime(running.payload["task_run"].pop("expected_start_time"))
        == task_run.expected_start_time
    )
    assert running.payload["task_run"].pop("task_key").startswith("happy_little_tree")
    assert (
        parse_datetime(running.payload["task_run"].pop("start_time"))
        == task_run.start_time
    )
    assert running.payload == {
        "intended": {"from": "PENDING", "to": "RUNNING"},
        "initial_state": {
            "type": "PENDING",
            "name": "Pending",
            "message": "",
            "state_details": {},
        },
        "validated_state": {
            "type": "RUNNING",
            "name": "Running",
            "message": "",
            "state_details": {},
            "data": None,
        },
        "task_run": {
            "dynamic_key": task_run.dynamic_key,
            "empirical_policy": {
                "max_retries": 0,
                "retries": 0,
                "retry_delay": 0,
                "retry_delay_seconds": 0.0,
            },
            "flow_run_run_count": 1,
            "name": task_run.name,
            "run_count": 1,
            "tags": [],
            "labels": {},
            "task_inputs": {},
            "total_run_time": 0.0,
        },
    }

    assert completed.event == "prefect.task-run.Completed"
    assert completed.id == task_run_states[2].id
    assert completed.occurred == task_run_states[2].timestamp
    assert completed.resource == Resource(
        {
            "prefect.resource.id": f"prefect.task-run.{task_run.id}",
            "prefect.resource.name": task_run.name,
            "prefect.run-count": "1",
            "prefect.state-message": "",
            "prefect.state-type": "COMPLETED",
            "prefect.state-name": "Completed",
            "prefect.state-timestamp": task_run_states[2].timestamp.isoformat(),
            "prefect.orchestration": "client",
        }
    )
    assert (
        parse_datetime(completed.payload["task_run"].pop("expected_start_time"))
        == task_run.expected_start_time
    )
    assert completed.payload["task_run"].pop("task_key").startswith("happy_little_tree")
    assert (
        parse_datetime(completed.payload["task_run"].pop("start_time"))
        == task_run.start_time
    )
    assert (
        parse_datetime(completed.payload["task_run"].pop("end_time"))
        == task_run.end_time
    )
    assert completed.payload["task_run"].pop("total_run_time") > 0.0
    assert completed.payload == {
        "intended": {"from": "RUNNING", "to": "COMPLETED"},
        "initial_state": {
            "type": "RUNNING",
            "name": "Running",
            "message": "",
            "state_details": {},
        },
        "validated_state": {
            "type": "COMPLETED",
            "name": "Completed",
            "message": "",
            "state_details": {},
            "data": None,
        },
        "task_run": {
            "dynamic_key": task_run.dynamic_key,
            "empirical_policy": {
                "max_retries": 0,
                "retries": 0,
                "retry_delay": 0,
                "retry_delay_seconds": 0.0,
            },
            "flow_run_run_count": 1,
            "name": task_run.name,
            "run_count": 1,
            "tags": [],
            "labels": {},
            "task_inputs": {},
        },
    }


@pytest.mark.usefixtures("reset_worker_events")
async def test_task_state_change_task_failure(
    asserting_events_worker: EventsWorker,
    prefect_client: PrefectClient,
    events_pipeline: Any,
):
    @task
    def happy_little_tree():
        raise ValueError("Here's a happy little accident.")

    @flow
    def happy_path():
        return happy_little_tree(return_state=True)

    flow_state = happy_path(return_state=True)
    await events_pipeline.process_events(dequeue_events=False)

    task_state = await flow_state.result(raise_on_failure=False)
    task_run_id = task_state.state_details.task_run_id

    task_run = await prefect_client.read_task_run(task_run_id)
    task_run_states = await prefect_client.read_task_run_states(task_run_id)

    await asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    events = [
        event
        for event in asserting_events_worker._client.events
        if event.event.startswith("prefect.task-run.")
    ]
    assert len(task_run_states) == len(events) == 3

    pending, running, failed = events

    assert pending.event == "prefect.task-run.Pending"
    assert pending.id == task_run_states[0].id
    assert pending.occurred == task_run_states[0].timestamp
    assert pending.resource == Resource(
        {
            "prefect.resource.id": f"prefect.task-run.{task_run.id}",
            "prefect.resource.name": task_run.name,
            "prefect.run-count": "0",
            "prefect.state-message": "",
            "prefect.state-type": "PENDING",
            "prefect.state-name": "Pending",
            "prefect.state-timestamp": task_run_states[0].timestamp.isoformat(),
            "prefect.orchestration": "client",
        }
    )
    assert (
        parse_datetime(pending.payload["task_run"].pop("expected_start_time"))
        == task_run.expected_start_time
    )
    assert pending.payload["task_run"].pop("task_key").startswith("happy_little_tree")
    assert pending.payload == {
        "initial_state": None,
        "intended": {"from": None, "to": "PENDING"},
        "validated_state": {
            "type": "PENDING",
            "name": "Pending",
            "message": "",
            "state_details": {},
            "data": None,
        },
        "task_run": {
            "dynamic_key": task_run.dynamic_key,
            "empirical_policy": {
                "max_retries": 0,
                "retries": 0,
                "retry_delay": 0,
                "retry_delay_seconds": 0.0,
            },
            "flow_run_run_count": 0,
            "name": task_run.name,
            "run_count": 0,
            "tags": [],
            "labels": {},
            "task_inputs": {},
            "total_run_time": 0.0,
        },
    }

    assert running.event == "prefect.task-run.Running"
    assert running.id == task_run_states[1].id
    assert running.occurred == task_run_states[1].timestamp
    assert running.resource == Resource(
        {
            "prefect.resource.id": f"prefect.task-run.{task_run.id}",
            "prefect.resource.name": task_run.name,
            "prefect.run-count": "1",
            "prefect.state-message": "",
            "prefect.state-type": "RUNNING",
            "prefect.state-name": "Running",
            "prefect.state-timestamp": task_run_states[1].timestamp.isoformat(),
            "prefect.orchestration": "client",
        }
    )
    assert (
        parse_datetime(running.payload["task_run"].pop("expected_start_time"))
        == task_run.expected_start_time
    )
    assert (
        parse_datetime(running.payload["task_run"].pop("start_time"))
        == task_run.start_time
    )
    assert running.payload["task_run"].pop("task_key").startswith("happy_little_tree")
    assert running.payload == {
        "intended": {"from": "PENDING", "to": "RUNNING"},
        "initial_state": {
            "type": "PENDING",
            "name": "Pending",
            "message": "",
            "state_details": {},
        },
        "validated_state": {
            "type": "RUNNING",
            "name": "Running",
            "message": "",
            "state_details": {},
            "data": None,
        },
        "task_run": {
            "dynamic_key": task_run.dynamic_key,
            "empirical_policy": {
                "max_retries": 0,
                "retries": 0,
                "retry_delay": 0,
                "retry_delay_seconds": 0.0,
            },
            "flow_run_run_count": 1,
            "name": task_run.name,
            "run_count": 1,
            "tags": [],
            "labels": {},
            "task_inputs": {},
            "total_run_time": 0.0,
        },
    }

    assert failed.event == "prefect.task-run.Failed"
    assert failed.id == task_run_states[2].id
    assert failed.occurred == task_run_states[2].timestamp
    assert failed.resource == Resource(
        {
            "prefect.resource.id": f"prefect.task-run.{task_run.id}",
            "prefect.resource.name": task_run.name,
            "prefect.run-count": "1",
            "prefect.state-message": (
                "Task run encountered an exception ValueError: "
                "Here's a happy little accident."
            ),
            "prefect.state-type": "FAILED",
            "prefect.state-name": "Failed",
            "prefect.state-timestamp": task_run_states[2].timestamp.isoformat(),
            "prefect.orchestration": "client",
        }
    )
    assert (
        parse_datetime(failed.payload["task_run"].pop("expected_start_time"))
        == task_run.expected_start_time
    )
    assert failed.payload["task_run"].pop("task_key").startswith("happy_little_tree")
    assert (
        parse_datetime(failed.payload["task_run"].pop("start_time"))
        == task_run.start_time
    )
    assert (
        parse_datetime(failed.payload["task_run"].pop("end_time")) == task_run.end_time
    )
    assert failed.payload["task_run"].pop("total_run_time") > 0
    assert failed.payload == {
        "intended": {"from": "RUNNING", "to": "FAILED"},
        "initial_state": {
            "type": "RUNNING",
            "name": "Running",
            "message": "",
            "state_details": {},
        },
        "validated_state": {
            "type": "FAILED",
            "name": "Failed",
            "message": (
                "Task run encountered an exception ValueError: "
                "Here's a happy little accident."
            ),
            "state_details": {"retriable": False},
            "data": None,
        },
        "task_run": {
            "dynamic_key": task_run.dynamic_key,
            "empirical_policy": {
                "max_retries": 0,
                "retries": 0,
                "retry_delay": 0,
                "retry_delay_seconds": 0.0,
            },
            "flow_run_run_count": 1,
            "name": task_run.name,
            "run_count": 1,
            "tags": [],
            "labels": {},
            "task_inputs": {},
        },
    }


@pytest.mark.usefixtures("reset_worker_events")
async def test_background_task_state_changes(
    asserting_events_worker: EventsWorker,
    prefect_client: PrefectClient,
    tmp_path: Path,
    events_pipeline: Any,
):
    storage = LocalFileSystem(basepath=str(tmp_path))
    await storage.save("test")

    @task(result_storage=storage)
    def foo():
        pass

    task_run_future = foo.apply_async()
    task_run = await prefect_client.read_task_run(task_run_future.task_run_id)

    await TaskWorker(foo).execute_task_run(task_run)
    await events_pipeline.process_events(dequeue_events=False)

    task_run_states = await prefect_client.read_task_run_states(
        task_run_future.task_run_id
    )

    await asserting_events_worker.drain()

    events = sorted(asserting_events_worker._client.events, key=lambda e: e.occurred)
    events = [e for e in events if e.event.startswith("prefect.task-run.")]

    assert len(task_run_states) == len(events) == 4

    assert [e.event for e in events] == [
        "prefect.task-run.Scheduled",
        "prefect.task-run.Pending",
        "prefect.task-run.Running",
        "prefect.task-run.Completed",
    ]

    observed = [
        (e.payload["intended"]["from"], e.payload["intended"]["to"])
        for e in events
        if e.event.startswith("prefect.task-run.")
    ]
    expected = [
        (None, "SCHEDULED"),
        ("SCHEDULED", "PENDING"),
        ("PENDING", "RUNNING"),
        ("RUNNING", "COMPLETED"),
    ]
    assert observed == expected


async def test_task_state_change_includes_tags_as_related_resources(
    asserting_events_worker: EventsWorker,
    prefect_client: PrefectClient,
    events_pipeline: Any,
):
    @task(tags=["tag-c", "tag-a", "tag-b"])
    def tagged_task():
        return "tagged"

    @flow
    def flow_with_tagged_task():
        return tagged_task(return_state=True)

    flow_state: State[State[str]] = flow_with_tagged_task(return_state=True)

    await events_pipeline.process_events(dequeue_events=False)

    task_state: State[str] = await flow_state.result()
    task_run_id = task_state.state_details.task_run_id

    task_run = await prefect_client.read_task_run(task_run_id)
    assert sorted(task_run.tags) == ["tag-a", "tag-b", "tag-c"]

    await asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    events = [
        event
        for event in asserting_events_worker._client.events
        if event.event.startswith("prefect.task-run.")
    ]
    assert len(events) == 3

    # Check all three events have tags as related resources
    for event in events:
        tag_related = [r for r in event.related if r["prefect.resource.role"] == "tag"]
        assert len(tag_related) == 3

        # Verify tags are sorted
        tag_ids = [r["prefect.resource.id"] for r in tag_related]
        assert tag_ids == [
            "prefect.tag.tag-a",
            "prefect.tag.tag-b",
            "prefect.tag.tag-c",
        ]

        # Verify each tag has the correct structure
        for tag_resource in tag_related:
            assert tag_resource["prefect.resource.role"] == "tag"
            assert tag_resource["prefect.resource.id"].startswith("prefect.tag.")


async def test_task_state_change_with_no_tags_has_no_tag_related_resources(
    asserting_events_worker: EventsWorker,
    prefect_client: PrefectClient,
    events_pipeline: Any,
):
    @task
    def untagged_task():
        return "untagged"

    @flow
    def flow_with_untagged_task():
        return untagged_task(return_state=True)

    flow_state: State[State[str]] = flow_with_untagged_task(return_state=True)

    await events_pipeline.process_events(dequeue_events=False)

    await flow_state.result()

    await asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    events = [
        event
        for event in asserting_events_worker._client.events
        if event.event.startswith("prefect.task-run.")
    ]
    assert len(events) == 3

    # Check no events have tag related resources
    for event in events:
        tag_related = [r for r in event.related if r["prefect.resource.role"] == "tag"]
        assert len(tag_related) == 0


async def test_apply_async_emits_scheduled_event(
    asserting_events_worker: Any,
    prefect_client: PrefectClient,
):
    @task
    def happy_little_tree():
        return "🌳"

    future = happy_little_tree.apply_async()
    task_run_id = future.task_run_id

    await asserting_events_worker.drain()

    events = asserting_events_worker._client.events
    assert len(events) == 1
    scheduled = events[0]

    task_run = await prefect_client.read_task_run(task_run_id)
    assert task_run
    assert task_run.id == task_run_id
    task_run_states = await prefect_client.read_task_run_states(task_run_id)
    assert len(task_run_states) == 1

    assert scheduled.event == "prefect.task-run.Scheduled"
    assert scheduled.id == task_run_states[0].id
    assert scheduled.occurred == task_run_states[0].timestamp
    assert scheduled.resource == Resource(
        {
            "prefect.resource.id": f"prefect.task-run.{task_run_id}",
            "prefect.resource.name": task_run.name,
            "prefect.run-count": "0",
            "prefect.state-message": "",
            "prefect.state-type": "SCHEDULED",
            "prefect.state-name": "Scheduled",
            "prefect.state-timestamp": task_run_states[0].timestamp.isoformat(),
            "prefect.orchestration": "client",
        }
    )

    assert (
        parse_datetime(
            scheduled.payload["validated_state"]["state_details"].pop("scheduled_time")
        )
        == task_run.expected_start_time
    )
    assert (
        parse_datetime(scheduled.payload["task_run"].pop("next_scheduled_start_time"))
        == task_run.next_scheduled_start_time
    )
    assert (
        parse_datetime(scheduled.payload["task_run"].pop("expected_start_time"))
        == task_run.expected_start_time
    )

    assert scheduled.payload["task_run"].pop("name").startswith("happy_little_tree")
    assert (
        scheduled.payload["task_run"].pop("dynamic_key").startswith("happy_little_tree")
    )
    assert scheduled.payload["task_run"].pop("task_key").startswith("happy_little_tree")
    assert scheduled.payload == {
        "initial_state": None,
        "intended": {"from": None, "to": "SCHEDULED"},
        "validated_state": {
            "type": "SCHEDULED",
            "name": "Scheduled",
            "message": "",
            "state_details": {
                "pause_reschedule": False,
                "untrackable_result": False,
                "deferred": True,
            },
            "data": None,
        },
        "task_run": {
            "empirical_policy": {
                "max_retries": 0,
                "retries": 0,
                "retry_delay": 0,
                "retry_delay_seconds": 0.0,
            },
            "flow_run_run_count": 0,
            "run_count": 0,
            "tags": [],
            "labels": {},
            "task_inputs": {},
            "total_run_time": 0.0,
        },
    }
