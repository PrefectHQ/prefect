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
from prefect.server.models import deployments, flows
from prefect.server.schemas.actions import DeploymentScheduleCreate
from prefect.server.schemas.core import Deployment, Flow
from prefect.server.schemas.schedules import IntervalSchedule
from prefect.types import DateTime
from prefect.types._datetime import now
from prefect.utilities.pydantic import parse_obj_as


def test_source_determines_if_deployment_id_is_required_or_allowed():
    with pytest.raises(ValidationError):
        actions.PauseDeployment(source="selected")

    with pytest.raises(ValidationError):
        actions.PauseDeployment(source="inferred", deployment_id=uuid4())


@pytest.fixture
async def hourly_garden_patrol(session: AsyncSession) -> Deployment:
    walk_the_perimeter = await flows.create_flow(
        session=session,
        flow=Flow(name="walk-the-perimeter"),
    )
    assert walk_the_perimeter
    await session.flush()

    hourly_garden_patrol = await deployments.create_deployment(
        session=session,
        deployment=Deployment(
            name="Walk the perimeter of the garden",
            flow_id=walk_the_perimeter.id,
            paused=False,
        ),
    )

    assert hourly_garden_patrol

    await deployments.create_deployment_schedules(
        session=session,
        deployment_id=hourly_garden_patrol.id,
        schedules=[
            DeploymentScheduleCreate(
                active=True,
                schedule=IntervalSchedule(interval=timedelta(hours=1)),
            )
        ],
    )

    await session.commit()

    return Deployment.model_validate(hourly_garden_patrol, from_attributes=True)


@pytest.fixture
def when_the_guard_gets_sick_stop_the_patrol(
    hourly_garden_patrol: Deployment,
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
            actions.PauseDeployment(
                source="selected",
                deployment_id=hourly_garden_patrol.id,
            )
        ],
    )


@pytest.fixture
def guard_one_got_sick(
    hourly_garden_patrol: Deployment,
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
                "prefect.resource.role": "deployment",
                "prefect.resource.id": f"prefect.deployment.{hourly_garden_patrol.id}",
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
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
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


async def test_pausing_deployment(
    let_guard_one_get_some_sleep: TriggeredAction,
    hourly_garden_patrol: Deployment,
    session: AsyncSession,
):
    patrol = Deployment.model_validate(
        await deployments.read_deployment(session, hourly_garden_patrol.id),
        from_attributes=True,
    )
    assert not patrol.paused

    action = let_guard_one_get_some_sleep.action
    await action.act(let_guard_one_get_some_sleep)

    session.expunge_all()

    patrol = Deployment.model_validate(
        await deployments.read_deployment(session, hourly_garden_patrol.id),
        from_attributes=True,
    )

    assert patrol.paused


async def test_pausing_errors_are_reported_as_events(
    let_guard_one_get_some_sleep: TriggeredAction,
):
    action = let_guard_one_get_some_sleep.action
    assert isinstance(action, actions.PauseDeployment)

    action.deployment_id = uuid4()  # this doesn't exist

    with pytest.raises(actions.ActionFailed, match="Unexpected status"):
        await action.act(let_guard_one_get_some_sleep)


@pytest.fixture
def when_the_guard_gets_well_resume_the_patrol(
    hourly_garden_patrol: Deployment,
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
            actions.ResumeDeployment(
                source="selected",
                deployment_id=hourly_garden_patrol.id,
            )
        ],
    )


@pytest.fixture
def guard_one_got_well(
    hourly_garden_patrol: Deployment,
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
                "prefect.resource.role": "deployment",
                "prefect.resource.id": f"prefect.deployment.{hourly_garden_patrol.id}",
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
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
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


async def test_resuming_deployment(
    put_guard_one_back_on_duty: TriggeredAction,
    hourly_garden_patrol: Deployment,
    session: AsyncSession,
):
    patrol = await deployments.read_deployment(session, hourly_garden_patrol.id)
    patrol.paused = True
    await session.commit()

    patrol = Deployment.model_validate(
        await deployments.read_deployment(session, hourly_garden_patrol.id),
        from_attributes=True,
    )
    assert patrol.paused

    action = put_guard_one_back_on_duty.action
    await action.act(put_guard_one_back_on_duty)

    session.expunge_all()

    patrol = Deployment.model_validate(
        await deployments.read_deployment(session, hourly_garden_patrol.id),
        from_attributes=True,
    )

    assert not patrol.paused


async def test_resuming_errors_are_reported_as_events(
    put_guard_one_back_on_duty: TriggeredAction,
):
    action = put_guard_one_back_on_duty.action
    assert isinstance(action, actions.ResumeDeployment)

    action.deployment_id = uuid4()  # this doesn't exist

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
        actions=[actions.PauseDeployment(source="inferred")],
    )


