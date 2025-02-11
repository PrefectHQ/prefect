import datetime
import uuid
from abc import ABC, abstractmethod
from collections.abc import Hashable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Optional, Union

import sqlalchemy as sa
from sqlalchemy import FetchedValue
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
    registry,
    relationship,
    synonym,
)
from sqlalchemy.sql import roles
from sqlalchemy.sql.functions import coalesce

import prefect.server.schemas as schemas
from prefect.server.events.actions import ServerActionTypes
from prefect.server.events.schemas.automations import (
    AutomationSort,
    Firing,
    ServerTriggerTypes,
)
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.schemas.statuses import (
    DeploymentStatus,
    WorkerStatus,
    WorkPoolStatus,
    WorkQueueStatus,
)
from prefect.server.utilities.database import (
    CAMEL_TO_SNAKE,
    JSON,
    UUID,
    GenerateUUID,
    Pydantic,
    Timestamp,
)
from prefect.server.utilities.encryption import decrypt_fernet, encrypt_fernet
from prefect.types._datetime import DateTime, now
from prefect.utilities.names import generate_slug

# for 'plain JSON' columns, use the postgresql variant (which comes with an
# extra operator) and fall back to the generic JSON variant for SQLite
sa_JSON: postgresql.JSON = postgresql.JSON().with_variant(sa.JSON(), "sqlite")


class Base(DeclarativeBase):
    """
    Base SQLAlchemy model that automatically infers the table name
    and provides ID, created, and updated columns
    """

    registry: ClassVar[sa.orm.registry] = registry(
        metadata=sa.schema.MetaData(
            # define naming conventions for our Base class to use
            # sqlalchemy will use the following templated strings
            # to generate the names of indices, constraints, and keys
            #
            # we offset the table name with two underscores (__) to
            # help differentiate, for example, between "flow_run.state_type"
            # and "flow_run_state.type".
            #
            # more information on this templating and available
            # customization can be found here
            # https://docs.sqlalchemy.org/en/14/core/metadata.html#sqlalchemy.schema.MetaData
            #
            # this also allows us to avoid having to specify names explicitly
            # when using sa.ForeignKey.use_alter = True
            # https://docs.sqlalchemy.org/en/14/core/constraints.html
            naming_convention={
                "ix": "ix_%(table_name)s__%(column_0_N_name)s",
                "uq": "uq_%(table_name)s__%(column_0_N_name)s",
                "ck": "ck_%(table_name)s__%(constraint_name)s",
                "fk": "fk_%(table_name)s__%(column_0_N_name)s__%(referred_table_name)s",
                "pk": "pk_%(table_name)s",
            }
        ),
        type_annotation_map={
            uuid.UUID: UUID,
            DateTime: Timestamp,
        },
    )

    # required in order to access columns with server defaults
    # or SQL expression defaults, subsequent to a flush, without
    # triggering an expired load
    #
    # this allows us to load attributes with a server default after
    # an INSERT, for example
    #
    # https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html#preventing-implicit-io-when-using-asyncsession
    __mapper_args__: dict[str, Any] = {"eager_defaults": True}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id})"

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """
        By default, turn the model's camel-case class name
        into a snake-case table name. Override by providing
        an explicit `__tablename__` class property.
        """
        return CAMEL_TO_SNAKE.sub("_", cls.__name__).lower()

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=GenerateUUID(),
        default=uuid.uuid4,
    )

    created: Mapped[DateTime] = mapped_column(
        server_default=sa.func.now(), default=lambda: now("UTC")
    )

    # onupdate is only called when statements are actually issued
    # against the database. until COMMIT is issued, this column
    # will not be updated
    updated: Mapped[DateTime] = mapped_column(
        index=True,
        server_default=sa.func.now(),
        default=lambda: now("UTC"),
        onupdate=sa.func.now(),
        server_onupdate=FetchedValue(),
    )


class Flow(Base):
    """SQLAlchemy mixin of a flow."""

    name: Mapped[str]
    tags: Mapped[list[str]] = mapped_column(JSON, server_default="[]", default=list)
    labels: Mapped[Optional[schemas.core.KeyValueLabels]] = mapped_column(JSON)

    flow_runs: Mapped[list["FlowRun"]] = relationship(
        back_populates="flow", lazy="raise"
    )
    deployments: Mapped[list["Deployment"]] = relationship(
        back_populates="flow", lazy="raise"
    )

    __table_args__: Any = (
        sa.UniqueConstraint("name"),
        sa.Index("ix_flow__created", "created"),
        sa.Index("trgm_ix_flow_name", "name", postgresql_using="gin").ddl_if(
            dialect="postgresql"
        ),
    )


class FlowRunState(Base):
    """SQLAlchemy mixin of a flow run state."""

    flow_run_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("flow_run.id", ondelete="cascade")
    )

    type: Mapped[schemas.states.StateType] = mapped_column(
        sa.Enum(schemas.states.StateType, name="state_type"), index=True
    )
    timestamp: Mapped[DateTime] = mapped_column(
        server_default=sa.func.now(), default=lambda: now("UTC")
    )
    name: Mapped[str] = mapped_column(index=True)
    message: Mapped[Optional[str]]
    state_details: Mapped[schemas.states.StateDetails] = mapped_column(
        Pydantic(schemas.states.StateDetails),
        server_default="{}",
        default=schemas.states.StateDetails,
    )
    _data: Mapped[Optional[Any]] = mapped_column(JSON, name="data")

    result_artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("artifact.id", ondelete="SET NULL", use_alter=True),
        index=True,
    )

    _result_artifact: Mapped[Optional["Artifact"]] = relationship(
        lazy="selectin",
        foreign_keys=[result_artifact_id],
        primaryjoin="Artifact.id==FlowRunState.result_artifact_id",
    )

    @hybrid_property
    def data(self) -> Optional[Any]:
        if self._data:
            # ensures backwards compatibility for results stored on state objects
            return self._data
        if not self.result_artifact_id:
            # do not try to load the relationship if there's no artifact id
            return None
        if TYPE_CHECKING:
            assert self._result_artifact is not None
        return self._result_artifact.data

    flow_run: Mapped["FlowRun"] = relationship(lazy="raise", foreign_keys=[flow_run_id])

    def as_state(self) -> schemas.states.State:
        return schemas.states.State.model_validate(self, from_attributes=True)

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> Iterable[sa.Index]:
        return (
            sa.Index(
                "uq_flow_run_state__flow_run_id_timestamp_desc",
                cls.flow_run_id,
                cls.timestamp.desc(),
                unique=True,
            ),
        )


