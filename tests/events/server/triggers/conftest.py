from typing import Callable, List, Tuple, Union
from unittest import mock

import pytest

from prefect.server.events import messaging, triggers
from prefect.server.events.schemas.automations import Firing


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


@pytest.fixture
def assert_acted_with(
    act: mock.AsyncMock,
) -> Callable[[Union[Firing, List[Firing]]], None]:
    def assertion(expected: Union[Firing, List[Firing]]):
        if not isinstance(expected, list):
            expected = [expected]

        assert act.await_count == len(expected)
        actuals: list[Firing] = [args[0][0] for args in act.await_args_list]
        for actual in actuals:
            assert isinstance(actual, Firing)

        dumped_actuals = [actual.model_dump(exclude={"id"}) for actual in actuals]
        dumped_expected = [exp.model_dump(exclude={"id"}) for exp in expected]
        for exp in dumped_expected:
            assert exp in dumped_actuals

    return assertion
