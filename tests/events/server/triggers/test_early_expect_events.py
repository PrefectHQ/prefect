"""A proactive trigger with `after` must count an `expect` event by when it occurred,
not by when it was evaluated.

Events for one bucketing key can be evaluated in any order, and nothing orders an
`after` event against the `expect` events that follow it. An `expect`-only event
evaluated before its window opens must still count toward that window, or the
trigger fires on a window that was satisfied.
"""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest import mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.events import actions, triggers
from prefect.server.events.models import automations
from prefect.server.events.schemas.automations import (
    Automation,
    EventTrigger,
    Posture,
)
from prefect.server.events.schemas.events import Event
from prefect.types._datetime import DateTime

pytestmark = pytest.mark.clear_db

WITHIN = timedelta(seconds=60)
RESOURCE = "some.resource"

MakeTrigger = Callable[..., Awaitable[EventTrigger]]


@pytest.fixture
def act(monkeypatch: pytest.MonkeyPatch) -> mock.AsyncMock:
    mock_act = mock.AsyncMock()
    monkeypatch.setattr("prefect.server.events.triggers.act", mock_act)
    return mock_act


@pytest.fixture
def make_trigger(
    cleared_buckets: None,
    cleared_automations: None,
    automations_session: AsyncSession,
) -> MakeTrigger:
    async def make(
        expect: set[str], threshold: int = 1, within: timedelta = WITHIN
    ) -> EventTrigger:
        automation = await automations.create_automation(
            automations_session,
            Automation(
                name="after A, expect",
                trigger=EventTrigger(
                    match={"prefect.resource.id": "some.*"},
                    after={"A"},
                    expect=expect,
                    for_each={"prefect.resource.id"},
                    posture=Posture.Proactive,
                    threshold=threshold,
                    within=within,
                ),
                actions=[actions.DoNothing()],
            ),
        )
        triggers.load_automation(automation)
        await automations_session.commit()
        assert isinstance(automation.trigger, EventTrigger)
        return automation.trigger

    return make


async def receive(event: str, occurred: DateTime, id: UUID | None = None) -> None:
    await triggers.reactive_evaluation(
        Event(
            occurred=occurred,
            event=event,
            resource={"prefect.resource.id": RESOURCE},
            id=id or uuid4(),
        ).receive()
    )


EXPECT_SHAPES = [
    pytest.param({"A", "B"}, id="after-is-also-expected"),
    pytest.param({"B"}, id="after-is-not-expected"),
]


@pytest.mark.parametrize("expect", EXPECT_SHAPES)
async def test_expect_event_evaluated_before_its_window_opens_satisfies_it(
    act: mock.AsyncMock,
    frozen_time: DateTime,
    make_trigger: MakeTrigger,
    expect: set[str],
):
    """B occurs inside A's window but is evaluated first, so the window is satisfied."""
    trigger = await make_trigger(expect)

    await receive("B", frozen_time + timedelta(milliseconds=300))
    await receive("A", frozen_time)

    await triggers.proactive_evaluation(trigger, frozen_time + WITHIN * 2)
    act.assert_not_awaited()


@pytest.mark.parametrize("expect", EXPECT_SHAPES)
@pytest.mark.parametrize(
    "b_offset",
    [
        pytest.param(-timedelta(seconds=1), id="before-the-window"),
        pytest.param(WITHIN + timedelta(seconds=1), id="after-the-window"),
    ],
)
async def test_expect_event_outside_the_window_does_not_satisfy_it(
    act: mock.AsyncMock,
    frozen_time: DateTime,
    make_trigger: MakeTrigger,
    expect: set[str],
    b_offset: timedelta,
):
    """B evaluated first but occurring outside A's window leaves the window empty."""
    trigger = await make_trigger(expect)

    await receive("B", frozen_time + b_offset)
    await receive("A", frozen_time)

    await triggers.proactive_evaluation(trigger, frozen_time + WITHIN * 2)
    act.assert_awaited_once()


async def test_later_after_events_evaluated_late_keep_the_window_satisfied(
    act: mock.AsyncMock,
    frozen_time: DateTime,
    make_trigger: MakeTrigger,
):
    """Each late A rolls the window, and each new window still counts the early B."""
    trigger = await make_trigger({"A", "B"})

    await receive("B", frozen_time + timedelta(seconds=2))
    await receive("A", frozen_time)
    await receive("A", frozen_time + timedelta(seconds=1))

    await triggers.proactive_evaluation(trigger, frozen_time + WITHIN * 2)
    act.assert_not_awaited()


