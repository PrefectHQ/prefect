import copy
from collections import defaultdict
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)
from uuid import UUID

import pendulum

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import AnyHttpUrl, Field, root_validator, validator
else:
    from pydantic import AnyHttpUrl, Field, root_validator, validator

from prefect.logging import get_logger
from prefect.server.events.schemas.labelling import Labelled
from prefect.server.utilities.schemas import DateTimeTZ, PrefectBaseModel
from prefect.settings import (
    PREFECT_EVENTS_MAXIMUM_LABELS_PER_RESOURCE,
    PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES,
)

logger = get_logger(__name__)


class Resource(Labelled):
    """An observable business object of interest to the user"""

    @root_validator(pre=True)
    def enforce_maximum_labels(cls, values: Dict[str, Any]):
        labels = values.get("__root__")
        if not isinstance(labels, dict):
            return values

        if len(labels) > PREFECT_EVENTS_MAXIMUM_LABELS_PER_RESOURCE.value():
            raise ValueError(
                "The maximum number of labels per resource "
                f"is {PREFECT_EVENTS_MAXIMUM_LABELS_PER_RESOURCE.value()}"
            )

        return values

    @root_validator(pre=True)
    def requires_resource_id(cls, values: Dict[str, Any]):
        labels = values.get("__root__")
        if not isinstance(labels, dict):
            return values

        labels = cast(Dict[str, str], labels)

        if "prefect.resource.id" not in labels:
            raise ValueError("Resources must include the prefect.resource.id label")
        if not labels["prefect.resource.id"]:
            raise ValueError("The prefect.resource.id label must be non-empty")

        return values

    @property
    def id(self) -> str:
        return self["prefect.resource.id"]

    @property
    def name(self) -> Optional[str]:
        return self.get("prefect.resource.name")


class RelatedResource(Resource):
    """A Resource with a specific role in an Event"""

    @root_validator(pre=True)
    def requires_resource_role(cls, values: Dict[str, Any]):
        labels = values.get("__root__")
        if not isinstance(labels, dict):
            return values

        labels = cast(Dict[str, str], labels)

        if "prefect.resource.role" not in labels:
            raise ValueError(
                "Related Resources must include the prefect.resource.role label"
            )
        if not labels["prefect.resource.role"]:
            raise ValueError("The prefect.resource.role label must be non-empty")

        return values

    @property
    def role(self) -> str:
        return self["prefect.resource.role"]


class Event(PrefectBaseModel):
    """The client-side view of an event that has happened to a Resource"""

    occurred: DateTimeTZ = Field(
        description="When the event happened from the sender's perspective",
    )
    event: str = Field(
        description="The name of the event that happened",
    )
    resource: Resource = Field(
        description="The primary Resource this event concerns",
    )
    related: List[RelatedResource] = Field(
        default_factory=list,
        description="A list of additional Resources involved in this event",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="An open-ended set of data describing what happened",
    )
    id: UUID = Field(
        description="The client-provided identifier of this event",
    )
    follows: Optional[UUID] = Field(
        None,
        description=(
            "The ID of an event that is known to have occurred prior to this one. "
            "If set, this may be used to establish a more precise ordering of causally-"
            "related events when they occur close enough together in time that the "
            "system may receive them out-of-order."
        ),
    )

    @property
    def involved_resources(self) -> Sequence[Resource]:
        return [self.resource] + list(self.related)

    @property
    def resource_in_role(self) -> Mapping[str, RelatedResource]:
        """Returns a mapping of roles to the first related resource in that role"""
        return {related.role: related for related in reversed(self.related)}

    @property
    def resources_in_role(self) -> Mapping[str, Sequence[RelatedResource]]:
        """Returns a mapping of roles to related resources in that role"""
        resources: Dict[str, List[RelatedResource]] = defaultdict(list)
        for related in self.related:
            resources[related.role].append(related)
        return resources

    @validator("related")
    def enforce_maximum_related_resources(cls, value: List[RelatedResource]):
        if len(value) > PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value():
            raise ValueError(
                "The maximum number of related resources "
                f"is {PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value()}"
            )

        return value

    def receive(self, received: Optional[pendulum.DateTime] = None) -> "ReceivedEvent":
        kwargs = self.dict()
        if received is not None:
            kwargs["received"] = received
        return ReceivedEvent(**kwargs)

    def find_resource_label(self, label: str) -> Optional[str]:
        """Finds the value of the given label in this event's resource or one of its
        related resources.  If the label starts with `related:<role>:`, search for the
        first matching label in a related resource with that role."""
        directive, _, related_label = label.rpartition(":")
        directive, _, role = directive.partition(":")
        if directive == "related":
            for related in self.related:
                if related.role == role:
                    return related.get(related_label)
        return self.resource.get(label)