class TaskRunState(Base):
    """SQLAlchemy model of a task run state."""

    # this column isn't explicitly indexed because it is included in
    # the unique compound index on (task_run_id, timestamp)
    task_run_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("task_run.id", ondelete="cascade")
    )

    type: Mapped[schemas.states.StateType] = mapped_column(
        sa.Enum(schemas.states.StateType, name="state_type"), index=True
    )
    timestamp: Mapped[DateTime] = mapped_column(
        server_default=sa.func.now(), default=lambda: now("UTC")
    )
    name: Mapped[str] = mapped_column(index=True)
    message: Mapped[Optional[str]]
    state_details: Mapped[schemas.states.StateDetails] = mapped_column(
        Pydantic(schemas.states.StateDetails),
        server_default="{}",
        default=schemas.states.StateDetails,
    )
    _data: Mapped[Optional[Any]] = mapped_column(JSON, name="data")

    result_artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("artifact.id", ondelete="SET NULL", use_alter=True), index=True
    )

    _result_artifact: Mapped[Optional["Artifact"]] = relationship(
        lazy="selectin",
        foreign_keys=[result_artifact_id],
        primaryjoin="Artifact.id==TaskRunState.result_artifact_id",
    )

    @hybrid_property
    def data(self) -> Optional[Any]:
        if self._data:
            # ensures backwards compatibility for results stored on state objects
            return self._data
        if not self.result_artifact_id:
            # do not try to load the relationship if there's no artifact id
            return None
        if TYPE_CHECKING:
            assert self._result_artifact is not None
        return self._result_artifact.data

    task_run: Mapped["TaskRun"] = relationship(lazy="raise", foreign_keys=[task_run_id])

    def as_state(self) -> schemas.states.State:
        return schemas.states.State.model_validate(self, from_attributes=True)

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> Iterable[sa.Index]:
        return (
            sa.Index(
                "uq_task_run_state__task_run_id_timestamp_desc",
                cls.task_run_id,
                cls.timestamp.desc(),
                unique=True,
            ),
        )


class Artifact(Base):
    """
    SQLAlchemy model of artifacts.
    """

    key: Mapped[Optional[str]] = mapped_column(index=True)

    task_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(index=True)

    flow_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(index=True)

    type: Mapped[Optional[str]]
    data: Mapped[Optional[Any]] = mapped_column(sa_JSON)
    description: Mapped[Optional[str]]

    # Suffixed with underscore as attribute name 'metadata' is reserved for the MetaData instance when using a declarative base class.
    metadata_: Mapped[Optional[dict[str, str]]] = mapped_column(sa_JSON)

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> Iterable[sa.Index]:
        return (
            sa.Index(
                "ix_artifact__key",
                cls.key,
            ),
            sa.Index(
                "ix_artifact__key_created_desc",
                cls.key,
                cls.created.desc(),
                postgresql_include=[
                    "id",
                    "updated",
                    "type",
                    "task_run_id",
                    "flow_run_id",
                ],
            ),
        )


class ArtifactCollection(Base):
    key: Mapped[str]

    latest_id: Mapped[uuid.UUID]

    task_run_id: Mapped[Optional[uuid.UUID]]

    flow_run_id: Mapped[Optional[uuid.UUID]]

    type: Mapped[Optional[str]]
    data: Mapped[Optional[Any]] = mapped_column(sa_JSON)
    description: Mapped[Optional[str]]
    metadata_: Mapped[Optional[dict[str, str]]] = mapped_column(sa_JSON)

    __table_args__: Any = (
        sa.UniqueConstraint("key"),
        sa.Index(
            "ix_artifact_collection__key_latest_id",
            "key",
            "latest_id",
        ),
    )


class TaskRunStateCache(Base):
    """
    SQLAlchemy model of a task run state cache.
    """

    cache_key: Mapped[str] = mapped_column()
    cache_expiration: Mapped[Optional[DateTime]]
    task_run_state_id: Mapped[uuid.UUID]

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> Iterable[sa.Index]:
        return (
            sa.Index(
                "ix_task_run_state_cache__cache_key_created_desc",
                cls.cache_key,
                cls.created.desc(),
            ),
        )


