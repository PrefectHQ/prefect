from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional, Sequence, Union
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from pydantic import Field, PrivateAttr
from sqlalchemy.sql import Select

import prefect.types._datetime
from prefect.server.database import PrefectDBInterface, db_injector
from prefect.server.schemas.filters import (
    PrefectFilterBaseModel,
    PrefectOperatorFilterBaseModel,
)
from prefect.server.utilities.schemas.bases import PrefectBaseModel
from prefect.types import DateTime
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

    def _get_filter_list(
        self, db: PrefectDBInterface
    ) -> Iterable[sa.ColumnElement[bool]]:
        if self.before_ is not None:
            return [db.Automation.created <= self.before_]
        return ()


class AutomationFilterName(PrefectFilterBaseModel):
    """Filter by `Automation.created`."""

    any_: Optional[list[str]] = Field(
        default=None,
        description="Only include automations with names that match any of these strings",
    )

    def _get_filter_list(self, db: PrefectDBInterface) -> list[sa.ColumnElement[bool]]:
        if self.any_ is not None:
            return [db.Automation.name.in_(self.any_)]
        return []


class AutomationFilterTags(PrefectOperatorFilterBaseModel):
    """Filter by `Automation.tags`."""

    all_: Optional[list[str]] = Field(
        default=None,
        examples=[["tag-1", "tag-2"]],
        description="A list of tags. Automations will be returned only if their tags are a superset of the list",
    )
    any_: Optional[list[str]] = Field(
        default=None,
        examples=[["tag-1", "tag-2"]],
        description="A list of tags. Automations will be returned if their tags contain any of the tags in the list",
    )
    is_null_: Optional[bool] = Field(
        default=None, description="If true, only include automations without tags"
    )

    def _get_filter_list(
        self, db: PrefectDBInterface
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        from prefect.server.schemas.filters import _as_array

        filters: list[sa.ColumnElement[bool]] = []
        if self.all_ is not None:
            filters.append(db.Automation.tags.has_all(_as_array(self.all_)))
        if self.any_ is not None:
            filters.append(db.Automation.tags.has_any(_as_array(self.any_)))
        if self.is_null_ is not None:
            filters.append(
                db.Automation.tags == [] if self.is_null_ else db.Automation.tags != []
            )
        return filters


class AutomationFilter(PrefectOperatorFilterBaseModel):
    name: Optional[AutomationFilterName] = Field(
        default=None, description="Filter criteria for `Automation.name`"
    )
    created: Optional[AutomationFilterCreated] = Field(
        default=None, description="Filter criteria for `Automation.created`"
    )
    tags: Optional[AutomationFilterTags] = Field(
        default=None, description="Filter criteria for `Automation.tags`"
    )

    def _get_filter_list(
        self, db: PrefectDBInterface
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.name is not None:
            filters.append(self.name.as_sql_filter())
        if self.created is not None:
            filters.append(self.created.as_sql_filter())
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter())

        return filters


class EventDataFilter(PrefectBaseModel, extra="forbid"):
    """A base class for filtering event data."""

    _top_level_filter: Optional[Select[tuple[UUID]]] = PrivateAttr(None)

    def get_filters(self) -> list["EventDataFilter"]:
        filters: list[EventDataFilter] = []
        for filter in [
            getattr(self, name) for name in self.__class__.model_fields.keys()
        ]:
            # Any embedded list of filters are flattened and thus ANDed together
            subfilters: list[EventDataFilter] = (
                filter if isinstance(filter, list) else [filter]
            )

            for subfilter in subfilters:
                if not isinstance(subfilter, EventDataFilter):
                    continue

                subfilter._top_level_filter = self._top_level_filter
                filters.append(subfilter)

        return filters

    def includes(self, event: Event) -> bool:
        """Does the given event match the criteria of this filter?"""
        return all(filter.includes(event) for filter in self.get_filters())

    def excludes(self, event: Event) -> bool:
        """Would the given filter exclude this event?"""
        return not self.includes(event)

    def build_where_clauses(self) -> Sequence["ColumnExpressionArgument[bool]"]:
        """Convert the criteria to a WHERE clause."""
        clauses: list["ColumnExpressionArgument[bool]"] = []
        for filter in self.get_filters():
            clauses.extend(filter.build_where_clauses())
        return clauses


class EventOccurredFilter(EventDataFilter):
    since: DateTime = Field(
        default_factory=lambda: prefect.types._datetime.start_of_day(
            prefect.types._datetime.now("UTC")
        )
        - timedelta(days=180),
        description="Only include events after this time (inclusive)",
    )
    until: DateTime = Field(
        default_factory=lambda: prefect.types._datetime.now("UTC"),
        description="Only include events prior to this time (inclusive)",
    )

    def clamp(self, max_duration: timedelta) -> None:
        """Limit how far the query can look back based on the given duration"""
        # Using datetime.now() instead of prefect.types._datetime.now() to avoid
        # dropping timezone information which happens if pendulum is used
        earliest = datetime.now(ZoneInfo("UTC")) - max_duration
        self.since = max(earliest, self.since)

    def includes(self, event: Event) -> bool:
        return self.since <= event.occurred <= self.until

    @db_injector
    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence["ColumnExpressionArgument[bool]"]:
        return [
            db.Event.occurred >= self.since,
            db.Event.occurred <= self.until,
        ]


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

    @db_injector
    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence["ColumnExpressionArgument[bool]"]:
        filters: list["ColumnExpressionArgument[bool]"] = []

        if self.prefix:
            filters.append(
                sa.or_(*(db.Event.event.startswith(prefix) for prefix in self.prefix))
            )

        if self.exclude_prefix:
            filters.extend(
                sa.not_(db.Event.event.startswith(prefix))
                for prefix in self.exclude_prefix
            )

        if self.name:
            filters.append(db.Event.event.in_(self.name))

        if self.exclude_name:
            filters.append(db.Event.event.not_in(self.exclude_name))

        return filters


@dataclass
class LabelSet:
    simple: list[str] = field(default_factory=list)
    prefixes: list[str] = field(default_factory=list)


@dataclass
class LabelOperations:
    values: list[str]
    positive: LabelSet = field(default_factory=LabelSet)
    negative: LabelSet = field(default_factory=LabelSet)

    def __post_init__(self) -> None:
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

    @db_injector
    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence["ColumnExpressionArgument[bool]"]:
        filters: list["ColumnExpressionArgument[bool]"] = []

        # If we're doing an exact or prefix search on resource_id, this is efficient
        # enough to do on the events table without going to the event_resources table

        if self.id:
            filters.append(db.Event.resource_id.in_(self.id))

        if self.id_prefix:
            filters.append(
                sa.or_(
                    *(
                        db.Event.resource_id.startswith(prefix)
                        for prefix in self.id_prefix
                    )
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
                label_ops = LabelOperations(resource_ids)

                resource_id_column = db.EventResource.resource_id

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
                    # Empty label value arrays should match nothing
                    if not values:
                        label_filters.append(sa.false())
                        continue

                    label_ops = LabelOperations(values)

                    label_column = db.EventResource.resource[label].astext

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

            assert self._top_level_filter is not None
            filters.append(
                db.Event.id.in_(self._top_level_filter.where(*label_filters))
            )

        return filters


class EventRelatedFilter(EventDataFilter):
    id: Optional[list[str]] = Field(
        None, description="Only include events for related resources with these IDs"
    )
    role: Optional[list[str]] = Field(
        None, description="Only include events for related resources in these roles"
    )
    resources_in_roles: Optional[list[tuple[str, str]]] = Field(
        None,
        description=(
            "Only include events with specific related resources in specific roles"
        ),
    )
    labels: Optional[ResourceSpecification] = Field(
        None, description="Only include events for related resources with these labels"
    )

    @db_injector
    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence["ColumnExpressionArgument[bool]"]:
        filters: list["ColumnExpressionArgument[bool]"] = []

        if self.id:
            filters.append(db.EventResource.resource_id.in_(self.id))

        if self.role:
            filters.append(db.EventResource.resource_role.in_(self.role))

        if self.resources_in_roles:
            filters.append(
                sa.or_(
                    *(
                        sa.and_(
                            db.EventResource.resource_id == resource_id,
                            db.EventResource.resource_role == role,
                        )
                        for resource_id, role in self.resources_in_roles
                    )
                )
            )

        if self.labels:
            label_filters: list[ColumnElement[bool]] = []
            labels = self.labels.deepcopy()

            # On the event_resources table, resource_id and resource_role are unpacked
            # into columns, so we should search there for them
            if resource_ids := labels.pop("prefect.resource.id", None):
                label_ops = LabelOperations(resource_ids)

                resource_id_column = db.EventResource.resource_id

                if values := label_ops.positive.simple:
                    label_filters.append(resource_id_column.in_(values))
                if values := label_ops.negative.simple:
                    label_filters.append(resource_id_column.notin_(values))
                for prefix in label_ops.positive.prefixes:
                    label_filters.append(resource_id_column.startswith(prefix))
                for prefix in label_ops.negative.prefixes:
                    label_filters.append(sa.not_(resource_id_column.startswith(prefix)))

            if roles := labels.pop("prefect.resource.role", None):
                label_filters.append(db.EventResource.resource_role.in_(roles))

            if labels:
                for _, (label, values) in enumerate(labels.items()):
                    # Empty label value arrays should match nothing
                    if not values:
                        label_filters.append(sa.false())
                        continue

                    label_ops = LabelOperations(values)

                    label_column = db.EventResource.resource[label].astext

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
                filters.append(db.EventResource.resource_role != "")

            assert self._top_level_filter is not None
            filters = [db.Event.id.in_(self._top_level_filter.where(*filters))]

        return filters


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

    @db_injector
    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence["ColumnExpressionArgument[bool]"]:
        filters: list["ColumnExpressionArgument[bool]"] = []

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
            label_filters: list[ColumnElement[bool]] = []
            labels = self.labels.deepcopy()

            # On the event_resources table, resource_id and resource_role are unpacked
            # into columns, so we should search there for them
            if resource_ids := labels.pop("prefect.resource.id", None):
                label_ops = LabelOperations(resource_ids)

                resource_id_column = db.EventResource.resource_id

                if values := label_ops.positive.simple:
                    label_filters.append(resource_id_column.in_(values))
                if values := label_ops.negative.simple:
                    label_filters.append(resource_id_column.notin_(values))
                for prefix in label_ops.positive.prefixes:
                    label_filters.append(resource_id_column.startswith(prefix))
                for prefix in label_ops.negative.prefixes:
                    label_filters.append(sa.not_(resource_id_column.startswith(prefix)))

            if roles := labels.pop("prefect.resource.role", None):
                label_filters.append(db.EventResource.resource_role.in_(roles))

            if labels:
                for _, (label, values) in enumerate(labels.items()):
                    # Empty label value arrays should match nothing
                    if not values:
                        label_filters.append(sa.false())
                        continue

                    label_ops = LabelOperations(values)

                    label_column = db.EventResource.resource[label].astext

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
            assert self._top_level_filter is not None
            filters = [db.Event.id.in_(self._top_level_filter.where(*filters))]

        return filters


class EventIDFilter(EventDataFilter):
    id: Optional[list[UUID]] = Field(
        default=None, description="Only include events with one of these IDs"
    )

    def includes(self, event: Event) -> bool:
        if self.id:
            if not any(event.id == id for id in self.id):
                return False

        return True

    @db_injector
    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence["ColumnExpressionArgument[bool]"]:
        filters: list["ColumnExpressionArgument[bool]"] = []

        if self.id:
            filters.append(db.Event.id.in_(self.id))

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
        default=None,
        description="Filter criteria for the event name",
    )
    resource: Optional[EventResourceFilter] = Field(
        default=None, description="Filter criteria for the resource of the event"
    )
    related: Optional[Union[EventRelatedFilter, list[EventRelatedFilter]]] = Field(
        default=None,
        description="Filter criteria for the related resources of the event",
    )
    any_resource: Optional[
        Union[EventAnyResourceFilter, list[EventAnyResourceFilter]]
    ] = Field(
        default=None,
        description="Filter criteria for any resource involved in the event",
    )
    id: EventIDFilter = Field(
        default_factory=lambda: EventIDFilter(),
        description="Filter criteria for the events' ID",
    )

    order: EventOrder = Field(
        default=EventOrder.DESC,
        description="The order to return filtered events",
    )

    @db_injector
    def build_where_clauses(
        self, db: PrefectDBInterface
    ) -> Sequence["ColumnExpressionArgument[bool]"]:
        self._top_level_filter = self._scoped_event_resources(db)
        result = super().build_where_clauses()
        self._top_level_filter = None
        return result

    def _scoped_event_resources(self, db: PrefectDBInterface) -> Select[tuple[UUID]]:
        """Returns an event_resources query that is scoped to this filter's scope by occurred."""
        query = sa.select(db.EventResource.event_id).where(
            db.EventResource.occurred >= self.occurred.since,
            db.EventResource.occurred <= self.occurred.until,
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