@pytest.fixture
def pause_their_deployment(
    when_the_guard_gets_sick_stop_their_patrol: Automation,
    guard_one_got_sick: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=when_the_guard_gets_sick_stop_their_patrol.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
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


async def test_pausing_inferred_deployment(
    pause_their_deployment: TriggeredAction,
    hourly_garden_patrol: Deployment,
    session: AsyncSession,
):
    patrol = Deployment.model_validate(
        await deployments.read_deployment(session, hourly_garden_patrol.id),
        from_attributes=True,
    )
    assert not patrol.paused

    action = pause_their_deployment.action
    await action.act(pause_their_deployment)

    session.expunge_all()

    patrol = Deployment.model_validate(
        await deployments.read_deployment(session, hourly_garden_patrol.id),
        from_attributes=True,
    )
    assert patrol.paused


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
        actions=[actions.ResumeDeployment(source="inferred")],
    )


@pytest.fixture
def resume_their_deployment(
    when_the_guard_recovers_resume_their_patrol: Automation,
    guard_one_got_well: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=when_the_guard_recovers_resume_their_patrol.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
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


async def test_resuming_inferred_deployment(
    resume_their_deployment: TriggeredAction,
    hourly_garden_patrol: Deployment,
    session: AsyncSession,
):
    patrol = await deployments.read_deployment(session, hourly_garden_patrol.id)
    patrol.paused = True
    await session.commit()

    patrol = Deployment.model_validate(
        await deployments.read_deployment(session, hourly_garden_patrol.id),
        from_attributes=True,
    )
    assert patrol.paused

    action = resume_their_deployment.action
    await action.act(resume_their_deployment)

    session.expunge_all()

    patrol = Deployment.model_validate(
        await deployments.read_deployment(session, hourly_garden_patrol.id),
        from_attributes=True,
    )

    assert not patrol.paused


async def test_inferring_deployment_requires_event(
    resume_their_deployment: TriggeredAction,
):
    resume_their_deployment.triggering_event = None  # simulate a proactive trigger

    action = resume_their_deployment.action

    with pytest.raises(actions.ActionFailed, match="No event to infer the deployment"):
        await action.act(resume_their_deployment)


async def test_inferring_deployment_requires_some_matching_resource(
    resume_their_deployment: TriggeredAction,
):
    assert resume_their_deployment.triggering_event
    resume_their_deployment.triggering_event.related = []  # no relevant related resources

    action = resume_their_deployment.action

    with pytest.raises(actions.ActionFailed, match="No deployment could be inferred"):
        await action.act(resume_their_deployment)


async def test_inferring_deployment_requires_recognizable_resource_id(
    resume_their_deployment: TriggeredAction,
):
    assert resume_their_deployment.triggering_event
    resume_their_deployment.triggering_event.related = parse_obj_as(
        List[RelatedResource],
        [
            {
                "prefect.resource.role": "deployment",
                "prefect.resource.id": "prefect.deployment.nope",  # not a uuid
            },
            {
                "prefect.resource.role": "deployment",
                "prefect.resource.id": f"oh.so.close.{uuid4()}",  # not a deployment
            },
            {
                "prefect.resource.role": "deployment",
                "prefect.resource.id": "nah-ah",  # not a dotted name
            },
        ],
    )

    action = resume_their_deployment.action

    with pytest.raises(actions.ActionFailed, match="No deployment could be inferred"):
        await action.act(resume_their_deployment)


async def test_pausing_success_event(
    pause_their_deployment: TriggeredAction,
    hourly_garden_patrol: Deployment,
):
    action = pause_their_deployment.action

    await action.act(pause_their_deployment)
    await action.succeed(pause_their_deployment)

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.deployment.{hourly_garden_patrol.id}",
                "prefect.resource.role": "target",
            }
        )
    ]
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "pause-deployment",
        "invocation": str(pause_their_deployment.id),
    }

    assert executed_event.event == "prefect.automation.action.executed"
    assert executed_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.deployment.{hourly_garden_patrol.id}",
                "prefect.resource.role": "target",
            }
        )
    ]
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "pause-deployment",
        "invocation": str(pause_their_deployment.id),
        "status_code": 200,
    }


async def test_resuming_success_event(
    resume_their_deployment: TriggeredAction,
    hourly_garden_patrol: Deployment,
):
    action = resume_their_deployment.action

    await action.act(resume_their_deployment)
    await action.succeed(resume_their_deployment)

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.deployment.{hourly_garden_patrol.id}",
                "prefect.resource.role": "target",
            }
        )
    ]
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "resume-deployment",
        "invocation": str(resume_their_deployment.id),
    }

    assert executed_event.event == "prefect.automation.action.executed"
    assert executed_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.deployment.{hourly_garden_patrol.id}",
                "prefect.resource.role": "target",
            }
        )
    ]
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "resume-deployment",
        "invocation": str(resume_their_deployment.id),
        "status_code": 200,
    }
