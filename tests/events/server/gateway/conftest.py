from uuid import uuid4

import pendulum
import pytest
from prefect._vendor.fastapi import FastAPI
from prefect._vendor.fastapi.testclient import TestClient

from prefect.server.events.schemas.events import Event, Resource


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
        occurred=pendulum.now("UTC"),
        event="was.radical",
        resource=Resource(__root__={"prefect.resource.id": "my.resources"}),
        payload={"hello": "world"},
        id=uuid4(),
    )


@pytest.fixture
def event2() -> Event:
    return Event(
        occurred=pendulum.now("UTC"),
        event="was.super.awesome",
        resource=Resource(__root__={"prefect.resource.id": "my.resources"}),
        payload={"goodbye": "moon"},
        id=uuid4(),
    )
