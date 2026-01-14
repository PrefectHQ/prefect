from typing import AsyncGenerator, Generator
from unittest import mock

import pytest

from prefect._internal.uuid7 import uuid7
from prefect.server.events import actions
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.events.schemas.automations import (
    Automation,
    Firing,
    TriggeredAction,
    TriggerState,
)
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.utilities.messaging import MessageHandler
from prefect.server.utilities.messaging.memory import MemoryMessage
from prefect.types import DateTime
from prefect.types._datetime import now


@pytest.fixture
async def message_handler(act: mock.AsyncMock) -> AsyncGenerator[MessageHandler, None]:
    async with actions.consumer() as handler:
        yield handler


@pytest.fixture
def act() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch("prefect.server.events.actions.DoNothing.act", autospec=True) as m:
        yield m


async def test_skips_empty_messages(
    message_handler: MessageHandler,
    act: mock.AsyncMock,
):
    await message_handler(
        MemoryMessage(
            data=b"",
            attributes=None,
        )
    )

    act.assert_not_awaited()


async def test_reacts_to_messages(
    message_handler: MessageHandler,
    act: mock.AsyncMock,
    email_me_when_that_dang_spider_comes: TriggeredAction,
    caplog: pytest.LogCaptureFixture,
):
    with caplog.at_level("INFO"):
        await message_handler(
            MemoryMessage(
                data=email_me_when_that_dang_spider_comes.model_dump_json().encode(),
                attributes=None,
            )
        )

    act.assert_awaited_once_with(
        actions.DoNothing(),  # this is the self on which act is called
        email_me_when_that_dang_spider_comes,
    )


async def test_acks_actions_that_raise_actionfailed(
    message_handler: MessageHandler,
    act: mock.AsyncMock,
    email_me_when_that_dang_spider_comes: TriggeredAction,
    caplog: pytest.LogCaptureFixture,
):
    """ActionFailed errors should be handled and will not cause message redelivery"""
    act.side_effect = actions.ActionFailed("womp womp")
    with caplog.at_level("INFO"):
        await message_handler(
            MemoryMessage(
                data=email_me_when_that_dang_spider_comes.model_dump_json().encode(),
                attributes=None,
            )
        )

    act.assert_awaited_once_with(
        actions.DoNothing(),  # this is the self on which act is called
        email_me_when_that_dang_spider_comes,
    )


async def test_successes_emit_events(
    message_handler: MessageHandler,
    email_me_when_that_dang_spider_comes: TriggeredAction,
    start_of_test: DateTime,
):
    await message_handler(
        MemoryMessage(
            data=email_me_when_that_dang_spider_comes.model_dump_json().encode(),
            attributes=None,
        )
    )

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    automation_id = email_me_when_that_dang_spider_comes.automation.id

    assert triggered_event.occurred == email_me_when_that_dang_spider_comes.triggered
    assert (
        triggered_event.follows
        == email_me_when_that_dang_spider_comes.triggering_event.id
    )
    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.resource.id == f"prefect.automation.{automation_id}"
    assert (
        triggered_event.resource["prefect.resource.name"]
        == "React immediately to spiders"
    )
    # Verify related resource with triggering-event role
    assert len(triggered_event.related) == 1
    assert (
        triggered_event.related[0]["prefect.resource.id"]
        == f"prefect.event.{email_me_when_that_dang_spider_comes.triggering_event.id}"
    )
    assert triggered_event.related[0]["prefect.resource.role"] == "triggering-event"
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "do-nothing",
        "invocation": str(email_me_when_that_dang_spider_comes.id),
    }

    assert start_of_test <= executed_event.occurred <= now("UTC")
    assert executed_event.follows == triggered_event.id
    assert executed_event.event == "prefect.automation.action.executed"
    assert executed_event.resource.id == f"prefect.automation.{automation_id}"
    assert (
        executed_event.resource["prefect.resource.name"]
        == "React immediately to spiders"
    )
    assert not executed_event.related
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "do-nothing",
        "invocation": str(email_me_when_that_dang_spider_comes.id),
    }