class ReceivedEvent(Event, extra="ignore", orm_mode=True):
    """The server-side view of an event that has happened to a Resource after it has
    been received by the server"""

    received: DateTimeTZ = Field(
        default_factory=lambda: pendulum.now("UTC"),
        description="When the event was received by Prefect Cloud",
    )

    def as_database_row(self) -> Dict[str, Any]:
        row = self.dict()
        row["resource_id"] = self.resource.id
        row["recorded"] = pendulum.now("UTC")
        row["related_resource_ids"] = [related.id for related in self.related]
        return row

    def as_database_resource_rows(self) -> List[Dict[str, Any]]:
        def without_id_and_role(resource: Resource) -> Dict[str, str]:
            d: Dict[str, str] = resource.dict()["__root__"]
            d.pop("prefect.resource.id", None)
            d.pop("prefect.resource.role", None)
            return d

        return [
            {
                "occurred": self.occurred,
                "resource_id": resource.id,
                "resource_role": (
                    resource.role if isinstance(resource, RelatedResource) else ""
                ),
                "resource": without_id_and_role(resource),
                "event_id": self.id,
            }
            for resource in [self.resource, *self.related]
        ]


def matches(expected: str, value: Optional[str]) -> bool:
    """Returns true if the given value matches the expected string, which may
    include a a negation prefix ("!this-value") or a wildcard suffix
    ("any-value-starting-with*")"""
    if value is None:
        return False

    positive = True
    if expected.startswith("!"):
        expected = expected[1:]
        positive = False

    if expected.endswith("*"):
        match = value.startswith(expected[:-1])
    else:
        match = value == expected

    return match if positive else not match


class ResourceSpecification(PrefectBaseModel):
    """A specification that may match zero, one, or many resources, used to target or
    select a set of resources in a query or automation.  A resource must match at least
    one value of all of the provided labels"""

    __root__: Dict[str, Union[str, List[str]]]

    def matches_every_resource(self) -> bool:
        return len(self) == 0

    def matches_every_resource_of_kind(self, prefix: str) -> bool:
        if self.matches_every_resource():
            return True

        if len(self.__root__) == 1:
            if resource_id := self.__root__.get("prefect.resource.id"):
                values = [resource_id] if isinstance(resource_id, str) else resource_id
                return any(value == f"{prefix}.*" for value in values)

        return False

    def includes(self, candidates: Iterable[Resource]) -> bool:
        if self.matches_every_resource():
            return True

        for candidate in candidates:
            if self.matches(candidate):
                return True

        return False

    def matches(self, resource: Resource) -> bool:
        for label, expected in self.items():
            value = resource.get(label)
            if not any(matches(candidate, value) for candidate in expected):
                return False
        return True

    def items(self) -> Iterable[Tuple[str, List[str]]]:
        return [
            (label, [value] if isinstance(value, str) else value)
            for label, value in self.__root__.items()
        ]

    def __contains__(self, key: str) -> bool:
        return self.__root__.__contains__(key)

    def __getitem__(self, key: str) -> List[str]:
        value = self.__root__[key]
        if not value:
            return []
        if not isinstance(value, list):
            value = [value]
        return value

    def pop(
        self, key: str, default: Optional[Union[str, List[str]]] = None
    ) -> Optional[List[str]]:
        value = self.__root__.pop(key, default)
        if not value:
            return []
        if not isinstance(value, list):
            value = [value]
        return value

    def get(
        self, key: str, default: Optional[Union[str, List[str]]] = None
    ) -> Optional[List[str]]:
        value = self.__root__.get(key, default)
        if not value:
            return []
        if not isinstance(value, list):
            value = [value]
        return value

    def __len__(self) -> int:
        return len(self.__root__)

    def deepcopy(self) -> "ResourceSpecification":
        return ResourceSpecification.parse_obj(copy.deepcopy(self.__root__))


class EventPage(PrefectBaseModel):
    """A single page of events returned from the API, with an optional link to the
    next page of results"""

    events: List[ReceivedEvent] = Field(
        ..., description="The Events matching the query"
    )
    total: int = Field(..., description="The total number of matching Events")
    next_page: Optional[AnyHttpUrl] = Field(
        ..., description="The URL for the next page of results, if there are more"
    )


class EventCount(PrefectBaseModel):
    """The count of events with the given filter value"""

    value: str = Field(..., description="The value to use for filtering")
    label: str = Field(..., description="The value to display for this count")
    count: int = Field(..., description="The count of matching events")
    start_time: DateTimeTZ = Field(
        ..., description="The start time of this group of events"
    )
    end_time: DateTimeTZ = Field(
        ..., description="The end time of this group of events"
    )
