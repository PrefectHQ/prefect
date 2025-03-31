from datetime import timedelta
from typing import List
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.events import actions
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.events.schemas.automations import (
    Automation,
    EventTrigger,
    Firing,
    Posture,
    TriggeredAction,
    TriggerState,
)
from prefect.server.events.schemas.events import ReceivedEvent, RelatedResource
from prefect.server.models import work_queues
from prefect.server.schemas.actions import WorkQueueCreate, WorkQueueUpdate
from prefect.server.schemas.core import WorkQueue
from prefect.types import DateTime
from prefect.types._datetime import now
from prefect.utilities.pydantic import parse_obj_as


def test_source_determines_if_work_queue_id_is_required_or_allowed():
    with pytest.raises(ValidationError):
        actions.PauseWorkQueue(source="selected")

    with pytest.raises(ValidationError):
        actions.ResumeWorkQueue(source="selected")

    with pytest.raises(ValidationError):
        actions.PauseWorkQueue(source="inferred", work_queue_id=uuid4())

    with pytest.raises(ValidationError):
        actions.ResumeWorkQueue(source="inferred", work_queue_id=uuid4())


@pytest.fixture
async def patrols_queue(
    session: AsyncSession,
) -> WorkQueue:
    patrols_queue = await work_queues.create_work_queue(
        session=session,
        work_queue=WorkQueueCreate(name="Patrols"),
    )
    await session.commit()
    return WorkQueue.model_validate(patrols_queue, from_attributes=True)


@pytest.fixture
def when_the_guard_gets_sick_stop_the_patrol(
    patrols_queue: WorkQueue,
) -> Automation:
    return Automation(
        name="If a guard gets sick, stop the hourly patrol",
        trigger=EventTrigger(
            expect={"guard.sick"},
            posture=Posture.Reactive,
            threshold=0,
            within=timedelta(seconds=30),
        ),
        actions=[
            actions.PauseWorkQueue(
                source="selected",
                work_queue_id=patrols_queue.id,
            )
        ],
    )


@pytest.fixture
def guard_one_got_sick(
    patrols_queue: WorkQueue,
    start_of_test: DateTime,
) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=2),
        event="guard.sick",
        resource={
            "prefect.resource.id": "guard-1",
        },
        related=[
            {
                "prefect.resource.role": "work-queue",
                "prefect.resource.id": f"prefect.work-queue.{patrols_queue.id}",
            }
        ],
        id=uuid4(),
    )


@pytest.fixture
def let_guard_one_get_some_sleep(
    when_the_guard_gets_sick_stop_the_patrol: Automation,
    guard_one_got_sick: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=when_the_guard_gets_sick_stop_the_patrol.trigger,
        triggered=now("UTC"),
        trigger_states={TriggerState.Triggered},
        triggering_labels={},
        triggering_event=guard_one_got_sick,
    )
    return TriggeredAction(
        automation=when_the_guard_gets_sick_stop_the_patrol,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=when_the_guard_gets_sick_stop_the_patrol.actions[0],
    )


async def test_pausing_work_queue(
    let_guard_one_get_some_sleep: TriggeredAction,
    patrols_queue: WorkQueue,
    session: AsyncSession,
):
    patrol = await work_queues.read_work_queue(session, work_queue_id=patrols_queue.id)
    assert patrol
    assert not patrol.is_paused

    action = let_guard_one_get_some_sleep.action
    await action.act(let_guard_one_get_some_sleep)

    session.expunge_all()

    patrol = await work_queues.read_work_queue(session, work_queue_id=patrols_queue.id)
    assert patrol

    assert patrol.is_paused


async def test_pausing_errors_are_reported_as_events(
    let_guard_one_get_some_sleep: TriggeredAction,
):
    action = let_guard_one_get_some_sleep.action
    assert isinstance(action, actions.PauseWorkQueue)

    action.work_queue_id = uuid4()  # this doesn't exist

    with pytest.raises(actions.ActionFailed, match="Unexpected status"):
        await action.act(let_guard_one_get_some_sleep)


@pytest.fixture
def when_the_guard_gets_well_resume_the_patrol(
    patrols_queue: WorkQueue,
) -> Automation:
    return Automation(
        name="If a guard gets well, resume the hourly patrol",
        trigger=EventTrigger(
            expect={"guard.well"},
            posture=Posture.Reactive,
            threshold=0,
            within=timedelta(seconds=30),
        ),
        actions=[
            actions.ResumeWorkQueue(
                source="selected",
                work_queue_id=patrols_queue.id,
            )
        ],
    )


