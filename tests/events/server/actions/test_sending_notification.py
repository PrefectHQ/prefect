import re
from datetime import timedelta
from typing import Type
from unittest import mock
from uuid import UUID, uuid4

import pytest

from prefect.blocks.abstract import NotificationBlock
from prefect.blocks.notifications import NotificationError
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
from prefect.server.events.schemas.events import (
    ReceivedEvent,
    RelatedResource,
    Resource,
)
from prefect.types._datetime import now


@pytest.fixture
def TestNotificationBlock(
    DebugPrintNotification: Type[NotificationBlock],
) -> Type[NotificationBlock]:
    return DebugPrintNotification


@pytest.fixture
async def email_me_block_id(notifier_block: NotificationBlock) -> UUID:
    return notifier_block._block_document_id


@pytest.fixture
async def tell_me_about_the_culprit(
    email_me_block_id: UUID,
) -> Automation:
    return Automation(
        name="If my lilies get nibbled, tell me about it",
        description="Send an email notification whenever the lillies are nibbled",
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
            actions.SendNotification(
                block_document_id=email_me_block_id,
                body="{{ automation.name }}",
            ),
            actions.SendNotification(
                block_document_id=uuid4(),
                body="Invalid block id",
            ),
        ],
    )


@pytest.fixture
def notify_me(
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
def invalid_block_id(
    tell_me_about_the_culprit: Automation,
    woodchonk_nibbled: ReceivedEvent,
) -> TriggeredAction:
    firing = Firing(
        trigger=tell_me_about_the_culprit.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={},
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


async def test_sending_notification(
    TestNotificationBlock: Type[NotificationBlock], notify_me: TriggeredAction
):
    action = notify_me.action

    with mock.patch.object(TestNotificationBlock, "notify") as notify:
        assert isinstance(action, actions.SendNotification)
        await action.act(notify_me)

    notify.assert_called_once_with(
        body="If my lilies get nibbled, tell me about it",
        subject="Prefect automated notification",
    )


async def test_invalid_block_id(invalid_block_id: TriggeredAction):
    action = invalid_block_id.action
    assert isinstance(action, actions.SendNotification)
    with pytest.raises(actions.ActionFailed):
        await action.act(invalid_block_id)


async def test_validation_error_loading_block(notify_me: TriggeredAction):
    """If there is a ValidationError loading the NotificationBlock, handle it and
    fail the action.  This is a regression test for an alert we got about a Slack
    webhook missing its URL in production."""
    action = notify_me.action
    assert isinstance(action, actions.SendNotification)
    error = ValueError("woops")
    expected_reason = re.escape(
        "The notification block was invalid: ValueError('woops')"
    )
    with mock.patch(
        "prefect.server.events.actions._load_block_from_block_document",
        side_effect=error,
    ):
        with pytest.raises(actions.ActionFailed, match=expected_reason):
            await action.act(notify_me)


async def test_action_validates_body_as_template(email_me_block_id: UUID):
    with pytest.raises(
        ValueError, match="'body' is not a valid template: unexpected '}'"
    ):
        actions.SendNotification(
            block_document_id=email_me_block_id,
            subject="This is fine",
            body="This is an {{ invalid } template.",
        )


async def test_action_validates_subject_as_template(email_me_block_id: UUID):
    with pytest.raises(
        ValueError, match="'subject' is not a valid template: unexpected '}'"
    ):
        actions.SendNotification(
            block_document_id=email_me_block_id,
            subject="This is an {{ invalid } template.",
            body="This is fine",
        )


async def test_subject_is_rendered(notify_me: TriggeredAction):
    assert notify_me.triggering_event
    action = actions.SendNotification(
        block_document_id=uuid4(),
        subject="{{ event.id }}",
        body="",
    )
    subject, _ = await action.render(notify_me)
    assert subject == str(notify_me.triggering_event.id)


async def test_body_is_rendered(notify_me: TriggeredAction):
    assert notify_me.triggering_event
    action = actions.SendNotification(
        block_document_id=uuid4(),
        subject="",
        body="{{ event.id }}",
    )
    _, body = await action.render(notify_me)
    assert body == str(notify_me.triggering_event.id)


async def test_success_event(
    TestNotificationBlock: Type[NotificationBlock],
    notify_me: TriggeredAction,
    email_me_block_id: UUID,
):
    action = notify_me.action

    with mock.patch.object(TestNotificationBlock, "notify"):
        await action.act(notify_me)

    await action.succeed(notify_me)

    block_loaded_event = AssertingEventsClient.all[0].events[0]
    assert block_loaded_event is not None

    assert block_loaded_event.event == "prefect.block.debug-print-notification.loaded"
    assert block_loaded_event.resource == Resource.model_validate(
        {
            "prefect.resource.id": f"prefect.block-document.{email_me_block_id}",
            "prefect.resource.name": "debug-print-notification",
        }
    )
    assert block_loaded_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.block-type.{TestNotificationBlock.get_block_type_slug()}",
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
                "prefect.resource.id": f"prefect.block-document.{email_me_block_id}",
                "prefect.resource.role": "block",
                "prefect.resource.name": "debug-print-notification",
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": "prefect.block-type.debug-print-notification",
                "prefect.resource.role": "block-type",
            }
        ),
    ]
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "send-notification",
        "invocation": str(notify_me.id),
    }

    assert executed_event.event == "prefect.automation.action.executed"
    assert executed_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.block-document.{email_me_block_id}",
                "prefect.resource.role": "block",
                "prefect.resource.name": "debug-print-notification",
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": "prefect.block-type.debug-print-notification",
                "prefect.resource.role": "block-type",
            }
        ),
    ]
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "send-notification",
        "invocation": str(notify_me.id),
    }


async def test_captures_notification_failures(
    TestNotificationBlock: Type[NotificationBlock],
    notify_me: TriggeredAction,
    email_me_block_id: UUID,
):
    action = notify_me.action

    with mock.patch.object(
        TestNotificationBlock,
        "notify",
        side_effect=NotificationError(log="bad\nthings\nhappened\n"),
    ):
        with pytest.raises(actions.ActionFailed) as captured:
            await action.act(notify_me)

    await action.fail(notify_me, captured.value.reason)

    assert AssertingEventsClient.last
    (triggered_event, failed_event) = AssertingEventsClient.last.events

    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.block-document.{email_me_block_id}",
                "prefect.resource.role": "block",
                "prefect.resource.name": "debug-print-notification",
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": "prefect.block-type.debug-print-notification",
                "prefect.resource.role": "block-type",
            }
        ),
    ]
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "send-notification",
        "invocation": str(notify_me.id),
    }

    assert failed_event.event == "prefect.automation.action.failed"
    assert failed_event.related == [
        RelatedResource.model_validate(
            {
                "prefect.resource.id": f"prefect.block-document.{email_me_block_id}",
                "prefect.resource.role": "block",
                "prefect.resource.name": "debug-print-notification",
            }
        ),
        RelatedResource.model_validate(
            {
                "prefect.resource.id": "prefect.block-type.debug-print-notification",
                "prefect.resource.role": "block-type",
            }
        ),
    ]
    assert failed_event.payload == {
        "action_index": 0,
        "action_type": "send-notification",
        "invocation": str(notify_me.id),
        "reason": "Notification failed",
        "notification_log": "bad\nthings\nhappened\n",
    }
