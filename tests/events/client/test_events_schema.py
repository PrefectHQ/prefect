import json
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from prefect.events import Event, RelatedResource, Resource
from prefect.types import DateTime
from prefect.types._datetime import now


def test_client_events_generate_an_id_by_default():
    event1 = Event(event="hello", resource={"prefect.resource.id": "hello"})
    event2 = Event(event="hello", resource={"prefect.resource.id": "hello"})
    assert isinstance(event1.id, UUID)
    assert isinstance(event2.id, UUID)
    assert event1.id != event2.id


def test_client_events_generate_occurred_by_default(start_of_test: DateTime):
    event = Event(event="hello", resource={"prefect.resource.id": "hello"})
    assert start_of_test <= event.occurred <= now("UTC")


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


def test_json_representation():
    event = Event(
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
        follows=uuid4(),
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
        "follows": str(event.follows),
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


# Tests for naive datetime coercion (issue #21949)


def test_naive_occurred_is_coerced_to_utc():
    """A naive datetime passed to Event.occurred must be treated as UTC, not silently
    dropped by the server's SQL bind layer."""
    naive = datetime(2024, 6, 1, 12, 0, 0)
    assert naive.tzinfo is None

    event = Event(
        occurred=naive,
        event="test.naive",
        resource={"prefect.resource.id": "test"},
    )

    assert event.occurred.tzinfo is not None, "occurred must be tz-aware after coercion"
    assert event.occurred.replace(tzinfo=None) == naive
    # Naive datetimes are assumed to be UTC
    assert event.occurred.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_tz_aware_occurred_is_unchanged():
    """A tz-aware datetime must pass through the validator without modification."""
    aware = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    event = Event(
        occurred=aware,
        event="test.aware",
        resource={"prefect.resource.id": "test"},
    )
    assert event.occurred == aware
    assert event.occurred.tzinfo is not None


def test_non_utc_aware_occurred_is_unchanged():
    """A tz-aware datetime in a non-UTC zone must not be altered."""
    eastern = ZoneInfo("America/New_York")
    aware = datetime(2024, 6, 1, 12, 0, 0, tzinfo=eastern)
    event = Event(
        occurred=aware,
        event="test.aware.eastern",
        resource={"prefect.resource.id": "test"},
    )
    assert event.occurred.tzinfo is not None
    # Offset for America/New_York in summer (EDT) is -4h
    assert event.occurred.utcoffset().total_seconds() == -4 * 3600  # type: ignore[union-attr]


def test_naive_iso_string_occurred_is_coerced_to_utc():
    """A naive ISO-8601 string passed to Event.occurred must also be coerced to UTC.

    On Python >= 3.13 Pydantic parses the string into a bare datetime.datetime
    before validators run, so a mode='before' isinstance check would miss it.
    The mode='after' validator catches it regardless of the input type.
    """
    event = Event(
        occurred="2024-06-01T12:00:00",
        event="test.naive.string",
        resource={"prefect.resource.id": "test"},
    )
    assert event.occurred.tzinfo is not None, (
        "occurred must be tz-aware when constructed from a naive ISO string"
    )
    assert event.occurred.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


@pytest.mark.skipif(
    sys.version_info < (3, 13),
    reason="Naive datetime was only silently accepted on Python >= 3.13",
)
def test_naive_occurred_has_tz_on_py313_plus():
    """Regression test: on Python >= 3.13 DateTime is a bare datetime.datetime, which
    previously allowed naive values to bypass validation entirely (issue #21949)."""
    naive = datetime(2026, 1, 1, 0, 0, 0)
    event = Event(
        occurred=naive,
        event="prefect.regression.21949",
        resource={"prefect.resource.id": "test"},
    )
    assert event.occurred.tzinfo is not None, (
        "Event.occurred must be tz-aware on Python 3.13+ (regression: issue #21949)"
    )
