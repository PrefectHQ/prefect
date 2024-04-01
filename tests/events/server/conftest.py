from typing import Optional, Union

import pendulum
import pytest
from pendulum.tz.timezone import Timezone

from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.utilities.messaging import Message


@pytest.fixture
def frozen_time(monkeypatch: pytest.MonkeyPatch) -> pendulum.DateTime:
    frozen = pendulum.now("UTC")

    def frozen_time(tz: Optional[Union[str, Timezone]] = None):
        if tz is None:
            return frozen
        return frozen.in_timezone(tz)

    monkeypatch.setattr(pendulum, "now", frozen_time)
    return frozen


def assert_message_represents_event(message: Message, event: ReceivedEvent):
    """Confirms that the message adequately represents the event"""
    assert message.data
    assert ReceivedEvent.parse_raw(message.data) == event
    assert message.attributes
    assert message.attributes["id"] == str(event.id)
    assert message.attributes["event"] == event.event
