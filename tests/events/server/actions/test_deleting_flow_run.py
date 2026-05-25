from datetime import timedelta
from typing import AsyncGenerator
from uuid import uuid4

import pytest
from docket import Docket
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.api.server import create_app
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
from prefect.settings import get_current_settings
from prefect.types._datetime import now

pytestmark = pytest.mark.clear_db


@pytest.fixture
async def orchestration_api_docket() -> AsyncGenerator[None, None]:
    settings = get_current_settings()
    async with Docket(
        name=f"test-docket-{uuid4().hex[:8]}",
        url=settings.server.docket.url,
        execution_ttl=timedelta(0),
    ) as docket:
        docket.register_collection(
            "prefect.server.api.background_workers:task_functions"
        )
        create_app().api_app.state.docket = docket
        yield


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
def delete_exposures_that_last_over_a_minute(
    take_a_picture: Deployment,
) -> Automation:
    return Automation(
        name="If the exposure is longer than 1 minute, delete it",
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
        actions=[actions.DeleteFlowRun()],
    )


@pytest.fixture
def delete_that_long_exposure(
    delete_exposures_that_last_over_a_minute: Automation,
    super_long_exposure: FlowRun,
) -> TriggeredAction:
    firing = Firing(
        trigger=delete_exposures_that_last_over_a_minute.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={
            "prefect.resource.id": f"prefect.flow-run.{super_long_exposure.id}"
        },
        triggering_event=None,
    )
    return TriggeredAction(
        automation=delete_exposures_that_last_over_a_minute,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=delete_exposures_that_last_over_a_minute.actions[0],
    )


async def test_deleting_long_exposure(
    delete_that_long_exposure: TriggeredAction,
    super_long_exposure: FlowRun,
    session: AsyncSession,
    orchestration_api_docket,
):
    flow_run = await flow_runs.read_flow_run(
        session=session,
        flow_run_id=super_long_exposure.id,
    )
    assert flow_run is not None
    assert flow_run.state_type == StateType.RUNNING

    action = delete_that_long_exposure.action
    assert isinstance(action, actions.DeleteFlowRun)

    await action.act(delete_that_long_exposure)

    session.expunge_all()

    flow_run = await flow_runs.read_flow_run(
        session=session,
        flow_run_id=super_long_exposure.id,
    )
    assert flow_run is None


@pytest.fixture
def delete_exposures_that_go_into_a_weirdo_state(
    take_a_picture: Deployment,
) -> Automation:
    return Automation(
        name="If the exposure goes into a weird state, delete it",
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
        actions=[actions.DeleteFlowRun()],
    )


@pytest.fixture
def delete_that_weird_exposure(
    delete_exposures_that_go_into_a_weirdo_state: Automation,
    super_long_exposure: FlowRun,
) -> TriggeredAction:
    firing = Firing(
        trigger=delete_exposures_that_go_into_a_weirdo_state.trigger,
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
        automation=delete_exposures_that_go_into_a_weirdo_state,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=delete_exposures_that_go_into_a_weirdo_state.actions[0],
    )


async def test_success_event(
    delete_that_weird_exposure: TriggeredAction,
    super_long_exposure: FlowRun,
    orchestration_api_docket,
):
    action = delete_that_weird_exposure.action

    await action.act(delete_that_weird_exposure)
    await action.succeed(delete_that_weird_exposure)

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    expected_related = [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.flow-run.{super_long_exposure.id}",
                "prefect.resource.role": "target",
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.event.{delete_that_weird_exposure.triggering_event.id}",
                "prefect.resource.role": "triggering-event",
            }
        ),
    ]

    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.related == expected_related
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "delete-flow-run",
        "invocation": str(delete_that_weird_exposure.id),
    }

    assert executed_event.event == "prefect.automation.action.executed"
    assert executed_event.related == expected_related
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "delete-flow-run",
        "invocation": str(delete_that_weird_exposure.id),
        "status_code": 204,
    }
