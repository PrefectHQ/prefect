"""Tests that the client automations schemas are compatible with the server."""

from datetime import timedelta
from typing import List, Set, Type
from uuid import uuid4

import pytest

from prefect.client.orchestration import get_client
from prefect.events import Trigger, TriggerTypes
from prefect.events.actions import (
    Action,
    ActionTypes,
    CallWebhook,
    CancelFlowRun,
    ChangeFlowRunState,
    DeclareIncident,
    DoNothing,
    PauseAutomation,
    PauseDeployment,
    PauseWorkPool,
    PauseWorkQueue,
    ResumeAutomation,
    ResumeDeployment,
    ResumeWorkPool,
    ResumeWorkQueue,
    RunDeployment,
    SendNotification,
    SuspendFlowRun,
)
from prefect.events.schemas.automations import (
    AutomationCore,
    CompoundTrigger,
    EventTrigger,
    MetricTrigger,
    Posture,
    SequenceTrigger,
)
from prefect.events.schemas.deployment_triggers import (
    DeploymentCompoundTrigger,
    DeploymentEventTrigger,
    DeploymentMetricTrigger,
    DeploymentSequenceTrigger,
    DeploymentTriggerTypes,
)
from prefect.settings import (
    PREFECT_API_SERVICES_TRIGGERS_ENABLED,
    PREFECT_EXPERIMENTAL_ENABLE_EVENTS,
    temporary_settings,
)

CLIENT_TRIGGER_TYPES: List[Type[Trigger]] = list(TriggerTypes.__args__)  # type: ignore[attr-defined]
CLOUD_ONLY_TRIGGER_TYPES: Set[Type[Trigger]] = {MetricTrigger}

EXAMPLE_TRIGGERS: List[TriggerTypes] = [
    EventTrigger(),
    EventTrigger(posture=Posture.Reactive),
    EventTrigger(posture=Posture.Proactive),
    EventTrigger(
        after={"a.b.c", "d.e.f"},
        expect={"g.h.i", "j.k.l"},
        match={
            "a.b.c": ["d.e.f", "g.h.i"],
            "j.k.l": "m.n.o",
        },
        match_related={
            "a.b.c": ["d.e.f", "g.h.i"],
            "j.k.l": "m.n.o",
        },
        for_each={"foo.bar.baz", "blip.bloop.blorp"},
        threshold=42,
        within=timedelta(minutes=42),
    ),
    CompoundTrigger(
        require="all",
        triggers=[
            EventTrigger(posture=Posture.Reactive),
            EventTrigger(posture=Posture.Proactive),
            CompoundTrigger(
                require="all",
                triggers=[
                    EventTrigger(posture=Posture.Reactive),
                    EventTrigger(posture=Posture.Proactive),
                ],
            ),
            SequenceTrigger(
                triggers=[
                    EventTrigger(posture=Posture.Reactive),
                    EventTrigger(posture=Posture.Proactive),
                    CompoundTrigger(
                        require="all",
                        triggers=[
                            EventTrigger(posture=Posture.Reactive),
                            EventTrigger(posture=Posture.Proactive),
                        ],
                    ),
                ]
            ),
        ],
    ),
    SequenceTrigger(
        triggers=[
            EventTrigger(posture=Posture.Reactive),
            EventTrigger(posture=Posture.Proactive),
            CompoundTrigger(
                require="all",
                triggers=[
                    EventTrigger(posture=Posture.Reactive),
                    EventTrigger(posture=Posture.Proactive),
                ],
            ),
            SequenceTrigger(
                triggers=[
                    EventTrigger(posture=Posture.Reactive),
                    EventTrigger(posture=Posture.Proactive),
                    CompoundTrigger(
                        require="all",
                        triggers=[
                            EventTrigger(posture=Posture.Reactive),
                            EventTrigger(posture=Posture.Proactive),
                        ],
                    ),
                ]
            ),
        ]
    ),
]


@pytest.fixture(autouse=True)
def enable_events():
    with temporary_settings(
        {
            PREFECT_EXPERIMENTAL_ENABLE_EVENTS: True,
            PREFECT_API_SERVICES_TRIGGERS_ENABLED: True,
        }
    ):
        yield


def test_all_triggers_represented():
    """Ensures that we have an example for all client-side trigger types"""
    assert (
        set(CLIENT_TRIGGER_TYPES)
        == set(type(t) for t in EXAMPLE_TRIGGERS) | CLOUD_ONLY_TRIGGER_TYPES
    )


@pytest.mark.parametrize("trigger", EXAMPLE_TRIGGERS)
async def test_trigger_round_tripping(trigger: TriggerTypes):
    """Tests that any of the example client triggers can be round-tripped to the
    Prefect server"""
    async with get_client() as client:
        automation_id = await client.create_automation(
            AutomationCore(
                name="test",
                trigger=trigger,
                actions=[DoNothing()],
            )
        )
        automation = await client.read_automation(automation_id)

    sent = trigger.dict()
    returned = automation.trigger.dict()

    assert sent == returned


DEPLOYMENT_TRIGGER_TYPES: List[Type[Trigger]] = list(DeploymentTriggerTypes.__args__)  # type: ignore[attr-defined]
CLOUD_ONLY_DEPLOYMENT_TRIGGER_TYPES: Set[Type[Trigger]] = {DeploymentMetricTrigger}