async def test_failures_emit_events(
    message_handler: MessageHandler,
    act: mock.AsyncMock,
    email_me_when_that_dang_spider_comes: TriggeredAction,
    start_of_test: DateTime,
):
    """ActionFailed errors should be handled and will not cause message redelivery"""
    act.side_effect = actions.ActionFailed("womp womp")
    await message_handler(
        MemoryMessage(
            data=email_me_when_that_dang_spider_comes.model_dump_json().encode(),
            attributes=None,
        )
    )

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    automation_id = email_me_when_that_dang_spider_comes.automation.id

    assert triggered_event.occurred == email_me_when_that_dang_spider_comes.triggered
    assert (
        triggered_event.follows
        == email_me_when_that_dang_spider_comes.triggering_event.id
    )
    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.resource.id == f"prefect.automation.{automation_id}"
    assert (
        triggered_event.resource["prefect.resource.name"]
        == "React immediately to spiders"
    )
    # Verify related resource with triggering-event role
    assert len(triggered_event.related) == 1
    assert (
        triggered_event.related[0]["prefect.resource.id"]
        == f"prefect.event.{email_me_when_that_dang_spider_comes.triggering_event.id}"
    )
    assert triggered_event.related[0]["prefect.resource.role"] == "triggering-event"
    assert triggered_event.payload == {
        "action_index": 0,
        "action_type": "do-nothing",
        "invocation": str(email_me_when_that_dang_spider_comes.id),
    }

    assert start_of_test <= executed_event.occurred <= now("UTC")
    assert executed_event.follows == triggered_event.id
    assert executed_event.event == "prefect.automation.action.failed"
    assert executed_event.resource.id == f"prefect.automation.{automation_id}"
    assert (
        executed_event.resource["prefect.resource.name"]
        == "React immediately to spiders"
    )
    assert not executed_event.related
    assert executed_event.payload == {
        "action_index": 0,
        "action_type": "do-nothing",
        "invocation": str(email_me_when_that_dang_spider_comes.id),
        "reason": "womp womp",
    }


async def test_does_not_ack_actions_that_raise_unexpected_errors(
    message_handler: MessageHandler,
    act: mock.AsyncMock,
    email_me_when_that_dang_spider_comes: TriggeredAction,
    caplog: pytest.LogCaptureFixture,
):
    """Errors besides ActionFailed are passed through so the message is redelivered"""
    act.side_effect = ValueError("womp womp")
    with caplog.at_level("INFO"):
        with pytest.raises(ValueError, match="womp womp"):
            await message_handler(
                MemoryMessage(
                    data=email_me_when_that_dang_spider_comes.model_dump_json().encode(),
                    attributes=None,
                )
            )

    act.assert_awaited_once_with(
        actions.DoNothing(),  # this is the self on which act is called
        email_me_when_that_dang_spider_comes,
    )


async def test_actions_are_idempotent(
    message_handler: MessageHandler,
    act: mock.AsyncMock,
    email_me_when_that_dang_spider_comes: TriggeredAction,
):
    """Actions are only executed once"""
    await message_handler(
        MemoryMessage(
            data=email_me_when_that_dang_spider_comes.model_dump_json().encode(),
            attributes=None,
        )
    )

    await message_handler(
        MemoryMessage(
            data=email_me_when_that_dang_spider_comes.model_dump_json().encode(),
            attributes=None,
        )
    )

    act.assert_awaited_once_with(
        actions.DoNothing(),  # this is the self on which act is called
        email_me_when_that_dang_spider_comes,
    )


async def test_action_triggered_event_follows_triggering_event(
    message_handler: MessageHandler,
    email_me_when_that_dang_spider_comes: TriggeredAction,
):
    """
    Regression test for GitHub Discussion #19421.

    The action.triggered event should include:
    1. A 'follows' field linking to the event that triggered the automation
    2. A related resource with role 'triggering-event' pointing to that event

    This establishes a clear causal chain for easier debugging and tracing.
    """
    await message_handler(
        MemoryMessage(
            data=email_me_when_that_dang_spider_comes.model_dump_json().encode(),
            attributes=None,
        )
    )

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    # The action.triggered event should link to the original triggering event
    assert email_me_when_that_dang_spider_comes.triggering_event is not None
    triggering_event_id = email_me_when_that_dang_spider_comes.triggering_event.id

    # Verify follows field
    assert triggered_event.follows == triggering_event_id

    # Verify related resource with triggering-event role
    assert len(triggered_event.related) == 1
    assert (
        triggered_event.related[0]["prefect.resource.id"]
        == f"prefect.event.{triggering_event_id}"
    )
    assert triggered_event.related[0]["prefect.resource.role"] == "triggering-event"

    # The action.executed event should still link to action.triggered
    assert executed_event.follows == triggered_event.id


