import asyncio
import datetime
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import AsyncGenerator
from unittest import mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.events import actions, triggers
from prefect.server.events.ordering import get_triggers_causal_ordering
from prefect.server.events.schemas.automations import (
    Automation,
    EventTrigger,
    Firing,
    Posture,
    ReceivedEvent,
    TriggeredAction,
    TriggerState,
)
from prefect.server.utilities.messaging import MessageHandler
from prefect.server.utilities.messaging.memory import MemoryMessage
from prefect.types import DateTime
from prefect.types._datetime import now


async def test_acting_publishes_an_action_message_from_a_reactive_event(
    frozen_time: DateTime,
    arachnophobia: Automation,
    daddy_long_legs_walked: ReceivedEvent,
    actions_publish: mock.AsyncMock,
    create_actions_publisher: mock.MagicMock,
):
    firing = Firing(
        trigger=arachnophobia.trigger,
        trigger_states=[TriggerState.Triggered],
        triggered=frozen_time,
        triggering_labels={"hello": "world"},
        triggering_event=daddy_long_legs_walked,
    )
    await triggers.act(firing)

    assert actions_publish.await_count == 1
    assert actions_publish.await_args
    action_message: bytes = actions_publish.await_args_list[0].args[0]

    create_actions_publisher.assert_called_with()

    parsed = TriggeredAction.model_validate_json(action_message)
    assert parsed == TriggeredAction(
        automation=arachnophobia,
        firing=firing,
        triggered=frozen_time,
        triggering_labels={"hello": "world"},
        triggering_event=daddy_long_legs_walked,
        action=actions.DoNothing(),
        id=parsed.id,
    )


async def test_acting_publishes_an_action_message_from_a_proactive_trigger(
    frozen_time: DateTime,
    arachnophobia: Automation,
    actions_publish: mock.AsyncMock,
    create_actions_publisher: mock.MagicMock,
):
    firing = Firing(
        trigger=arachnophobia.trigger,
        trigger_states=[TriggerState.Triggered],
        triggered=frozen_time,
        triggering_labels={"hello": "world"},
    )
    await triggers.act(firing)

    assert actions_publish.await_count == 1
    assert actions_publish.await_args

    action_message: bytes = actions_publish.await_args_list[0].args[0]

    create_actions_publisher.assert_called_with()

    parsed = TriggeredAction.model_validate_json(action_message)
    assert parsed == TriggeredAction(
        triggered=frozen_time,
        automation=arachnophobia,
        firing=firing,
        triggering_labels={"hello": "world"},
        triggering_event=None,
        action=actions.DoNothing(),
        id=parsed.id,
    )


@pytest.fixture(autouse=True)
def load_automations(monkeypatch: pytest.MonkeyPatch) -> mock.AsyncMock:
    m = mock.AsyncMock()
    m.return_value = []
    monkeypatch.setattr("prefect.server.events.triggers.load_automations", m)
    return m


@pytest.fixture(autouse=True)
def periodic_evaluation(monkeypatch: pytest.MonkeyPatch) -> mock.AsyncMock:
    m = mock.AsyncMock(spec=triggers.periodic_evaluation)
    monkeypatch.setattr("prefect.server.events.triggers.periodic_evaluation", m)
    return m


@pytest.fixture(autouse=True)
def reactive_evaluation(monkeypatch: pytest.MonkeyPatch) -> mock.AsyncMock:
    m = mock.AsyncMock(spec=triggers.reactive_evaluation)
    monkeypatch.setattr("prefect.server.events.triggers.reactive_evaluation", m)
    return m


@pytest.fixture
def open_automations_session(monkeypatch: pytest.MonkeyPatch) -> mock.Mock:
    mock_session = mock.Mock()

    @asynccontextmanager
    async def automations_session() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session

    monkeypatch.setattr(
        "prefect.server.events.triggers.automations_session", automations_session
    )
    return mock_session


@pytest.fixture
def effective_automations(
    cleared_automations: None,
    frozen_time: DateTime,
):
    triggers.load_automation(
        Automation(
            id=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
            name="example automation 1",
            trigger=EventTrigger(
                expect={"stuff.happened"},
                match={"prefect.resource.id": "foo"},
                posture=Posture.Reactive,
                threshold=0,
                within=timedelta(seconds=10),
            ),
            actions=[actions.DoNothing()],
        )
    )
    triggers.load_automation(
        Automation(
            id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
            name="example automation 2",
            trigger=EventTrigger(
                expect={"stuff.happened"},
                match={"prefect.resource.id": "bar"},
                posture=Posture.Reactive,
                threshold=0,
                within=timedelta(seconds=10),
            ),
            actions=[actions.DoNothing()],
        )
    )


