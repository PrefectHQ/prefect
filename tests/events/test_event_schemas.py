import datetime
import json
from uuid import UUID, uuid4

import pendulum
import pytest
from pendulum.datetime import DateTime

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import ValidationError
else:
    from pydantic import ValidationError

from prefect.events.actions import RunDeployment
from prefect.events.schemas import (
    Automation,
    DeploymentTrigger,
    Event,
    Posture,
    RelatedResource,
    Resource,
    ResourceTrigger,
    Trigger,
)


def test_client_events_generate_an_id_by_default():
    event1 = Event(event="hello", resource={"prefect.resource.id": "hello"})
    event2 = Event(event="hello", resource={"prefect.resource.id": "hello"})
    assert isinstance(event1.id, UUID)
    assert isinstance(event2.id, UUID)
    assert event1.id != event2.id


def test_client_events_generate_occurred_by_default(start_of_test: DateTime):
    event = Event(event="hello", resource={"prefect.resource.id": "hello"})
    assert start_of_test <= event.occurred <= pendulum.now("UTC")


def test_client_events_may_have_empty_related_resources():
    event = Event(
        occurred=pendulum.now("UTC"),
        event="hello",
        resource={"prefect.resource.id": "hello"},
        id=uuid4(),
    )
    assert event.related == []


def test_client_event_resources_have_correct_types():
    event = Event(
        occurred=pendulum.now("UTC"),
        event="hello",
        resource={"prefect.resource.id": "hello"},
        related=[
            {"prefect.resource.id": "related-1", "prefect.resource.role": "role-1"},
        ],
        id=uuid4(),
    )
    assert isinstance(event.resource, Resource)
    assert isinstance(event.related[0], Resource)
    assert isinstance(event.related[0], RelatedResource)


def test_client_events_may_have_multiple_related_resources():
    event = Event(
        occurred=pendulum.now("UTC"),
        event="hello",
        resource={"prefect.resource.id": "hello"},
        related=[
            {"prefect.resource.id": "related-1", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-2", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-3", "prefect.resource.role": "role-2"},
        ],
        id=uuid4(),
    )
    assert event.related[0].id == "related-1"
    assert event.related[0].role == "role-1"
    assert event.related[1].id == "related-2"
    assert event.related[1].role == "role-1"
    assert event.related[2].id == "related-3"
    assert event.related[2].role == "role-2"


def test_json_representation():
    event = Event(
        occurred=pendulum.now("UTC"),
        event="hello",
        resource={"prefect.resource.id": "hello"},
        related=[
            {"prefect.resource.id": "related-1", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-2", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-3", "prefect.resource.role": "role-2"},
        ],
        payload={"hello": "world"},
        id=uuid4(),
        follows=uuid4(),
    )

    jsonified = json.loads(event.json().encode())

    assert jsonified == {
        "occurred": event.occurred.isoformat(),
        "event": "hello",
        "resource": {"prefect.resource.id": "hello"},
        "related": [
            {"prefect.resource.id": "related-1", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-2", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-3", "prefect.resource.role": "role-2"},
        ],
        "payload": {"hello": "world"},
        "id": str(event.id),
        "follows": str(event.follows),
    }


def test_limit_on_labels(monkeypatch: pytest.MonkeyPatch):
    labels = {"prefect.resource.id": "the.thing"}
    labels.update({str(i): str(i) for i in range(10)})

    monkeypatch.setattr("prefect.events.schemas.MAXIMUM_LABELS_PER_RESOURCE", 10)
    with pytest.raises(ValidationError, match="maximum number of labels"):
        Resource(__root__=labels)


def test_limit_on_related_resources(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("prefect.events.schemas.MAXIMUM_RELATED_RESOURCES", 10)
    with pytest.raises(ValidationError, match="maximum number of related"):
        Event(
            occurred=pendulum.now("UTC"),
            event="anything",
            resource={"prefect.resource.id": "the.thing"},
            related=[
                {
                    "prefect.resource.id": f"another.thing.{i}",
                    "prefect.resource.role": "related",
                }
                for i in range(11)
            ],
            id=uuid4(),
        )


def test_client_event_involved_resources():
    event = Event(
        occurred=pendulum.now("UTC"),
        event="hello",
        resource={"prefect.resource.id": "hello"},
        related=[
            {"prefect.resource.id": "related-1", "prefect.resource.role": "role-1"},
        ],
        id=uuid4(),
    )

    assert [resource.id for resource in event.involved_resources] == [
        "hello",
        "related-1",
    ]


def test_resource_trigger_actions_not_implemented():
    trigger = ResourceTrigger()
    with pytest.raises(NotImplementedError):
        trigger.actions()


def test_deployment_trigger_as_automation():
    trigger = DeploymentTrigger(
        name="A deployment automation",
    )
    trigger.set_deployment_id(uuid4())

    automation = trigger.as_automation()

    assert automation == Automation(
        name="A deployment automation",
        description="",
        enabled=True,
        trigger=Trigger(
            posture=Posture.Reactive,
            threshold=1,
            within=datetime.timedelta(0),
        ),
        actions=[
            RunDeployment(
                type="run-deployment",
                source="selected",
                parameters=None,
                deployment_id=trigger._deployment_id,
            )
        ],
        owner_resource=f"prefect.deployment.{trigger._deployment_id}",
    )
