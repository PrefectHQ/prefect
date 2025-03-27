from datetime import timedelta
from typing import Any, Dict, List, Sequence, Tuple
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface
from prefect.server.events import ResourceSpecification, actions, messaging
from prefect.server.events.schemas.automations import (
    Automation,
    EventTrigger,
    Firing,
    Posture,
    TriggeredAction,
    TriggerState,
)
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.utilities.messaging import Message
from prefect.types import DateTime
from prefect.types._datetime import now
from prefect.utilities.pydantic import parse_obj_as


@pytest.fixture
def act(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock_act = AsyncMock()
    monkeypatch.setattr("prefect.server.events.triggers.act", mock_act)
    return mock_act


@pytest.fixture
def automations_session(session: AsyncSession) -> AsyncSession:
    # pass through the existing session
    return session


@pytest.fixture
async def cleared_buckets(db: PrefectDBInterface, automations_session: AsyncSession):
    await automations_session.execute(sa.delete(db.AutomationBucket))
    await automations_session.commit()


@pytest.fixture
async def cleared_automations():
    from prefect.server.events import triggers

    await triggers.reset()
    yield
    await triggers.reset()


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
def chonk_party() -> Automation:
    return Automation(
        name="Three woodchucks is worth throwing a party",
        trigger=EventTrigger(
            expect={"animal.walked"},
            match={
                "genus": "Marmota",
                "species": "monax",
            },
            posture=Posture.Reactive,
            threshold=3,
            within=timedelta(seconds=10),
        ),
        actions=[actions.DoNothing()],
    )


@pytest.fixture
def flow_run_pending_automation() -> Automation:
    return Automation(
        name="Flow Run Pending",
        trigger=EventTrigger(
            expect={"prefect.flow-run.Pending"},
            match={
                "prefect.resource.id": "flow-run-pending",
            },
            posture=Posture.Reactive,
            threshold=1,
        ),
        actions=[actions.DoNothing()],
    )


@pytest.fixture
def flow_run_failed_automation() -> Automation:
    return Automation(
        name="Flow Run Failed",
        trigger=EventTrigger(
            expect={"prefect.flow-run.Failed"},
            match={
                "prefect.resource.id": "flow-run-failed",
            },
            posture=Posture.Reactive,
            threshold=1,
        ),
        actions=[actions.DoNothing()],
    )


@pytest.fixture
def flow_run_running_automation() -> Automation:
    return Automation(
        name="Flow Run Running",
        trigger=EventTrigger(
            expect={"prefect.flow-run.Running"},
            match={
                "prefect.resource.id": "flow-run-running",
            },
            posture=Posture.Reactive,
            threshold=1,
        ),
        actions=[actions.DoNothing()],
    )


@pytest.fixture
def chonk_lonely() -> Automation:
    return Automation(
        name="One woodchucks is worth throwing a party all alone",
        trigger=EventTrigger(
            expect={"animal.table_for_one"},
            match={
                "genus": "Marmota",
                "species": "monax",
            },
            posture=Posture.Reactive,
            threshold=1,
            within=timedelta(seconds=10),
        ),
        actions=[actions.DoNothing()],
    )


@pytest.fixture
def chonk_sadness() -> Automation:
    return Automation(
        name="If I haven't seen a woodchuck in 30 seconds, cry",
        trigger=EventTrigger(
            expect={"animal.walked"},
            match={
                "genus": "Marmota",
                "species": "monax",
            },
            posture=Posture.Proactive,
            threshold=1,
            within=timedelta(seconds=30),
        ),
        actions=[actions.DoNothing()],
    )


@pytest.fixture
def woodchonk_walked(start_of_test: DateTime) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=2),
        event="animal.walked",
        resource={
            "kingdom": "Animalia",
            "phylum": "Chordata",
            "class": "Mammalia",
            "order": "Rodentia",
            "family": "Sciuridae",
            "genus": "Marmota",
            "species": "monax",
            "prefect.resource.id": "woodchonk",
        },
        id=uuid4(),
    )


@pytest.fixture
def woodchonk_table_for_one(start_of_test: DateTime) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=2),
        event="animal.table_for_one",
        resource={
            "kingdom": "Animalia",
            "phylum": "Chordata",
            "class": "Mammalia",
            "order": "Rodentia",
            "family": "Sciuridae",
            "genus": "Marmota",
            "species": "monax",
            "prefect.resource.id": "woodchonk",
        },
        id=uuid4(),
    )


@pytest.fixture
def my_poor_lilies() -> Automation:
    return Automation(
        name="If my lilies get nibbled, let me know",
        trigger=EventTrigger(
            expect={"animal.ingested"},
            match_related={
                "prefect.resource.role": "meal",
                "genus": "Hemerocallis",
                "species": "fulva",
            },
            posture=Posture.Reactive,
            threshold=0,
            within=timedelta(seconds=30),
        ),
        actions=[actions.DoNothing()],
    )