class Run(Base):
    """
    Common columns and logic for FlowRun and TaskRun models
    """

    __abstract__ = True

    name: Mapped[str] = mapped_column(default=lambda: generate_slug(2), index=True)
    state_type: Mapped[Optional[schemas.states.StateType]] = mapped_column(
        sa.Enum(schemas.states.StateType, name="state_type")
    )
    state_name: Mapped[Optional[str]]
    state_timestamp: Mapped[Optional[DateTime]]
    run_count: Mapped[int] = mapped_column(server_default="0", default=0)
    expected_start_time: Mapped[Optional[DateTime]]
    next_scheduled_start_time: Mapped[Optional[DateTime]]
    start_time: Mapped[Optional[DateTime]]
    end_time: Mapped[Optional[DateTime]]
    total_run_time: Mapped[datetime.timedelta] = mapped_column(
        server_default="0", default=datetime.timedelta(0)
    )

    @hybrid_property
    def estimated_run_time(self) -> datetime.timedelta:
        """Total run time is incremented in the database whenever a RUNNING
        state is exited. To give up-to-date estimates, we estimate incremental
        run time for any runs currently in a RUNNING state."""
        if self.state_type and self.state_type == schemas.states.StateType.RUNNING:
            if TYPE_CHECKING:
                assert self.state_timestamp is not None
            return self.total_run_time + (now("UTC") - self.state_timestamp)
        else:
            return self.total_run_time

    @estimated_run_time.inplace.expression
    @classmethod
    def _estimated_run_time_expression(cls) -> sa.Label[datetime.timedelta]:
        return (
            sa.select(
                sa.case(
                    (
                        cls.state_type == schemas.states.StateType.RUNNING,
                        sa.func.interval_add(
                            cls.total_run_time,
                            sa.func.date_diff(sa.func.now(), cls.state_timestamp),
                        ),
                    ),
                    else_=cls.total_run_time,
                )
            )
            # add a correlate statement so this can reuse the `FROM` clause
            # of any parent query
            .correlate(cls)
            .label("estimated_run_time")
        )

    @hybrid_property
    def estimated_start_time_delta(self) -> datetime.timedelta:
        """The delta to the expected start time (or "lateness") is computed as
        the difference between the actual start time and expected start time. To
        give up-to-date estimates, we estimate lateness for any runs that don't
        have a start time and are not in a final state and were expected to
        start already."""
        if (
            self.start_time
            and self.expected_start_time is not None
            and self.start_time > (self.expected_start_time)
        ):
            return self.start_time - self.expected_start_time
        elif (
            self.start_time is None
            and self.expected_start_time
            and self.expected_start_time < now("UTC")
            and self.state_type not in schemas.states.TERMINAL_STATES
        ):
            return now("UTC") - self.expected_start_time
        else:
            return datetime.timedelta(0)

    @estimated_start_time_delta.inplace.expression
    @classmethod
    def _estimated_start_time_delta_expression(
        cls,
    ) -> sa.SQLColumnExpression[datetime.timedelta]:
        return sa.case(
            (
                cls.start_time > cls.expected_start_time,
                sa.func.date_diff(cls.start_time, cls.expected_start_time),
            ),
            (
                sa.and_(
                    cls.start_time.is_(None),
                    cls.state_type.not_in(schemas.states.TERMINAL_STATES),
                    cls.expected_start_time < sa.func.now(),
                ),
                sa.func.date_diff(sa.func.now(), cls.expected_start_time),
            ),
            else_=datetime.timedelta(0),
        )


