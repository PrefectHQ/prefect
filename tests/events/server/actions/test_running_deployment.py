from datetime import datetime, timedelta, timezone
from typing import Any
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
from prefect.server.models import deployments, flow_runs, flows, variables, workers
from prefect.server.schemas.actions import VariableCreate, WorkPoolCreate
from prefect.server.schemas.core import CreatedBy, Deployment, Flow
from prefect.types._datetime import now


async def test_action_can_omit_parameters():
    """Regression test for https://github.com/PrefectHQ/nebula/issues/2857, where
    `parameters` are omitted by the UI"""

    action = actions.RunDeployment.model_validate(
        {
            "type": "run-deployment",
            "source": "inferred",
        }
    )
    assert action.parameters is None

    action = actions.RunDeployment.model_validate(
        {
            "type": "run-deployment",
            "source": "inferred",
            "parameters": None,
        }
    )
    assert action.parameters is None

    action = actions.RunDeployment.model_validate(
        {
            "type": "run-deployment",
            "source": "inferred",
            "parameters": {},
        }
    )
    assert action.parameters == {}


@pytest.fixture
async def take_a_picture(session: AsyncSession) -> Deployment:
    work_pool = await workers.create_work_pool(
        session=session,
        work_pool=WorkPoolCreate(
            name="wp-1",
            type="None",
            description="None",
            base_job_template={},
        ),
    )

    snap_a_pic = await flows.create_flow(
        session=session,
        flow=Flow(name="snap-a-pic"),
    )
    await session.flush()

    deployment = await deployments.create_deployment(
        session=session,
        deployment=Deployment(
            name="Take a picture on demand",
            flow_id=snap_a_pic.id,
            paused=False,
            work_queue_id=work_pool.default_queue_id,
        ),
    )
    assert deployment
    await session.commit()

    return Deployment.model_validate(deployment, from_attributes=True)


@pytest.fixture
def take_a_picture_of_the_culprit(take_a_picture: Deployment) -> Automation:
    return Automation(
        name="If my lilies get nibbled, take a picture of the culprit",
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
        actions=[
            actions.RunDeployment(
                deployment_id=take_a_picture.id,
                parameters={
                    "camera": "back-yard",
                    "focal_ratio": 1 / 6,
                    "flash": False,
                    "meta": {
                        "automation": "{{ automation.name }}",
                    },
                },
                job_variables={"resolution": "high", "mode": "color"},
            )
        ],
    )


@pytest.fixture
def snap_that_naughty_woodchuck(
    take_a_picture_of_the_culprit: Automation,
    woodchonk_nibbled: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=take_a_picture_of_the_culprit.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={},
        triggering_event=woodchonk_nibbled,
    )
    return TriggeredAction(
        automation=take_a_picture_of_the_culprit,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=take_a_picture_of_the_culprit.actions[0],
    )


async def test_running_a_deployment(
    snap_that_naughty_woodchuck: TriggeredAction,
    take_a_picture: Deployment,
    session: AsyncSession,
):
    action = snap_that_naughty_woodchuck.action

    assert isinstance(action, actions.RunDeployment)
    assert action.source == "selected"
    assert action.deployment_id

    await action.act(snap_that_naughty_woodchuck)

    (run,) = await flow_runs.read_flow_runs(session)

    assert run.state
    assert run.state.name == "Scheduled"
    assert run.deployment_id == take_a_picture.id

    assert run.parameters == {
        "camera": "back-yard",
        "focal_ratio": 1 / 6,
        "flash": False,
        "meta": {
            "automation": snap_that_naughty_woodchuck.automation.name,
        },
    }

    assert run.created_by == CreatedBy(
        id=snap_that_naughty_woodchuck.automation.id,
        type="AUTOMATION",
        display_value=snap_that_naughty_woodchuck.automation.name,
    )

    assert run.job_variables == {"mode": "color", "resolution": "high"}


async def test_running_a_deployment_with_overrides_enabled(
    snap_that_naughty_woodchuck: TriggeredAction,
    session: AsyncSession,
):
    action = snap_that_naughty_woodchuck.action

    assert isinstance(action, actions.RunDeployment)
    assert action.job_variables is not None

    await action.act(snap_that_naughty_woodchuck)

    *_, run = await flow_runs.read_flow_runs(session)
    assert run.job_variables == {"resolution": "high", "mode": "color"}


