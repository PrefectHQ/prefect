import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from prefect.events.clients import AssertingEventsClient, EventsClient
from prefect.events.dependencies import events_client
from prefect.events.schemas import Event


@pytest.fixture
def app(example_event: Event) -> FastAPI:
    app = FastAPI()

    @app.post("/do-things/")
    async def do_something_cool(client: EventsClient = Depends(events_client)) -> str:
        await client.emit(example_event)
        return client.__class__.__name__

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_does_nothing_and_does_it_quietly_by_default(client: TestClient):
    response = client.post("/do-things/")
    assert response.status_code == 200, response.text
    assert response.json() == "NullEventsClient"


@pytest.fixture
def asserting_client(app: FastAPI) -> AssertingEventsClient:
    client = AssertingEventsClient()

    def asserting_events_client() -> EventsClient:
        return client

    app.dependency_overrides[events_client] = asserting_events_client
    return client


@pytest.fixture
def test_dependency_can_be_overridden(
    client: TestClient,
    asserting_client: AssertingEventsClient,
    example_event: Event,
):
    response = client.post("/do-things/")
    assert response.status_code == 200, response.text
    assert response.json() == "AssertingEventsClient"

    assert asserting_client.events == [example_event]
