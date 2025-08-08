import re
from datetime import timedelta
from unittest import mock
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import orjson
import pytest
from httpx import Response
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.blocks.webhook import Webhook
from prefect.server.database.orm_models import (
    ORMDeployment,
    ORMFlow,
    ORMFlowRun,
    ORMWorkQueue,
)
from prefect.server.events import actions
from prefect.server.events.actions import ActionFailed
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.events.schemas.automations import (
    Automation,
    EventTrigger,
    Firing,
    Posture,
    TriggeredAction,
    TriggerState,
)
from prefect.server.events.schemas.events import (
    ReceivedEvent,
    RelatedResource,
    Resource,
)
from prefect.server.models import deployments, flow_runs, flows, work_queues
from prefect.server.schemas.actions import WorkQueueCreate
from prefect.server.schemas.core import Deployment, Flow, FlowRun, WorkQueue
from prefect.types import DateTime
from prefect.types._datetime import now


@pytest.fixture
async def snap_a_pic(
    session: AsyncSession,
) -> ORMFlow:
    flow = await flows.create_flow(
        session=session,
        flow=Flow(name="snap-a-pic"),
    )
    await session.commit()
    return flow


@pytest.fixture
async def take_a_picture(
    session: AsyncSession,
    snap_a_pic: ORMFlow,
) -> ORMFlowRun:
    flow_run = await flow_runs.create_flow_run(
        session=session,
        flow_run=FlowRun(flow_id=snap_a_pic.id, flow_version="1.0"),
    )
    await session.commit()
    return flow_run


@pytest.fixture
async def take_a_picture_deployment(
    session: AsyncSession,
    take_a_picture: FlowRun,
) -> ORMDeployment:
    deployment = await deployments.create_deployment(
        session=session,
        deployment=Deployment(
            name="Take a picture on demand",
            flow_id=take_a_picture.flow_id,
            paused=False,
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def take_a_picture_work_queue(
    session: AsyncSession,
) -> ORMWorkQueue:
    work_queue = await work_queues.create_work_queue(
        session=session,
        work_queue=WorkQueueCreate(name="camera-queue"),
    )
    await session.commit()
    return work_queue


@pytest.fixture
async def webhook_block_id(in_memory_prefect_client) -> UUID:
    block = Webhook(method="POST", url="https://example.com", headers={"foo": "bar"})
    return await block.save(name="webhook-test", client=in_memory_prefect_client)


@pytest.fixture
def picture_taken(
    start_of_test: DateTime,
    take_a_picture: FlowRun,
    take_a_picture_deployment: Deployment,
    take_a_picture_work_queue: WorkQueue,
):
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=2),
        event="prefect.flow-run.completed",
        resource={"prefect.resource.id": f"prefect.flow-run.{take_a_picture.id}"},
        related=[
            {
                "prefect.resource.id": f"prefect.flow.{take_a_picture.flow_id}",
                "prefect.resource.role": "flow",
            },
            {
                "prefect.resource.id": f"prefect.deployment.{take_a_picture_deployment.id}",
                "prefect.resource.role": "deployment",
            },
            {
                "prefect.resource.id": f"prefect.work-queue.{take_a_picture_work_queue.id}",
                "prefect.resource.role": "work-queue",
            },
        ],
        id=uuid4(),
    )


@pytest.fixture
async def tell_me_about_the_culprit(
    webhook_block_id: UUID,
) -> Automation:
    return Automation(
        name="If my lilies get nibbled, tell me about it",
        description="Send a webhook whenever the lillies are nibbled",
        enabled=True,
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
            actions.CallWebhook(
                block_document_id=webhook_block_id,
            ),
            actions.CallWebhook(
                block_document_id=uuid4(),
            ),
            actions.CallWebhook(
                block_document_id=webhook_block_id,
                payload={
                    "automation": "{{ automation.name }}",
                },
            ),
        ],
    )


