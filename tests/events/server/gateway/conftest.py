import datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from prefect.server.events.schemas.events import Event, ReceivedEvent, Resource
from prefect.types._datetime import now


@pytest.fixture
def events_app(app: FastAPI) -> FastAPI:
    return app


@pytest.fixture
def test_client(events_app: FastAPI) -> TestClient:
    # We typically use the httpx.AsyncClient with an async ASGI transport for testing,
    # but for tests that involve websockets, we need to use the FastAPI TestClient
    return TestClient(events_app)


@pytest.fixture
def event1() -> Event:
    return Event(
        occurred=now("UTC"),
        event="was.radical",
        resource=Resource.model_validate({"prefect.resource.id": "my.resources"}),
        payload={"hello": "world"},
        id=uuid4(),
    )


@pytest.fixture
def event2() -> Event:
    return Event(
        occurred=now("UTC"),
        event="was.super.awesome",
        resource=Resource.model_validate({"prefect.resource.id": "my.resources"}),
        payload={"goodbye": "moon"},
        id=uuid4(),
    )


@pytest.fixture
def received_event1(event1: Event) -> ReceivedEvent:
    return event1.receive()


@pytest.fixture
def received_event2(
    event2: Event,
) -> ReceivedEvent:
    return event2.receive()


@pytest.fixture
def old_event1() -> ReceivedEvent:
    return Event(
        occurred=now("UTC") - datetime.timedelta(seconds=30),
        event="was.radical",
        resource=Resource.model_validate({"prefect.resource.id": "my.resources"}),
        payload={"hello": "world"},
        id=uuid4(),
    ).receive()


@pytest.fixture
def old_event2() -> ReceivedEvent:
    return Event(
        occurred=now("UTC") - datetime.timedelta(seconds=15),
        event="was.super.awesome",
        resource=Resource.model_validate({"prefect.resource.id": "my.resources"}),
        payload={"goodbye": "moon"},
        id=uuid4(),
    ).receive()
