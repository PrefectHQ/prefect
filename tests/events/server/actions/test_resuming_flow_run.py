import uuid
from datetime import timedelta

import pendulum
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
from prefect.server.schemas.states import Paused, Running, StateType


@pytest.fixture
async def paused_flow_run(session: AsyncSession) -> FlowRun:
    flow = await flows.create_flow(
        session=session,
        flow=Flow(name="test-flow"),
    )
    deployment = await deployments.create_deployment(
        session=session,
        deployment=Deployment(
            name="test-deployment",
            flow_id=flow.id,
            paused=False,
        ),
    )
    flow_run = await flow_runs.create_flow_run(
        session=session,
        flow_run=FlowRun(
            flow_id=flow.id,
            deployment_id=deployment.id,
            state=Paused(),
        ),
    )
    await session.commit()
    return FlowRun.model_validate(flow_run, from_attributes=True)


@pytest.fixture
def resume_paused_flow_run(paused_flow_run: FlowRun) -> Automation:
    return Automation(
        name="Resume paused flow run",
        trigger=EventTrigger(
            match_related={
                "prefect.resource.role": "flow-run",
                "prefect.resource.id": f"prefect.flow-run.{paused_flow_run.id}",
            },
            after={"prefect.flow-run.Paused"},
            expect={"prefect.flow-run.Running"},
            posture=Posture.Proactive,
            threshold=0,
            within=timedelta(minutes=1),
        ),
        actions=[actions.ResumeFlowRun()],
    )


@pytest.fixture
def resume_that_paused_flow_run(
    resume_paused_flow_run: Automation,
    paused_flow_run: FlowRun,
) -> TriggeredAction:
    firing = Firing(
        trigger=resume_paused_flow_run.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=pendulum.now("UTC"),
        triggering_labels={},
        triggering_event=ReceivedEvent(
            occurred=pendulum.now("UTC"),
            event="prefect.flow-run.Paused",
            resource={"prefect.resource.id": f"prefect.flow-run.{paused_flow_run.id}"},
            id=uuid.uuid4(),
        ),
    )
    return TriggeredAction(
        automation=resume_paused_flow_run,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=resume_paused_flow_run.actions[0],
    )


async def test_resuming_paused_flow_run(
    resume_that_paused_flow_run: TriggeredAction,
    paused_flow_run: FlowRun,
    session: AsyncSession,
):
    flow_run = await flow_runs.read_flow_run(
        session,
        paused_flow_run.id,
    )
    assert flow_run
    assert flow_run.state.type == StateType.PAUSED

    action = resume_that_paused_flow_run.action
    assert isinstance(action, actions.ResumeFlowRun)

    await action.act(resume_that_paused_flow_run)

    session.expunge_all()

    flow_run = await flow_runs.read_flow_run(
        session,
        paused_flow_run.id,
    )
    assert flow_run
    assert flow_run.state.type == StateType.RUNNING


async def test_resume_flow_run_success_event(
    resume_that_paused_flow_run: TriggeredAction,
    paused_flow_run: FlowRun,
):
    action = resume_that_paused_flow_run.action

    await action.act(resume_that_paused_flow_run)
    await action.succeed(resume_that_paused_flow_run)

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.flow-run.{paused_flow_run.id}",
                "prefect.resource.role": "target",
            }
        )
    ]
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "resume-flow-run",
        "invocation": str(resume_that_paused_flow_run.id),
    }

    assert executed_event.event == "prefect.automation.action.executed"
    assert executed_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.flow-run.{paused_flow_run.id}",
                "prefect.resource.role": "target",
            }
        )
    ]
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "resume-flow-run",
        "invocation": str(resume_that_paused_flow_run.id),
    }


async def test_resume_flow_run_not_paused(
    resume_that_paused_flow_run: TriggeredAction,
    paused_flow_run: FlowRun,
    session: AsyncSession,
):
    # Set the flow run to Running state
    await flow_runs.set_flow_run_state(
        session=session,
        flow_run_id=paused_flow_run.id,
        state=Running(),
    )
    await session.commit()

    action = resume_that_paused_flow_run.action
    assert isinstance(action, actions.ResumeFlowRun)

    with pytest.raises(actions.ActionFailed, match="Failed to resume flow run"):
        await action.act(resume_that_paused_flow_run)

    session.expunge_all()

    flow_run = await flow_runs.read_flow_run(
        session,
        paused_flow_run.id,
    )
    assert flow_run
    assert flow_run.state.type == StateType.RUNNING
