from datetime import timedelta
from uuid import uuid4

import pytest
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
from prefect.server.models import deployments, flow_runs, flows
from prefect.server.schemas.core import Deployment, Flow, FlowRun
from prefect.server.schemas.states import Running, StateType
from prefect.types._datetime import now


@pytest.fixture
async def take_a_picture(session: AsyncSession) -> Deployment:
    snap_a_pic = await flows.create_flow(
        session=session,
        flow=Flow(name="snap-a-pic"),
    )
    assert snap_a_pic
    await session.flush()

    deployment = await deployments.create_deployment(
        session=session,
        deployment=Deployment(
            name="Take a picture on demand",
            flow_id=snap_a_pic.id,
            paused=False,
        ),
    )
    await session.commit()
    return Deployment.model_validate(deployment, from_attributes=True)


@pytest.fixture
async def super_long_exposure(
    take_a_picture: Deployment, session: AsyncSession
) -> FlowRun:
    super_long_exposure = await flow_runs.create_flow_run(
        session=session,
        flow_run=FlowRun(
            deployment_id=take_a_picture.id,
            flow_id=take_a_picture.flow_id,
            state=Running(),
        ),
    )
    await session.commit()

    return FlowRun.model_validate(super_long_exposure, from_attributes=True)


@pytest.fixture
def suspend_exposures_that_last_over_a_minute(
    take_a_picture: Deployment,
) -> Automation:
    return Automation(
        name="If the exposure is longer than 1 minute, suspend it",
        trigger=EventTrigger(
            match_related={
                "prefect.resource.role": "deployment",
                "prefect.resource.id": f"prefect.deployment.{take_a_picture.id}",
            },
            after={"prefect.flow-run.Running"},
            expect={"prefect.flow-run.Completed"},
            posture=Posture.Proactive,
            threshold=0,
            within=timedelta(minutes=1),
        ),
        actions=[actions.SuspendFlowRun()],
    )


@pytest.fixture
def suspend_that_long_exposure(
    suspend_exposures_that_last_over_a_minute: Automation,
    super_long_exposure: FlowRun,
) -> TriggeredAction:
    firing = Firing(
        trigger=suspend_exposures_that_last_over_a_minute.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={
            "prefect.resource.id": f"prefect.flow-run.{super_long_exposure.id}"
        },
    )
    return TriggeredAction(
        automation=suspend_exposures_that_last_over_a_minute,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=suspend_exposures_that_last_over_a_minute.actions[0],
    )


async def pausing_long_exposure(
    suspend_that_long_exposure: TriggeredAction,
    super_long_exposure: FlowRun,
    session: AsyncSession,
):
    flow_run = await flow_runs.read_flow_run(
        session,
        super_long_exposure.id,
    )
    assert flow_run.state_type == StateType.RUNNING

    action = suspend_that_long_exposure.action
    assert isinstance(action, actions.SuspendFlowRun)

    await action.act(suspend_that_long_exposure)

    flow_run = await flow_runs.read_flow_run(
        session,
        super_long_exposure.id,
    )
    assert flow_run.state.type == StateType.PAUSED
    assert flow_run.state.name == "Suspended"


@pytest.fixture
def suspend_exposures_that_go_into_a_weirdo_state(
    take_a_picture: Deployment,
) -> Automation:
    return Automation(
        name="If the exposure is longer than 1 minute, suspend it",
        trigger=EventTrigger(
            match_related={
                "prefect.resource.role": "deployment",
                "prefect.resource.id": f"prefect.deployment.{take_a_picture.id}",
            },
            after={"prefect.flow-run.Running"},
            expect={"prefect.flow-run.Weirdo"},
            posture=Posture.Reactive,
            threshold=0,
            within=timedelta(minutes=1),
        ),
        actions=[actions.SuspendFlowRun()],
    )


@pytest.fixture
def suspend_that_weird_exposure(
    suspend_exposures_that_go_into_a_weirdo_state: Automation,
    super_long_exposure: FlowRun,
) -> TriggeredAction:
    firing = Firing(
        trigger=suspend_exposures_that_go_into_a_weirdo_state.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={},
        triggering_event=ReceivedEvent(
            occurred=now("UTC"),
            event="prefect.flow-run.Weirdo",
            resource={
                "prefect.resource.id": f"prefect.flow-run.{super_long_exposure.id}"
            },
            id=uuid4(),
        ),
    )
    return TriggeredAction(
        automation=suspend_exposures_that_go_into_a_weirdo_state,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=suspend_exposures_that_go_into_a_weirdo_state.actions[0],
    )


async def test_suspending_weird_exposure(
    suspend_that_weird_exposure: TriggeredAction,
    super_long_exposure: FlowRun,
    session: AsyncSession,
):
    flow_run = await flow_runs.read_flow_run(
        session,
        super_long_exposure.id,
    )
    assert flow_run.state_type == StateType.RUNNING

    action = suspend_that_weird_exposure.action
    assert isinstance(action, actions.SuspendFlowRun)

    await action.act(suspend_that_weird_exposure)

    session.expunge_all()

    flow_run = await flow_runs.read_flow_run(
        session,
        super_long_exposure.id,
    )
    assert flow_run.state_type == StateType.PAUSED


async def test_success_event(
    suspend_that_weird_exposure: TriggeredAction,
    super_long_exposure: FlowRun,
):
    action = suspend_that_weird_exposure.action

    await action.act(suspend_that_weird_exposure)
    await action.succeed(suspend_that_weird_exposure)

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.flow-run.{super_long_exposure.id}",
                "prefect.resource.role": "target",
            }
        )
    ]
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "suspend-flow-run",
        "invocation": str(suspend_that_weird_exposure.id),
    }

    assert executed_event.event == "prefect.automation.action.executed"
    assert executed_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.flow-run.{super_long_exposure.id}",
                "prefect.resource.role": "target",
            }
        )
    ]
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "suspend-flow-run",
        "invocation": str(suspend_that_weird_exposure.id),
        "status_code": 201,
    }
