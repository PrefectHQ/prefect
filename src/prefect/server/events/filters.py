import sys
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple, cast
from uuid import UUID

import pendulum
import sqlalchemy as sa
from pydantic import Field, PrivateAttr
from pydantic_extra_types.pendulum_dt import DateTime
from sqlalchemy.sql import Select

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.server.database import orm_models
from prefect.server.schemas.filters import (
    PrefectFilterBaseModel,
    PrefectOperatorFilterBaseModel,
)
from prefect.server.utilities.database import json_extract
from prefect.utilities.collections import AutoEnum

from .schemas.events import Event, Resource, ResourceSpecification

if TYPE_CHECKING:
    from sqlalchemy.sql.expression import ColumnElement, ColumnExpressionArgument


class AutomationFilterCreated(PrefectFilterBaseModel):
    """Filter by `Automation.created`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description="Only include automations created before this datetime",
    )

    def _get_filter_list(self) -> list:
        filters = []
        if self.before_ is not None:
            filters.append(orm_models.Automation.created <= self.before_)
        return filters


class AutomationFilterName(PrefectFilterBaseModel):
    """Filter by `Automation.created`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="Only include automations with names that match any of these strings",
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm_models.Automation.name.in_(self.any_))
        return filters


class AutomationFilter(PrefectOperatorFilterBaseModel):
    name: Optional[AutomationFilterName] = Field(
        default=None, description="Filter criteria for `Automation.name`"
    )
    created: Optional[AutomationFilterCreated] = Field(
        default=None, description="Filter criteria for `Automation.created`"
    )

    def _get_filter_list(self) -> List:
        filters = []

        if self.name is not None:
            filters.append(self.name.as_sql_filter())
        if self.created is not None:
            filters.append(self.created.as_sql_filter())

        return filters


class EventDataFilter(PrefectBaseModel, extra="forbid"):
    """A base class for filtering event data."""

    _top_level_filter: Optional["EventFilter"] = PrivateAttr(None)

    def get_filters(self) -> List["EventDataFilter"]:
        filters: List[EventDataFilter] = [
            filter
            for filter in [
                getattr(self, name) for name, field in self.model_fields.items()
            ]
            if isinstance(filter, EventDataFilter)
        ]
        for filter in filters:
            filter._top_level_filter = self._top_level_filter
        return filters

    def includes(self, event: Event) -> bool:
        """Does the given event match the criteria of this filter?"""
        return all(filter.includes(event) for filter in self.get_filters())

    def excludes(self, event: Event) -> bool:
        """Would the given filter exclude this event?"""
        return not self.includes(event)

    def build_where_clauses(self) -> Sequence["ColumnExpressionArgument[bool]"]:
        """Convert the criteria to a WHERE clause."""
        clauses: List["ColumnExpressionArgument[bool]"] = []
        for filter in self.get_filters():
            clauses.extend(filter.build_where_clauses())
        return clauses


class EventOccurredFilter(EventDataFilter):
    since: DateTime = Field(
        default_factory=lambda: cast(
            DateTime,
            pendulum.now("UTC").start_of("day").subtract(days=180),
        ),
        description="Only include events after this time (inclusive)",
    )
    until: DateTime = Field(
        default_factory=lambda: cast(DateTime, pendulum.now("UTC")),
        description="Only include events prior to this time (inclusive)",
    )

    def clamp(self, max_duration: timedelta):
        """Limit how far the query can look back based on the given duration"""
        earliest = pendulum.now("UTC") - max_duration
        self.since = max(earliest, cast(pendulum.DateTime, self.since))

    def includes(self, event: Event) -> bool:
        return self.since <= event.occurred <= self.until

    def build_where_clauses(self) -> Sequence["ColumnExpressionArgument[bool]"]:
        filters: List["ColumnExpressionArgument[bool]"] = []

        filters.append(orm_models.Event.occurred >= self.since)
        filters.append(orm_models.Event.occurred <= self.until)

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

    def build_where_clauses(self) -> Sequence["ColumnExpressionArgument[bool]"]:
        filters: List["ColumnExpressionArgument[bool]"] = []

        if self.prefix:
            filters.append(
                sa.or_(
                    *[
                        orm_models.Event.event.startswith(prefix)
                        for prefix in self.prefix
                    ]
                )
            )

        if self.exclude_prefix:
            filters.append(
                sa.and_(
                    *[
                        sa.not_(orm_models.Event.event.startswith(prefix))
                        for prefix in self.exclude_prefix
                    ]
                )
            )

        if self.name:
            filters.append(orm_models.Event.event.in_(self.name))

        if self.exclude_name:
            filters.append(orm_models.Event.event.not_in(self.exclude_name))

        return filters


