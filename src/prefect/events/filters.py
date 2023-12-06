from typing import List, Optional, Tuple, cast
from uuid import UUID

import pendulum

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.events.schemas import Event, Resource, ResourceSpecification
from prefect.server.utilities.schemas import DateTimeTZ, PrefectBaseModel

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field
else:
    from pydantic import Field


class EventDataFilter(PrefectBaseModel):
    """A base class for filtering event data."""

    class Config:
        extra = "forbid"

    def get_filters(self) -> List["EventDataFilter"]:
        return [
            filter
            for filter in [
                getattr(self, name)
                for name, field in self.__fields__.items()
                if issubclass(field.type_, EventDataFilter)
            ]
            if filter
        ]

    def includes(self, event: Event) -> bool:
        """Does the given event match the criteria of this filter?"""
        return all(filter.includes(event) for filter in self.get_filters())

    def excludes(self, event: Event) -> bool:
        """Would the given filter exclude this event?"""
        return not self.includes(event)


class EventOccurredFilter(EventDataFilter):
    since: DateTimeTZ = Field(
        default_factory=lambda: cast(
            DateTimeTZ,
            pendulum.now("UTC").start_of("day").subtract(days=180),
        ),
        description="Only include events after this time (inclusive)",
    )
    until: DateTimeTZ = Field(
        default_factory=lambda: cast(DateTimeTZ, pendulum.now("UTC")),
        description="Only include events prior to this time (inclusive)",
    )

    def includes(self, event: Event) -> bool:
        return self.since <= event.occurred <= self.until


class EventNameFilter(EventDataFilter):
    prefix: Optional[List[str]] = Field(
        None, description="Only include events matching one of these prefixes"
    )
    exclude_prefix: Optional[List[str]] = Field(
        None, description="Exclude events matching one of these prefixes"
    )

    name: Optional[List[str]] = Field(
        None, description="Only include events matching one of these names exactly"
    )
    exclude_name: Optional[List[str]] = Field(
        None, description="Exclude events matching one of these names exactly"
    )

    def includes(self, event: Event) -> bool:
        if self.prefix:
            if not any(event.event.startswith(prefix) for prefix in self.prefix):
                return False

        if self.exclude_prefix:
            if any(event.event.startswith(prefix) for prefix in self.exclude_prefix):
                return False

        if self.name:
            if not any(event.event == name for name in self.name):
                return False

        if self.exclude_name:
            if any(event.event == name for name in self.exclude_name):
                return False

        return True


class EventResourceFilter(EventDataFilter):
    id: Optional[List[str]] = Field(
        None, description="Only include events for resources with these IDs"
    )
    id_prefix: Optional[List[str]] = Field(
        None,
        description=(
            "Only include events for resources with IDs starting with these prefixes."
        ),
    )
    labels: Optional[ResourceSpecification] = Field(
        None, description="Only include events for resources with these labels"
    )

    def includes(self, event: Event) -> bool:
        if self.id:
            if not any(event.resource.id == resource_id for resource_id in self.id):
                return False

        if self.id_prefix:
            if not any(
                event.resource.id.startswith(prefix) for prefix in self.id_prefix
            ):
                return False

        if self.labels:
            if not self.labels.matches(event.resource):
                return False

        return True


class EventRelatedFilter(EventDataFilter):
    id: Optional[List[str]] = Field(
        None, description="Only include events for related resources with these IDs"
    )
    role: Optional[List[str]] = Field(
        None, description="Only include events for related resources in these roles"
    )
    resources_in_roles: Optional[List[Tuple[str, str]]] = Field(
        None,
        description=(
            "Only include events with specific related resources in specific roles"
        ),
    )
    labels: Optional[ResourceSpecification] = Field(
        None, description="Only include events for related resources with these labels"
    )


class EventAnyResourceFilter(EventDataFilter):
    id: Optional[List[str]] = Field(
        None, description="Only include events for resources with these IDs"
    )
    id_prefix: Optional[List[str]] = Field(
        None,
        description=(
            "Only include events for resources with IDs starting with these prefixes"
        ),
    )
    labels: Optional[ResourceSpecification] = Field(
        None, description="Only include events for related resources with these labels"
    )

    def includes(self, event: Event) -> bool:
        resources = [event.resource] + event.related
        if not any(self._includes(resource) for resource in resources):
            return False
        return True

    def _includes(self, resource: Resource) -> bool:
        if self.id:
            if not any(resource.id == resource_id for resource_id in self.id):
                return False

        if self.id_prefix:
            if not any(resource.id.startswith(prefix) for prefix in self.id_prefix):
                return False

        if self.labels:
            if not self.labels.matches(resource):
                return False

        return True


class EventIDFilter(EventDataFilter):
    id: Optional[List[UUID]] = Field(
        None, description="Only include events with one of these IDs"
    )

    def includes(self, event: Event) -> bool:
        if self.id:
            if not any(event.id == id for id in self.id):
                return False

        return True


class EventFilter(EventDataFilter):
    occurred: EventOccurredFilter = Field(
        default_factory=EventOccurredFilter,
        description="Filter criteria for when the events occurred",
    )
    event: Optional[EventNameFilter] = Field(
        None,
        description="Filter criteria for the event name",
    )
    any_resource: Optional[EventAnyResourceFilter] = Field(
        None, description="Filter criteria for any resource involved in the event"
    )
    resource: Optional[EventResourceFilter] = Field(
        None, description="Filter criteria for the resource of the event"
    )
    related: Optional[EventRelatedFilter] = Field(
        None, description="Filter criteria for the related resources of the event"
    )
    id: EventIDFilter = Field(
        default_factory=EventIDFilter,
        description="Filter criteria for the events' ID",
    )
