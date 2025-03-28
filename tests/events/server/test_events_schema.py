import datetime
import json
from datetime import timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from prefect.server.events.schemas.events import (
    Event,
    ReceivedEvent,
    RelatedResource,
    Resource,
)
from prefect.types import DateTime
from prefect.types._datetime import now


def test_client_events_do_not_have_defaults_for_the_fields_it_seems_they_should():
    """While it seems tempting to include a default for `occurred` or `id`, these
    _must_ be provided by the client for truthiness.  They can have defaults in
    client implementations, but should _not_ have them here."""
    with pytest.raises(ValidationError) as error:
        Event(  # type: ignore
            event="hello",
            resource={"prefect.resource.id": "hello"},
            id=uuid4(),
        )

    assert len(error.value.errors()) == 1
    (error,) = error.value.errors()
    assert error["loc"] == ("occurred",)
    assert error["msg"] == "Field required"
    assert error["type"] == "missing"

    with pytest.raises(ValidationError) as error:
        Event(  # type: ignore
            occurred=now("UTC"),
            event="hello",
            resource={"prefect.resource.id": "hello"},
        )

    assert len(error.value.errors()) == 1
    (error,) = error.value.errors()
    assert error["loc"] == ("id",)
    assert error["msg"] == "Field required"
    assert error["type"] == "missing"


def test_client_events_may_have_empty_related_resources():
    event = Event(
        occurred=now("UTC"),
        event="hello",
        resource={"prefect.resource.id": "hello"},
        id=uuid4(),
    )
    assert event.related == []


def test_client_event_resources_have_correct_types():
    event = Event(
        occurred=now("UTC"),
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
        occurred=now("UTC"),
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


def test_client_events_may_have_a_name_label():
    event = Event(
        occurred=now("UTC"),
        event="hello",
        resource={"prefect.resource.id": "hello", "prefect.resource.name": "Hello!"},
        related=[
            {
                "prefect.resource.id": "related-1",
                "prefect.resource.role": "role-1",
                "prefect.resource.name": "Related 1",
            },
            {
                "prefect.resource.id": "related-2",
                "prefect.resource.role": "role-1",
                "prefect.resource.name": "Related 2",
            },
            {
                "prefect.resource.id": "related-3",
                "prefect.resource.role": "role-2",
                # deliberately lacks a name
            },
        ],
        id=uuid4(),
    )
    assert event.resource.name == "Hello!"
    assert [related.name for related in event.related] == [
        "Related 1",
        "Related 2",
        None,
    ]


def test_server_events_default_received(start_of_test: DateTime):
    event = ReceivedEvent(
        occurred=now("UTC"),
        event="hello",
        resource={"prefect.resource.id": "hello"},
        id=uuid4(),
    )
    assert start_of_test <= event.received <= now("UTC")


def test_server_events_can_be_received_from_client_events(start_of_test: DateTime):
    client_event = Event(
        occurred=now("UTC"),
        event="hello",
        resource={"prefect.resource.id": "hello"},
        related=[
            {"prefect.resource.id": "related-1", "prefect.resource.role": "role-1"},
        ],
        id=uuid4(),
    )

    server_event = client_event.receive()

    assert isinstance(server_event, ReceivedEvent)

    assert server_event.occurred == client_event.occurred
    assert server_event.event == client_event.event
    assert server_event.resource == client_event.resource
    assert server_event.related == client_event.related
    assert server_event.id == client_event.id
    assert start_of_test <= server_event.received <= now("UTC")


def test_server_events_can_be_received_from_client_events_with_times(
    start_of_test: DateTime,
):
    client_event = Event(
        occurred=now("UTC"),
        event="hello",
        resource={"prefect.resource.id": "hello"},
        related=[
            {"prefect.resource.id": "related-1", "prefect.resource.role": "role-1"},
        ],
        id=uuid4(),
    )

    expected_received = now("UTC") - datetime.timedelta(minutes=5)

    server_event = client_event.receive(received=expected_received)

    assert isinstance(server_event, ReceivedEvent)

    assert server_event.occurred == client_event.occurred
    assert server_event.event == client_event.event
    assert server_event.resource == client_event.resource
    assert server_event.related == client_event.related
    assert server_event.id == client_event.id
    assert server_event.received == expected_received


def test_json_representation():
    event = ReceivedEvent(
        occurred=DateTime(2021, 2, 3, 4, 5, 6, 7, tzinfo=timezone.utc),
        event="hello",
        resource={"prefect.resource.id": "hello"},
        related=[
            {"prefect.resource.id": "related-1", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-2", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-3", "prefect.resource.role": "role-2"},
        ],
        payload={"hello": "world"},
        id=uuid4(),
        received=DateTime(2021, 2, 3, 4, 5, 6, 78, tzinfo=timezone.utc),
    )

    jsonified = json.loads(event.model_dump_json())

    assert jsonified == {
        "occurred": "2021-02-03T04:05:06.000007Z",
        "event": "hello",
        "resource": {"prefect.resource.id": "hello"},
        "related": [
            {"prefect.resource.id": "related-1", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-2", "prefect.resource.role": "role-1"},
            {"prefect.resource.id": "related-3", "prefect.resource.role": "role-2"},
        ],
        "payload": {"hello": "world"},
        "id": str(event.id),
        "follows": None,
        "received": "2021-02-03T04:05:06.000078Z",
    }


def test_client_event_involved_resources():
    event = Event(
        occurred=now("UTC"),
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


@pytest.fixture
def example_event() -> Event:
    return Event(
        occurred=now("UTC"),
        event="hello",
        resource={
            "prefect.resource.id": "hello",
            "name": "Hello!",
            "related:psychout:name": "Psych!",
        },
        related=[
            {
                "prefect.resource.id": "related-1",
                "prefect.resource.role": "role-1",
                "name": "Related 1",
            },
            {
                "prefect.resource.id": "related-2",
                "prefect.resource.role": "role-1",
                "name": "Related 2",
            },
            {
                "prefect.resource.id": "related-3",
                "prefect.resource.role": "role-2",
                "name": "Related 3",
            },
        ],
        id=uuid4(),
    )


def test_finding_resource_label_top_level(example_event: Event):
    assert example_event.find_resource_label("name") == "Hello!"


def test_finding_resource_label_first_related(example_event: Event):
    assert example_event.find_resource_label("related:role-1:name") == "Related 1"


def test_finding_resource_label_other_related(example_event: Event):
    assert example_event.find_resource_label("related:role-2:name") == "Related 3"


def test_finding_resource_label_fallsback_to_resource(example_event: Event):
    assert example_event.find_resource_label("related:psychout:name") == "Psych!"


def test_finding_resource_in_role(example_event: Event):
    assert example_event.resource_in_role["role-1"].id == "related-1"
    assert example_event.resource_in_role["role-2"].id == "related-3"

    with pytest.raises(KeyError):
        assert example_event.resource_in_role["role-3"] is None


def test_finding_resources_in_role(example_event: Event):
    assert [r.id for r in example_event.resources_in_role["role-1"]] == [
        "related-1",
        "related-2",
    ]
    assert [r.id for r in example_event.resources_in_role["role-2"]] == ["related-3"]
    assert example_event.resources_in_role["role-3"] == []


def test_event_name_length(example_event: Event):
    with pytest.raises(ValidationError, match="Event name must be at most"):
        Event(event="x" * 1025, **example_event.model_dump(exclude={"event"}))
