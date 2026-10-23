"""A proactive trigger whose `after` event is also expected must stay satisfied by an
`expect`-only event, such as a terminal flow run state, that arrives alongside or
before the next `after` event.

https://github.com/PrefectHQ/prefect/issues/21932
"""

from datetime import timedelta
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.events import actions, triggers
from prefect.server.events.models import automations
from prefect.server.events.schemas.automations import (
    Automation,
    EventTrigger,
    Posture,
)
from prefect.server.events.schemas.events import Event
from prefect.types._datetime import DateTime

pytestmark = pytest.mark.clear_db


@pytest.fixture
def act(monkeypatch: pytest.MonkeyPatch) -> mock.AsyncMock:
    mock_act = mock.AsyncMock()
    monkeypatch.setattr("prefect.server.events.triggers.act", mock_act)
    return mock_act


async def receive(event: str, occurred: DateTime, resource_id: str) -> None:
    await triggers.reactive_evaluation(
        Event(
            occurred=occurred,
            event=event,
            resource={"prefect.resource.id": resource_id},
            id=uuid4(),
        ).receive()
    )


@pytest.fixture
async def zombie_flow_detection(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> EventTrigger:
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Crash zombie flows",
            trigger=EventTrigger(
                match={"prefect.resource.id": "prefect.flow-run.*"},
                after={"prefect.flow-run.heartbeat"},
                expect={"prefect.flow-run.*"},
                for_each={"prefect.resource.id"},
                posture=Posture.Proactive,
                threshold=1,
                within=timedelta(seconds=90),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    assert isinstance(automation.trigger, EventTrigger)
    return automation.trigger


async def test_zombie_flow_detection_does_not_fire_when_flow_completes(
    act: mock.AsyncMock,
    frozen_time: DateTime,
    zombie_flow_detection: EventTrigger,
):
    """A healthy flow sends heartbeats and then reaches a terminal state."""
    resource_id = f"prefect.flow-run.{uuid4()}"

    for i in range(3):
        await receive(
            "prefect.flow-run.heartbeat",
            frozen_time + timedelta(seconds=30 * i),
            resource_id,
        )
    await receive(
        "prefect.flow-run.Completed", frozen_time + timedelta(seconds=60), resource_id
    )

    await triggers.proactive_evaluation(
        zombie_flow_detection, frozen_time + timedelta(seconds=60 + 90 + 1)
    )
    act.assert_not_awaited()


async def test_zombie_flow_detection_does_not_fire_when_heartbeat_races_terminal(
    act: mock.AsyncMock,
    frozen_time: DateTime,
    zombie_flow_detection: EventTrigger,
):
    """The final heartbeat occurs at the same instant as the terminal state and is
    evaluated after it."""
    resource_id = f"prefect.flow-run.{uuid4()}"

    for i in range(3):
        await receive(
            "prefect.flow-run.heartbeat",
            frozen_time + timedelta(seconds=30 * i),
            resource_id,
        )
    await receive(
        "prefect.flow-run.Completed", frozen_time + timedelta(seconds=60), resource_id
    )
    await receive(
        "prefect.flow-run.heartbeat", frozen_time + timedelta(seconds=60), resource_id
    )

    await triggers.proactive_evaluation(
        zombie_flow_detection, frozen_time + timedelta(seconds=60 + 90 + 1)
    )
    act.assert_not_awaited()


@pytest.fixture
async def after_a_expect_a_or_b(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> EventTrigger:
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="after A, expect A or B",
            trigger=EventTrigger(
                match={"prefect.resource.id": "some.*"},
                after={"A"},
                expect={"A", "B"},
                for_each={"prefect.resource.id"},
                posture=Posture.Proactive,
                threshold=1,
                within=timedelta(seconds=10),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    assert isinstance(automation.trigger, EventTrigger)
    return automation.trigger


async def test_after_event_following_an_expect_event_re_arms_the_window(
    act: mock.AsyncMock,
    frozen_time: DateTime,
    after_a_expect_a_or_b: EventTrigger,
):
    """The second A opens a fresh window at t=2. B occurred at t=1, before that
    window, so it does not count, and silence after it fires the trigger."""
    for offset, event in ((0, "A"), (1, "B"), (2, "A")):
        await receive(event, frozen_time + timedelta(seconds=offset), "some.resource")

    await triggers.proactive_evaluation(
        after_a_expect_a_or_b, frozen_time + timedelta(seconds=13)
    )
    act.assert_awaited_once()


@pytest.fixture
async def flow_run_timeout_enforcer(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> EventTrigger:
    # Every non-terminal state is both an `after` and an `expect` event, and every
    # terminal state is an `expect`-only event.
    automation = await automations.create_automation(
        automations_session,
        Automation(
            name="Flow run timeout enforcer",
            trigger=EventTrigger(
                match={"prefect.resource.id": "prefect.flow-run.*"},
                after={
                    "prefect.flow-run.Pending",
                    "prefect.flow-run.Running",
                    "prefect.flow-run.Retrying",
                    "prefect.flow-run.Paused",
                    "prefect.flow-run.Suspended",
                    "prefect.flow-run.Cancelling",
                },
                expect={"prefect.flow-run.*"},
                for_each={"prefect.resource.id"},
                posture=Posture.Proactive,
                threshold=1,
                within=timedelta(minutes=10),
            ),
            actions=[actions.DoNothing()],
        ),
    )
    triggers.load_automation(automation)
    await automations_session.commit()
    assert isinstance(automation.trigger, EventTrigger)
    return automation.trigger


async def test_flow_run_timeout_enforcer_does_not_fire_when_run_completes(
    act: mock.AsyncMock,
    frozen_time: DateTime,
    flow_run_timeout_enforcer: EventTrigger,
):
    """The run goes Pending, Running, Completed well inside the window, but Running
    is evaluated after Completed. Running re-arms the window at t=29, and Completed
    at t=86 falls inside it, so the completed run must not trip the trigger."""
    resource_id = f"prefect.flow-run.{uuid4()}"

    for offset, state in (
        (0, "prefect.flow-run.Pending"),
        (86, "prefect.flow-run.Completed"),
        (29, "prefect.flow-run.Running"),
    ):
        await receive(state, frozen_time + timedelta(seconds=offset), resource_id)

    await triggers.proactive_evaluation(
        flow_run_timeout_enforcer, frozen_time + timedelta(minutes=10, seconds=30)
    )
    act.assert_not_awaited()
