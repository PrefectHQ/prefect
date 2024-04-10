from typing import List, Optional, Sequence, Tuple, cast
from uuid import UUID

import pendulum
import sqlalchemy as sa
from sqlalchemy import ColumnElement, ColumnExpressionArgument

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.schemas.bases import PrefectBaseModel
from prefect._internal.schemas.fields import DateTimeTZ
from prefect.server.database.interface import PrefectDBInterface
from prefect.utilities.collections import AutoEnum

from .schemas.events import Event, Resource, ResourceSpecification

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field, PrivateAttr
else:
    from pydantic import Field, PrivateAttr


class EventDataFilter(PrefectBaseModel, extra="forbid"):
    """A base class for filtering event data."""

    _top_level_filter: "EventFilter | None" = PrivateAttr(None)

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

    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence[ColumnExpressionArgument[bool]]:
        """Convert the criteria to a WHERE clause."""
        clauses: List[ColumnExpressionArgument[bool]] = []
        for filter in self.get_filters():
            clauses.extend(filter.build_where_clauses(db))
        return clauses


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

    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence[ColumnExpressionArgument[bool]]:
        filters: List[ColumnExpressionArgument[bool]] = []

        filters.append(db.Event.occurred >= self.since)
        filters.append(db.Event.occurred <= self.until)

        return filters


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

    def build_postgres_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence[ColumnExpressionArgument[bool]]:
        filters: List[ColumnExpressionArgument[bool]] = []

        if self.prefix:
            filters.append(
                sa.or_(*[db.Event.event.startswith(prefix) for prefix in self.prefix])
            )

        if self.exclude_prefix:
            filters.append(
                sa.and_(
                    *[
                        sa.not_(db.Event.event.startswith(prefix))
                        for prefix in self.exclude_prefix
                    ]
                )
            )

        if self.name:
            filters.append(db.Event.event.in_(self.name))

        if self.exclude_name:
            filters.append(db.Event.event.not_in(self.exclude_name))

        return filters