class FlowRun(Run):
    """SQLAlchemy model of a flow run."""

    flow_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("flow.id", ondelete="cascade"), index=True
    )

    deployment_id: Mapped[Optional[uuid.UUID]] = mapped_column()
    work_queue_name: Mapped[Optional[str]] = mapped_column(index=True)
    flow_version: Mapped[Optional[str]] = mapped_column(index=True)
    deployment_version: Mapped[Optional[str]] = mapped_column(index=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSON, server_default="{}", default=dict
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column()
    context: Mapped[dict[str, Any]] = mapped_column(
        JSON, server_default="{}", default=dict
    )
    empirical_policy: Mapped[schemas.core.FlowRunPolicy] = mapped_column(
        Pydantic(schemas.core.FlowRunPolicy),
        server_default="{}",
        default=schemas.core.FlowRunPolicy,
    )
    tags: Mapped[list[str]] = mapped_column(JSON, server_default="[]", default=list)
    labels: Mapped[Optional[schemas.core.KeyValueLabels]] = mapped_column(JSON)

    created_by: Mapped[Optional[schemas.core.CreatedBy]] = mapped_column(
        Pydantic(schemas.core.CreatedBy)
    )

    infrastructure_pid: Mapped[Optional[str]]
    job_variables: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, server_default="{}", default=dict
    )

    infrastructure_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("block_document.id", ondelete="CASCADE"), index=True
    )

    parent_task_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("task_run.id", ondelete="SET NULL", use_alter=True), index=True
    )

    auto_scheduled: Mapped[bool] = mapped_column(server_default="0", default=False)

    # TODO remove this foreign key for significant delete performance gains
    state_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("flow_run_state.id", ondelete="SET NULL", use_alter=True),
        index=True,
    )

    work_queue_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("work_queue.id", ondelete="SET NULL"), index=True
    )

    # -------------------------- relationships

    # current states are eagerly loaded unless otherwise specified
    _state: Mapped[Optional["FlowRunState"]] = relationship(
        lazy="selectin",
        foreign_keys=[state_id],
        primaryjoin="FlowRunState.id==FlowRun.state_id",
    )

    @hybrid_property
    def state(self) -> Optional[FlowRunState]:
        return self._state

    @state.inplace.setter
    def _set_state(self, value: Optional[FlowRunState]) -> None:
        # because this is a slightly non-standard SQLAlchemy relationship, we
        # prefer an explicit setter method to a setter property, because
        # user expectations about SQLAlchemy attribute assignment might not be
        # met, namely that an unrelated (from SQLAlchemy's perspective) field of
        # the provided state is also modified. However, property assignment
        # still works because the ORM model's __init__ depends on it.
        return self.set_state(value)

    def set_state(self, state: Optional[FlowRunState]) -> None:
        """
        If a state is assigned to this run, populate its run id.

        This would normally be handled by the back-populated SQLAlchemy
        relationship, but because this is a one-to-one pointer to a
        one-to-many relationship, SQLAlchemy can't figure it out.
        """
        if state is not None:
            state.flow_run_id = self.id
        self._state = state

    flow: Mapped["Flow"] = relationship(back_populates="flow_runs", lazy="raise")

    task_runs: Mapped[list["TaskRun"]] = relationship(
        back_populates="flow_run",
        lazy="raise",
        # foreign_keys=lambda: [flow_run_id],
        primaryjoin="TaskRun.flow_run_id==FlowRun.id",
    )

    parent_task_run: Mapped[Optional["TaskRun"]] = relationship(
        back_populates="subflow_run",
        lazy="raise",
        foreign_keys=[parent_task_run_id],
    )

    work_queue: Mapped[Optional["WorkQueue"]] = relationship(
        lazy="selectin", foreign_keys=[work_queue_id]
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> Iterable[sa.Index]:
        return (
            sa.Index(
                "uq_flow_run__flow_id_idempotency_key",
                cls.flow_id,
                cls.idempotency_key,
                unique=True,
            ),
            sa.Index(
                "ix_flow_run__coalesce_start_time_expected_start_time_desc",
                coalesce(cls.start_time, cls.expected_start_time).desc(),
            ),
            sa.Index(
                "ix_flow_run__coalesce_start_time_expected_start_time_asc",
                coalesce(cls.start_time, cls.expected_start_time).asc(),
            ),
            sa.Index(
                "ix_flow_run__expected_start_time_desc",
                cls.expected_start_time.desc(),
            ),
            sa.Index(
                "ix_flow_run__next_scheduled_start_time_asc",
                cls.next_scheduled_start_time.asc(),
            ),
            sa.Index(
                "ix_flow_run__end_time_desc",
                cls.end_time.desc(),
            ),
            sa.Index(
                "ix_flow_run__start_time",
                cls.start_time,
            ),
            sa.Index(
                "ix_flow_run__state_type",
                cls.state_type,
            ),
            sa.Index(
                "ix_flow_run__state_name",
                cls.state_name,
            ),
            sa.Index(
                "ix_flow_run__state_timestamp",
                cls.state_timestamp,
            ),
            sa.Index("trgm_ix_flow_run_name", cls.name, postgresql_using="gin").ddl_if(
                dialect="postgresql"
            ),
            sa.Index(
                # index names are at most 63 characters long.
                "ix_flow_run__scheduler_deployment_id_auto_scheduled_next_schedu",
                cls.deployment_id,
                cls.auto_scheduled,
                cls.next_scheduled_start_time,
                postgresql_where=cls.state_type == schemas.states.StateType.SCHEDULED,
                sqlite_where=cls.state_type == schemas.states.StateType.SCHEDULED,
            ),
        )


_TaskInput = Union[
    schemas.core.TaskRunResult, schemas.core.Parameter, schemas.core.Constant
]
_TaskInputs = dict[str, list[_TaskInput]]


class TaskRun(Run):
    """SQLAlchemy model of a task run."""

    flow_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("flow_run.id", ondelete="cascade"), index=True
    )

    task_key: Mapped[str] = mapped_column()
    dynamic_key: Mapped[str] = mapped_column()
    cache_key: Mapped[Optional[str]]
    cache_expiration: Mapped[Optional[DateTime]]
    task_version: Mapped[Optional[str]]
    flow_run_run_count: Mapped[int] = mapped_column(server_default="0", default=0)
    empirical_policy: Mapped[schemas.core.TaskRunPolicy] = mapped_column(
        Pydantic(schemas.core.TaskRunPolicy),
        server_default="{}",
        default=schemas.core.TaskRunPolicy,
    )
    task_inputs: Mapped[_TaskInputs] = mapped_column(
        Pydantic(_TaskInputs), server_default="{}", default=dict
    )
    tags: Mapped[list[str]] = mapped_column(JSON, server_default="[]", default=list)
    labels: Mapped[Optional[schemas.core.KeyValueLabels]] = mapped_column(JSON)

    # TODO remove this foreign key for significant delete performance gains
    state_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("task_run_state.id", ondelete="SET NULL", use_alter=True),
        index=True,
    )

    # -------------------------- relationships

    # current states are eagerly loaded unless otherwise specified
    _state: Mapped[Optional[TaskRunState]] = relationship(
        lazy="selectin",
        foreign_keys=[state_id],
        primaryjoin="TaskRunState.id==TaskRun.state_id",
    )

    @hybrid_property
    def state(self) -> Optional[TaskRunState]:
        return self._state

    @state.inplace.setter
    def _set_state(self, value: Optional[TaskRunState]) -> None:
        # because this is a slightly non-standard SQLAlchemy relationship, we
        # prefer an explicit setter method to a setter property, because
        # user expectations about SQLAlchemy attribute assignment might not be
        # met, namely that an unrelated (from SQLAlchemy's perspective) field of
        # the provided state is also modified. However, property assignment
        # still works because the ORM model's __init__ depends on it.
        return self.set_state(value)

    def set_state(self, state: Optional[TaskRunState]) -> None:
        """
        If a state is assigned to this run, populate its run id.

        This would normally be handled by the back-populated SQLAlchemy
        relationship, but because this is a one-to-one pointer to a
        one-to-many relationship, SQLAlchemy can't figure it out.
        """
        if state is not None:
            state.task_run_id = self.id
        self._state = state

    flow_run: Mapped[Optional["FlowRun"]] = relationship(
        back_populates="task_runs",
        lazy="raise",
        foreign_keys=[flow_run_id],
    )

    subflow_run: Mapped["FlowRun"] = relationship(
        back_populates="parent_task_run",
        lazy="raise",
        # foreign_keys=["FlowRun.parent_task_run_id"],
        primaryjoin="FlowRun.parent_task_run_id==TaskRun.id",
        uselist=False,
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> Iterable[sa.Index]:
        return (
            sa.Index(
                "uq_task_run__flow_run_id_task_key_dynamic_key",
                cls.flow_run_id,
                cls.task_key,
                cls.dynamic_key,
                unique=True,
            ),
            sa.Index(
                "ix_task_run__expected_start_time_desc",
                cls.expected_start_time.desc(),
            ),
            sa.Index(
                "ix_task_run__next_scheduled_start_time_asc",
                cls.next_scheduled_start_time.asc(),
            ),
            sa.Index(
                "ix_task_run__end_time_desc",
                cls.end_time.desc(),
            ),
            sa.Index(
                "ix_task_run__start_time",
                cls.start_time,
            ),
            sa.Index(
                "ix_task_run__state_type",
                cls.state_type,
            ),
            sa.Index(
                "ix_task_run__state_name",
                cls.state_name,
            ),
            sa.Index(
                "ix_task_run__state_timestamp",
                cls.state_timestamp,
            ),
            sa.Index("trgm_ix_task_run_name", cls.name, postgresql_using="gin").ddl_if(
                dialect="postgresql"
            ),
        )


class DeploymentSchedule(Base):
    deployment_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("deployment.id", ondelete="CASCADE"), index=True
    )

    schedule: Mapped[schemas.schedules.SCHEDULE_TYPES] = mapped_column(
        Pydantic(schemas.schedules.SCHEDULE_TYPES)
    )
    active: Mapped[bool] = mapped_column(default=True)
    max_scheduled_runs: Mapped[Optional[int]]
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSON, server_default="{}", default=dict, nullable=False
    )
    slug: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True)


