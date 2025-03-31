from typing import AsyncGenerator, Generator
from unittest import mock

import pytest

from prefect.server.events import actions
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.events.schemas.automations import TriggeredAction
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
    assert triggered_event.follows is None
    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.resource.id == f"prefect.automation.{automation_id}"
    assert (
        triggered_event.resource["prefect.resource.name"]
        == "React immediately to spiders"
    )
    assert not triggered_event.related
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
    assert triggered_event.follows is None
    assert triggered_event.event == "prefect.automation.action.triggered"
    assert triggered_event.resource.id == f"prefect.automation.{automation_id}"
    assert (
        triggered_event.resource["prefect.resource.name"]
        == "React immediately to spiders"
    )
    assert not triggered_event.related
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