@pytest.fixture
def call_webhook(
    tell_me_about_the_culprit: Automation,
    woodchonk_nibbled: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=tell_me_about_the_culprit.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={"i.am.so": "triggered"},
        triggering_event=woodchonk_nibbled,
    )
    return TriggeredAction(
        automation=tell_me_about_the_culprit,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=tell_me_about_the_culprit.actions[0],
    )


@pytest.fixture
def call_webhook_with_templated_payload(
    tell_me_about_the_culprit: Automation,
    woodchonk_nibbled: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=tell_me_about_the_culprit.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={"i.am.so": "triggered"},
        triggering_event=woodchonk_nibbled,
    )
    return TriggeredAction(
        automation=tell_me_about_the_culprit,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=tell_me_about_the_culprit.actions[2],
    )


@pytest.fixture
def invalid_block_id(
    tell_me_about_the_culprit: Automation,
    woodchonk_nibbled: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=tell_me_about_the_culprit.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={"i.am.so": "triggered"},
        triggering_event=woodchonk_nibbled,
    )
    return TriggeredAction(
        automation=tell_me_about_the_culprit,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=tell_me_about_the_culprit.actions[1],
    )


@pytest.fixture
def took_a_picture(
    tell_me_about_the_culprit: Automation,
    picture_taken: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=tell_me_about_the_culprit.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=picture_taken.occurred,
        triggering_labels={},
        triggering_event=picture_taken,
    )
    return TriggeredAction(
        automation=tell_me_about_the_culprit,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=tell_me_about_the_culprit.actions[0],
    )


async def test_sending_webhook(
    call_webhook: TriggeredAction, monkeypatch: pytest.MonkeyPatch
):
    action = call_webhook.action

    call = AsyncMock()
    call.return_value = Response(status_code=200)
    monkeypatch.setattr("prefect.blocks.webhook.Webhook.call", call)

    assert isinstance(action, actions.CallWebhook)
    await action.act(call_webhook)
    assert call_webhook.triggering_event

    assert call_webhook.triggering_event
    call.assert_called_once_with(payload="")


async def test_sending_webhook_with_payload(
    call_webhook_with_templated_payload: TriggeredAction,
    tell_me_about_the_culprit: Automation,
    monkeypatch: pytest.MonkeyPatch,
):
    action = call_webhook_with_templated_payload.action

    call = AsyncMock()
    call.return_value = Response(
        status_code=200,
        headers={
            "foo": "bar",
            "Authorization": "trust me bro",
            "via": "the interwebs",
        },
        text="Booped the snoot!",
    )
    monkeypatch.setattr("prefect.blocks.webhook.Webhook.call", call)

    assert isinstance(action, actions.CallWebhook)
    await action.act(call_webhook_with_templated_payload)

    assert call_webhook_with_templated_payload.triggering_event
    call.assert_called_once_with(
        payload=orjson.dumps(
            {
                "automation": tell_me_about_the_culprit.name,
            },
            option=orjson.OPT_INDENT_2,
        ).decode()
    )
    assert action._result_details["status_code"] == 200
    response_headers = action._result_details["response_headers"]
    assert response_headers.get("foo") == "bar"
    assert response_headers.get("Authorization") is None
    assert response_headers.get("via") is None
    assert action._result_details.get("response_body") == "Booped the snoot!"


async def test_error_calling_webhook(
    call_webhook_with_templated_payload: TriggeredAction,
    monkeypatch: pytest.MonkeyPatch,
):
    action = call_webhook_with_templated_payload.action

    call = AsyncMock(side_effect=ValueError("woops!"))
    monkeypatch.setattr("prefect.blocks.webhook.Webhook.call", call)

    assert isinstance(action, actions.CallWebhook)

    with pytest.raises(ActionFailed, match="woops!"):
        await action.act(call_webhook_with_templated_payload)


