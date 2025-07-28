import asyncio
import datetime
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncGenerator, Dict
from uuid import uuid4

import anyio
import pytest

from prefect import flow
from prefect.client.orchestration import get_client
from prefect.events import Event
from prefect.events.clients import get_events_client, get_events_subscriber
from prefect.events.filters import (
    EventFilter,
    EventNameFilter,
    EventOccurredFilter,
    EventResourceFilter,
)
from prefect.logging import get_run_logger
from prefect.types._datetime import now, parse_datetime

SERVER_VERSION = os.getenv("SERVER_VERSION")


@asynccontextmanager
async def create_or_replace_automation(
    automation: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    logger = get_run_logger()

    async with get_client() as prefect:
        # Clean up any older automations with the same name prefix
        response = await prefect._client.post("/automations/filter")
        response.raise_for_status()
        for existing in response.json():
            name = str(existing["name"])
            if name.startswith(automation["name"]):
                parsed_datetime = parse_datetime(existing["created"])
                assert isinstance(parsed_datetime, datetime.datetime)
                age = now("UTC") - parsed_datetime
                assert isinstance(age, timedelta)
                if age > timedelta(minutes=10):
                    logger.info(
                        "Deleting old automation %s (%s)",
                        existing["name"],
                        existing["id"],
                    )
                await prefect._client.delete(f"/automations/{existing['id']}")

        automation["name"] = f"{automation['name']}:{uuid4()}"

        response = await prefect._client.post("/automations/", json=automation)
        response.raise_for_status()

        automation = response.json()
        logger.info("Created automation %s (%s)", automation["name"], automation["id"])

        logger.info("Waiting 1s for the automation to be loaded the triggers services")
        await asyncio.sleep(1)

        try:
            yield automation
        finally:
            response = await prefect._client.delete(f"/automations/{automation['id']}")
            response.raise_for_status()


async def wait_for_event(
    listening: asyncio.Event, event: str, resource_id: str
) -> Event:
    logger = get_run_logger()

    filter = EventFilter(
        occurred=EventOccurredFilter(since=now("UTC")),
        event=EventNameFilter(name=[]),
        resource=EventResourceFilter(id=[resource_id]),
    )
    async with get_events_subscriber(filter=filter) as subscriber:
        listening.set()
        async for event in subscriber:
            logger.info(event)
            return event

    raise Exception("Disconnected without an event")


@flow
async def assess_reactive_automation():
    expected_resource = {"prefect.resource.id": f"integration:reactive:{uuid4()}"}
    async with create_or_replace_automation(
        {
            "name": "reactive-automation",
            "trigger": {
                "posture": "Reactive",
                "expect": ["integration.example.event"],
                "match": expected_resource,
                "threshold": 5,
                "within": 60,
            },
            "actions": [{"type": "do-nothing"}],
        }
    ) as automation:
        listening = asyncio.Event()
        listener = asyncio.create_task(
            wait_for_event(
                listening,
                "prefect.automation.triggered",
                f"prefect.automation.{automation['id']}",
            )
        )
        await listening.wait()

        async with get_events_client() as events:
            for i in range(5):
                await events.emit(
                    Event(
                        event="integration.example.event",
                        resource=expected_resource,
                        payload={"iteration": i},
                    )
                )

        # Wait until we see the automation triggered event, or fail if it takes longer
        # than 60 seconds.  The reactive trigger should fire almost immediately.
        try:
            with anyio.fail_after(60):
                await listener
        except asyncio.TimeoutError:
            raise Exception("Reactive automation did not trigger in 60s")


@flow
async def assess_proactive_automation():
    expected_resource = {"prefect.resource.id": f"integration:proactive:{uuid4()}"}
    async with create_or_replace_automation(
        {
            "name": "proactive-automation",
            "trigger": {
                "posture": "Proactive",
                "expect": ["integration.example.event"],
                # Doing it for_each resource ID should prevent it from firing endlessly
                # while the integration tests are _not_ running
                "for_each": ["prefect.resource.id"],
                "match": expected_resource,
                "threshold": 5,
                "within": 15,
            },
            "actions": [{"type": "do-nothing"}],
        }
    ) as automation:
        listening = asyncio.Event()
        listener = asyncio.create_task(
            wait_for_event(
                listening,
                "prefect.automation.triggered",
                f"prefect.automation.{automation['id']}",
            )
        )
        await listening.wait()

        async with get_events_client() as events:
            for i in range(2):  # not enough events to close the automation
                await events.emit(
                    Event(
                        event="integration.example.event",
                        resource=expected_resource,
                        payload={"iteration": i},
                    )
                )

        # Wait until we see the automation triggered event, or fail if it takes longer
        # than 60 seconds.  The proactive trigger should take a little over 15s to fire.
        try:
            with anyio.fail_after(60):
                await listener
        except asyncio.TimeoutError:
            raise Exception("Proactive automation did not trigger in 60s")


@flow
async def assess_compound_automation():
    expected_resource = {"prefect.resource.id": f"integration:compound:{uuid4()}"}
    async with create_or_replace_automation(
        {
            "name": "compound-automation",
            "trigger": {
                "type": "compound",
                "require": "all",
                "within": 60,
                "triggers": [
                    {
                        "posture": "Reactive",
                        "expect": ["integration.example.event.A"],
                        "match": expected_resource,
                        "threshold": 1,
                        "within": 0,
                    },
                    {
                        "posture": "Reactive",
                        "expect": ["integration.example.event.B"],
                        "match": expected_resource,
                        "threshold": 1,
                        "within": 0,
                    },
                ],
            },
            "actions": [{"type": "do-nothing"}],
        }
    ) as automation:
        listening = asyncio.Event()
        listener = asyncio.create_task(
            wait_for_event(
                listening,
                "prefect.automation.triggered",
                f"prefect.automation.{automation['id']}",
            )
        )
        await listening.wait()

        async with get_events_client() as events:
            await events.emit(
                Event(
                    event="integration.example.event.A",
                    resource=expected_resource,
                )
            )
            await events.emit(
                Event(
                    event="integration.example.event.B",
                    resource=expected_resource,
                )
            )

        # Wait until we see the automation triggered event, or fail if it takes longer
        # than 60 seconds.  The compound trigger should fire almost immediately.
        try:
            with anyio.fail_after(60):
                await listener
        except asyncio.TimeoutError:
            raise Exception("Compound automation did not trigger in 60s")


@flow
async def assess_sequence_automation():
    expected_resource = {"prefect.resource.id": f"integration:sequence:{uuid4()}"}
    async with create_or_replace_automation(
        {
            "name": "sequence-automation",
            "trigger": {
                "type": "sequence",
                "within": 60,
                "triggers": [
                    {
                        "posture": "Reactive",
                        "expect": ["integration.example.event.A"],
                        "match": expected_resource,
                        "threshold": 1,
                        "within": 0,
                    },
                    {
                        "posture": "Reactive",
                        "expect": ["integration.example.event.B"],
                        "match": expected_resource,
                        "threshold": 1,
                        "within": 0,
                    },
                ],
            },
            "actions": [{"type": "do-nothing"}],
        }
    ) as automation:
        listening = asyncio.Event()
        listener = asyncio.create_task(
            wait_for_event(
                listening,
                "prefect.automation.triggered",
                f"prefect.automation.{automation['id']}",
            )
        )
        await listening.wait()

        first = uuid4()
        second = uuid4()
        async with get_events_client() as events:
            await events.emit(
                Event(
                    id=first,
                    event="integration.example.event.A",
                    resource=expected_resource,
                )
            )

        get_run_logger().info("Waiting 1s to make sure the sequence is unambiguous")
        await asyncio.sleep(1)

        async with get_events_client() as events:
            await events.emit(
                Event(
                    id=second,
                    follows=first,
                    event="integration.example.event.B",
                    resource=expected_resource,
                )
            )

        # Wait until we see the automation triggered event, or fail if it takes longer
        # than 60 seconds.  The compound trigger should fire almost immediately.
        try:
            with anyio.fail_after(60):
                await listener
        except asyncio.TimeoutError:
            raise Exception("Sequence automation did not trigger in 60s")


@pytest.mark.skipif(
    SERVER_VERSION == "9.9.9+for.the.tests",
    reason="Prefect Cloud has its own automation assessment integration test, skipping",
)
async def test_reactive_automation():
    await assess_reactive_automation()


@pytest.mark.skipif(
    SERVER_VERSION == "9.9.9+for.the.tests",
    reason="Prefect Cloud has its own automation assessment integration test, skipping",
)
async def test_proactive_automation():
    await assess_proactive_automation()


@pytest.mark.skipif(
    SERVER_VERSION == "9.9.9+for.the.tests",
    reason="Prefect Cloud has its own automation assessment integration test, skipping",
)
async def test_compound_automation():
    await assess_compound_automation()


@pytest.mark.skipif(
    SERVER_VERSION == "9.9.9+for.the.tests",
    reason="Prefect Cloud has its own automation assessment integration test, skipping",
)
async def test_sequence_automation():
    await assess_sequence_automation()