@dataclass
class LabelSet:
    simple: List[str] = field(default_factory=list)
    prefixes: List[str] = field(default_factory=list)


@dataclass
class LabelOperations:
    values: List[str]
    positive: LabelSet = field(default_factory=LabelSet)
    negative: LabelSet = field(default_factory=LabelSet)

    def __post_init__(self):
        for value in self.values:
            label_set = self.positive
            if value.startswith("!"):
                label_set = self.negative
                value = value[1:]

            if value.endswith("*"):
                label_set.prefixes.append(value.rstrip("*"))
            else:
                label_set.simple.append(value)


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

    def build_where_clauses(self) -> Sequence["ColumnExpressionArgument[bool]"]:
        filters: List["ColumnExpressionArgument[bool]"] = []

        # If we're doing an exact or prefix search on resource_id, this is efficient
        # enough to do on the events table without going to the event_resources table

        if self.id:
            filters.append(orm_models.Event.resource_id.in_(self.id))

        if self.id_prefix:
            filters.append(
                sa.or_(
                    *[
                        orm_models.Event.resource_id.startswith(prefix)
                        for prefix in self.id_prefix
                    ]
                )
            )

        if self.labels:
            labels = self.labels.deepcopy()

            # We are explicitly searching for the primary resource here so the
            # resource_role must be ''
            label_filters = [orm_models.EventResource.resource_role == ""]

            # On the event_resources table, resource_id is unpacked
            # into a column, so we should search for it there
            if resource_ids := labels.pop("prefect.resource.id", None):
                label_ops = LabelOperations(resource_ids)

                resource_id_column = orm_models.EventResource.resource_id

                if values := label_ops.positive.simple:
                    label_filters.append(resource_id_column.in_(values))
                if values := label_ops.negative.simple:
                    label_filters.append(resource_id_column.not_in(values))
                for prefix in label_ops.positive.prefixes:
                    label_filters.append(resource_id_column.startswith(prefix))
                for prefix in label_ops.negative.prefixes:
                    label_filters.append(sa.not_(resource_id_column.startswith(prefix)))

            if labels:
                for _, (label, values) in enumerate(labels.items()):
                    label_ops = LabelOperations(values)

                    label_column = json_extract(
                        orm_models.EventResource.resource, label
                    )

                    # With negative labels, the resource _must_ have the label
                    if label_ops.negative.simple or label_ops.negative.prefixes:
                        label_filters.append(label_column.is_not(None))

                    if values := label_ops.positive.simple:
                        label_filters.append(label_column.in_(values))
                    if values := label_ops.negative.simple:
                        label_filters.append(label_column.notin_(values))
                    for prefix in label_ops.positive.prefixes:
                        label_filters.append(label_column.startswith(prefix))
                    for prefix in label_ops.negative.prefixes:
                        label_filters.append(sa.not_(label_column.startswith(prefix)))

            assert self._top_level_filter
            filters.append(
                orm_models.Event.id.in_(
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

    def build_where_clauses(self) -> Sequence["ColumnExpressionArgument[bool]"]:
        filters: List["ColumnExpressionArgument[bool]"] = []

        if self.id:
            filters.append(orm_models.EventResource.resource_id.in_(self.id))

        if self.role:
            filters.append(orm_models.EventResource.resource_role.in_(self.role))

        if self.resources_in_roles:
            filters.append(
                sa.or_(
                    *[
                        sa.and_(
                            orm_models.EventResource.resource_id == resource_id,
                            orm_models.EventResource.resource_role == role,
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
                label_ops = LabelOperations(resource_ids)

                resource_id_column = orm_models.EventResource.resource_id

                if values := label_ops.positive.simple:
                    label_filters.append(resource_id_column.in_(values))
                if values := label_ops.negative.simple:
                    label_filters.append(resource_id_column.notin_(values))
                for prefix in label_ops.positive.prefixes:
                    label_filters.append(resource_id_column.startswith(prefix))
                for prefix in label_ops.negative.prefixes:
                    label_filters.append(sa.not_(resource_id_column.startswith(prefix)))

            if roles := labels.pop("prefect.resource.role", None):
                label_filters.append(orm_models.EventResource.resource_role.in_(roles))

            if labels:
                for _, (label, values) in enumerate(labels.items()):
                    label_ops = LabelOperations(values)

                    label_column = json_extract(
                        orm_models.EventResource.resource, label
                    )

                    if label_ops.negative.simple or label_ops.negative.prefixes:
                        label_filters.append(label_column.is_not(None))

                    if values := label_ops.positive.simple:
                        label_filters.append(label_column.in_(values))
                    if values := label_ops.negative.simple:
                        label_filters.append(label_column.notin_(values))
                    for prefix in label_ops.positive.prefixes:
                        label_filters.append(label_column.startswith(prefix))
                    for prefix in label_ops.negative.prefixes:
                        label_filters.append(sa.not_(label_column.startswith(prefix)))

            filters.append(sa.and_(*label_filters))

        if filters:
            # This filter is explicitly searching for related resources, so if no other
            # role is specified, and we're doing any kind of filtering with this filter,
            # also filter out primary resources (those with an empty role) for any of
            # these queries
            if not self.role:
                filters.append(orm_models.EventResource.resource_role != "")

            assert self._top_level_filter
            filters = [
                orm_models.Event.id.in_(
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

    def build_where_clauses(self) -> Sequence["ColumnExpressionArgument[bool]"]:
        filters: List["ColumnExpressionArgument[bool]"] = []

        if self.id:
            filters.append(orm_models.EventResource.resource_id.in_(self.id))

        if self.id_prefix:
            filters.append(
                sa.or_(
                    *[
                        orm_models.EventResource.resource_id.startswith(prefix)
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
                label_ops = LabelOperations(resource_ids)

                resource_id_column = orm_models.EventResource.resource_id

                if values := label_ops.positive.simple:
                    label_filters.append(resource_id_column.in_(values))
                if values := label_ops.negative.simple:
                    label_filters.append(resource_id_column.notin_(values))
                for prefix in label_ops.positive.prefixes:
                    label_filters.append(resource_id_column.startswith(prefix))
                for prefix in label_ops.negative.prefixes:
                    label_filters.append(sa.not_(resource_id_column.startswith(prefix)))

            if roles := labels.pop("prefect.resource.role", None):
                label_filters.append(orm_models.EventResource.resource_role.in_(roles))

            if labels:
                for _, (label, values) in enumerate(labels.items()):
                    label_ops = LabelOperations(values)

                    label_column = json_extract(
                        orm_models.EventResource.resource, label
                    )

                    if label_ops.negative.simple or label_ops.negative.prefixes:
                        label_filters.append(label_column.is_not(None))

                    if values := label_ops.positive.simple:
                        label_filters.append(label_column.in_(values))
                    if values := label_ops.negative.simple:
                        label_filters.append(label_column.notin_(values))
                    for prefix in label_ops.positive.prefixes:
                        label_filters.append(label_column.startswith(prefix))
                    for prefix in label_ops.negative.prefixes:
                        label_filters.append(sa.not_(label_column.startswith(prefix)))

            filters.append(sa.and_(*label_filters))

        if filters:
            assert self._top_level_filter
            filters = [
                orm_models.Event.id.in_(
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

    def build_where_clauses(self) -> Sequence["ColumnExpressionArgument[bool]"]:
        filters: List["ColumnExpressionArgument[bool]"] = []

        if self.id:
            filters.append(orm_models.Event.id.in_(self.id))

        return filters


class EventOrder(AutoEnum):
    ASC = "ASC"
    DESC = "DESC"


class EventFilter(EventDataFilter):
    occurred: EventOccurredFilter = Field(
        default_factory=lambda: EventOccurredFilter(),
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
        default_factory=lambda: EventIDFilter(),
        description="Filter criteria for the events' ID",
    )

    order: EventOrder = Field(
        EventOrder.DESC,
        description="The order to return filtered events",
    )

    def build_where_clauses(self) -> Sequence["ColumnExpressionArgument[bool]"]:
        self._top_level_filter = self
        return super().build_where_clauses()

    def _scoped_event_resources(self) -> Select:
        """Returns an event_resources query that is scoped to this filter's scope by occurred."""
        query = sa.select(orm_models.EventResource.event_id).where(
            orm_models.EventResource.occurred >= self.occurred.since,
            orm_models.EventResource.occurred <= self.occurred.until,
        )
        return query

    @property
    def logical_limit(self) -> int:
        """The logical limit for this query, which is a maximum number of rows that it
        _could_ return (regardless of what the caller has requested).  May be used as
        an optimization for DB queries"""
        if self.id and self.id.id:
            # If we're asking for a specific set of IDs, the most we could get back is
            # that number of rows
            return len(self.id.id)

        return sys.maxsize