async def test_invalid_block_id(invalid_block_id: TriggeredAction):
    action = invalid_block_id.action
    assert isinstance(action, actions.CallWebhook)
    with pytest.raises(actions.ActionFailed):
        await action.act(invalid_block_id)


async def test_validation_error_loading_block(took_a_picture: TriggeredAction):
    """If there is a ValidationError loading the Webhook Block, handle it and
    fail the action.  This is a regression test for an alert we got about a Slack
    webhook missing its URL in production."""
    action = took_a_picture.action
    assert isinstance(action, actions.CallWebhook)
    error = ValueError("woops")
    expected_reason = re.escape("The webhook block was invalid: ValueError('woops')")
    with mock.patch(
        "prefect.server.events.actions._load_block_from_block_document",
        side_effect=error,
    ):
        with pytest.raises(actions.ActionFailed, match=expected_reason):
            await action.act(took_a_picture)


async def test_success_event(
    call_webhook: TriggeredAction,
    monkeypatch: pytest.MonkeyPatch,
    webhook_block_id: UUID,
):
    action = call_webhook.action

    webhook_call = AsyncMock()
    webhook_call.return_value = Response(status_code=200, text="🦊")
    monkeypatch.setattr("prefect.blocks.webhook.Webhook.call", webhook_call)

    await action.act(call_webhook)
    await action.succeed(call_webhook)

    block_loaded_event = AssertingEventsClient.all[0].events[0]
    assert block_loaded_event is not None

    assert block_loaded_event.event == "prefect.block.webhook.loaded"
    assert block_loaded_event.resource == Resource.model_validate(
        {
            "prefect.resource.id": f"prefect.block-document.{webhook_block_id}",
            "prefect.resource.name": "webhook-test",
        }
    )
    assert block_loaded_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": "prefect.block-type.webhook",
                "prefect.resource.role": "block-type",
            }
        ),
    ]

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.block-document.{webhook_block_id}",
                "prefect.resource.role": "block",
                "prefect.resource.name": "webhook-test",
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": "prefect.block-type.webhook",
                "prefect.resource.role": "block-type",
            }
        ),
    ]
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "call-webhook",
        "invocation": str(call_webhook.id),
    }

    assert executed_event.event == "prefect.automation.action.executed"
    assert executed_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.block-document.{webhook_block_id}",
                "prefect.resource.role": "block",
                "prefect.resource.name": "webhook-test",
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": "prefect.block-type.webhook",
                "prefect.resource.role": "block-type",
            }
        ),
    ]
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "call-webhook",
        "invocation": str(call_webhook.id),
        "status_code": webhook_call.return_value.status_code,
        "response_headers": {
            "content-length": "4",
            "content-type": "text/plain; charset=utf-8",
        },
        "response_body": "🦊",
    }


async def test_migrating_to_templates():
    """Confirms that our plan to migrate `payload` from dict[str, Any] to str will
    parse payloads from both the database and the UI."""

    action = actions.CallWebhook(
        block_document_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        payload={"message": "hello world"},
    )
    assert isinstance(action.payload, str)
    assert action.payload == '{\n  "message": "hello world"\n}'

    actions_adapter = TypeAdapter(actions.ServerActionTypes)

    # The form it will be when read from the database
    action = actions_adapter.validate_python(
        {
            "type": "call-webhook",
            "block_document_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "payload": {"message": "hello world"},
        },
    )
    assert isinstance(action, actions.CallWebhook)
    assert isinstance(action.payload, str)
    assert action.payload == '{\n  "message": "hello world"\n}'

    # The form it will be when read from an API body
    action = actions_adapter.validate_json(
        """
        {
            "type" : "call-webhook",
            "block_document_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "payload": {"message": "hello world"}
        }
        """,
    )
    assert isinstance(action, actions.CallWebhook)
    assert isinstance(action.payload, str)
    assert action.payload == '{\n  "message": "hello world"\n}'
