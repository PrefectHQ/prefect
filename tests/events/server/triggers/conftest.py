from typing import Tuple
from unittest import mock

import pytest

from prefect.server.events import messaging, triggers


@pytest.fixture(autouse=True)
async def reset_triggers(cleared_automations: None):
    await triggers.reset()
    yield
    await triggers.reset()


@pytest.fixture
async def reset_events_clock():
    await triggers.reset_events_clock()


@pytest.fixture
def actions_publish_mocks(
    monkeypatch: pytest.MonkeyPatch,
) -> Tuple[mock.MagicMock, mock.AsyncMock]:
    mock_create_publisher = mock.MagicMock(spec=messaging.create_actions_publisher)
    mock_publish = mock.AsyncMock()
    mock_create_publisher.return_value.__aenter__.return_value.publish_data = (
        mock_publish
    )

    monkeypatch.setattr(
        "prefect.server.events.messaging.create_actions_publisher",
        mock_create_publisher,
    )

    return mock_create_publisher, mock_publish


@pytest.fixture
def actions_publish(
    actions_publish_mocks: Tuple[mock.MagicMock, mock.AsyncMock],
) -> mock.AsyncMock:
    return actions_publish_mocks[1]


@pytest.fixture
def create_actions_publisher(
    actions_publish_mocks: Tuple[mock.MagicMock, mock.AsyncMock],
) -> mock.MagicMock:
    return actions_publish_mocks[0]
