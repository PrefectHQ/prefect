from typing import Any, Dict, Iterable, List, Tuple, cast
from uuid import UUID, uuid4

import pendulum
from pydantic import Field, root_validator, validator

from prefect.server.utilities.schemas import DateTimeTZ, PrefectBaseModel

# These are defined by Prefect Cloud
MAXIMUM_LABELS_PER_RESOURCE = 500
MAXIMUM_RELATED_RESOURCES = 500


class Labelled(PrefectBaseModel):
    """An object defined by string labels and values"""

    __root__: Dict[str, str]

    def keys(self) -> Iterable[str]:
        return self.__root__.keys()

    def items(self) -> Iterable[Tuple[str, str]]:
        return self.__root__.items()

    def __getitem__(self, label: str) -> str:
        return self.__root__[label]


class Resource(Labelled):
    """An observable business object of interest to the user"""

    @root_validator(pre=True)
    def enforce_maximum_labels(cls, values: Dict[str, Any]):
        labels = values.get("__root__")
        if not isinstance(labels, dict):
            return values

        if len(labels) > MAXIMUM_LABELS_PER_RESOURCE:
            raise ValueError(
                "The maximum number of labels per resource "
                f"is {MAXIMUM_LABELS_PER_RESOURCE}"
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
        default_factory=pendulum.now,
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
        default_factory=uuid4,
        description="The client-provided identifier of this event",
    )

    @validator("related")
    def enforce_maximum_related_resources(cls, value: List[RelatedResource]):
        if len(value) > MAXIMUM_RELATED_RESOURCES:
            raise ValueError(
                "The maximum number of related resources "
                f"is {MAXIMUM_RELATED_RESOURCES}"
            )

        return value