@pytest.fixture
def guard_one_got_well(
    patrols_queue: WorkQueue,
    start_of_test: DateTime,
):
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=2),
        event="guard.well",
        resource={
            "prefect.resource.id": "guard-1",
        },
        related=[
            {
                "prefect.resource.role": "work-queue",
                "prefect.resource.id": f"prefect.work-queue.{patrols_queue.id}",
            }
        ],
        id=uuid4(),
    )


@pytest.fixture
def put_guard_one_back_on_duty(
    when_the_guard_gets_well_resume_the_patrol: Automation,
    guard_one_got_sick: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=when_the_guard_gets_well_resume_the_patrol.trigger,
        triggered=now("UTC"),
        trigger_states={TriggerState.Triggered},
        triggering_labels={},
        triggering_event=guard_one_got_sick,
    )
    return TriggeredAction(
        automation=when_the_guard_gets_well_resume_the_patrol,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=when_the_guard_gets_well_resume_the_patrol.actions[0],
    )


async def test_resuming_work_queue(
    put_guard_one_back_on_duty: TriggeredAction,
    patrols_queue: WorkQueue,
    session: AsyncSession,
):
    await work_queues.update_work_queue(
        session=session,
        work_queue_id=patrols_queue.id,
        work_queue=WorkQueueUpdate(
            is_paused=True,
        ),
    )
    await session.commit()

    patrol = await work_queues.read_work_queue(session, work_queue_id=patrols_queue.id)
    assert patrol
    assert patrol.is_paused

    action = put_guard_one_back_on_duty.action
    await action.act(put_guard_one_back_on_duty)

    session.expunge_all()

    patrol = await work_queues.read_work_queue(session, work_queue_id=patrols_queue.id)

    assert patrol
    assert not patrol.is_paused


async def test_orion_errors_are_reported_as_events(
    put_guard_one_back_on_duty: TriggeredAction,
):
    action = put_guard_one_back_on_duty.action
    assert isinstance(action, actions.ResumeWorkQueue)

    action.work_queue_id = uuid4()  # this doesn't exist

    with pytest.raises(actions.ActionFailed, match="Unexpected status"):
        await action.act(put_guard_one_back_on_duty)


@pytest.fixture
def when_the_guard_gets_sick_stop_their_patrol() -> Automation:
    return Automation(
        name="If a guard gets sick, stop the hourly patrol",
        trigger=EventTrigger(
            expect={"guard.sick"},
            posture=Posture.Reactive,
            threshold=0,
            within=timedelta(seconds=30),
        ),
        actions=[actions.PauseWorkQueue(source="inferred")],
    )


@pytest.fixture
def pause_related_patrols(
    when_the_guard_gets_sick_stop_their_patrol: Automation,
    guard_one_got_sick: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=when_the_guard_gets_sick_stop_their_patrol.trigger,
        triggered=now("UTC"),
        trigger_states={TriggerState.Triggered},
        triggering_labels={},
        triggering_event=guard_one_got_sick,
    )
    return TriggeredAction(
        automation=when_the_guard_gets_sick_stop_their_patrol,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=when_the_guard_gets_sick_stop_their_patrol.actions[0],
    )


async def test_pausing_inferred_work_queue(
    pause_related_patrols: TriggeredAction,
    patrols_queue: WorkQueue,
    session: AsyncSession,
):
    patrol = await work_queues.read_work_queue(session, work_queue_id=patrols_queue.id)
    assert patrol
    assert not patrol.is_paused

    action = pause_related_patrols.action
    await action.act(pause_related_patrols)

    session.expunge_all()

    patrol = await work_queues.read_work_queue(session, work_queue_id=patrols_queue.id)

    assert patrol
    assert patrol.is_paused


@pytest.fixture
def when_the_guard_recovers_resume_their_patrol() -> Automation:
    return Automation(
        name="If a guard gets sick, stop the hourly patrol",
        trigger=EventTrigger(
            expect={"guard.sick"},
            posture=Posture.Reactive,
            threshold=0,
            within=timedelta(seconds=30),
        ),
        actions=[actions.ResumeWorkQueue(source="inferred")],
    )


