from datetime import timedelta
from typing import TYPE_CHECKING, List
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface
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
from prefect.server.models import workers
from prefect.server.schemas.actions import WorkPoolCreate
from prefect.types import DateTime
from prefect.utilities.pydantic import parse_obj_as

if TYPE_CHECKING:
    from prefect.server.database.orm_models import ORMWorkPool


def test_source_determines_if_work_pool_id_is_required_or_allowed():
    with pytest.raises(ValidationError):
        actions.PauseWorkPool(source="selected")

    with pytest.raises(ValidationError):
        actions.ResumeWorkPool(source="selected")

    with pytest.raises(ValidationError):
        actions.PauseWorkPool(source="inferred", work_pool_id=uuid4())

    with pytest.raises(ValidationError):
        actions.ResumeWorkPool(source="inferred", work_pool_id=uuid4())


@pytest.fixture
async def work_pool(session: AsyncSession) -> "ORMWorkPool":
    """An unpaused work pool"""
    work_pool = await workers.create_work_pool(
        session=session,
        work_pool=WorkPoolCreate(name="pause-resume-action-work-pool", is_paused=False),
    )
    await session.commit()

    assert work_pool.is_paused is False
    return work_pool


@pytest.fixture
def pause_work_pool_on_scream_n_shout(
    work_pool: "ORMWorkPool",
) -> Automation:
    return Automation(
        name="If someone screams n shouts, then pause the work pool already!",
        trigger=EventTrigger(
            expect={"scream-n-shout"},
            posture=Posture.Reactive,
            threshold=0,
            within=timedelta(seconds=30),
        ),
        actions=[
            actions.PauseWorkPool(
                source="selected",
                work_pool_id=work_pool.id,
            )
        ],
        description="An automation that pauses a work pool when a scream-n-shout event is received",
        enabled=True,
    )


@pytest.fixture
def scream_n_shout(
    work_pool: "ORMWorkPool",
    start_of_test: DateTime,
) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=2),
        event="scream-n-shout",
        resource={"prefect.resource.id": "toddler"},
        related=[
            {
                "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                "prefect.resource.role": "work-pool",
                "prefect.resource.name": work_pool.name,
            }
        ],
        id=uuid4(),
        follows=None,
    )


@pytest.fixture
def triggered_pause_action(
    scream_n_shout: ReceivedEvent,
    pause_work_pool_on_scream_n_shout: Automation,
) -> TriggeredAction:
    firing = Firing(
        trigger=pause_work_pool_on_scream_n_shout.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=scream_n_shout.occurred,
        triggering_labels={},
        triggering_event=scream_n_shout,
    )
    return TriggeredAction(
        automation=pause_work_pool_on_scream_n_shout,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=pause_work_pool_on_scream_n_shout.actions[0],
        action_index=0,
    )


async def _get_work_pool(work_pool_id: UUID, session) -> "ORMWorkPool":
    work_pool = await workers.read_work_pool(session=session, work_pool_id=work_pool_id)
    assert work_pool is not None
    return work_pool


async def test_pausing_work_pool(
    triggered_pause_action: TriggeredAction,
    work_pool: "ORMWorkPool",
    session: AsyncSession,
):
    assert work_pool.is_paused is False
    action = triggered_pause_action.action

    await action.act(triggered_pause_action)

    session.expunge_all()

    refreshed = await _get_work_pool(work_pool.id, session)
    assert refreshed.is_paused is True


async def test_pausing_work_pool_orion_errors_are_reported_as_events(
    triggered_pause_action: TriggeredAction,
):
    action = triggered_pause_action.action
    assert isinstance(action, actions.PauseWorkPool)

    action.work_pool_id = uuid4()  # this doesn't exist

    with pytest.raises(actions.ActionFailed, match="Work pool .+ not found"):
        await action.act(triggered_pause_action)


@pytest.fixture
def pause_inferred_work_pool_on_scream_n_shout(
    pause_work_pool_on_scream_n_shout,
) -> Automation:
    pause_work_pool_on_scream_n_shout.actions = [
        actions.PauseWorkPool(
            source="inferred",
            work_pool_id=None,
        )
    ]
    return pause_work_pool_on_scream_n_shout


@pytest.fixture
def triggered_pause_action_with_source_inferred(
    scream_n_shout: ReceivedEvent,
    pause_inferred_work_pool_on_scream_n_shout: Automation,
) -> TriggeredAction:
    firing = Firing(
        trigger=pause_inferred_work_pool_on_scream_n_shout.trigger,
        triggered=scream_n_shout.occurred,
        trigger_states={TriggerState.Triggered},
        triggering_labels={},
        triggering_event=scream_n_shout,
    )
    return TriggeredAction(
        automation=pause_inferred_work_pool_on_scream_n_shout,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=pause_inferred_work_pool_on_scream_n_shout.actions[0],
        action_index=0,
    )