class Deployment(Base):
    """SQLAlchemy model of a deployment."""

    name: Mapped[str]
    version: Mapped[Optional[str]]
    description: Mapped[Optional[str]] = mapped_column(sa.Text())
    work_queue_name: Mapped[Optional[str]] = mapped_column(index=True)
    infra_overrides: Mapped[dict[str, Any]] = mapped_column(
        JSON, server_default="{}", default=dict
    )
    path: Mapped[Optional[str]]
    entrypoint: Mapped[Optional[str]]

    last_polled: Mapped[Optional[DateTime]]
    status: Mapped[DeploymentStatus] = mapped_column(
        sa.Enum(DeploymentStatus, name="deployment_status"),
        default=DeploymentStatus.NOT_READY,
        server_default="NOT_READY",
    )

    @declared_attr
    def job_variables(self) -> Mapped[dict[str, Any]]:
        return synonym("infra_overrides")

    flow_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("flow.id", ondelete="CASCADE"), index=True
    )

    work_queue_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("work_queue.id", ondelete="SET NULL"), index=True
    )
    paused: Mapped[bool] = mapped_column(server_default="0", default=False, index=True)

    schedules: Mapped[list["DeploymentSchedule"]] = relationship(
        lazy="selectin", order_by=lambda: DeploymentSchedule.updated.desc()
    )

    # deprecated in favor of `concurrency_limit_id` FK
    _concurrency_limit: Mapped[Optional[int]] = mapped_column(name="concurrency_limit")
    concurrency_limit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("concurrency_limit_v2.id", ondelete="SET NULL"),
    )
    global_concurrency_limit: Mapped[Optional["ConcurrencyLimitV2"]] = (
        sa.orm.relationship(
            lazy="selectin",
        )
    )
    concurrency_options: Mapped[Optional[schemas.core.ConcurrencyOptions]] = (
        mapped_column(
            Pydantic(schemas.core.ConcurrencyOptions),
            server_default=None,
            nullable=True,
            default=None,
        )
    )

    tags: Mapped[list[str]] = mapped_column(JSON, server_default="[]", default=list)
    labels: Mapped[Optional[schemas.core.KeyValueLabels]] = mapped_column(JSON)
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSON, server_default="{}", default=dict
    )
    pull_steps: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSON, default=list
    )
    parameter_openapi_schema: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, default=dict
    )
    enforce_parameter_schema: Mapped[bool] = mapped_column(
        default=True, server_default="0"
    )
    created_by: Mapped[Optional[schemas.core.CreatedBy]] = mapped_column(
        Pydantic(schemas.core.CreatedBy)
    )
    updated_by: Mapped[Optional[schemas.core.UpdatedBy]] = mapped_column(
        Pydantic(schemas.core.UpdatedBy)
    )

    infrastructure_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("block_document.id", ondelete="CASCADE"), index=False
    )

    storage_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.ForeignKey("block_document.id", ondelete="CASCADE"),
        index=False,
    )

    flow: Mapped["Flow"] = relationship(
        "Flow", back_populates="deployments", lazy="raise"
    )

    work_queue: Mapped[Optional["WorkQueue"]] = relationship(
        lazy="selectin", foreign_keys=[work_queue_id]
    )

    __table_args__: Any = (
        sa.Index(
            "uq_deployment__flow_id_name",
            "flow_id",
            "name",
            unique=True,
        ),
        sa.Index(
            "ix_deployment__created",
            "created",
        ),
        sa.Index("trgm_ix_deployment_name", "name", postgresql_using="gin").ddl_if(
            dialect="postgresql"
        ),
    )


class Log(Base):
    """
    SQLAlchemy model of a logging statement.
    """

    name: Mapped[str]
    level: Mapped[int] = mapped_column(sa.SmallInteger, index=True)
    flow_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(index=True)
    task_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(index=True)
    message: Mapped[str] = mapped_column(sa.Text)

    # The client-side timestamp of this logged statement.
    timestamp: Mapped[DateTime] = mapped_column(index=True)

    __table_args__: Any = (
        sa.Index(
            "ix_log__flow_run_id_timestamp",
            "flow_run_id",
            "timestamp",
        ),
    )


class ConcurrencyLimit(Base):
    tag: Mapped[str]
    concurrency_limit: Mapped[int]
    active_slots: Mapped[list[str]] = mapped_column(
        JSON, server_default="[]", default=list
    )

    __table_args__: Any = (sa.Index("uq_concurrency_limit__tag", "tag", unique=True),)


class ConcurrencyLimitV2(Base):
    active: Mapped[bool] = mapped_column(default=True)
    name: Mapped[str]
    limit: Mapped[int]
    active_slots: Mapped[int] = mapped_column(default=0)
    denied_slots: Mapped[int] = mapped_column(default=0)

    slot_decay_per_second: Mapped[float] = mapped_column(default=0.0)
    avg_slot_occupancy_seconds: Mapped[float] = mapped_column(default=2.0)

    __table_args__: Any = (sa.UniqueConstraint("name"),)


class BlockType(Base):
    name: Mapped[str]
    slug: Mapped[str]
    logo_url: Mapped[Optional[str]]
    documentation_url: Mapped[Optional[str]]
    description: Mapped[Optional[str]]
    code_example: Mapped[Optional[str]]
    is_protected: Mapped[bool] = mapped_column(server_default="0", default=False)

    __table_args__: Any = (
        sa.Index(
            "uq_block_type__slug",
            "slug",
            unique=True,
        ),
        sa.Index("trgm_ix_block_type_name", "name", postgresql_using="gin").ddl_if(
            dialect="postgresql"
        ),
    )


class BlockSchema(Base):
    checksum: Mapped[str]
    fields: Mapped[dict[str, Any]] = mapped_column(
        JSON, server_default="{}", default=dict
    )
    capabilities: Mapped[list[str]] = mapped_column(
        JSON, server_default="[]", default=list
    )
    version: Mapped[str] = mapped_column(
        server_default=schemas.core.DEFAULT_BLOCK_SCHEMA_VERSION,
    )

    block_type_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("block_type.id", ondelete="cascade"), index=True
    )

    block_type: Mapped["BlockType"] = relationship(lazy="selectin")

    __table_args__: Any = (
        sa.Index(
            "uq_block_schema__checksum_version",
            "checksum",
            "version",
            unique=True,
        ),
        sa.Index("ix_block_schema__created", "created"),
        sa.Index(
            "ix_block_schema__capabilities", "capabilities", postgresql_using="gin"
        ).ddl_if(dialect="postgresql"),
    )