@pytest.mark.parametrize("expect", EXPECT_SHAPES)
@pytest.mark.parametrize(
    "early_b_events, fires",
    [
        pytest.param(1, True, id="one-of-two"),
        pytest.param(2, False, id="two-of-two"),
    ],
)
async def test_expect_events_evaluated_early_count_toward_the_threshold(
    act: mock.AsyncMock,
    frozen_time: DateTime,
    make_trigger: MakeTrigger,
    expect: set[str],
    early_b_events: int,
    fires: bool,
):
    """Every early B inside the window counts toward the threshold, not just one."""
    trigger = await make_trigger(expect, threshold=2)

    for i in range(early_b_events):
        await receive("B", frozen_time + timedelta(seconds=1 + i))
    await receive("A", frozen_time)

    await triggers.proactive_evaluation(trigger, frozen_time + WITHIN * 2)
    assert act.await_count == (1 if fires else 0)


async def test_expect_event_counted_in_a_window_carries_into_a_late_roll(
    act: mock.AsyncMock,
    frozen_time: DateTime,
    make_trigger: MakeTrigger,
):
    """B counts in A's open window. A later A that occurred just before B rolls the
    window, and the new window still counts B, however late that A is evaluated."""
    within = timedelta(minutes=10)
    trigger = await make_trigger({"A", "B"}, within=within)

    await receive("A", frozen_time)
    await receive("B", frozen_time + timedelta(seconds=60, milliseconds=300))
    await receive("A", frozen_time + timedelta(seconds=60))

    await triggers.proactive_evaluation(trigger, frozen_time + within * 2)
    act.assert_not_awaited()


async def test_rolled_window_fires_with_the_carried_expect_event(
    act: mock.AsyncMock,
    frozen_time: DateTime,
    make_trigger: MakeTrigger,
):
    """A rolled window that still falls short fires with the carried B as its
    triggering event."""
    trigger = await make_trigger({"A", "B"}, threshold=2)

    await receive("A", frozen_time)
    await receive("B", frozen_time + timedelta(seconds=30))
    await receive("A", frozen_time + timedelta(seconds=29))

    await triggers.proactive_evaluation(trigger, frozen_time + WITHIN * 2)
    act.assert_awaited_once()
    firing = act.await_args_list[0].args[0]
    assert firing.triggering_event is not None
    assert firing.triggering_event.event == "B"


@pytest.mark.parametrize("expect", EXPECT_SHAPES)
async def test_one_expect_event_evaluated_twice_counts_once(
    act: mock.AsyncMock,
    frozen_time: DateTime,
    make_trigger: MakeTrigger,
    expect: set[str],
):
    """A redelivered B, evaluated once before A's window opens and once after, is
    still one event, so a threshold of two is not met."""
    trigger = await make_trigger(expect, threshold=2)

    b_id = uuid4()
    await receive("B", frozen_time + timedelta(seconds=1), id=b_id)
    await receive("A", frozen_time)
    await receive("B", frozen_time + timedelta(seconds=1), id=b_id)

    await triggers.proactive_evaluation(trigger, frozen_time + WITHIN * 2)
    act.assert_awaited_once()


@pytest.mark.parametrize("expect", EXPECT_SHAPES)
@pytest.mark.parametrize(
    "evaluation_order",
    [pytest.param(["B", "A"], id="b-first"), pytest.param(["A", "B"], id="a-first")],
)
async def test_expect_event_at_the_same_instant_as_after_counts_in_either_order(
    act: mock.AsyncMock,
    frozen_time: DateTime,
    make_trigger: MakeTrigger,
    expect: set[str],
    evaluation_order: list[str],
):
    """A window starts at its A, so a B that occurred at that same instant is inside
    it, whichever of the two is evaluated first."""
    trigger = await make_trigger(expect)

    for event in evaluation_order:
        await receive(event, frozen_time)

    await triggers.proactive_evaluation(trigger, frozen_time + WITHIN * 2)
    act.assert_not_awaited()
