from typing import Any, Dict, Iterable, List, Optional, Tuple, cast
from uuid import UUID

from pydantic import Field, root_validator

from prefect.orion.utilities.schemas import DateTimeTZ, PrefectBaseModel


class Resource(PrefectBaseModel):
    """An observable business object of interest to the user"""

    __root__: Dict[str, str]

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

    def labels(self) -> Iterable[str]:
        return self.__root__.keys()

    def items(self) -> Iterable[Tuple[str, str]]:
        return self.__root__.items()

    @property
    def id(self) -> str:
        return self["prefect.resource.id"]

    def __getitem__(self, label: str) -> str:
        return self.__root__[label]

    def get(self, label: str, default: Optional[str] = None) -> Optional[str]:
        return self.__root__.get(label, default)


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