async def test_running_a_deployment_unicode_automation_name(
    snap_that_naughty_woodchuck: TriggeredAction,
    take_a_picture: Deployment,
    session: AsyncSession,
):
    action = snap_that_naughty_woodchuck.action

    snap_that_naughty_woodchuck.automation.name = "📸 Gotcha!"

    assert isinstance(action, actions.RunDeployment)
    assert action.source == "selected"
    assert action.deployment_id

    await action.act(snap_that_naughty_woodchuck)

    (run,) = await flow_runs.read_flow_runs(session)

    assert run.state
    assert run.state.name == "Scheduled"
    assert run.deployment_id == take_a_picture.id

    assert run.parameters == {
        "camera": "back-yard",
        "focal_ratio": 1 / 6,
        "flash": False,
        "meta": {
            "automation": snap_that_naughty_woodchuck.automation.name,
        },
    }

    assert run.created_by == CreatedBy(
        id=snap_that_naughty_woodchuck.automation.id,
        type="AUTOMATION",
        display_value="📸 Gotcha!",
    )


@pytest.fixture
async def my_workspace_variable(
    session: AsyncSession,
) -> None:
    await variables.create_variable(
        session, VariableCreate(name="my_variable", value="my variable value")
    )
    await session.commit()


async def test_running_a_deployment_supports_schemas_v2(
    snap_that_naughty_woodchuck: TriggeredAction,
    take_a_picture: Deployment,
    session: AsyncSession,
    my_workspace_variable: None,
):
    action = snap_that_naughty_woodchuck.action

    snap_that_naughty_woodchuck.automation.name = "📸 Gotcha!"

    assert isinstance(action, actions.RunDeployment)
    assert action.source == "selected"
    assert action.deployment_id

    action.parameters = {
        "camera": "back-yard",
        "focal_ratio": {"__prefect_kind": "whatevs", "value": 1 / 6},
        "flash": {"__prefect_kind": "json", "value": "false"},
        "meta": {
            "__prefect_kind": "json",
            "value": '{"one_thing": "hello", "another_thing": 5}',
        },
        "somefin": {
            "__prefect_kind": "workspace_variable",
            "variable_name": "my_variable",
        },
    }

    await action.act(snap_that_naughty_woodchuck)

    (run,) = await flow_runs.read_flow_runs(session)

    assert run.state
    assert run.state.name == "Scheduled"
    assert run.deployment_id == take_a_picture.id

    assert run.parameters == {
        "camera": "back-yard",
        "focal_ratio": 1 / 6,
        "flash": False,
        "meta": {"one_thing": "hello", "another_thing": 5},
        "somefin": "my variable value",
    }

    assert run.created_by == CreatedBy(
        id=snap_that_naughty_woodchuck.automation.id,
        type="AUTOMATION",
        display_value="📸 Gotcha!",
    )


async def test_run_deployment_parameter_validation_handles_workspace_variables(
    snap_that_naughty_woodchuck: TriggeredAction,
    my_workspace_variable: None,
):
    # regression test for https://github.com/PrefectHQ/nebula/issues/7425
    # previously this would raise a `ValidationError` due to the workspace variable not being found
    # and failing to hydrate.

    actions.RunDeployment(
        deployment_id=uuid4(),
        parameters={
            "my_string": {
                "__prefect_kind": "workspace_variable",
                "variable_name": "my_variable",
            }
        },
    )


@pytest.mark.parametrize(
    "value",
    [
        "string-value",
        '"string-value"',
        123,
        12.3,
        True,
        False,
        None,
        {"key": "value"},
        ["value1", "value2"],
        {"key": ["value1", "value2"]},
    ],
)
async def test_run_deployment_handles_json_workspace_variables(
    snap_that_naughty_woodchuck: TriggeredAction,
    session: AsyncSession,
    value: Any,
):
    await variables.create_variable(
        session, VariableCreate(name="my_workspace_var", value=value)
    )
    await session.commit()

    action = snap_that_naughty_woodchuck.action
    assert action
    assert isinstance(action, actions.RunDeployment)

    action.parameters = {
        "my_param": {
            "__prefect_kind": "workspace_variable",
            "variable_name": "my_workspace_var",
        }
    }

    await action.act(snap_that_naughty_woodchuck)