class BlockSchemaReference(Base):
    name: Mapped[str]

    parent_block_schema_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("block_schema.id", ondelete="cascade")
    )

    reference_block_schema_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("block_schema.id", ondelete="cascade")
    )


class BlockDocument(Base):
    name: Mapped[str] = mapped_column(index=True)
    data: Mapped[Any] = mapped_column(JSON, server_default="{}", default=dict)
    is_anonymous: Mapped[bool] = mapped_column(server_default="0", index=True)

    block_type_name: Mapped[Optional[str]]

    block_type_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("block_type.id", ondelete="cascade")
    )

    block_type: Mapped["BlockType"] = relationship(lazy="selectin")

    block_schema_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("block_schema.id", ondelete="cascade")
    )

    block_schema: Mapped["BlockSchema"] = relationship(lazy="selectin")

    __table_args__: Any = (
        sa.Index(
            "uq_block__type_id_name",
            "block_type_id",
            "name",
            unique=True,
        ),
        sa.Index("ix_block_document__block_type_name__name", "block_type_name", "name"),
        sa.Index("trgm_ix_block_document_name", "name", postgresql_using="gin").ddl_if(
            dialect="postgresql"
        ),
    )

    async def encrypt_data(self, session: AsyncSession, data: dict[str, Any]) -> None:
        """
        Store encrypted data on the ORM model

        Note: will only succeed if the caller has sufficient permission.
        """
        self.data = await encrypt_fernet(session, data)

    async def decrypt_data(self, session: AsyncSession) -> dict[str, Any]:
        """
        Retrieve decrypted data from the ORM model.

        Note: will only succeed if the caller has sufficient permission.
        """
        return await decrypt_fernet(session, self.data)


class BlockDocumentReference(Base):
    name: Mapped[str]

    parent_block_document_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("block_document.id", ondelete="cascade"),
    )

    reference_block_document_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("block_document.id", ondelete="cascade"),
    )


class Configuration(Base):
    key: Mapped[str] = mapped_column(index=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)

    __table_args__: Any = (sa.UniqueConstraint("key"),)


class SavedSearch(Base):
    """SQLAlchemy model of a saved search."""

    name: Mapped[str]
    filters: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, server_default="[]", default=list
    )

    __table_args__: Any = (sa.UniqueConstraint("name"),)


class WorkQueue(Base):
    """SQLAlchemy model of a work queue"""

    name: Mapped[str]

    filter: Mapped[Optional[schemas.core.QueueFilter]] = mapped_column(
        Pydantic(schemas.core.QueueFilter)
    )
    description: Mapped[str] = mapped_column(default="", server_default="")
    is_paused: Mapped[bool] = mapped_column(server_default="0", default=False)
    concurrency_limit: Mapped[Optional[int]]
    priority: Mapped[int]

    last_polled: Mapped[Optional[DateTime]]
    status: Mapped[WorkQueueStatus] = mapped_column(
        sa.Enum(WorkQueueStatus, name="work_queue_status"),
        default=WorkQueueStatus.NOT_READY,
        server_default=WorkQueueStatus.NOT_READY,
    )

    work_pool_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("work_pool.id", ondelete="cascade"), index=True
    )

    work_pool: Mapped["WorkPool"] = relationship(
        lazy="selectin", foreign_keys=[work_pool_id]
    )

    __table_args__: ClassVar[Any] = (
        sa.UniqueConstraint("work_pool_id", "name"),
        sa.Index("ix_work_queue__work_pool_id_priority", "work_pool_id", "priority"),
        sa.Index("trgm_ix_work_queue_name", "name", postgresql_using="gin").ddl_if(
            dialect="postgresql"
        ),
    )


class WorkPool(Base):
    """SQLAlchemy model of an worker"""

    name: Mapped[str]
    description: Mapped[Optional[str]]
    type: Mapped[str] = mapped_column(index=True)
    base_job_template: Mapped[dict[str, Any]] = mapped_column(
        JSON, server_default="{}", default={}
    )
    is_paused: Mapped[bool] = mapped_column(server_default="0", default=False)
    default_queue_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID,
        sa.ForeignKey("work_queue.id", ondelete="RESTRICT", use_alter=True),
        nullable=True,
    )
    concurrency_limit: Mapped[Optional[int]]

    status: Mapped[WorkPoolStatus] = mapped_column(
        sa.Enum(WorkPoolStatus, name="work_pool_status"),
        default=WorkPoolStatus.NOT_READY,
        server_default=WorkPoolStatus.NOT_READY,
    )
    last_transitioned_status_at: Mapped[Optional[DateTime]]
    last_status_event_id: Mapped[Optional[uuid.UUID]]

    __table_args__: Any = (sa.UniqueConstraint("name"),)


class Worker(Base):
    """SQLAlchemy model of an worker"""

    work_pool_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("work_pool.id", ondelete="cascade"), index=True
    )

    name: Mapped[str]
    last_heartbeat_time: Mapped[DateTime] = mapped_column(
        server_default=sa.func.now(), default=lambda: now("UTC")
    )
    heartbeat_interval_seconds: Mapped[Optional[int]]

    status: Mapped[WorkerStatus] = mapped_column(
        sa.Enum(WorkerStatus, name="worker_status"),
        default=WorkerStatus.OFFLINE,
        server_default=WorkerStatus.OFFLINE,
    )

    __table_args__: Any = (
        sa.UniqueConstraint("work_pool_id", "name"),
        sa.Index(
            "ix_worker__work_pool_id_last_heartbeat_time",
            "work_pool_id",
            "last_heartbeat_time",
        ),
    )


class Agent(Base):
    """SQLAlchemy model of an agent"""

    name: Mapped[str]

    work_queue_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("work_queue.id"), index=True
    )

    last_activity_time: Mapped[DateTime] = mapped_column(
        server_default=sa.func.now(), default=lambda: now("UTC")
    )

    __table_args__: Any = (sa.UniqueConstraint("name"),)


