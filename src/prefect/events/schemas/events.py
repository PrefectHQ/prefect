import copy
from collections import defaultdict
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)
from uuid import UUID, uuid4

from pydantic import (
    AfterValidator,
    ConfigDict,
    Field,
    RootModel,
    model_validator,
)
from typing_extensions import Annotated, Self

import prefect.types._datetime
from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_EVENTS_MAXIMUM_LABELS_PER_RESOURCE,
)

from .labelling import Labelled

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)


class Resource(Labelled):
    """An observable business object of interest to the user"""

    @model_validator(mode="after")
    def enforce_maximum_labels(self) -> Self:
        if len(self.root) > PREFECT_EVENTS_MAXIMUM_LABELS_PER_RESOURCE.value():
            raise ValueError(
                "The maximum number of labels per resource "
                f"is {PREFECT_EVENTS_MAXIMUM_LABELS_PER_RESOURCE.value()}"
            )

        return self

    @model_validator(mode="after")
    def requires_resource_id(self) -> Self:
        if "prefect.resource.id" not in self.root:
            raise ValueError("Resources must include the prefect.resource.id label")
        if not self.root["prefect.resource.id"]:
            raise ValueError("The prefect.resource.id label must be non-empty")

        return self

    @property
    def id(self) -> str:
        return self["prefect.resource.id"]

    @property
    def name(self) -> Optional[str]:
        return self.get("prefect.resource.name")

    def prefect_object_id(self, kind: str) -> UUID:
        """Extracts the UUID from an event's resource ID if it's the expected kind
        of prefect resource"""
        prefix = f"{kind}." if not kind.endswith(".") else kind

        if not self.id.startswith(prefix):
            raise ValueError(f"Resource ID {self.id} does not start with {prefix}")

        return UUID(self.id[len(prefix) :])


class RelatedResource(Resource):
    """A Resource with a specific role in an Event"""

    @model_validator(mode="after")
    def requires_resource_role(self) -> Self:
        if "prefect.resource.role" not in self.root:
            raise ValueError(
                "Related Resources must include the prefect.resource.role label"
            )
        if not self.root["prefect.resource.role"]:
            raise ValueError("The prefect.resource.role label must be non-empty")

        return self

    @property
    def role(self) -> str:
        return self["prefect.resource.role"]


def _validate_related_resources(value) -> List:
    from prefect.settings import PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES

    if len(value) > PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value():
        raise ValueError(
            "The maximum number of related resources "
            f"is {PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value()}"
        )
    return value


class Event(PrefectBaseModel):
    """The client-side view of an event that has happened to a Resource"""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    occurred: prefect.types._datetime.DateTime = Field(
        default_factory=lambda: prefect.types._datetime.now("UTC"),
        description="When the event happened from the sender's perspective",
    )
    event: str = Field(description="The name of the event that happened")
    resource: Resource = Field(
        description="The primary Resource this event concerns",
    )
    related: Annotated[
        List[RelatedResource],
        AfterValidator(_validate_related_resources),
    ] = Field(
        default_factory=list,
        description="A list of additional Resources involved in this event",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="An open-ended set of data describing what happened",
    )
    id: UUID = Field(
        default_factory=uuid4,
        description="The client-provided identifier of this event",
    )
    follows: Optional[UUID] = Field(
        default=None,
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


class ReceivedEvent(Event):
    """The server-side view of an event that has happened to a Resource after it has
    been received by the server"""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    received: prefect.types._datetime.DateTime = Field(
        ...,
        description="When the event was received by Prefect Cloud",
    )


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


class ResourceSpecification(RootModel[Dict[str, Union[str, List[str]]]]):
    def matches_every_resource(self) -> bool:
        return len(self.root) == 0

    def matches_every_resource_of_kind(self, prefix: str) -> bool:
        if self.matches_every_resource():
            return True
        if len(self.root) == 1:
            resource_id = self.root.get("prefect.resource.id")
            if resource_id:
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
            for label, value in self.root.items()
        ]

    def __contains__(self, key: str) -> bool:
        return key in self.root

    def __getitem__(self, key: str) -> List[str]:
        value = self.root[key]
        if not value:
            return []
        if not isinstance(value, list):
            value = [value]
        return value

    def pop(
        self, key: str, default: Optional[Union[str, List[str]]] = None
    ) -> Optional[List[str]]:
        value = self.root.pop(key, default)
        if not value:
            return []
        if not isinstance(value, list):
            value = [value]
        return value

    def get(
        self, key: str, default: Optional[Union[str, List[str]]] = None
    ) -> Optional[List[str]]:
        value = self.root.get(key, default)
        if not value:
            return []
        if not isinstance(value, list):
            value = [value]
        return value

    def __len__(self) -> int:
        return len(self.root)

    def deepcopy(self) -> "ResourceSpecification":
        return ResourceSpecification(root=copy.deepcopy(self.root))