EXAMPLE_DEPLOYMENT_TRIGGERS: List[DeploymentTriggerTypes] = [
    DeploymentEventTrigger(),
    DeploymentEventTrigger(posture=Posture.Reactive),
    DeploymentEventTrigger(posture=Posture.Proactive),
    DeploymentEventTrigger(
        after={"a.b.c", "d.e.f"},
        expect={"g.h.i", "j.k.l"},
        match={
            "a.b.c": ["d.e.f", "g.h.i"],
            "j.k.l": "m.n.o",
        },
        match_related={
            "a.b.c": ["d.e.f", "g.h.i"],
            "j.k.l": "m.n.o",
        },
        for_each={"foo.bar.baz", "blip.bloop.blorp"},
        threshold=42,
        within=timedelta(minutes=42),
    ),
    DeploymentCompoundTrigger(
        require="all",
        triggers=[
            EventTrigger(posture=Posture.Reactive),
            EventTrigger(posture=Posture.Proactive),
            CompoundTrigger(
                require="all",
                triggers=[
                    EventTrigger(posture=Posture.Reactive),
                    EventTrigger(posture=Posture.Proactive),
                ],
            ),
            SequenceTrigger(
                triggers=[
                    EventTrigger(posture=Posture.Reactive),
                    EventTrigger(posture=Posture.Proactive),
                    CompoundTrigger(
                        require="all",
                        triggers=[
                            EventTrigger(posture=Posture.Reactive),
                            EventTrigger(posture=Posture.Proactive),
                        ],
                    ),
                ]
            ),
        ],
    ),
    DeploymentSequenceTrigger(
        triggers=[
            EventTrigger(posture=Posture.Reactive),
            EventTrigger(posture=Posture.Proactive),
            CompoundTrigger(
                require="all",
                triggers=[
                    EventTrigger(posture=Posture.Reactive),
                    EventTrigger(posture=Posture.Proactive),
                ],
            ),
            SequenceTrigger(
                triggers=[
                    EventTrigger(posture=Posture.Reactive),
                    EventTrigger(posture=Posture.Proactive),
                    CompoundTrigger(
                        require="all",
                        triggers=[
                            EventTrigger(posture=Posture.Reactive),
                            EventTrigger(posture=Posture.Proactive),
                        ],
                    ),
                ]
            ),
        ]
    ),
]


def test_all_deployment_triggers_represented():
    """Ensures that we have an example for all deploymnet trigger types"""
    assert (
        set(DEPLOYMENT_TRIGGER_TYPES)
        == set(type(t) for t in EXAMPLE_DEPLOYMENT_TRIGGERS)
        | CLOUD_ONLY_DEPLOYMENT_TRIGGER_TYPES
    )


@pytest.mark.parametrize("deployment_trigger", EXAMPLE_DEPLOYMENT_TRIGGERS)
def test_trigger_serialization(deployment_trigger: DeploymentTriggerTypes):
    """Tests that any of the example deployment triggers can be round-tripped to the
    equivalent client trigger type"""
    serialized = deployment_trigger.dict()

    # Remove automation fields
    serialized.pop("name", None)
    serialized.pop("description", None)
    serialized.pop("enabled", None)

    # Remove action fields
    serialized.pop("parameters", None)
    serialized.pop("job_variables", None)

    trigger = deployment_trigger.trigger_type.parse_obj(serialized)

    assert trigger.dict() == serialized


CLIENT_ACTION_TYPES: List[Type[Action]] = list(ActionTypes.__args__)  # type: ignore[attr-defined]
CLOUD_ONLY_ACTION_TYPES: Set[Type[Action]] = {DeclareIncident}


EXAMPLE_ACTIONS: List[ActionTypes] = [
    DoNothing(),
    RunDeployment(source="inferred"),
    RunDeployment(source="selected", deployment_id=uuid4()),
    PauseDeployment(source="inferred"),
    PauseDeployment(source="selected", deployment_id=uuid4()),
    ResumeDeployment(source="inferred"),
    ResumeDeployment(source="selected", deployment_id=uuid4()),
    ChangeFlowRunState(state="RUNNING", name="Runnin'", message="I'm running!"),
    CancelFlowRun(),
    SuspendFlowRun(),
    CallWebhook(block_document_id=uuid4(), payload="Hi there!"),
    SendNotification(block_document_id=uuid4(), subject="Hello, world!", body="Hi!"),
    PauseWorkPool(source="inferred"),
    PauseWorkPool(source="selected", work_pool_id=uuid4()),
    ResumeWorkPool(source="inferred"),
    ResumeWorkPool(source="selected", work_pool_id=uuid4()),
    PauseWorkQueue(source="inferred"),
    PauseWorkQueue(source="selected", work_queue_id=uuid4()),
    ResumeWorkQueue(source="inferred"),
    ResumeWorkQueue(source="selected", work_queue_id=uuid4()),
    PauseAutomation(source="inferred"),
    PauseAutomation(source="selected", automation_id=uuid4()),
    ResumeAutomation(source="inferred"),
    ResumeAutomation(source="selected", automation_id=uuid4()),
]


def test_all_actions_represented():
    """Ensures that we have an example for all client-side action types"""
    assert (
        set(CLIENT_ACTION_TYPES)
        == set(type(a) for a in EXAMPLE_ACTIONS) | CLOUD_ONLY_ACTION_TYPES
    )


@pytest.mark.parametrize("action", EXAMPLE_ACTIONS)
async def test_action_round_tripping(action: ActionTypes):
    """Tests that any of the example client triggers can be round-tripped to the
    Prefect server"""
    async with get_client() as client:
        automation_id = await client.create_automation(
            AutomationCore(
                name="test",
                trigger=EventTrigger(),
                actions=[action],
            )
        )
        automation = await client.read_automation(automation_id)

    sent = action.dict()
    returned = automation.actions[0].dict()

    assert sent == returned