class FlowRunNotificationPolicy(Base):
    is_active: Mapped[bool] = mapped_column(server_default="1", default=True)
    state_names: Mapped[list[str]] = mapped_column(
        JSON, server_default="[]", default=[]
    )
    tags: Mapped[list[str]] = mapped_column(JSON, server_default="[]", default=[])
    message_template: Mapped[Optional[str]]

    block_document_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("block_document.id", ondelete="cascade")
    )

    block_document: Mapped["BlockDocument"] = relationship(
        lazy="selectin", foreign_keys=[block_document_id]
    )


class FlowRunNotificationQueue(Base):
    # these are both foreign keys but there is no need to enforce that constraint
    # as this is just a queue for service workers; if the keys don't match at the
    # time work is pulled, the work can be discarded
    flow_run_notification_policy_id: Mapped[uuid.UUID]
    flow_run_state_id: Mapped[uuid.UUID]


class Variable(Base):
    name: Mapped[str]
    value: Mapped[Optional[Any]] = mapped_column(JSON)
    tags: Mapped[list[str]] = mapped_column(JSON, server_default="[]", default=list)

    __table_args__: Any = (sa.UniqueConstraint("name"),)


class FlowRunInput(Base):
    flow_run_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("flow_run.id", ondelete="cascade")
    )

    key: Mapped[str]
    value: Mapped[str] = mapped_column(sa.Text())
    sender: Mapped[Optional[str]]

    __table_args__: Any = (sa.UniqueConstraint("flow_run_id", "key"),)


class CsrfToken(Base):
    token: Mapped[str]
    client: Mapped[str] = mapped_column(unique=True)
    expiration: Mapped[DateTime]


class Automation(Base):
    name: Mapped[str]
    description: Mapped[str] = mapped_column(default="")

    enabled: Mapped[bool] = mapped_column(server_default="1", default=True)

    trigger: Mapped[ServerTriggerTypes] = mapped_column(Pydantic(ServerTriggerTypes))

    actions: Mapped[ServerActionTypes] = mapped_column(
        Pydantic(list[ServerActionTypes])
    )
    actions_on_trigger: Mapped[list[ServerActionTypes]] = mapped_column(
        Pydantic(list[ServerActionTypes]), server_default="[]", default=list
    )
    actions_on_resolve: Mapped[list[ServerActionTypes]] = mapped_column(
        Pydantic(list[ServerActionTypes]), server_default="[]", default=list
    )

    related_resources: Mapped[list["AutomationRelatedResource"]] = relationship(
        "AutomationRelatedResource", back_populates="automation", lazy="raise"
    )

    @classmethod
    def sort_expression(cls, value: AutomationSort) -> sa.ColumnExpressionArgument[Any]:
        """Return an expression used to sort Automations"""
        sort_mapping: dict[AutomationSort, sa.ColumnExpressionArgument[Any]] = {
            AutomationSort.CREATED_DESC: cls.created.desc(),
            AutomationSort.UPDATED_DESC: cls.updated.desc(),
            AutomationSort.NAME_ASC: cls.name.asc(),
            AutomationSort.NAME_DESC: cls.name.desc(),
        }
        return sort_mapping[value]


class AutomationBucket(Base):
    __table_args__: Any = (
        sa.Index(
            "uq_automation_bucket__automation_id__trigger_id__bucketing_key",
            "automation_id",
            "trigger_id",
            "bucketing_key",
            unique=True,
        ),
        sa.Index(
            "ix_automation_bucket__automation_id__end",
            "automation_id",
            "end",
        ),
    )

    automation_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("automation.id", ondelete="CASCADE")
    )

    trigger_id: Mapped[uuid.UUID]

    bucketing_key: Mapped[list[str]] = mapped_column(
        JSON, server_default="[]", default=list
    )

    last_event: Mapped[Optional[ReceivedEvent]] = mapped_column(Pydantic(ReceivedEvent))

    start: Mapped[DateTime]
    end: Mapped[DateTime]

    count: Mapped[int]

    last_operation: Mapped[Optional[str]]

    triggered_at: Mapped[Optional[DateTime]]


class AutomationRelatedResource(Base):
    __table_args__: Any = (
        sa.Index(
            "uq_automation_related_resource__automation_id__resource_id",
            "automation_id",
            "resource_id",
            unique=True,
        ),
    )

    automation_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("automation.id", ondelete="CASCADE")
    )

    resource_id: Mapped[Optional[str]] = mapped_column(index=True)
    automation_owned_by_resource: Mapped[bool] = mapped_column(
        default=False, server_default="0"
    )

    automation: Mapped["Automation"] = relationship(
        "Automation", back_populates="related_resources", lazy="raise"
    )


class CompositeTriggerChildFiring(Base):
    __table_args__: Any = (
        sa.Index(
            "uq_composite_trigger_child_firing__a_id__pt_id__ct__id",
            "automation_id",
            "parent_trigger_id",
            "child_trigger_id",
            unique=True,
        ),
    )

    automation_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("automation.id", ondelete="CASCADE")
    )

    parent_trigger_id: Mapped[uuid.UUID]

    child_trigger_id: Mapped[uuid.UUID]
    child_firing_id: Mapped[uuid.UUID]
    child_fired_at: Mapped[Optional[DateTime]]
    child_firing: Mapped[Firing] = mapped_column(Pydantic(Firing))


class AutomationEventFollower(Base):
    __table_args__: Any = (
        sa.Index(
            "uq_follower_for_scope",
            "scope",
            "follower_event_id",
            unique=True,
        ),
    )
    scope: Mapped[str] = mapped_column(default="", index=True)
    leader_event_id: Mapped[uuid.UUID] = mapped_column(index=True)
    follower_event_id: Mapped[uuid.UUID]
    received: Mapped[DateTime] = mapped_column(index=True)
    follower: Mapped[ReceivedEvent] = mapped_column(Pydantic(ReceivedEvent))


