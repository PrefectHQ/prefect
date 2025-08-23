"""Tests that the client automations schemas are compatible with the server."""

from datetime import timedelta
from typing import List, Set, Type, get_args
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
from prefect.settings import PREFECT_API_SERVICES_TRIGGERS_ENABLED, temporary_settings


@pytest.fixture(autouse=True)
def enable_triggers():
    with temporary_settings({PREFECT_API_SERVICES_TRIGGERS_ENABLED: True}):
        yield


# Extract the Union types from the Annotated TriggerTypes
_trigger_union = (
    get_args(TriggerTypes)[0] if hasattr(TriggerTypes, "__metadata__") else TriggerTypes
)
# Each element in the union is now Annotated[Type, Tag], so we need to extract the actual type
CLIENT_TRIGGER_TYPES: List[Type[Trigger]] = [
    get_args(t)[0] for t in get_args(_trigger_union)
]
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
                    DeploymentCompoundTrigger(
                        require="all",
                        triggers=[
                            DeploymentEventTrigger(posture=Posture.Reactive),
                            DeploymentEventTrigger(posture=Posture.Proactive),
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
                    DeploymentCompoundTrigger(
                        require="all",
                        triggers=[
                            DeploymentEventTrigger(posture=Posture.Reactive),
                            DeploymentEventTrigger(posture=Posture.Proactive),
                        ],
                    ),
                ]
            ),
        ]
    ),
]


def test_all_triggers_represented():
    """Ensures that we have an example for all client-side trigger types"""
    assert (
        set(CLIENT_TRIGGER_TYPES)
        == set(type(t) for t in EXAMPLE_TRIGGERS) | CLOUD_ONLY_TRIGGER_TYPES
    )


@pytest.mark.parametrize("trigger", EXAMPLE_TRIGGERS)
async def test_trigger_round_tripping(trigger: TriggerTypes, in_memory_prefect_client):
    """Tests that any of the example client triggers can be round-tripped to the
    Prefect server"""
    # Using an in-memory client because the Pydantic model marshalling doesn't work
    # with the hosted API server. It appears to chose the client-side model for EventTrigger
    # instead of the server-side model.
    # TODO: Fix the model resolution to work with the hosted API server
    automation_id = await in_memory_prefect_client.create_automation(
        AutomationCore(
            name="test",
            trigger=trigger,
            actions=[DoNothing()],
        )
    )
    automation = await in_memory_prefect_client.read_automation(automation_id)

    sent = trigger.model_dump()
    returned = automation.trigger.model_dump()

    assert sent == returned


# Extract the Union types from the Annotated DeploymentTriggerTypes
_deployment_trigger_union = (
    get_args(DeploymentTriggerTypes)[0]
    if hasattr(DeploymentTriggerTypes, "__metadata__")
    else DeploymentTriggerTypes
)
# Each element in the union is now Annotated[Type, Tag], so we need to extract the actual type
DEPLOYMENT_TRIGGER_TYPES: List[Type[Trigger]] = [
    get_args(t)[0] for t in get_args(_deployment_trigger_union)
]
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
                    DeploymentCompoundTrigger(
                        require="all",
                        triggers=[
                            DeploymentEventTrigger(posture=Posture.Reactive),
                            DeploymentEventTrigger(posture=Posture.Proactive),
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
    serialized = deployment_trigger.model_dump()

    # Remove automation fields
    serialized.pop("name", None)
    serialized.pop("description", None)
    serialized.pop("enabled", None)

    # Remove action fields
    serialized.pop("parameters", None)
    serialized.pop("job_variables", None)
    serialized.pop("schedule_after", None)

    trigger_type: Type[Trigger] = deployment_trigger.trigger_type
    trigger = trigger_type.model_validate(serialized)

    assert trigger.model_dump() == serialized


def test_metric_trigger_deserialization():
    """Test that metric triggers can be deserialized from API-like data (issue #18747)."""
    import uuid

    from prefect.events.schemas.automations import (
        Automation,
        MetricTrigger,
        Posture,
    )

    # This is the type of data that would come from the API
    test_data = {
        "id": str(uuid.uuid4()),
        "name": "Test Metric Automation",
        "description": "Test metric trigger validation",
        "enabled": True,
        "trigger": {
            "type": "metric",
            "posture": "Metric",
            "metric": {
                "name": "duration",
                "threshold": 100.0,
                "operator": ">",
                "range": 300.0,
                "firing_for": 300.0,
            },
            "match": {"prefect.resource.id": "prefect.flow-run.*"},
        },
        "actions": [],
    }

    # Should not raise validation error
    automation = Automation.model_validate(test_data)

    # Verify correct type
    assert isinstance(automation.trigger, MetricTrigger)
    assert automation.trigger.type == "metric"
    assert automation.trigger.posture == Posture.Metric

    # Verify metric details
    assert automation.trigger.metric.name.value == "duration"
    assert automation.trigger.metric.threshold == 100.0
    assert automation.trigger.metric.operator.value == ">"


def test_metric_trigger_round_trip():
    """Test that metric triggers can be serialized and deserialized."""
    import uuid

    from prefect.events.schemas.automations import (
        Automation,
        MetricTrigger,
        MetricTriggerQuery,
        Posture,
    )

    # Create an automation with a metric trigger
    automation = Automation(
        id=uuid.uuid4(),
        name="Test Metric Automation",
        description="Test",
        enabled=True,
        trigger=MetricTrigger(
            posture=Posture.Metric,
            metric=MetricTriggerQuery(
                name="successes",
                threshold=10,
                operator="<",
                range=600.0,
                firing_for=300.0,
            ),
            match={"prefect.resource.id": "prefect.flow-run.*"},
        ),
        actions=[],
    )

    # Serialize and deserialize
    data = automation.model_dump()
    restored = Automation.model_validate(data)

    # Should maintain the same structure
    assert isinstance(restored.trigger, MetricTrigger)
    assert restored.trigger.type == "metric"
    assert restored.trigger.metric.name.value == "successes"
    assert restored.trigger.metric.threshold == 10


def test_trigger_type_discrimination_with_metric():
    """Test that the discriminator correctly identifies metric triggers."""
    import uuid

    from prefect.events.schemas.automations import Automation, MetricTrigger

    # Test with explicit type field
    data_with_type = {
        "id": str(uuid.uuid4()),
        "name": "Test",
        "trigger": {
            "type": "metric",
            "posture": "Metric",
            "metric": {
                "name": "lateness",
                "threshold": 5,
                "operator": ">",
                "range": 300.0,
                "firing_for": 300.0,
            },
        },
        "actions": [],
    }

    automation = Automation.model_validate(data_with_type)
    assert isinstance(automation.trigger, MetricTrigger)
    assert automation.trigger.type == "metric"


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

    sent = action.model_dump()
    returned = automation.actions[0].model_dump()

    assert sent == returned
