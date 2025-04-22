import datetime
from datetime import timedelta
from typing import List
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface
from prefect.server.events import actions, triggers
from prefect.server.events.models import automations
from prefect.server.events.schemas.automations import (
    Automation,
    CompoundTrigger,
    EventTrigger,
    Firing,
    Posture,
    SequenceTrigger,
    TriggerState,
)
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.types import DateTime
from prefect.types._datetime import now


@pytest.fixture
def flow_run_events(
    start_of_test: DateTime,
) -> List[ReceivedEvent]:
    # give me a sequence of events along with some superfluous events
    return [
        ReceivedEvent(
            occurred=start_of_test + timedelta(microseconds=1),
            event="prefect.flow-run.Pending",
            resource={
                "flow_run_id": "1234",
                "flow_id": "5678",
                "tenant_id": "1234",
                "prefect.resource.id": "prefect.flow-run.23456",
            },
            related=[
                {
                    "prefect.resource.id": "my-deployment",
                    "prefect.resource.role": "deployment",
                    "prefect.resource.name": "My Sweet Deployment",
                },
            ],
            id=uuid4(),
        ),
        ReceivedEvent(
            occurred=start_of_test + timedelta(microseconds=2),
            event="prefect.flow-run.Running",
            resource={
                "flow_run_id": "1234",
                "flow_id": "5678",
                "tenant_id": "1234",
                "prefect.resource.id": "prefect.flow-run.34567",
            },
            related=[
                {
                    "prefect.resource.id": "my-deployment",
                    "prefect.resource.role": "deployment",
                    "prefect.resource.name": "My Sweet Deployment",
                },
            ],
            id=uuid4(),
        ),
        ReceivedEvent(
            occurred=start_of_test + timedelta(microseconds=3),
            event="prefect.flow-run.Completed",
            resource={
                "flow_run_id": "1234",
                "flow_id": "5678",
                "tenant_id": "1234",
                "prefect.resource.id": "prefect.flow-run.45678",
            },
            related=[
                {
                    "prefect.resource.id": "my-deployment",
                    "prefect.resource.role": "deployment",
                    "prefect.resource.name": "My Sweet Deployment",
                },
            ],
            id=uuid4(),
        ),
        ReceivedEvent(
            occurred=start_of_test + timedelta(microseconds=4),
            event="prefect.flow-run.Failed",
            resource={
                "flow_run_id": "1234",
                "flow_id": "5678",
                "tenant_id": "1234",
                "prefect.resource.id": "prefect.flow-run.56789",
            },
            related=[
                {
                    "prefect.resource.id": "my-deployment",
                    "prefect.resource.role": "deployment",
                    "prefect.resource.name": "My Sweet Deployment",
                },
            ],
            id=uuid4(),
        ),
    ]


@pytest.fixture
def act(monkeypatch: pytest.MonkeyPatch) -> mock.AsyncMock:
    mock_act = mock.AsyncMock()
    monkeypatch.setattr("prefect.server.events.triggers.act", mock_act)
    return mock_act