@pytest.fixture
def woodchonk_nibbled(start_of_test: DateTime):
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=2),
        event="animal.ingested",
        resource={
            "kingdom": "Animalia",
            "phylum": "Chordata",
            "class": "Mammalia",
            "order": "Rodentia",
            "family": "Sciuridae",
            "genus": "Marmota",
            "species": "monax",
            "prefect.resource.id": "woodchonk",
        },
        related=[
            {
                "prefect.resource.role": "meal",
                "kingdom": "Plantae",
                "order": "Asparagales",
                "family": "Asphodelaceae",
                "genus": "Hemerocallis",
                "species": "fulva",
                "prefect.resource.id": "my-lily",
            },
            {
                "prefect.resource.role": "meal",
                "kingdom": "Plantae",
                "order": "Liliales",
                "family": "Liliaceae",
                "genus": "Tulipa",
                "species": "gesneriana",
                "prefect.resource.id": "my-tulip",
            },
        ],
        id=uuid4(),
    )


@pytest.fixture
def woodchonk_gobbled(start_of_test: DateTime):
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=3),
        event="animal.ingested",
        resource={
            "kingdom": "Animalia",
            "phylum": "Chordata",
            "class": "Mammalia",
            "order": "Rodentia",
            "family": "Sciuridae",
            "genus": "Marmota",
            "species": "monax",
            "prefect.resource.id": "woodchonk",
        },
        related=[
            {
                "prefect.resource.role": "meal",
                "kingdom": "Plantae",
                "order": "Ranunculales",
                "family": "Papaveraceae",
                "genus": "Dicentra",
                "species": "cucullaria",
                "prefect.resource.id": "my-bleeding-heart",
            },
            {
                "prefect.resource.role": "meal",
                "kingdom": "Plantae",
                "order": "Asparagales",
                "family": "Amaryllidaceae",
                "genus": "Narcissus",
                "species": "poeticus",
                "prefect.resource.id": "my-daffodil",
            },
        ],
        id=uuid4(),
    )


@pytest.fixture
def animal_lover() -> Automation:
    return Automation(
        name="I get excited about just about anything an animal does",
        trigger=EventTrigger(
            expect=set(),
            match={
                "kingdom": "Animalia",
            },
            posture=Posture.Reactive,
            threshold=0,
            within=timedelta(seconds=30),
        ),
        actions=[actions.DoNothing()],
    )


@pytest.fixture
def email_me_when_that_dang_spider_comes(
    arachnophobia: Automation,
    daddy_long_legs_walked: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=arachnophobia.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={"hello": "world"},
        triggering_event=daddy_long_legs_walked,
    )
    return TriggeredAction(
        automation=arachnophobia,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=arachnophobia.actions[0],
    )


@pytest.fixture
async def some_workspace_automations(
    db: PrefectDBInterface, automations_session: AsyncSession
) -> Sequence[Automation]:
    uninteresting_kwargs: Dict[str, Any] = dict(
        trigger=EventTrigger(
            expect=("things.happened",),
            match=ResourceSpecification.model_validate(
                {"prefect.resource.id": "some-resource"}
            ),
            match_related=ResourceSpecification.model_validate({}),
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
        db.Automation(
            id=uuid4(),
            name="automation 4",
            **uninteresting_kwargs,
        ),
    ]

    automations_session.add_all(automations)
    await automations_session.commit()
    return parse_obj_as(List[Automation], automations)


@pytest.fixture
def publish_mocks(
    monkeypatch: pytest.MonkeyPatch,
) -> Tuple[MagicMock, AsyncMock]:
    mock_create_publisher = MagicMock(spec=messaging.create_event_publisher)
    mock_publish = AsyncMock()
    mock_create_publisher.return_value.__aenter__.return_value.publish_data = (
        mock_publish
    )

    monkeypatch.setattr(
        "prefect.server.events.messaging.create_event_publisher", mock_create_publisher
    )

    return mock_create_publisher, mock_publish


@pytest.fixture
def publish(publish_mocks: Tuple[MagicMock, AsyncMock]) -> AsyncMock:
    return publish_mocks[1]


@pytest.fixture
def create_publisher(
    publish_mocks: Tuple[MagicMock, AsyncMock],
) -> MagicMock:
    return publish_mocks[0]


def assert_message_represents_event(message: Message, event: ReceivedEvent):
    """Confirms that the message adequately represents the event"""
    assert message.data
    assert ReceivedEvent.model_validate_json(message.data) == event
    assert message.attributes
    assert message.attributes["id"] == str(event.id)
    assert message.attributes["event"] == event.event
