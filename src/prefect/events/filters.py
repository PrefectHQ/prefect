from typing import Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.types import DateTime
from prefect.utilities.collections import AutoEnum

from .schemas.events import Event, Resource, ResourceSpecification


class AutomationFilterCreated(PrefectBaseModel):
    """Filter by `Automation.created`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description="Only include automations created before this datetime",
    )


class AutomationFilterName(PrefectBaseModel):
    """Filter by `Automation.created`."""

    any_: Optional[list[str]] = Field(
        default=None,
        description="Only include automations with names that match any of these strings",
    )


class AutomationFilter(PrefectBaseModel):
    name: Optional[AutomationFilterName] = Field(
        default=None, description="Filter criteria for `Automation.name`"
    )
    created: Optional[AutomationFilterCreated] = Field(
        default=None, description="Filter criteria for `Automation.created`"
    )


class EventDataFilter(PrefectBaseModel, extra="forbid"):  # type: ignore[call-arg]
    """A base class for filtering event data."""

    def get_filters(self) -> list["EventDataFilter"]:
        filters: list["EventDataFilter"] = [
            filter
            for filter in [getattr(self, name) for name in self.model_fields]
            if isinstance(filter, EventDataFilter)
        ]
        return filters

    def includes(self, event: Event) -> bool:
        """Does the given event match the criteria of this filter?"""
        return all(filter.includes(event) for filter in self.get_filters())

    def excludes(self, event: Event) -> bool:
        """Would the given filter exclude this event?"""
        return not self.includes(event)


class EventOccurredFilter(EventDataFilter):
    since: DateTime = Field(
        default_factory=lambda: DateTime.now("UTC").start_of("day").subtract(days=180),
        description="Only include events after this time (inclusive)",
    )
    until: DateTime = Field(
        default_factory=lambda: DateTime.now("UTC"),
        description="Only include events prior to this time (inclusive)",
    )

    def includes(self, event: Event) -> bool:
        return self.since <= event.occurred <= self.until


class EventNameFilter(EventDataFilter):
    prefix: Optional[list[str]] = Field(
        default=None, description="Only include events matching one of these prefixes"
    )
    exclude_prefix: Optional[list[str]] = Field(
        default=None, description="Exclude events matching one of these prefixes"
    )

    name: Optional[list[str]] = Field(
        default=None,
        description="Only include events matching one of these names exactly",
    )
    exclude_name: Optional[list[str]] = Field(
        default=None, description="Exclude events matching one of these names exactly"
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
    id: Optional[list[str]] = Field(
        default=None, description="Only include events for resources with these IDs"
    )
    id_prefix: Optional[list[str]] = Field(
        default=None,
        description=(
            "Only include events for resources with IDs starting with these prefixes."
        ),
    )
    labels: Optional[ResourceSpecification] = Field(
        default=None, description="Only include events for resources with these labels"
    )
    distinct: bool = Field(
        default=False,
        description="Only include events for distinct resources",
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
    id: Optional[list[str]] = Field(
        default=None,
        description="Only include events for related resources with these IDs",
    )
    role: Optional[list[str]] = Field(
        default=None,
        description="Only include events for related resources in these roles",
    )
    resources_in_roles: Optional[list[tuple[str, str]]] = Field(
        default=None,
        description=(
            "Only include events with specific related resources in specific roles"
        ),
    )
    labels: Optional[ResourceSpecification] = Field(
        default=None,
        description="Only include events for related resources with these labels",
    )


class EventAnyResourceFilter(EventDataFilter):
    id: Optional[list[str]] = Field(
        default=None, description="Only include events for resources with these IDs"
    )
    id_prefix: Optional[list[str]] = Field(
        default=None,
        description=(
            "Only include events for resources with IDs starting with these prefixes"
        ),
    )
    labels: Optional[ResourceSpecification] = Field(
        default=None,
        description="Only include events for related resources with these labels",
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
    id: Optional[list[UUID]] = Field(
        default=None, description="Only include events with one of these IDs"
    )

    def includes(self, event: Event) -> bool:
        if self.id:
            if not any(event.id == id for id in self.id):
                return False

        return True


class EventOrder(AutoEnum):
    ASC = "ASC"
    DESC = "DESC"


class EventFilter(EventDataFilter):
    occurred: EventOccurredFilter = Field(
        default_factory=lambda: EventOccurredFilter(),
        description="Filter criteria for when the events occurred",
    )
    event: Optional[EventNameFilter] = Field(
        default=None,
        description="Filter criteria for the event name",
    )
    any_resource: Optional[EventAnyResourceFilter] = Field(
        default=None,
        description="Filter criteria for any resource involved in the event",
    )
    resource: Optional[EventResourceFilter] = Field(
        default=None,
        description="Filter criteria for the resource of the event",
    )
    related: Optional[EventRelatedFilter] = Field(
        default=None,
        description="Filter criteria for the related resources of the event",
    )
    id: EventIDFilter = Field(
        default_factory=lambda: EventIDFilter(id=[]),
        description="Filter criteria for the events' ID",
    )

    order: EventOrder = Field(
        default=EventOrder.DESC,
        description="The order to return filtered events",
    )