async def test_pausing_inferred_work_pool(
    triggered_pause_action_with_source_inferred: TriggeredAction,
    work_pool: "ORMWorkPool",
    session: AsyncSession,
):
    assert work_pool.is_paused is False
    action = triggered_pause_action_with_source_inferred.action

    await action.act(triggered_pause_action_with_source_inferred)

    session.expunge_all()

    refreshed = await _get_work_pool(work_pool.id, session)
    assert refreshed.is_paused is True


async def test_inferring_work_pool_requires_event(
    triggered_pause_action_with_source_inferred: TriggeredAction,
):
    triggered_pause_action_with_source_inferred.triggering_event = (
        None  # simulate a proactive trigger
    )

    action = triggered_pause_action_with_source_inferred.action

    with pytest.raises(actions.ActionFailed, match="No event to infer the work pool"):
        await action.act(triggered_pause_action_with_source_inferred)


async def test_inferring_work_pool_requires_some_matching_resource(
    triggered_pause_action_with_source_inferred: TriggeredAction,
):
    assert triggered_pause_action_with_source_inferred.triggering_event
    triggered_pause_action_with_source_inferred.triggering_event.related = []  # no relevant related resources

    action = triggered_pause_action_with_source_inferred.action

    with pytest.raises(actions.ActionFailed, match="No work pool could be inferred"):
        await action.act(triggered_pause_action_with_source_inferred)


async def test_inferring_work_pool_requires_recognizable_resource_id(
    triggered_pause_action_with_source_inferred: TriggeredAction,
):
    assert triggered_pause_action_with_source_inferred.triggering_event
    triggered_pause_action_with_source_inferred.triggering_event.related = parse_obj_as(
        List[RelatedResource],
        [
            {
                "prefect.resource.role": "work-pool",
                "prefect.resource.id": "prefect.work-pool.nope",  # not a uuid
            },
            {
                "prefect.resource.role": "work-pool",
                "prefect.resource.id": f"oh.so.close.{uuid4()}",  # not a work-pool
            },
            {
                "prefect.resource.role": "work-pool",
                "prefect.resource.id": "nah-ah",  # not a dotted name
            },
        ],
    )

    action = triggered_pause_action_with_source_inferred.action

    with pytest.raises(actions.ActionFailed, match="No work pool could be inferred"):
        await action.act(triggered_pause_action_with_source_inferred)


async def test_pausing_publishes_success_event(
    triggered_pause_action: TriggeredAction,
    work_pool: "ORMWorkPool",
):
    action = triggered_pause_action.action

    await action.act(triggered_pause_action)
    await action.succeed(triggered_pause_action)

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                "prefect.resource.name": work_pool.name,
                "prefect.resource.role": "target",
            }
        )
    ]
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "pause-work-pool",
        "invocation": str(triggered_pause_action.id),
    }

    assert executed_event.event == "prefect.automation.action.executed"
    assert executed_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                "prefect.resource.name": work_pool.name,
                "prefect.resource.role": "target",
            }
        )
    ]
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "pause-work-pool",
        "invocation": str(triggered_pause_action.id),
        "status_code": 204,
    }


# -----------------------------------------------------
# --
# --
# -- Resume Work Pool Action
# --
# --
# -----------------------------------------------------
@pytest.fixture
async def paused_work_pool(
    db: PrefectDBInterface, work_pool: "ORMWorkPool", session: AsyncSession
) -> "ORMWorkPool":
    work_pool = await session.get(db.WorkPool, work_pool.id)
    work_pool.is_paused = True
    await session.commit()

    assert work_pool.is_paused is True
    return work_pool


@pytest.fixture
def resume_work_pool_on_scream_n_shout(
    paused_work_pool: "ORMWorkPool",
) -> Automation:
    return Automation(
        name="If someone screams n shouts, then resume/unpause the work pool already!",
        trigger=EventTrigger(
            expect={"scream-n-shout"},
            posture=Posture.Reactive,
            threshold=0,
            within=timedelta(seconds=30),
        ),
        actions=[
            actions.ResumeWorkPool(
                source="selected",
                work_pool_id=paused_work_pool.id,
            )
        ],
        description="An automation that resumes a work pool when a scream-n-shout event is received",
        enabled=True,
    )


@pytest.fixture
def triggered_resume_action(
    scream_n_shout: ReceivedEvent,
    resume_work_pool_on_scream_n_shout: Automation,
) -> TriggeredAction:
    firing = Firing(
        trigger=resume_work_pool_on_scream_n_shout.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=scream_n_shout.occurred,
        triggering_labels={},
        triggering_event=scream_n_shout,
    )
    return TriggeredAction(
        automation=resume_work_pool_on_scream_n_shout,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=resume_work_pool_on_scream_n_shout.actions[0],
        action_index=0,
    )