@pytest.fixture
async def message_handler(
    cleared_buckets: None,
    effective_automations,
) -> AsyncGenerator[MessageHandler, None]:
    async with triggers.consumer(
        periodic_granularity=timedelta(seconds=0.0001),
    ) as handler:
        yield handler


async def test_loading_none_automation_is_a_noop():
    original_triggers_length = len(triggers.triggers)
    original_automations_length = len(triggers.automations_by_id)

    triggers.load_automation(None)

    assert len(triggers.triggers) == original_triggers_length
    assert len(triggers.automations_by_id) == original_automations_length


async def test_skips_empty_messages(
    message_handler: MessageHandler,
    reactive_evaluation: mock.AsyncMock,
):
    await message_handler(
        MemoryMessage(
            data=b"",
            attributes=None,
        )
    )

    reactive_evaluation.assert_not_awaited()


async def test_runs_periodic_tasks(
    reset_events_clock: None,
    message_handler: MessageHandler,
    open_automations_session: mock.Mock,
    periodic_evaluation: mock.AsyncMock,
    frozen_time: DateTime,
):
    # it's called one time up front to catch any buckets that may have expired since
    # we restored them from backup
    periodic_evaluation.assert_awaited_once_with(frozen_time)
    periodic_evaluation.reset_mock()

    # Note that periodic_evaluation should take the current wall-clock time and then it
    # internally adjusts it for the local triggers time offset.  We can set it to
    # anything we want here and it shouldn't affect what's passed into
    # periodic_evaluation from the periodic task
    event = ReceivedEvent(
        occurred=frozen_time - timedelta(seconds=42),
        event="not.important",
        resource={"prefect.resource.id": "not.important"},
        id=uuid4(),
    )
    await triggers.update_events_clock(event)
    assert await triggers.get_events_clock_offset() == -42.0

    await asyncio.sleep(0.01)  # 100x more time than required (see fixture)

    assert periodic_evaluation.await_count >= 1
    periodic_evaluation.assert_awaited_with(frozen_time)


async def test_loads_automations_at_startup(
    effective_automations,
    open_automations_session: mock.Mock,
    load_automations: mock.AsyncMock,
):
    async with triggers.consumer(
        periodic_granularity=timedelta(seconds=0.0001),
    ):
        load_automations.assert_awaited_once_with(open_automations_session)


async def test_only_considers_messages_with_attributes(
    effective_automations,
    reactive_evaluation: mock.AsyncMock,
    daddy_long_legs_walked: ReceivedEvent,
):
    async with triggers.consumer() as handler:
        await handler(
            MemoryMessage(
                data=daddy_long_legs_walked.model_dump_json().encode(),
                attributes=None,  # ...but no attributes
            )
        )
        reactive_evaluation.assert_not_awaited()


async def test_only_considers_messages_that_are_not_log_writes(
    effective_automations,
    reactive_evaluation: mock.AsyncMock,
    daddy_long_legs_walked: ReceivedEvent,
):
    async with triggers.consumer() as handler:
        await handler(
            MemoryMessage(
                data=daddy_long_legs_walked.model_dump_json().encode(),
                attributes={
                    "event": "prefect.log.write",
                },
            )
        )
        reactive_evaluation.assert_not_awaited()


async def test_only_considers_messages_with_event_ids(
    start_of_test: DateTime,
    effective_automations,
    message_handler: MessageHandler,
    reactive_evaluation: mock.AsyncMock,
    daddy_long_legs_walked: ReceivedEvent,
):
    event = ReceivedEvent(
        occurred=start_of_test,
        event="things.happened",
        resource={"prefect.resource.id": "something"},
        id=uuid4(),
    )

    await message_handler(
        MemoryMessage(
            data=event.model_dump_json().encode(),
            attributes={},
        )
    )

    reactive_evaluation.assert_not_awaited()


async def test_only_considers_messages_with_valid_event_ids(
    start_of_test: DateTime,
    effective_automations,
    message_handler: MessageHandler,
    reactive_evaluation: mock.AsyncMock,
    daddy_long_legs_walked: ReceivedEvent,
):
    event = ReceivedEvent(
        occurred=start_of_test,
        event="things.happened",
        resource={"prefect.resource.id": "something"},
        id=uuid4(),
    )

    await message_handler(
        MemoryMessage(
            data=event.model_dump_json().encode(),
            attributes={
                "id": "do you even UUID, bro?",
            },
        )
    )

    reactive_evaluation.assert_not_awaited()


async def test_acks_early_arrivals(
    start_of_test: DateTime,
    message_handler: MessageHandler,
    reactive_evaluation: mock.AsyncMock,
):
    event = ReceivedEvent(
        occurred=start_of_test,
        event="things.happened",
        resource={"prefect.resource.id": "something"},
        id=uuid4(),
    )
    reactive_evaluation.side_effect = triggers.EventArrivedEarly(event)

    # the fact that the message handler does _not_ raise means we will ack this message
    await message_handler(
        MemoryMessage(
            data=event.model_dump_json().encode(),
            attributes={
                "id": str(event.id),
            },
        )
    )

    reactive_evaluation.assert_awaited_once_with(event)


