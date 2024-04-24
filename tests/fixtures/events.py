import pytest

from prefect.server.events.clients import AssertingEventsClient


@pytest.fixture
def clean_asserting_events_client():
    AssertingEventsClient.last = None
    AssertingEventsClient.all.clear()


@pytest.fixture(autouse=True)
def workspace_events_client(
    clean_asserting_events_client: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "prefect.server.events.clients.PrefectServerEventsClient",
        AssertingEventsClient,
    )
    monkeypatch.setattr(
        "prefect.server.events.actions.PrefectServerEventsClient",
        AssertingEventsClient,
    )
    monkeypatch.setattr(
        "prefect.server.orchestration.instrumentation_policies.PrefectServerEventsClient",
        AssertingEventsClient,
    )
    monkeypatch.setattr(
        "prefect.server.models.deployments.PrefectServerEventsClient",
        AssertingEventsClient,
    )