async def test_success_events_include_automation_triggered_event_link(
    message_handler: MessageHandler,
    arachnophobia: Automation,
    daddy_long_legs_walked: ReceivedEvent,
):
    """
    When automation_triggered_event_id is set on a TriggeredAction, action events
    should include a related resource linking to the automation.triggered event.

    This enables users to trace from automation.action.failed back to the
    corresponding automation.triggered event.
    """
    automation_triggered_id = uuid7()

    firing = Firing(
        trigger=arachnophobia.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={"hello": "world"},
        triggering_event=daddy_long_legs_walked,
    )
    triggered_action = TriggeredAction(
        automation=arachnophobia,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=arachnophobia.actions[0],
        automation_triggered_event_id=automation_triggered_id,
    )

    await message_handler(
        MemoryMessage(
            data=triggered_action.model_dump_json().encode(),
            attributes=None,
        )
    )

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    # Verify automation-triggered-event related resource on action.triggered event
    automation_triggered_related = next(
        (
            r
            for r in triggered_event.related
            if r["prefect.resource.role"] == "automation-triggered-event"
        ),
        None,
    )
    assert automation_triggered_related is not None
    assert (
        automation_triggered_related["prefect.resource.id"]
        == f"prefect.event.{automation_triggered_id}"
    )

    # The triggering-event related resource should still be present
    triggering_event_related = next(
        (
            r
            for r in triggered_event.related
            if r["prefect.resource.role"] == "triggering-event"
        ),
        None,
    )
    assert triggering_event_related is not None
    assert (
        triggering_event_related["prefect.resource.id"]
        == f"prefect.event.{daddy_long_legs_walked.id}"
    )

    # Verify automation-triggered-event related resource on action.executed event
    executed_automation_triggered_related = next(
        (
            r
            for r in executed_event.related
            if r["prefect.resource.role"] == "automation-triggered-event"
        ),
        None,
    )
    assert executed_automation_triggered_related is not None
    assert (
        executed_automation_triggered_related["prefect.resource.id"]
        == f"prefect.event.{automation_triggered_id}"
    )


async def test_failure_events_include_automation_triggered_event_link(
    message_handler: MessageHandler,
    act: mock.AsyncMock,
    arachnophobia: Automation,
    daddy_long_legs_walked: ReceivedEvent,
):
    """
    When automation_triggered_event_id is set on a TriggeredAction and the action
    fails, the action.triggered event should include a related resource linking to
    the automation.triggered event.
    """
    act.side_effect = actions.ActionFailed("something went wrong")

    automation_triggered_id = uuid7()

    firing = Firing(
        trigger=arachnophobia.trigger,
        trigger_states={TriggerState.Triggered},
        triggered=now("UTC"),
        triggering_labels={"hello": "world"},
        triggering_event=daddy_long_legs_walked,
    )
    triggered_action = TriggeredAction(
        automation=arachnophobia,
        firing=firing,
        triggered=firing.triggered,
        triggering_labels=firing.triggering_labels,
        triggering_event=firing.triggering_event,
        action=arachnophobia.actions[0],
        automation_triggered_event_id=automation_triggered_id,
    )

    await message_handler(
        MemoryMessage(
            data=triggered_action.model_dump_json().encode(),
            attributes=None,
        )
    )

    assert AssertingEventsClient.last
    (triggered_event, failed_event) = AssertingEventsClient.last.events

    # Verify automation-triggered-event related resource on action.triggered event
    automation_triggered_related = next(
        (
            r
            for r in triggered_event.related
            if r["prefect.resource.role"] == "automation-triggered-event"
        ),
        None,
    )
    assert automation_triggered_related is not None
    assert (
        automation_triggered_related["prefect.resource.id"]
        == f"prefect.event.{automation_triggered_id}"
    )

    # Verify the failed event is properly formed
    assert failed_event.event == "prefect.automation.action.failed"
    assert failed_event.payload["reason"] == "something went wrong"

    # Verify automation-triggered-event related resource on action.failed event
    failed_automation_triggered_related = next(
        (
            r
            for r in failed_event.related
            if r["prefect.resource.role"] == "automation-triggered-event"
        ),
        None,
    )
    assert failed_automation_triggered_related is not None
    assert (
        failed_automation_triggered_related["prefect.resource.id"]
        == f"prefect.event.{automation_triggered_id}"
    )


async def test_action_events_without_automation_triggered_event_id(
    message_handler: MessageHandler,
    email_me_when_that_dang_spider_comes: TriggeredAction,
):
    """
    For backward compatibility, when automation_triggered_event_id is None (the
    default), only the triggering-event related resource should be included on
    action.triggered and no automation-triggered-event on action.executed.
    """
    # The default fixture doesn't set automation_triggered_event_id
    assert email_me_when_that_dang_spider_comes.automation_triggered_event_id is None

    await message_handler(
        MemoryMessage(
            data=email_me_when_that_dang_spider_comes.model_dump_json().encode(),
            attributes=None,
        )
    )

    assert AssertingEventsClient.last
    (triggered_event, executed_event) = AssertingEventsClient.last.events

    # action.triggered should only have the triggering-event related resource
    assert len(triggered_event.related) == 1
    assert triggered_event.related[0]["prefect.resource.role"] == "triggering-event"

    # No automation-triggered-event related resource on action.triggered
    triggered_automation_related = next(
        (
            r
            for r in triggered_event.related
            if r["prefect.resource.role"] == "automation-triggered-event"
        ),
        None,
    )
    assert triggered_automation_related is None

    # No automation-triggered-event related resource on action.executed either
    executed_automation_related = next(
        (
            r
            for r in executed_event.related
            if r["prefect.resource.role"] == "automation-triggered-event"
        ),
        None,
    )
    assert executed_automation_related is None