async def test_run_deployment_parameter_validation_handles_top_level_hydration_error(
    snap_that_naughty_woodchuck: TriggeredAction,
):
    # regression test for: https://github.com/PrefectHQ/prefect/issues/12585
    # Model instantiation would fail with `AttributeError` instead of correctly raising a ValidationError

    with pytest.raises(ValidationError) as exc:
        actions.RunDeployment(
            deployment_id=uuid4(),
            parameters={"__prefect_kind": "json", "value": "{notajsonstring}"},
        )
    assert (
        "Invalid JSON: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"
        in str(exc.value)
    )


async def test_running_a_deployment_handles_top_level_hydration_error(
    snap_that_naughty_woodchuck: TriggeredAction,
):
    # regression test for: https://github.com/PrefectHQ/prefect/issues/12585
    # The action would fail due to an `AttributeError` instead of `InvalidJSON`

    action = snap_that_naughty_woodchuck.action
    assert isinstance(action, actions.RunDeployment)
    action.parameters = {
        "__prefect_kind": "json",
        "value": "{notvalidjson}",
    }

    with pytest.raises(
        actions.ActionFailed,
    ) as exc:
        await action.act(snap_that_naughty_woodchuck)
    assert "Unable to create flow run from deployment: InvalidJSON()" in str(exc.value)


async def test_running_an_inferred_deployment(
    snap_that_naughty_woodchuck: TriggeredAction,
    take_a_picture: Deployment,
    session: AsyncSession,
):
    action = snap_that_naughty_woodchuck.action

    assert isinstance(action, actions.RunDeployment)
    action.source = "inferred"
    action.deployment_id = None

    # add a related resource for finding the associated deployment
    assert snap_that_naughty_woodchuck.triggering_event
    snap_that_naughty_woodchuck.triggering_event.related.append(
        RelatedResource.model_validate(
            {
                "prefect.resource.role": "deployment",
                "prefect.resource.id": f"prefect.deployment.{take_a_picture.id}",
            }
        )
    )

    await action.act(snap_that_naughty_woodchuck)

    (run,) = await flow_runs.read_flow_runs(session)

    assert run.state
    assert run.state.name == "Scheduled"
    assert run.deployment_id == take_a_picture.id

    assert run.parameters == {
        "camera": "back-yard",
        "focal_ratio": 1 / 6,
        "flash": False,
        "meta": {
            "automation": snap_that_naughty_woodchuck.automation.name,
        },
    }

    assert run.created_by == CreatedBy(
        id=snap_that_naughty_woodchuck.automation.id,
        type="AUTOMATION",
        display_value=snap_that_naughty_woodchuck.automation.name,
    )


async def test_orchestration_errors_are_reported_as_events(
    snap_that_naughty_woodchuck: TriggeredAction,
):
    action = snap_that_naughty_woodchuck.action
    assert isinstance(action, actions.RunDeployment)

    action.deployment_id = uuid4()  # this doesn't exist

    with pytest.raises(
        actions.ActionFailed,
        match="Unexpected status from 'run-deployment' action: 404",
    ):
        await action.act(snap_that_naughty_woodchuck)


async def test_validates_templates_in_parameters(
    take_a_picture: Deployment,
):
    expected_error = "bad_template: Invalid jinja: unexpected '}'"
    with pytest.raises(ValueError, match=expected_error):
        actions.RunDeployment(
            deployment_id=take_a_picture.id,
            parameters={
                "bad_template": "This is an {{ invalid } template.",
            },
        )


async def test_success_event(
    snap_that_naughty_woodchuck: TriggeredAction,
    take_a_picture: Deployment,
    session: AsyncSession,
):
    action = snap_that_naughty_woodchuck.action

    await action.act(snap_that_naughty_woodchuck)
    await action.succeed(snap_that_naughty_woodchuck)

    runs = await flow_runs.read_flow_runs(session)
    (new_flow_run,) = runs

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.deployment.{take_a_picture.id}",
                "prefect.resource.role": "target",
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.flow-run.{new_flow_run.id}",
                "prefect.resource.name": new_flow_run.name,
                "prefect.resource.role": "flow-run",
            }
        ),
    ]
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "run-deployment",
        "invocation": str(snap_that_naughty_woodchuck.id),
    }

    assert executed_event.event == "prefect.automation.action.executed"
    assert executed_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.deployment.{take_a_picture.id}",
                "prefect.resource.role": "target",
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.flow-run.{new_flow_run.id}",
                "prefect.resource.name": new_flow_run.name,
                "prefect.resource.role": "flow-run",
            }
        ),
    ]
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "run-deployment",
        "invocation": str(snap_that_naughty_woodchuck.id),
        "status_code": 201,
    }