class TestCompoundTriggerAny:
    @pytest.fixture
    async def compound_automation_any(
        self,
        automations_session: AsyncSession,
        cleared_buckets: None,
        cleared_automations: None,
    ):
        """
        This automation has a compound trigger that requires any of the triggers to be met.
        """
        compound_automation = Automation(
            name="Compound Automation",
            description="",
            trigger=CompoundTrigger(
                require="any",
                within=timedelta(minutes=5),
                triggers=[
                    EventTrigger(
                        expect={"prefect.flow-run.Failed"},
                        match={"prefect.resource.id": "prefect.flow-run.*"},
                        posture=Posture.Reactive,
                        threshold=1,
                    ),
                    EventTrigger(
                        expect={"prefect.flow-run.NonExistent"},
                        match={"prefect.resource.id": "prefect.flow-run.*"},
                        posture=Posture.Reactive,
                        threshold=1,
                    ),
                ],
            ),
            actions=[actions.DoNothing()],
        )

        persisted = await automations.create_automation(
            session=automations_session, automation=compound_automation
        )
        compound_automation.created = persisted.created
        compound_automation.updated = persisted.updated
        triggers.load_automation(persisted)
        await automations_session.commit()

        return compound_automation

    @pytest.fixture
    async def compound_automation_any_nested(
        self,
        automations_session: AsyncSession,
        cleared_buckets: None,
        cleared_automations: None,
    ):
        """
        This automation has a compound trigger that requires any of the triggers to be met.
        """
        nested_compound_automation = Automation(
            name="Compound Automation",
            description="",
            trigger=CompoundTrigger(
                require="any",
                within=timedelta(minutes=5),
                triggers=[
                    CompoundTrigger(
                        require="any",
                        within=timedelta(minutes=5),
                        triggers=[
                            EventTrigger(
                                expect={"prefect.flow-run.Failed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                            EventTrigger(
                                expect={"prefect.flow-run.NonExistent"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                        ],
                    ),
                ],
            ),
            actions=[actions.DoNothing()],
        )

        persisted = await automations.create_automation(
            session=automations_session, automation=nested_compound_automation
        )
        nested_compound_automation.created = persisted.created
        nested_compound_automation.updated = persisted.updated
        triggers.load_automation(persisted)
        await automations_session.commit()

        return nested_compound_automation

    @pytest.fixture
    async def compound_automation_any_double_nested(
        self,
        automations_session: AsyncSession,
        cleared_buckets: None,
        cleared_automations: None,
    ):
        """
        This automation has a compound trigger that requires any of the triggers to be met.
        """
        nested_compound_automation = Automation(
            name="Compound Automation",
            description="",
            trigger=CompoundTrigger(
                require="any",  # ideally this would get change to all
                within=timedelta(minutes=5),
                triggers=[
                    CompoundTrigger(
                        require="any",
                        within=timedelta(minutes=5),
                        triggers=[
                            EventTrigger(
                                expect={"prefect.flow-run.Failed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                            EventTrigger(
                                expect={"prefect.flow-run.NonExistent"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                        ],
                    ),
                    CompoundTrigger(
                        require="any",
                        within=timedelta(minutes=5),
                        triggers=[
                            EventTrigger(
                                expect={"prefect.flow-run.Completed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                            EventTrigger(
                                expect={"prefect.flow-run.NonExistent"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                        ],
                    ),
                ],
            ),
            actions=[actions.DoNothing()],
        )

        persisted = await automations.create_automation(
            session=automations_session, automation=nested_compound_automation
        )
        nested_compound_automation.created = persisted.created
        nested_compound_automation.updated = persisted.updated
        triggers.load_automation(persisted)
        await automations_session.commit()

        return nested_compound_automation

    async def test_compound_automation_any_trigger(
        self,
        act: mock.AsyncMock,
        flow_run_events: List[ReceivedEvent],
        compound_automation_any: Automation,
    ):
        """
        Ensures that when a stream of events is received,
        the compound trigger is called if any expected event is present.
        """
        for received_event in flow_run_events:
            await triggers.reactive_evaluation(received_event)

        act.assert_called_once()

        firing: Firing = act.call_args.args[0]

        assert firing.trigger.id == compound_automation_any.trigger.id

    async def test_compound_automation_any_nested_trigger(
        self,
        act: mock.AsyncMock,
        flow_run_events: List[ReceivedEvent],
        compound_automation_any_nested: Automation,
    ):
        """
        Ensures that when a stream of events is received,
        the compound trigger is called if any expected event is present.
        """
        for received_event in flow_run_events:
            await triggers.reactive_evaluation(received_event)

        act.assert_called_once()

        firing: Firing = act.call_args.args[0]

        assert firing.trigger.id == compound_automation_any_nested.trigger.id
        assert firing.triggering_event == flow_run_events[-1]

    async def test_compound_automation_any_double_nested_trigger(
        self,
        act: mock.AsyncMock,
        flow_run_events: List[ReceivedEvent],
        compound_automation_any_double_nested: Automation,
    ):
        """ """
        for received_event in flow_run_events:
            await triggers.reactive_evaluation(received_event)

        act.call_count == 2

        firing: Firing = act.call_args.args[0]

        assert firing.trigger.id == compound_automation_any_double_nested.trigger.id
        assert firing.triggering_event == flow_run_events[-1]


class TestCompoundTriggerAll:
    @pytest.fixture
    async def compound_automation_all_no_match(
        self,
        automations_session: AsyncSession,
        cleared_buckets: None,
        cleared_automations: None,
    ):
        """
        This automation has a compound trigger that requires all of the triggers to be met.
        """
        compound_automation = Automation(
            name="Compound Automation",
            description="",
            trigger=CompoundTrigger(
                require="all",
                within=timedelta(minutes=5),
                triggers=[
                    EventTrigger(
                        expect={"prefect.flow-run.Failed"},
                        match={"prefect.resource.id": "prefect.flow-run.*"},
                        posture=Posture.Reactive,
                        threshold=1,
                    ),
                    EventTrigger(
                        expect={"prefect.flow-run.NotExistent"},
                        match={"prefect.resource.id": "prefect.flow-run.*"},
                        posture=Posture.Reactive,
                        threshold=1,
                    ),
                ],
            ),
            actions=[actions.DoNothing()],
        )

        persisted = await automations.create_automation(
            session=automations_session, automation=compound_automation
        )
        compound_automation.created = persisted.created
        compound_automation.updated = persisted.updated
        triggers.load_automation(persisted)
        await automations_session.commit()

        return compound_automation

    async def test_compound_automation_all_no_match_trigger_does_not_act(
        self,
        act: mock.AsyncMock,
        flow_run_events: List[ReceivedEvent],
        compound_automation_all_no_match: Automation,
    ):
        """
        Ensures that when a stream of events is received,
        the compound trigger is not called if the expected event is not present.
        """
        for received_event in flow_run_events:
            await triggers.reactive_evaluation(received_event)

        act.assert_not_called()

    @pytest.fixture
    async def compound_automation_all_with_match(
        self,
        automations_session: AsyncSession,
        cleared_buckets: None,
        cleared_automations: None,
    ):
        """
        This automation has a compound trigger that requires all of the triggers to be met.
        """
        compound_automation = Automation(
            name="Compound Automation",
            description="",
            trigger=CompoundTrigger(
                require="all",
                within=timedelta(minutes=5),
                triggers=[
                    EventTrigger(
                        expect={"prefect.flow-run.Failed"},
                        match={"prefect.resource.id": "prefect.flow-run.*"},
                        posture=Posture.Reactive,
                        threshold=1,
                    ),
                    EventTrigger(
                        expect={"prefect.flow-run.Completed"},
                        match={"prefect.resource.id": "prefect.flow-run.*"},
                        posture=Posture.Reactive,
                        threshold=1,
                    ),
                ],
            ),
            actions=[actions.DoNothing()],
        )

        persisted = await automations.create_automation(
            session=automations_session, automation=compound_automation
        )
        compound_automation.created = persisted.created
        compound_automation.updated = persisted.updated
        triggers.load_automation(persisted)
        await automations_session.commit()

        return compound_automation

    async def test_compound_automation_all_match_trigger_acts(
        self,
        act: mock.AsyncMock,
        flow_run_events: List[ReceivedEvent],
        compound_automation_all_with_match: Automation,
    ):
        """
        Ensures that when a stream of events is received,
        the compound trigger is called if all expected events are present.
        """
        for received_event in flow_run_events:
            await triggers.reactive_evaluation(received_event)

        act.assert_called_once()

        firing: Firing = act.call_args.args[0]

        assert firing.trigger.id == compound_automation_all_with_match.trigger.id

    async def test_compound_automation_all_will_not_double_fire(
        self,
        db: PrefectDBInterface,
        act: mock.AsyncMock,
        flow_run_events: List[ReceivedEvent],
        compound_automation_all_with_match: Automation,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """
        Special case test for the race condition where two identical firings land at the
        same time.  This can't be reproduced reliably during tests, so it is mocked.
        """

        # Replace the get_child_firings function with one that returns firings that
        # are _not_ the one that should have just happened
        async def get_child_firings(
            session: AsyncSession, firing: Firing
        ) -> List[db.CompositeTriggerChildFiring]:
            assert isinstance(
                compound_automation_all_with_match.trigger, CompoundTrigger
            )
            return [
                db.CompositeTriggerChildFiring(
                    child_firing=Firing(
                        id=uuid4(),
                        trigger=compound_automation_all_with_match.trigger.triggers[0],
                        trigger_states={TriggerState.Triggered},
                        triggered=now("UTC"),
                    )
                ),
                db.CompositeTriggerChildFiring(
                    child_firing=Firing(
                        id=uuid4(),
                        trigger=compound_automation_all_with_match.trigger.triggers[1],
                        trigger_states={TriggerState.Triggered},
                        triggered=now("UTC"),
                    )
                ),
            ]

        monkeypatch.setattr(
            "prefect.server.events.triggers.get_child_firings", get_child_firings
        )

        for received_event in flow_run_events:
            await triggers.reactive_evaluation(received_event)

        act.assert_not_called()

    @pytest.fixture
    async def compound_automation_all_double_nested_anys(
        self,
        automations_session: AsyncSession,
        cleared_buckets: None,
        cleared_automations: None,
    ):
        """
        This automation has a compound trigger that requires any of the triggers to be met in both compound triggers.
        """
        nested_compound_automation = Automation(
            name="Compound Automation",
            description="",
            trigger=CompoundTrigger(
                require="all",
                within=timedelta(minutes=5),
                triggers=[
                    CompoundTrigger(
                        require="any",
                        within=timedelta(minutes=5),
                        triggers=[
                            EventTrigger(
                                expect={"prefect.flow-run.Failed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                            EventTrigger(
                                expect={"prefect.flow-run.Completed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                        ],
                    ),
                    CompoundTrigger(
                        require="any",
                        within=timedelta(minutes=5),
                        triggers=[
                            EventTrigger(
                                expect={"prefect.flow-run.Completed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                            EventTrigger(
                                expect={"prefect.flow-run.NonExistent"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                        ],
                    ),
                ],
            ),
            actions=[actions.DoNothing()],
        )

        persisted = await automations.create_automation(
            session=automations_session, automation=nested_compound_automation
        )
        nested_compound_automation.created = persisted.created
        nested_compound_automation.updated = persisted.updated
        triggers.load_automation(persisted)
        await automations_session.commit()

        return nested_compound_automation

    async def test_compound_automation_all_double_nested_trigger_anys_acts(
        self,
        act: mock.AsyncMock,
        flow_run_events: List[ReceivedEvent],
        compound_automation_all_double_nested_anys: Automation,
    ):
        """
        Ensures that when a stream of events is received,
        the compound trigger is called if any expected events are present in both compound triggers.
        """
        for received_event in flow_run_events:
            await triggers.reactive_evaluation(received_event)

        act.assert_called_once()

        firing: Firing = act.call_args.args[0]

        assert (
            firing.trigger.id == compound_automation_all_double_nested_anys.trigger.id
        )

    @pytest.fixture
    async def compound_automation_all_double_nested_all_and_any(
        self,
        automations_session: AsyncSession,
        cleared_buckets: None,
        cleared_automations: None,
    ):
        """
        This automation has a compound trigger that requires any of the triggers to be met.
        """
        nested_compound_automation = Automation(
            name="Compound Automation",
            description="",
            trigger=CompoundTrigger(
                require="all",
                within=timedelta(minutes=5),
                triggers=[
                    CompoundTrigger(
                        require="all",
                        within=timedelta(minutes=5),
                        triggers=[
                            EventTrigger(
                                expect={"prefect.flow-run.Failed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                            EventTrigger(
                                expect={"prefect.flow-run.Completed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                        ],
                    ),
                    CompoundTrigger(
                        require="any",
                        within=timedelta(minutes=5),
                        triggers=[
                            EventTrigger(
                                expect={"prefect.flow-run.Completed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                            EventTrigger(
                                expect={"prefect.flow-run.NonExistent"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                        ],
                    ),
                ],
            ),
            actions=[actions.DoNothing()],
        )

        persisted = await automations.create_automation(
            session=automations_session, automation=nested_compound_automation
        )
        nested_compound_automation.created = persisted.created
        nested_compound_automation.updated = persisted.updated
        triggers.load_automation(persisted)
        await automations_session.commit()

        return nested_compound_automation

    async def test_compound_automation_all_double_nested_trigger_any_all_does_not_act(
        self,
        act: mock.AsyncMock,
        flow_run_events: List[ReceivedEvent],
        compound_automation_all_double_nested_all_and_any: Automation,
    ):
        """
        Ensures that when a stream of events is received,
        the compound trigger is not called if the expected event is not present.
        """
        for received_event in flow_run_events:
            await triggers.reactive_evaluation(received_event)

        act.call_count == 2

        firing: Firing = act.call_args.args[0]

        assert (
            firing.trigger.id
            == compound_automation_all_double_nested_all_and_any.trigger.id
        )

    @pytest.fixture
    async def compound_automation_all_double_nested_all_and_all_no_match(
        self,
        automations_session: AsyncSession,
        cleared_buckets: None,
        cleared_automations: None,
    ):
        """
        This automation has a compound trigger that requires all of the triggers to be met.
        """
        nested_compound_automation = Automation(
            name="Compound Automation",
            description="",
            trigger=CompoundTrigger(
                require="all",
                within=timedelta(minutes=5),
                triggers=[
                    CompoundTrigger(
                        require="all",
                        within=timedelta(minutes=5),
                        triggers=[
                            EventTrigger(
                                expect={"prefect.flow-run.Failed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                            EventTrigger(
                                expect={"prefect.flow-run.Completed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                        ],
                    ),
                    CompoundTrigger(
                        require="all",
                        within=timedelta(minutes=5),
                        triggers=[
                            EventTrigger(
                                expect={"prefect.flow-run.Completed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                            EventTrigger(
                                expect={"prefect.flow-run.NonExistent"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                        ],
                    ),
                ],
            ),
            actions=[actions.DoNothing()],
        )

        persisted = await automations.create_automation(
            session=automations_session, automation=nested_compound_automation
        )
        nested_compound_automation.created = persisted.created
        nested_compound_automation.updated = persisted.updated
        triggers.load_automation(persisted)
        await automations_session.commit()

        return nested_compound_automation

    async def test_compound_automation_all_double_nested_trigger_all_all_does_not_act(
        self,
        act: mock.AsyncMock,
        flow_run_events: List[ReceivedEvent],
        compound_automation_all_double_nested_all_and_all_no_match: Automation,
    ):
        """
        Ensures that when a stream of events is received,
        the compound trigger is not called if the expected event is not present.
        """
        for received_event in flow_run_events:
            await triggers.reactive_evaluation(received_event)

        act.assert_not_called()

    @pytest.fixture
    async def compound_automation_all_double_nested_events_all_and_all_with_match(
        self,
        automations_session: AsyncSession,
        cleared_buckets: None,
        cleared_automations: None,
    ):
        """
        This automation has a compound trigger that requires all of the triggers to be met.
        """
        nested_compound_automation = Automation(
            name="Compound Automation",
            description="",
            trigger=CompoundTrigger(
                require="all",
                within=timedelta(minutes=5),
                triggers=[
                    CompoundTrigger(
                        require="all",
                        within=timedelta(minutes=5),
                        triggers=[
                            EventTrigger(
                                expect={"prefect.flow-run.Failed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                            EventTrigger(
                                expect={"prefect.flow-run.Completed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                        ],
                    ),
                    CompoundTrigger(
                        require="all",
                        within=timedelta(minutes=5),
                        triggers=[
                            EventTrigger(
                                expect={"prefect.flow-run.Completed"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                            EventTrigger(
                                expect={"prefect.flow-run.Pending"},
                                match={"prefect.resource.id": "prefect.flow-run.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                        ],
                    ),
                ],
            ),
            actions=[actions.DoNothing()],
        )

        persisted = await automations.create_automation(
            session=automations_session, automation=nested_compound_automation
        )
        nested_compound_automation.created = persisted.created
        nested_compound_automation.updated = persisted.updated
        triggers.load_automation(persisted)
        await automations_session.commit()

        return nested_compound_automation

    async def test_compound_automation_all_double_nested_trigger_acts(
        self,
        act: mock.AsyncMock,
        flow_run_events: List[ReceivedEvent],
        compound_automation_all_double_nested_events_all_and_all_with_match: Automation,
    ):
        """
        Ensure that the compound trigger is fired when all triggers are met.
        """
        for received_event in flow_run_events:
            await triggers.reactive_evaluation(received_event)

        act.call_count == 1

        firing: Firing = act.call_args.args[0]

        assert (
            firing.trigger.id
            == compound_automation_all_double_nested_events_all_and_all_with_match.trigger.id
        )

    async def test_compound_automation_all_double_nested_trigger_acts_and_queues_action(
        self,
        act: mock.AsyncMock,
        flow_run_events: List[ReceivedEvent],
        compound_automation_all_double_nested_events_all_and_all_with_match: Automation,
        publish: mock.AsyncMock,
        create_publisher: mock.MagicMock,
    ):
        """
        Ensure one action is queued after the compound trigger is fired.
        """
        for received_event in flow_run_events:
            await triggers.reactive_evaluation(received_event)

        act.assert_awaited_once()


@pytest.fixture
async def chonk_baker(
    automations_session: AsyncSession,
    cleared_buckets: None,
    cleared_automations: None,
) -> Automation:
    """
    Create a sequence automation that triggers on the following events:
    - ingredients.buy
    - ingredients.mix
    - cake.bake
    """
    sequence_automation = Automation(
        name="Sequence Automation",
        trigger=SequenceTrigger(
            triggers=[
                EventTrigger(
                    expect={"ingredients.buy"},
                    match={"prefect.resource.id": "prefect.ingredients.*"},
                    posture=Posture.Reactive,
                    threshold=1,
                ),
                EventTrigger(
                    expect={"ingredients.mix"},
                    match={"prefect.resource.id": "prefect.ingredients.*"},
                    posture=Posture.Reactive,
                    threshold=1,
                ),
                EventTrigger(
                    expect={"cake.bake"},
                    match={"prefect.resource.id": "prefect.cake.*"},
                    posture=Posture.Reactive,
                    threshold=1,
                ),
            ],
            within=5,
        ),
        actions=[actions.DoNothing()],
    )
    persisted = await automations.create_automation(
        automations_session, sequence_automation
    )
    sequence_automation.created = persisted.created
    sequence_automation.updated = persisted.updated
    triggers.load_automation(sequence_automation)
    await automations_session.commit()

    return sequence_automation


@pytest.fixture
async def chonk_twins(
    automations_session: AsyncSession,
    cleared_buckets: None,
    cleared_automations: None,
) -> Automation:
    """
    Create a sequence automation that triggers on the following events:
    - ingredients.buy
    - ingredients.buy
    """
    sequence_automation = Automation(
        name="Sequence Automation",
        trigger=SequenceTrigger(
            triggers=[
                EventTrigger(
                    expect={"ingredients.buy"},
                    match={"prefect.resource.id": "prefect.ingredients.*"},
                    posture=Posture.Reactive,
                ),
                EventTrigger(
                    expect={"ingredients.buy"},
                    match={"prefect.resource.id": "prefect.ingredients.*"},
                    posture=Posture.Reactive,
                ),
            ],
            within=5,
        ),
        actions=[actions.DoNothing()],
    )
    persisted = await automations.create_automation(
        automations_session, sequence_automation
    )
    sequence_automation.created = persisted.created
    sequence_automation.updated = persisted.updated
    triggers.load_automation(sequence_automation)
    await automations_session.commit()

    return sequence_automation


@pytest.fixture
async def chonk_buyer(
    automations_session: AsyncSession,
    cleared_buckets: None,
    cleared_automations: None,
) -> Automation:
    sequence_automation = Automation(
        name="Sequence Automation",
        trigger=SequenceTrigger(
            triggers=[
                EventTrigger(
                    expect={"cake.buy"},
                    match={"prefect.resource.id": "prefect.cake.*"},
                    posture=Posture.Reactive,
                    threshold=1,
                ),
            ],
            within=5,
        ),
        actions=[actions.DoNothing()],
    )

    persisted = await automations.create_automation(
        automations_session, sequence_automation
    )
    sequence_automation.created = persisted.created
    sequence_automation.updated = persisted.updated
    triggers.load_automation(sequence_automation)
    await automations_session.commit()

    return sequence_automation


class TestSequenceTriggers:
    @pytest.fixture
    def cake_buy(
        self,
        start_of_test: DateTime,
    ) -> ReceivedEvent:
        return ReceivedEvent(
            occurred=start_of_test + timedelta(seconds=4),
            resource={
                "prefect.resource.id": "prefect.cake.12345",
            },
            event="cake.buy",
            id=uuid4(),
        )

    async def test_sequence_trigger_single_trigger_fired_acts(
        self,
        chonk_buyer: Automation,
        cake_buy: ReceivedEvent,
        act: mock.AsyncMock,
    ):
        await triggers.reactive_evaluation(cake_buy)

        act.assert_called_once()

        firing: Firing = act.call_args.args[0]

        assert firing.trigger.id == chonk_buyer.trigger.id

        act.reset_mock()

    @pytest.fixture
    def ingredients_buy(
        self,
        start_of_test: DateTime,
    ) -> ReceivedEvent:
        return ReceivedEvent(
            occurred=start_of_test + timedelta(seconds=1),
            resource={
                "prefect.resource.id": "prefect.ingredients.12345",
            },
            event="ingredients.buy",
            id=uuid4(),
        )

    async def test_sequence_trigger_single_trigger_not_fired_does_not_act(
        self,
        chonk_buyer: Automation,
        ingredients_buy: ReceivedEvent,
        act: mock.AsyncMock,
    ):
        await triggers.reactive_evaluation(ingredients_buy)

        act.assert_not_called()

    @pytest.fixture
    def baking_wrong(
        self,
        start_of_test: DateTime,
    ) -> List[ReceivedEvent]:
        return [
            ReceivedEvent(
                occurred=start_of_test + timedelta(seconds=1),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.buy",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=start_of_test + timedelta(seconds=2),
                resource={
                    "prefect.resource.id": "prefect.cake.23456",
                },
                event="cake.bake",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=start_of_test + timedelta(seconds=3),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.mix",
                id=uuid4(),
            ),
        ]

    async def test_sequence_trigger_multiple_triggers_fired_out_of_order_does_not_act(
        self,
        chonk_baker: Automation,
        baking_wrong: List[ReceivedEvent],
        act: mock.AsyncMock,
    ):
        for event in baking_wrong:
            await triggers.reactive_evaluation(event)

        act.assert_not_called()

    @pytest.fixture
    def baking_right(
        self,
        start_of_test: DateTime,
    ) -> List[ReceivedEvent]:
        return [
            ReceivedEvent(
                occurred=start_of_test + timedelta(seconds=1),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.buy",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=start_of_test + timedelta(seconds=2),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.mix",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=start_of_test + timedelta(seconds=3),
                resource={
                    "prefect.resource.id": "prefect.cake.23456",
                },
                event="cake.bake",
                id=uuid4(),
            ),
        ]

    async def test_sequence_trigger_multiple_triggers_fired_in_order_acts(
        self,
        chonk_baker: Automation,
        baking_right: List[ReceivedEvent],
        act: mock.AsyncMock,
    ):
        for event in baking_right:
            await triggers.reactive_evaluation(event)

        act.assert_called_once()

        firing: Firing = act.call_args.args[0]

        assert firing.trigger.id == chonk_baker.trigger.id

        act.reset_mock()

    @pytest.fixture
    def baking_right_but_expired(
        self,
        start_of_test: DateTime,
    ) -> List[ReceivedEvent]:
        baseline: DateTime = start_of_test
        return [
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=1),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.buy",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=2),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.mix",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(minutes=14),
                resource={
                    "prefect.resource.id": "prefect.cake.23456",
                },
                event="cake.bake",
                id=uuid4(),
            ),
        ]

    @pytest.mark.xfail(reason="`act` is called once, even though it shouldn't be")
    async def test_sequence_trigger_multiple_triggers_fire_in_order_expired_does_not_act(
        self,
        chonk_baker: Automation,
        baking_right_but_expired: List[ReceivedEvent],
        act: mock.AsyncMock,
    ):
        """
        SequenceTrigger(triggers=[event1, event2, event3])

        1. event1 (the ingredients have all expired)
        2. event2
        3. event3
        """
        for event in baking_right_but_expired:
            await triggers.reactive_evaluation(event)

        act.assert_not_called()

    async def test_sequence_trigger_no_within_and_expired_triggers(
        self,
        chonk_baker: Automation,
        baking_right_but_expired: List[ReceivedEvent],
        act: mock.AsyncMock,
    ):
        """
        SequenceTrigger(triggers=[event1, event2, event3])

        1. event1 (the ingredients have all expired, but we don't care)
        2. event2
        3. event3
        """
        assert isinstance(chonk_baker.trigger, SequenceTrigger)
        chonk_baker.trigger.within = None

        for event in baking_right_but_expired:
            await triggers.reactive_evaluation(event)

        act.assert_called_once()

    @pytest.fixture
    def baking_right_with_dupes(
        self,
        start_of_test: DateTime,
    ) -> List[ReceivedEvent]:
        return [
            ReceivedEvent(
                occurred=start_of_test + timedelta(seconds=1),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.buy",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=start_of_test + timedelta(seconds=2),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.mix",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=start_of_test + timedelta(seconds=3),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.mix",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=start_of_test + timedelta(seconds=4),
                resource={
                    "prefect.resource.id": "prefect.cake.23456",
                },
                event="cake.bake",
                id=uuid4(),
            ),
        ]

    async def test_sequence_trigger_multiple_triggers_fired_in_order_duplicate_events_acts(
        self,
        chonk_baker: Automation,
        baking_right_with_dupes: List[ReceivedEvent],
        act: mock.AsyncMock,
    ):
        """
        SequenceTrigger(triggers=[event1, event2, event3])

        1. event1
        2. event2
        3. event2
        4. event3
        """
        for event in baking_right_with_dupes:
            await triggers.reactive_evaluation(event)

        act.assert_called_once()

        firing: Firing = act.call_args.args[0]

        assert firing.trigger.id == chonk_baker.trigger.id

        act.reset_mock()

    @pytest.fixture
    def baking_wrong_with_dupes(
        self,
        start_of_test: DateTime,
    ) -> List[ReceivedEvent]:
        baseline: DateTime = start_of_test
        return [
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=1),
                resource={
                    "prefect.resource.id": "prefect.ingredients.23456",
                },
                event="ingredients.buy",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=2),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.mix",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=3),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.buy",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=4),
                resource={
                    "prefect.resource.id": "prefect.cake.23456",
                },
                event="cake.bake",
                id=uuid4(),
            ),
        ]

    async def test_sequence_trigger_multiple_triggers_fired_somewhat_out_of_order_duplicate_events_does_not_act(
        self,
        chonk_baker: Automation,
        baking_wrong_with_dupes: List[ReceivedEvent],
        act: mock.AsyncMock,
    ):
        """
        SequenceTrigger(triggers=[event1, event2, event3])

        1. event1
        2. event2
        3. event1
        4. event3
        """

        for event in baking_wrong_with_dupes:
            await triggers.reactive_evaluation(event)

        act.assert_not_called()

    @pytest.fixture
    def baking_right_with_dupes_but_expired(
        self,
        start_of_test: DateTime,
    ) -> List[ReceivedEvent]:
        baseline: DateTime = start_of_test
        return [
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=1),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.buy",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=2),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.mix",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=3),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.mix",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(minutes=14),
                resource={
                    "prefect.resource.id": "prefect.cake.23456",
                },
                event="cake.bake",
                id=uuid4(),
            ),
        ]

    @pytest.mark.xfail(reason="`act` is called once, even though it shouldn't be")
    async def test_sequence_trigger_multiple_triggers_fired_in_order_duplicate_events_expired_does_not_act(
        self,
        chonk_baker: Automation,
        baking_right_with_dupes_but_expired: List[ReceivedEvent],
        act: mock.AsyncMock,
    ):
        """
        SequenceTrigger(triggers=[event1, event2, event3])

        1. event1 (this one will be expired by the time event3 triggers)
        2. event2
        3. event2
        4. event3
        """

        for event in baking_right_with_dupes_but_expired:
            await triggers.reactive_evaluation(event)

        act.assert_not_called()

    @pytest.fixture
    async def chonk_host(
        self,
        automations_session: AsyncSession,
        cleared_buckets: None,
        cleared_automations: None,
    ) -> Automation:
        sequence_automation = Automation(
            name="Sequence Automation",
            trigger=SequenceTrigger(
                triggers=[
                    EventTrigger(
                        expect={"ingredients.buy"},
                        match={"prefect.resource.id": "prefect.ingredients.*"},
                        posture=Posture.Reactive,
                        threshold=1,
                    ),
                    EventTrigger(
                        expect={"ingredients.mix"},
                        match={"prefect.resource.id": "prefect.ingredients.*"},
                        posture=Posture.Reactive,
                        threshold=1,
                    ),
                    EventTrigger(
                        expect={"cake.bake"},
                        match={"prefect.resource.id": "prefect.cake.*"},
                        posture=Posture.Reactive,
                        threshold=1,
                    ),
                    CompoundTrigger(
                        require="all",
                        within=timedelta(minutes=5),
                        triggers=[
                            EventTrigger(
                                expect={"guests.greet"},
                                match={"prefect.resource.id": "prefect.guests.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                            EventTrigger(
                                expect={"cake.serve"},
                                match={"prefect.resource.id": "prefect.cake.*"},
                                posture=Posture.Reactive,
                                threshold=1,
                            ),
                        ],
                    ),
                ],
                within=5,
            ),
            actions=[actions.DoNothing()],
        )

        persisted = await automations.create_automation(
            automations_session, sequence_automation
        )
        sequence_automation.created = persisted.created
        sequence_automation.updated = persisted.updated
        triggers.load_automation(sequence_automation)
        await automations_session.commit()

        return sequence_automation

    @pytest.fixture
    def host_duties(
        self,
        start_of_test: DateTime,
    ) -> List[ReceivedEvent]:
        baseline: DateTime = start_of_test
        return [
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=4),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.buy",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=5),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.mix",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=6),
                resource={
                    "prefect.resource.id": "prefect.cake.23456",
                },
                event="cake.bake",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=7),
                resource={
                    "prefect.resource.id": "prefect.guests.12345",
                },
                event="guests.greet",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=8),
                resource={
                    "prefect.resource.id": "prefect.cake.23456",
                },
                event="cake.serve",
                id=uuid4(),
            ),
        ]

    async def test_sequence_and_compound_trigger_multiple_triggers_fired_in_order_acts(
        self,
        chonk_host: Automation,
        baking_right: List[ReceivedEvent],
        host_duties: List[ReceivedEvent],
        act: mock.AsyncMock,
    ):
        for event in baking_right:
            await triggers.reactive_evaluation(event)

        for event in host_duties:
            await triggers.reactive_evaluation(event)

        act.assert_called_once()

        firing: Firing = act.call_args.args[0]

        assert firing.trigger.id == chonk_host.trigger.id

        act.reset_mock()

    async def test_sequence_and_compound_trigger_multiple_triggers_fired_in_order_acts_and_queues_action(
        self,
        act: mock.AsyncMock,
        chonk_host: Automation,
        baking_right: List[ReceivedEvent],
        host_duties: List[ReceivedEvent],
        publish: mock.AsyncMock,
        create_publisher: mock.MagicMock,
    ):
        for event in baking_right:
            await triggers.reactive_evaluation(event)

        for event in host_duties:
            await triggers.reactive_evaluation(event)

        act.assert_awaited_once()

    @pytest.fixture
    def host_duties_out_of_order(
        self,
        start_of_test: DateTime,
    ) -> List[ReceivedEvent]:
        baseline: DateTime = start_of_test
        return [
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=4),
                resource={
                    "prefect.resource.id": "prefect.ingredients.12345",
                },
                event="ingredients.buy",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=5),
                resource={
                    "prefect.resource.id": "prefect.cake.12345",
                },
                event="cake.bake",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=6),
                resource={
                    "prefect.resource.id": "prefect.ingredients.23456",
                },
                event="ingredients.mix",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=7),
                resource={
                    "prefect.resource.id": "prefect.cake.23456",
                },
                event="cake.serve",
                id=uuid4(),
            ),
            ReceivedEvent(
                occurred=baseline + datetime.timedelta(seconds=8),
                resource={
                    "prefect.resource.id": "prefect.guests.12345",
                },
                event="guests.greet",
                id=uuid4(),
            ),
        ]

    async def test_sequence_and_compound_trigger_multiple_triggers_fired_out_of_order_does_not_act(
        self,
        chonk_host: Automation,
        host_duties_out_of_order: List[ReceivedEvent],
        act: mock.AsyncMock,
    ):
        for event in host_duties_out_of_order:
            await triggers.reactive_evaluation(event)

        act.assert_not_called()

    @pytest.mark.xfail
    async def test_sequence_trigger_identical_event_triggers_only_one_fired_does_not_act(
        self,
        chonk_twins: Automation,
        ingredients_buy: ReceivedEvent,
        act: mock.AsyncMock,
    ):
        await triggers.reactive_evaluation(ingredients_buy)

        act.assert_not_called()
