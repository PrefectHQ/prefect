from datetime import timedelta
from typing import Any, Dict, List, Optional, Sequence, Union
from uuid import uuid4

import pendulum
import pydantic
import pytest
from pendulum.datetime import DateTime
from pendulum.tz.timezone import Timezone
from sqlalchemy.ext.asyncio import AsyncSession

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic
else:
    import pydantic

from prefect.server.database.interface import PrefectDBInterface
from prefect.server.events import ResourceSpecification, actions
from prefect.server.events.schemas.automations import (
    Automation,
    EventTrigger,
    Posture,
    TriggeredAction,
)
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


@pytest.fixture
def automations_session(session: AsyncSession) -> AsyncSession:
    # pass through the nebula session
    return session


@pytest.fixture
def arachnophobia() -> Automation:
    return Automation(
        name="React immediately to spiders",
        trigger=EventTrigger(
            expect={"animal.walked"},
            match={
                "class": "Arachnida",
                "order": "Araneae",
            },
            posture=Posture.Reactive,
            threshold=1,
        ),
        actions=[actions.DoNothing()],
    )


@pytest.fixture
def daddy_long_legs_walked(start_of_test: DateTime) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=1),
        event="animal.walked",
        resource={
            "kingdom": "Animalia",
            "phylum": "Arthropoda",
            "class": "Arachnida",
            "order": "Araneae",
            "family": "Pholcidae",
            "genus": "Pholcus",
            "species": "phalangioides",
            "prefect.resource.id": "daddy-long-legs",
        },
        id=uuid4(),
    )


@pytest.fixture
def email_me_when_that_dang_spider_comes(
    arachnophobia: Automation,
    daddy_long_legs_walked: ReceivedEvent,
) -> TriggeredAction:
    return TriggeredAction(
        automation=arachnophobia,
        triggered=pendulum.now("UTC"),
        triggering_labels={"hello": "world"},
        triggering_event=daddy_long_legs_walked,
        action=arachnophobia.actions[0],
    )


@pytest.fixture
async def some_workspace_automations(
    db: PrefectDBInterface, automations_session: AsyncSession
) -> Sequence[Automation]:
    uninteresting_kwargs: Dict[str, Any] = dict(
        trigger=EventTrigger(
            expect=("things.happened",),
            match=ResourceSpecification.parse_obj(
                {"prefect.resource.id": "some-resource"}
            ),
            match_related=ResourceSpecification.parse_obj({}),
            posture=Posture.Reactive,
            threshold=1,
            within=timedelta(seconds=10),
        ),
        actions=[actions.DoNothing()],
    )

    automations = [
        db.Automation(
            id=uuid4(),
            name="automation 1",
            **uninteresting_kwargs,
        ),
        db.Automation(
            id=uuid4(),
            name="automation 2",
            **uninteresting_kwargs,
        ),
        db.Automation(
            id=uuid4(),
            name="automation 3",
            **uninteresting_kwargs,
        ),
    ]

    automations_session.add_all(automations)
    await automations_session.flush()
    return pydantic.parse_obj_as(List[Automation], automations)


def assert_message_represents_event(message: Message, event: ReceivedEvent):
    """Confirms that the message adequately represents the event"""
    assert message.data
    assert ReceivedEvent.parse_raw(message.data) == event
    assert message.attributes
    assert message.attributes["id"] == str(event.id)
    assert message.attributes["event"] == event.event