async def test_resuming_work_pool(
    triggered_resume_action: TriggeredAction,
    paused_work_pool: "ORMWorkPool",
    session: AsyncSession,
):
    assert paused_work_pool.is_paused is True
    action = triggered_resume_action.action

    await action.act(triggered_resume_action)

    session.expunge_all()

    work_pool = await _get_work_pool(paused_work_pool.id, session)
    assert work_pool.is_paused is False


@pytest.fixture
def resume_inferred_work_pool_on_scream_n_shout(
    resume_work_pool_on_scream_n_shout,
) -> Automation:
    resume_work_pool_on_scream_n_shout.actions = [
        actions.ResumeWorkPool(
            source="inferred",
            work_pool_id=None,
        )
    ]
    return resume_work_pool_on_scream_n_shout


@pytest.fixture
def triggered_resume_action_with_source_inferred(
    scream_n_shout: ReceivedEvent,
    resume_inferred_work_pool_on_scream_n_shout: Automation,
) -> TriggeredAction:
    firing = Firing(
        trigger=resume_inferred_work_pool_on_scream_n_shout.trigger,
        triggered=scream_n_shout.occurred,
        trigger_states={TriggerState.Triggered},
        triggering_labels={},
        triggering_event=scream_n_shout,
    )
    return TriggeredAction(
        automation=resume_inferred_work_pool_on_scream_n_shout,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=resume_inferred_work_pool_on_scream_n_shout.actions[0],
        action_index=0,
    )


async def test_resuming_inferred_work_pool(
    triggered_resume_action_with_source_inferred: TriggeredAction,
    paused_work_pool: "ORMWorkPool",
    session: AsyncSession,
):
    assert paused_work_pool.is_paused is True
    action = triggered_resume_action_with_source_inferred.action

    await action.act(triggered_resume_action_with_source_inferred)

    session.expunge_all()

    work_pool = await _get_work_pool(paused_work_pool.id, session)
    assert work_pool.is_paused is False


async def test_resuming_with_inferred_work_pool_requires_event(
    triggered_resume_action_with_source_inferred: TriggeredAction,
):
    triggered_resume_action_with_source_inferred.triggering_event = (
        None  # simulate a proactive trigger
    )

    action = triggered_resume_action_with_source_inferred.action

    with pytest.raises(actions.ActionFailed, match="No event to infer the work pool"):
        await action.act(triggered_resume_action_with_source_inferred)


async def test_resuming_with_inferred_work_pool_requires_some_matching_resource(
    triggered_resume_action_with_source_inferred: TriggeredAction,
):
    assert triggered_resume_action_with_source_inferred.triggering_event
    triggered_resume_action_with_source_inferred.triggering_event.related = []  # no relevant related resources

    action = triggered_resume_action_with_source_inferred.action

    with pytest.raises(actions.ActionFailed, match="No work pool could be inferred"):
        await action.act(triggered_resume_action_with_source_inferred)


async def test_resuming_with_inferred_work_pool_requires_recognizable_resource_id(
    triggered_resume_action_with_source_inferred: TriggeredAction,
):
    assert triggered_resume_action_with_source_inferred.triggering_event
    triggered_resume_action_with_source_inferred.triggering_event.related = (
        parse_obj_as(
            List[RelatedResource],
            [
                {
                    "prefect.resource.role": "work-pool",
                    "prefect.resource.id": "prefect.work-pool.nope",  # not a uuid
                },
                {
                    "prefect.resource.role": "work-pool",
                    "prefect.resource.id": f"oh.so.close.{uuid4()}",  # not a work-pool
                },
                {
                    "prefect.resource.role": "work-pool",
                    "prefect.resource.id": "nah-ah",  # not a dotted name
                },
            ],
        )
    )

    action = triggered_resume_action_with_source_inferred.action

    with pytest.raises(actions.ActionFailed, match="No work pool could be inferred"):
        await action.act(triggered_resume_action_with_source_inferred)


async def test_resuming_publishes_success_event(
    triggered_resume_action: TriggeredAction,
    paused_work_pool: "ORMWorkPool",
):
    action = triggered_resume_action.action

    await action.act(triggered_resume_action)
    await action.succeed(triggered_resume_action)

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.work-pool.{paused_work_pool.id}",
                "prefect.resource.name": paused_work_pool.name,
                "prefect.resource.role": "target",
            }
        )
    ]
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "resume-work-pool",
        "invocation": str(triggered_resume_action.id),
    }

    assert executed_event.event == "prefect.automation.action.executed"
    assert executed_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.work-pool.{paused_work_pool.id}",
                "prefect.resource.name": paused_work_pool.name,
                "prefect.resource.role": "target",
            }
        )
    ]
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "resume-work-pool",
        "invocation": str(triggered_resume_action.id),
        "status_code": 204,
    }