async def test_only_processes_event_once(
    start_of_test: DateTime,
    message_handler: MessageHandler,
    reactive_evaluation: mock.AsyncMock,
):
    event = ReceivedEvent(
        occurred=start_of_test,
        event="things.happened",
        resource={"prefect.resource.id": "something"},
        id=uuid4(),
    )
    message = MemoryMessage(
        data=event.model_dump_json().encode(),
        attributes={
            "id": str(event.id),
        },
    )

    causal_ordering = get_triggers_causal_ordering()
    reactive_evaluation.side_effect = causal_ordering.record_event_as_seen

    await asyncio.gather(*[message_handler(message) for _ in range(50)])

    reactive_evaluation.assert_awaited_once_with(event)


async def test_periodic_evaluation_continues_event_if_it_raises(
    periodic_evaluation: mock.AsyncMock,
):
    """Regression test for discovery that periodic evaluation would sometimes
    go offline after any brief error"""
    periodic_evaluation.side_effect = ValueError("woops!")
    task = asyncio.create_task(triggers.evaluate_periodically(timedelta(seconds=0.01)))

    await asyncio.sleep(0.1)  # 10x what's needed to register some evaluations

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert periodic_evaluation.await_count > 1


async def test_event_clock_produces_none_when_never_updated(reset_events_clock: None):
    assert await triggers.get_events_clock() is None
    assert await triggers.get_events_clock_offset() == 0.0


async def test_event_clock_produces_accurate_offsets(
    reset_events_clock: None,
    frozen_time: DateTime,
):
    event = ReceivedEvent(
        occurred=frozen_time - timedelta(seconds=42),
        event="not.important",
        resource={"prefect.resource.id": "not.important"},
        id=uuid4(),
    )
    await triggers.update_events_clock(event)
    assert await triggers.get_events_clock_offset() == -42.0


async def test_event_clock_only_moves_forward(
    reset_events_clock: None, start_of_test: DateTime
):
    event = ReceivedEvent(
        occurred=now("UTC"),
        event="things.happened",
        resource={"prefect.resource.id": "something"},
        id=uuid4(),
    )

    event.occurred = now("UTC") - datetime.timedelta(seconds=100)
    await triggers.update_events_clock(event)
    first_tick = await triggers.get_events_clock()
    assert first_tick == event.occurred.timestamp()

    event.occurred += timedelta(seconds=10)
    await triggers.update_events_clock(event)
    second_tick = await triggers.get_events_clock()
    assert second_tick == event.occurred.timestamp()

    # now try to move backwards and see that the clock doesn't move backward
    event.occurred -= timedelta(seconds=5)
    await triggers.update_events_clock(event)
    third_tick = await triggers.get_events_clock()
    assert third_tick == second_tick


async def test_event_clock_avoids_the_future(
    reset_events_clock: None, start_of_test: DateTime
):
    event = ReceivedEvent(
        occurred=now("UTC"),
        event="things.happened",
        resource={"prefect.resource.id": "something"},
        id=uuid4(),
    )

    event.occurred = now("UTC") - timedelta(seconds=100)
    await triggers.update_events_clock(event)
    first_tick = await triggers.get_events_clock()
    assert first_tick
    assert first_tick == event.occurred.timestamp()

    # now try a future date and see that the clock stays pinned to the present
    event.occurred = now("UTC") + timedelta(seconds=100)
    await triggers.update_events_clock(event)
    second_tick = await triggers.get_events_clock()
    assert second_tick
    assert first_tick < second_tick <= now("UTC").timestamp()


async def test_offset_is_resilient_to_low_volume(
    reset_events_clock: None, monkeypatch: pytest.MonkeyPatch
):
    base_time = now("UTC")

    mock_now = mock.Mock()
    monkeypatch.setattr("prefect.types._datetime.now", mock_now)

    mock_now.return_value = base_time

    event = ReceivedEvent(
        occurred=base_time - timedelta(seconds=42),
        event="things.happened",
        resource={"prefect.resource.id": "something"},
        id=uuid4(),
    )
    await triggers.update_events_clock(event)
    assert await triggers.get_events_clock() == event.occurred.timestamp()
    assert await triggers.get_events_clock_offset() == -42.0

    # now advance time a bit without an event, and confirm that the offset is the same

    mock_now.return_value = base_time + timedelta(seconds=10)
    assert await triggers.get_events_clock() == event.occurred.timestamp()
    assert await triggers.get_events_clock_offset() == -42.0