async def test_running_a_deployment_action_succeeds_paramaters_too_large(
    snap_that_naughty_woodchuck: TriggeredAction,
    take_a_picture: Deployment,
    session: AsyncSession,
):
    """In a significant difference from Prefect Cloud, we will not restrict the size of
    parameters in the open-source Prefect API"""
    action = snap_that_naughty_woodchuck.action

    assert isinstance(action, actions.RunDeployment)
    assert action.source == "selected"
    assert action.deployment_id
    assert action.parameters

    action.parameters["camera"] = "testing" * 100000

    await action.act(snap_that_naughty_woodchuck)


async def test_deployment_action_accepts_job_variables():
    action = actions.RunDeployment.model_validate(
        {
            "type": "run-deployment",
            "source": "inferred",
        }
    )
    assert action.job_variables is None

    action = actions.RunDeployment.model_validate(
        {
            "type": "run-deployment",
            "source": "inferred",
            "job_variables": None,
        }
    )
    assert action.job_variables is None

    action = actions.RunDeployment.model_validate(
        {
            "type": "run-deployment",
            "source": "inferred",
            "job_variables": {},
        }
    )
    assert action.job_variables == {}

    job_vars = {"foo": "bar"}
    action = actions.RunDeployment.model_validate(
        {
            "type": "run-deployment",
            "source": "inferred",
            "job_variables": job_vars,
        }
    )
    assert action.job_variables == job_vars

    job_vars = {"nested": {"vars": "ok"}}
    action = actions.RunDeployment.model_validate(
        {
            "type": "run-deployment",
            "source": "inferred",
            "job_variables": job_vars,
        }
    )
    assert action.job_variables == job_vars


async def test_action_can_omit_schedule_after_field():
    """Test that the schedule_after field defaults to timedelta(0)"""
    action = actions.RunDeployment.model_validate(
        {
            "type": "run-deployment",
            "source": "inferred",
        }
    )
    assert action.schedule_after == timedelta(0)


async def test_action_accepts_schedule_after_field():
    """Test that the schedule_after field accepts various timedelta values"""
    action = actions.RunDeployment.model_validate(
        {
            "type": "run-deployment",
            "source": "inferred",
            "schedule_after": 3600,  # seconds
        }
    )
    assert action.schedule_after == timedelta(hours=1)

    action = actions.RunDeployment.model_validate(
        {
            "type": "run-deployment",
            "source": "inferred",
            "schedule_after": "PT2H",  # ISO 8601 duration
        }
    )
    assert action.schedule_after == timedelta(hours=2)


async def test_action_rejects_negative_schedule_after():
    """Test that negative schedule_after values are rejected"""
    with pytest.raises(ValidationError, match="schedule_after must be non-negative"):
        actions.RunDeployment.model_validate(
            {
                "type": "run-deployment",
                "source": "inferred",
                "schedule_after": -3600,
            }
        )


async def test_running_deployment_with_delay(
    snap_that_naughty_woodchuck: TriggeredAction,
    take_a_picture: Deployment,
    session: AsyncSession,
):
    """Test that the schedule_after field correctly schedules the deployment for later"""
    action = snap_that_naughty_woodchuck.action

    assert isinstance(action, actions.RunDeployment)
    # Set a 2-hour delay
    action.schedule_after = timedelta(hours=2)

    start_time = datetime.now(timezone.utc)

    await action.act(snap_that_naughty_woodchuck)

    runs = await flow_runs.read_flow_runs(session)
    assert len(runs) == 1
    run = runs[0]

    assert run.state
    assert run.state.name == "Scheduled"
    assert run.state.state_details
    assert run.state.state_details.scheduled_time

    # Verify the scheduled time is approximately 2 hours from start_time
    scheduled_time = run.state.state_details.scheduled_time
    expected_time = start_time + timedelta(hours=2)

    # Allow 10 second tolerance for test execution time
    time_diff = abs((scheduled_time - expected_time).total_seconds())
    assert time_diff < 10, (
        f"Scheduled time {scheduled_time} not close enough to expected {expected_time}"
    )