@pytest.fixture
def resume_the_associated_queue(
    when_the_guard_recovers_resume_their_patrol: Automation,
    guard_one_got_well: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=when_the_guard_recovers_resume_their_patrol.trigger,
        triggered=now("UTC"),
        trigger_states={TriggerState.Triggered},
        triggering_labels={},
        triggering_event=guard_one_got_well,
    )
    return TriggeredAction(
        automation=when_the_guard_recovers_resume_their_patrol,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=when_the_guard_recovers_resume_their_patrol.actions[0],
    )


async def test_resuming_inferred_work_queue(
    resume_the_associated_queue: TriggeredAction,
    patrols_queue: WorkQueue,
    session: AsyncSession,
):
    await work_queues.update_work_queue(
        session=session,
        work_queue_id=patrols_queue.id,
        work_queue=WorkQueueUpdate(
            is_paused=True,
        ),
    )
    await session.commit()

    patrol = await work_queues.read_work_queue(session, work_queue_id=patrols_queue.id)
    assert patrol
    assert patrol.is_paused

    action = resume_the_associated_queue.action
    await action.act(resume_the_associated_queue)

    session.expunge_all()

    patrol = await work_queues.read_work_queue(session, work_queue_id=patrols_queue.id)

    assert patrol
    assert not patrol.is_paused


async def test_inferring_work_queue_requires_event(
    resume_the_associated_queue: TriggeredAction,
):
    resume_the_associated_queue.triggering_event = None  # simulate a proactive trigger

    action = resume_the_associated_queue.action

    with pytest.raises(actions.ActionFailed, match="No event to infer the work queue"):
        await action.act(resume_the_associated_queue)


async def test_inferring_work_queue_requires_some_matching_resource(
    resume_the_associated_queue: TriggeredAction,
):
    assert resume_the_associated_queue.triggering_event
    resume_the_associated_queue.triggering_event.related = []  # no relevant related resources

    action = resume_the_associated_queue.action

    with pytest.raises(actions.ActionFailed, match="No work queue could be inferred"):
        await action.act(resume_the_associated_queue)


async def test_inferring_work_queue_requires_recognizable_resource_id(
    resume_the_associated_queue: TriggeredAction,
):
    assert resume_the_associated_queue.triggering_event
    resume_the_associated_queue.triggering_event.related = parse_obj_as(
        List[RelatedResource],
        [
            {
                "prefect.resource.role": "work-queue",
                "prefect.resource.id": "prefect.work-queue.nope",  # not a uuid
            },
            {
                "prefect.resource.role": "work-queue",
                "prefect.resource.id": f"oh.so.close.{uuid4()}",  # not a work-queue
            },
            {
                "prefect.resource.role": "work-queue",
                "prefect.resource.id": "nah-ah",  # not a dotted name
            },
        ],
    )

    action = resume_the_associated_queue.action

    with pytest.raises(actions.ActionFailed, match="No work queue could be inferred"):
        await action.act(resume_the_associated_queue)


async def test_pausing_success_event(
    pause_related_patrols: TriggeredAction,
    patrols_queue: WorkQueue,
):
    action = pause_related_patrols.action

    await action.act(pause_related_patrols)
    await action.succeed(pause_related_patrols)

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.work-queue.{patrols_queue.id}",
                "prefect.resource.role": "target",
            }
        )
    ]
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "pause-work-queue",
        "invocation": str(pause_related_patrols.id),
    }

    assert executed_event.event == "prefect.automation.action.executed"
    assert executed_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.work-queue.{patrols_queue.id}",
                "prefect.resource.role": "target",
            }
        )
    ]
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "pause-work-queue",
        "invocation": str(pause_related_patrols.id),
        "status_code": 204,
    }


async def test_resuming_success_event(
    resume_the_associated_queue: TriggeredAction,
    patrols_queue: WorkQueue,
):
    action = resume_the_associated_queue.action

    await action.act(resume_the_associated_queue)
    await action.succeed(resume_the_associated_queue)

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.work-queue.{patrols_queue.id}",
                "prefect.resource.role": "target",
            }
        )
    ]
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "resume-work-queue",
        "invocation": str(resume_the_associated_queue.id),
    }

    assert executed_event.event == "prefect.automation.action.executed"
    assert executed_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.work-queue.{patrols_queue.id}",
                "prefect.resource.role": "target",
            }
        )
    ]
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "resume-work-queue",
        "invocation": str(resume_the_associated_queue.id),
        "status_code": 204,
    }