class Event(Base):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "events"

    __table_args__: Any = (
        sa.Index("ix_events__related_resource_ids", "related_resource_ids"),
        sa.Index("ix_events__occurred", "occurred"),
        sa.Index("ix_events__event__id", "event", "id"),
        sa.Index(
            "ix_events__event_resource_id_occurred",
            "event",
            "resource_id",
            "occurred",
        ),
        sa.Index("ix_events__occurred_id", "occurred", "id"),
        sa.Index("ix_events__event_occurred_id", "event", "occurred", "id"),
        sa.Index("ix_events__event_related_occurred", "event", "related", "occurred"),
    )

    occurred: Mapped[DateTime]
    event: Mapped[str] = mapped_column(sa.Text())
    resource_id: Mapped[str] = mapped_column(sa.Text())
    resource: Mapped[dict[str, Any]] = mapped_column(JSON())
    related_resource_ids: Mapped[list[str]] = mapped_column(
        JSON(), server_default="[]", default=list
    )
    related: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON(), server_default="[]", default=list
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON())
    received: Mapped[DateTime]
    recorded: Mapped[DateTime]
    follows: Mapped[Optional[uuid.UUID]]


class EventResource(Base):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "event_resources"

    __table_args__: Any = (
        sa.Index(
            "ix_event_resources__resource_id__occurred",
            "resource_id",
            "occurred",
        ),
    )

    occurred: Mapped[DateTime]
    resource_id: Mapped[str] = mapped_column(sa.Text())
    resource_role: Mapped[str] = mapped_column(sa.Text())
    resource: Mapped[dict[str, Any]] = mapped_column(sa_JSON)
    event_id: Mapped[uuid.UUID]


# These are temporary until we've migrated all the references to the new,
# non-ORM names

ORMFlow = Flow
ORMFlowRunState = FlowRunState
ORMTaskRunState = TaskRunState
ORMArtifact = Artifact
ORMArtifactCollection = ArtifactCollection
ORMTaskRunStateCache = TaskRunStateCache
ORMRun = Run
ORMFlowRun = FlowRun
ORMTaskRun = TaskRun
ORMDeploymentSchedule = DeploymentSchedule
ORMDeployment = Deployment
ORMLog = Log
ORMConcurrencyLimit = ConcurrencyLimit
ORMConcurrencyLimitV2 = ConcurrencyLimitV2
ORMBlockType = BlockType
ORMBlockSchema = BlockSchema
ORMBlockSchemaReference = BlockSchemaReference
ORMBlockDocument = BlockDocument
ORMBlockDocumentReference = BlockDocumentReference
ORMConfiguration = Configuration
ORMSavedSearch = SavedSearch
ORMWorkQueue = WorkQueue
ORMWorkPool = WorkPool
ORMWorker = Worker
ORMAgent = Agent
ORMFlowRunNotificationPolicy = FlowRunNotificationPolicy
ORMFlowRunNotificationQueue = FlowRunNotificationQueue
ORMVariable = Variable
ORMFlowRunInput = FlowRunInput
ORMCsrfToken = CsrfToken
ORMAutomation = Automation
ORMAutomationBucket = AutomationBucket
ORMAutomationRelatedResource = AutomationRelatedResource
ORMCompositeTriggerChildFiring = CompositeTriggerChildFiring
ORMAutomationEventFollower = AutomationEventFollower
ORMEvent = Event
ORMEventResource = EventResource


_UpsertColumns = Iterable[Union[str, "sa.Column[Any]", roles.DDLConstraintColumnRole]]


class BaseORMConfiguration(ABC):
    """
    Abstract base class used to inject database-specific ORM configuration into Prefect.

    Modifications to core Prefect REST API data structures can have unintended consequences.
    Use with caution.
    """

    def unique_key(self) -> tuple[Hashable, ...]:
        """
        Returns a key used to determine whether to instantiate a new DB interface.
        """
        return (self.__class__, Base.metadata)

    @property
    @abstractmethod
    def versions_dir(self) -> Path:
        """Directory containing migrations"""
        ...

    @property
    def deployment_unique_upsert_columns(self) -> _UpsertColumns:
        """Unique columns for upserting a Deployment"""
        return [Deployment.flow_id, Deployment.name]

    @property
    def concurrency_limit_unique_upsert_columns(self) -> _UpsertColumns:
        """Unique columns for upserting a ConcurrencyLimit"""
        return [ConcurrencyLimit.tag]

    @property
    def flow_run_unique_upsert_columns(self) -> _UpsertColumns:
        """Unique columns for upserting a FlowRun"""
        return [FlowRun.flow_id, FlowRun.idempotency_key]

    @property
    def block_type_unique_upsert_columns(self) -> _UpsertColumns:
        """Unique columns for upserting a BlockType"""
        return [BlockType.slug]

    @property
    def artifact_collection_unique_upsert_columns(self) -> _UpsertColumns:
        """Unique columns for upserting an ArtifactCollection"""
        return [ArtifactCollection.key]

    @property
    def block_schema_unique_upsert_columns(self) -> _UpsertColumns:
        """Unique columns for upserting a BlockSchema"""
        return [BlockSchema.checksum, BlockSchema.version]

    @property
    def flow_unique_upsert_columns(self) -> _UpsertColumns:
        """Unique columns for upserting a Flow"""
        return [Flow.name]

    @property
    def saved_search_unique_upsert_columns(self) -> _UpsertColumns:
        """Unique columns for upserting a SavedSearch"""
        return [SavedSearch.name]

    @property
    def task_run_unique_upsert_columns(self) -> _UpsertColumns:
        """Unique columns for upserting a TaskRun"""
        return [
            TaskRun.flow_run_id,
            TaskRun.task_key,
            TaskRun.dynamic_key,
        ]

    @property
    def block_document_unique_upsert_columns(self) -> _UpsertColumns:
        """Unique columns for upserting a BlockDocument"""
        return [BlockDocument.block_type_id, BlockDocument.name]


class AsyncPostgresORMConfiguration(BaseORMConfiguration):
    """Postgres specific orm configuration"""

    @property
    def versions_dir(self) -> Path:
        """Directory containing migrations"""
        import prefect.server.database

        return (
            Path(prefect.server.database.__file__).parent
            / "_migrations"
            / "versions"
            / "postgresql"
        )


class AioSqliteORMConfiguration(BaseORMConfiguration):
    """SQLite specific orm configuration"""

    @property
    def versions_dir(self) -> Path:
        """Directory containing migrations"""
        import prefect.server.database

        return (
            Path(prefect.server.database.__file__).parent
            / "_migrations"
            / "versions"
            / "sqlite"
        )