def _partition_by_wildcards(names: List[str]) -> Tuple[List[str], List[str]]:
    """Partition a list of names into those with wildcards and those without"""
    without_wildcards, with_wildcards = [], []
    for name in names:
        if name.endswith("*"):
            with_wildcards.append(name.strip("*"))
        else:
            without_wildcards.append(name)
    return without_wildcards, with_wildcards


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
    distinct: bool = Field(
        False,
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

    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence[ColumnExpressionArgument[bool]]:
        filters: List[ColumnExpressionArgument[bool]] = []

        # If we're doing an exact or prefix search on resource_id, this is efficient
        # enough to do on the events table without going to the event_resources table

        if self.id:
            filters.append(db.Event.resource_id.in_(self.id))

        if self.id_prefix:
            filters.append(
                sa.or_(
                    *[
                        db.Event.resource_id.startswith(prefix)
                        for prefix in self.id_prefix
                    ]
                )
            )

        if self.labels:
            labels = self.labels.deepcopy()

            # We are explicitly searching for the primary resource here so the
            # resource_role must be ''
            label_filters = [db.EventResource.resource_role == ""]

            # On the event_resources table, resource_id is unpacked
            # into a column, so we should search for it there
            if resource_ids := labels.pop("prefect.resource.id", None):
                simple, prefixes = _partition_by_wildcards(resource_ids)
                if simple:
                    label_filters.append(db.EventResource.resource_id.in_(simple))
                for prefix in prefixes:
                    label_filters.append(
                        db.EventResource.resource_id.startswith(prefix)
                    )

            if labels:
                for _, (label, values) in enumerate(labels.items()):
                    simple, prefixes = _partition_by_wildcards(values)
                    if simple:
                        label_filters.append(
                            db.EventResource.resource.op("->>")(label).in_(simple)
                        )
                    for prefix in prefixes:
                        label_filters.append(
                            db.EventResource.resource.op("->>")(label).startswith(
                                prefix
                            )
                        )

            assert self._top_level_filter
            filters.append(
                db.Event.id.in_(
                    self._top_level_filter._scoped_event_resources().where(
                        *label_filters
                    )
                )
            )

        return filters


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

    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence[ColumnExpressionArgument[bool]]:
        filters: List[ColumnExpressionArgument[bool]] = []

        if self.id:
            filters.append(db.EventResource.resource_id.in_(self.id))

        if self.role:
            filters.append(db.EventResource.resource_role.in_(self.role))

        if self.resources_in_roles:
            filters.append(
                sa.or_(
                    *[
                        sa.and_(
                            db.EventResource.resource_id == resource_id,
                            db.EventResource.resource_role == role,
                        )
                        for resource_id, role in self.resources_in_roles
                    ]
                )
            )

        if self.labels:
            label_filters: List[ColumnElement[bool]] = []
            labels = self.labels.deepcopy()

            # On the event_resources table, resource_id and resource_role are unpacked
            # into columns, so we should search there for them
            if resource_ids := labels.pop("prefect.resource.id", None):
                simple, prefixes = _partition_by_wildcards(resource_ids)
                if simple:
                    label_filters.append(db.EventResource.resource_id.in_(simple))
                for prefix in prefixes:
                    label_filters.append(
                        db.EventResource.resource_id.startswith(prefix)
                    )

            if roles := labels.pop("prefect.resource.role", None):
                label_filters.append(db.EventResource.resource_role.in_(roles))

            if labels:
                for _, (label, values) in enumerate(labels.items()):
                    simple, prefixes = _partition_by_wildcards(values)
                    if simple:
                        label_filters.append(
                            db.EventResource.resource.op("->>")(label).in_(simple)
                        )
                    for prefix in prefixes:
                        label_filters.append(
                            db.EventResource.resource.op("->>")(label).startswith(
                                prefix
                            )
                        )

            filters.append(sa.and_(*label_filters))

        if filters:
            # This filter is explicitly searching for related resources, so if no other
            # role is specified, and we're doing any kind of filtering with this filter,
            # also filter out primary resources (those with an empty role) for any of
            # these queries
            if not self.role:
                filters.append(db.EventResource.resource_role != "")

            assert self._top_level_filter
            filters = [
                db.Event.id.in_(
                    self._top_level_filter._scoped_event_resources().where(*filters)
                )
            ]

        return filters


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

    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence[ColumnExpressionArgument[bool]]:
        filters: List[ColumnExpressionArgument[bool]] = []

        if self.id:
            filters.append(db.EventResource.resource_id.in_(self.id))

        if self.id_prefix:
            filters.append(
                sa.or_(
                    *[
                        db.EventResource.resource_id.startswith(prefix)
                        for prefix in self.id_prefix
                    ]
                )
            )

        if self.labels:
            label_filters: List[ColumnElement[bool]] = []
            labels = self.labels.deepcopy()

            # On the event_resources table, resource_id and resource_role are unpacked
            # into columns, so we should search there for them
            if resource_ids := labels.pop("prefect.resource.id", None):
                simple, prefixes = _partition_by_wildcards(resource_ids)
                if simple:
                    label_filters.append(db.EventResource.resource_id.in_(simple))
                for prefix in prefixes:
                    label_filters.append(
                        db.EventResource.resource_id.startswith(prefix)
                    )

            if roles := labels.pop("prefect.resource.role", None):
                label_filters.append(db.EventResource.resource_role.in_(roles))

            if labels:
                for _, (label, values) in enumerate(labels.items()):
                    simple, prefixes = _partition_by_wildcards(values)
                    if simple:
                        label_filters.append(
                            db.EventResource.resource.op("->>")(label).in_(simple)
                        )
                    for prefix in prefixes:
                        label_filters.append(
                            db.EventResource.resource.op("->>")(label).startswith(
                                prefix
                            )
                        )

            filters.append(sa.and_(*label_filters))

        if filters:
            assert self._top_level_filter
            filters = [
                db.Event.id.in_(
                    self._top_level_filter._scoped_event_resources().where(*filters)
                )
            ]

        return filters


class EventIDFilter(EventDataFilter):
    id: Optional[List[UUID]] = Field(
        None, description="Only include events with one of these IDs"
    )

    def includes(self, event: Event) -> bool:
        if self.id:
            if not any(event.id == id for id in self.id):
                return False

        return True

    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence[ColumnExpressionArgument[bool]]:
        filters: List[ColumnExpressionArgument[bool]] = []

        if self.id:
            filters.append(db.Event.id.in_(self.id))

        return filters


class EventOrder(AutoEnum):
    ASC = "ASC"
    DESC = "DESC"


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

    order: EventOrder = Field(
        EventOrder.DESC,
        description="The order to return filtered events",
    )

    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence[ColumnExpressionArgument[bool]]:
        self._top_level_filter = self
        return super().build_where_clauses(db)
