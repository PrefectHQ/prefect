import datetime
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Hashable, List, Tuple, Union, cast

import pendulum
import sqlalchemy as sa
from sqlalchemy import FetchedValue
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
    registry,
    synonym,
)
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.sql.functions import coalesce

import prefect
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
    JSON,
    UUID,
    GenerateUUID,
    Pydantic,
    Timestamp,
    camel_to_snake,
    date_diff,
    interval_add,
    now,
)
from prefect.server.utilities.encryption import decrypt_fernet, encrypt_fernet
from prefect.utilities.names import generate_slug


class Base(DeclarativeBase):
    """
    Base SQLAlchemy model that automatically infers the table name
    and provides ID, created, and updated columns
    """

    registry = registry(
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
    __mapper_args__ = {"eager_defaults": True}

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.id})"

    @declared_attr
    def __tablename__(cls):
        """
        By default, turn the model's camel-case class name
        into a snake-case table name. Override by providing
        an explicit `__tablename__` class property.
        """
        return camel_to_snake.sub("_", cls.__name__).lower()

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=GenerateUUID(),
        default=uuid.uuid4,
    )

    created: Mapped[pendulum.DateTime] = mapped_column(
        Timestamp(),
        nullable=False,
        server_default=now(),
        default=lambda: pendulum.now("UTC"),
    )

    # onupdate is only called when statements are actually issued
    # against the database. until COMMIT is issued, this column
    # will not be updated
    updated = sa.Column(
        Timestamp(),
        nullable=False,
        index=True,
        server_default=now(),
        default=lambda: pendulum.now("UTC"),
        onupdate=now(),
        server_onupdate=FetchedValue(),
    )


class Flow(Base):
    """SQLAlchemy mixin of a flow."""

    name = sa.Column(sa.String, nullable=False)
    tags: Mapped[List[str]] = mapped_column(
        JSON, server_default="[]", default=list, nullable=False
    )

    flow_runs = sa.orm.relationship("FlowRun", back_populates="flow", lazy="raise")
    deployments = sa.orm.relationship("Deployment", back_populates="flow", lazy="raise")

    __table_args__ = (
        sa.UniqueConstraint("name"),
        sa.Index("ix_flow__created", "created"),
    )


class FlowRunState(Base):
    """SQLAlchemy mixin of a flow run state."""

    flow_run_id = sa.Column(
        UUID(), sa.ForeignKey("flow_run.id", ondelete="cascade"), nullable=False
    )

    type = sa.Column(
        sa.Enum(schemas.states.StateType, name="state_type"), nullable=False, index=True
    )
    timestamp = sa.Column(
        Timestamp(),
        nullable=False,
        server_default=now(),
        default=lambda: pendulum.now("UTC"),
    )
    name = sa.Column(sa.String, nullable=False, index=True)
    message = sa.Column(sa.String)
    state_details = sa.Column(
        Pydantic(schemas.states.StateDetails),
        server_default="{}",
        default=schemas.states.StateDetails,
        nullable=False,
    )
    _data = sa.Column(sa.JSON, nullable=True, name="data")

    result_artifact_id = sa.Column(
        UUID(),
        sa.ForeignKey(
            "artifact.id",
            ondelete="SET NULL",
            use_alter=True,
        ),
        index=True,
    )

    _result_artifact = sa.orm.relationship(
        "Artifact",
        lazy="selectin",
        foreign_keys=[result_artifact_id],
        primaryjoin="Artifact.id==FlowRunState.result_artifact_id",
    )

    @hybrid_property
    def data(self):
        if self._data:
            # ensures backwards compatibility for results stored on state objects
            return self._data
        if not self.result_artifact_id:
            # do not try to load the relationship if there's no artifact id
            return None
        return self._result_artifact.data

    flow_run = sa.orm.relationship(
        "FlowRun",
        lazy="raise",
        foreign_keys=[flow_run_id],
    )

    def as_state(self) -> schemas.states.State:
        return schemas.states.State.model_validate(self, from_attributes=True)

    __table_args__ = (
        sa.Index(
            "uq_flow_run_state__flow_run_id_timestamp_desc",
            "flow_run_id",
            sa.desc("timestamp"),
            unique=True,
        ),
    )


class TaskRunState(Base):
    """SQLAlchemy model of a task run state."""

    # this column isn't explicitly indexed because it is included in
    # the unique compound index on (task_run_id, timestamp)
    task_run_id = sa.Column(
        UUID(), sa.ForeignKey("task_run.id", ondelete="cascade"), nullable=False
    )

    type = sa.Column(
        sa.Enum(schemas.states.StateType, name="state_type"), nullable=False, index=True
    )
    timestamp = sa.Column(
        Timestamp(),
        nullable=False,
        server_default=now(),
        default=lambda: pendulum.now("UTC"),
    )
    name = sa.Column(sa.String, nullable=False, index=True)
    message = sa.Column(sa.String)
    state_details = sa.Column(
        Pydantic(schemas.states.StateDetails),
        server_default="{}",
        default=schemas.states.StateDetails,
        nullable=False,
    )
    _data = sa.Column(sa.JSON, nullable=True, name="data")

    result_artifact_id = sa.Column(
        UUID(),
        sa.ForeignKey(
            "artifact.id",
            ondelete="SET NULL",
            use_alter=True,
        ),
        index=True,
    )

    _result_artifact = sa.orm.relationship(
        "Artifact",
        lazy="selectin",
        foreign_keys=[result_artifact_id],
        primaryjoin="Artifact.id==TaskRunState.result_artifact_id",
    )

    @hybrid_property
    def data(self):
        if self._data:
            # ensures backwards compatibility for results stored on state objects
            return self._data
        if not self.result_artifact_id:
            # do not try to load the relationship if there's no artifact id
            return None
        return self._result_artifact.data

    task_run = sa.orm.relationship(
        "TaskRun",
        lazy="raise",
        foreign_keys=[task_run_id],
    )

    def as_state(self) -> schemas.states.State:
        return schemas.states.State.model_validate(self, from_attributes=True)

    __table_args__ = (
        sa.Index(
            "uq_task_run_state__task_run_id_timestamp_desc",
            "task_run_id",
            sa.desc("timestamp"),
            unique=True,
        ),
    )


class Artifact(Base):
    """
    SQLAlchemy model of artifacts.
    """

    key = sa.Column(
        sa.String,
        nullable=True,
        index=True,
    )

    task_run_id = sa.Column(
        UUID(),
        nullable=True,
        index=True,
    )

    flow_run_id = sa.Column(
        UUID(),
        nullable=True,
        index=True,
    )

    type = sa.Column(sa.String)
    data = sa.Column(sa.JSON, nullable=True)
    description = sa.Column(sa.String, nullable=True)

    # Suffixed with underscore as attribute name 'metadata' is reserved for the MetaData instance when using a declarative base class.
    metadata_ = sa.Column(sa.JSON, nullable=True)

    __table_args__ = (
        sa.Index(
            "ix_artifact__key",
            "key",
        ),
    )


class ArtifactCollection(Base):
    key = sa.Column(
        sa.String,
        nullable=False,
    )

    latest_id: Mapped[UUID] = mapped_column(UUID(), nullable=False)

    task_run_id = sa.Column(
        UUID(),
        nullable=True,
    )

    flow_run_id = sa.Column(
        UUID(),
        nullable=True,
    )

    type = sa.Column(sa.String)
    data = sa.Column(sa.JSON, nullable=True)
    description = sa.Column(sa.String, nullable=True)
    metadata_ = sa.Column(sa.JSON, nullable=True)

    __table_args__ = (
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

    cache_key = sa.Column(sa.String, nullable=False)
    cache_expiration = sa.Column(
        Timestamp(),
        nullable=True,
    )
    task_run_state_id = sa.Column(UUID(), nullable=False)

    __table_args__ = (
        sa.Index(
            "ix_task_run_state_cache__cache_key_created_desc",
            "cache_key",
            sa.desc("created"),
        ),
    )


class Run(Base):
    """
    Common columns and logic for FlowRun and TaskRun models
    """

    __abstract__ = True

    name: Mapped[str] = mapped_column(
        sa.String,
        default=lambda: generate_slug(2),
        nullable=False,
        index=True,
    )
    state_type = sa.Column(sa.Enum(schemas.states.StateType, name="state_type"))
    state_name = sa.Column(sa.String, nullable=True)
    state_timestamp: Mapped[Union[pendulum.DateTime, None]] = mapped_column(
        Timestamp(), nullable=True
    )
    run_count = sa.Column(sa.Integer, server_default="0", default=0, nullable=False)
    expected_start_time: Mapped[pendulum.DateTime] = mapped_column(Timestamp())
    next_scheduled_start_time = sa.Column(Timestamp())
    start_time: Mapped[pendulum.DateTime] = mapped_column(Timestamp())
    end_time: Mapped[pendulum.DateTime] = mapped_column(Timestamp())
    total_run_time: Mapped[datetime.timedelta] = mapped_column(
        sa.Interval(),
        server_default="0",
        default=datetime.timedelta(0),
        nullable=False,
    )

    @hybrid_property
    def estimated_run_time(self):
        """Total run time is incremented in the database whenever a RUNNING
        state is exited. To give up-to-date estimates, we estimate incremental
        run time for any runs currently in a RUNNING state."""
        if self.state_type and self.state_type == schemas.states.StateType.RUNNING:
            return self.total_run_time + (pendulum.now("UTC") - self.state_timestamp)
        else:
            return self.total_run_time

    @estimated_run_time.expression
    def estimated_run_time(cls):
        return (
            sa.select(
                sa.case(
                    (
                        cls.state_type == schemas.states.StateType.RUNNING,
                        interval_add(
                            cls.total_run_time,
                            date_diff(now(), cls.state_timestamp),
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
        if self.start_time and self.start_time > self.expected_start_time:
            return self.start_time - self.expected_start_time
        elif (
            self.start_time is None
            and self.expected_start_time
            and self.expected_start_time < pendulum.now("UTC")
            and self.state_type not in schemas.states.TERMINAL_STATES
        ):
            return pendulum.now("UTC") - self.expected_start_time
        else:
            return datetime.timedelta(0)

    @estimated_start_time_delta.expression
    def estimated_start_time_delta(cls):
        return sa.case(
            (
                cls.start_time > cls.expected_start_time,
                date_diff(cls.start_time, cls.expected_start_time),
            ),
            (
                sa.and_(
                    cls.start_time.is_(None),
                    cls.state_type.not_in(schemas.states.TERMINAL_STATES),
                    cls.expected_start_time < now(),
                ),
                date_diff(now(), cls.expected_start_time),
            ),
            else_=datetime.timedelta(0),
        )


class FlowRun(Run):
    """SQLAlchemy model of a flow run."""

    flow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(),
        sa.ForeignKey("flow.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    deployment_id: Mapped[Union[uuid.UUID, None]] = mapped_column(UUID(), nullable=True)
    work_queue_name = sa.Column(sa.String, index=True)
    flow_version = sa.Column(sa.String, index=True)
    deployment_version = sa.Column(sa.String, index=True)
    parameters = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    idempotency_key = sa.Column(sa.String)
    context = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    empirical_policy = sa.Column(
        Pydantic(schemas.core.FlowRunPolicy),
        server_default="{}",
        default=schemas.core.FlowRunPolicy,
        nullable=False,
    )
    tags: Mapped[List[str]] = mapped_column(
        JSON, server_default="[]", default=list, nullable=False
    )

    created_by: Mapped[Union[schemas.core.CreatedBy, None]] = mapped_column(
        Pydantic(schemas.core.CreatedBy),
        server_default=None,
        default=None,
        nullable=True,
    )

    infrastructure_pid = sa.Column(sa.String)
    job_variables = sa.Column(JSON, server_default="{}", default=dict, nullable=True)

    infrastructure_document_id = sa.Column(
        UUID,
        sa.ForeignKey("block_document.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    parent_task_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(),
        sa.ForeignKey(
            "task_run.id",
            ondelete="SET NULL",
            use_alter=True,
        ),
        index=True,
    )

    auto_scheduled = sa.Column(
        sa.Boolean, server_default="0", default=False, nullable=False
    )

    # TODO remove this foreign key for significant delete performance gains
    state_id = sa.Column(
        UUID(),
        sa.ForeignKey(
            "flow_run_state.id",
            ondelete="SET NULL",
            use_alter=True,
        ),
        index=True,
    )

    work_queue_id: Mapped[Union[uuid.UUID, None]] = mapped_column(
        UUID,
        sa.ForeignKey("work_queue.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # -------------------------- relationships

    # current states are eagerly loaded unless otherwise specified
    _state = sa.orm.relationship(
        "FlowRunState",
        lazy="selectin",
        foreign_keys=[state_id],
        primaryjoin="FlowRunState.id==FlowRun.state_id",
    )

    @hybrid_property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        # because this is a slightly non-standard SQLAlchemy relationship, we
        # prefer an explicit setter method to a setter property, because
        # user expectations about SQLAlchemy attribute assignment might not be
        # met, namely that an unrelated (from SQLAlchemy's perspective) field of
        # the provided state is also modified. However, property assignment
        # still works because the ORM model's __init__ depends on it.
        return self.set_state(value)

    def set_state(self, state):
        """
        If a state is assigned to this run, populate its run id.

        This would normally be handled by the back-populated SQLAlchemy
        relationship, but because this is a one-to-one pointer to a
        one-to-many relationship, SQLAlchemy can't figure it out.
        """
        if state is not None:
            state.flow_run_id = self.id
        self._state = state

    flow = sa.orm.relationship("Flow", back_populates="flow_runs", lazy="raise")

    task_runs = sa.orm.relationship(
        "TaskRun",
        back_populates="flow_run",
        lazy="raise",
        # foreign_keys=lambda: [flow_run_id],
        primaryjoin="TaskRun.flow_run_id==FlowRun.id",
    )

    parent_task_run = sa.orm.relationship(
        "TaskRun",
        back_populates="subflow_run",
        lazy="raise",
        foreign_keys=[parent_task_run_id],
    )

    work_queue = sa.orm.relationship(
        "WorkQueue",
        lazy="selectin",
        foreign_keys=[work_queue_id],
    )

    __table_args__ = (
        sa.Index(
            "uq_flow_run__flow_id_idempotency_key",
            "flow_id",
            "idempotency_key",
            unique=True,
        ),
        sa.Index(
            "ix_flow_run__coalesce_start_time_expected_start_time_desc",
            sa.desc(coalesce("start_time", "expected_start_time")),
        ),
        sa.Index(
            "ix_flow_run__coalesce_start_time_expected_start_time_asc",
            sa.asc(coalesce("start_time", "expected_start_time")),
        ),
        sa.Index(
            "ix_flow_run__expected_start_time_desc",
            sa.desc("expected_start_time"),
        ),
        sa.Index(
            "ix_flow_run__next_scheduled_start_time_asc",
            sa.asc("next_scheduled_start_time"),
        ),
        sa.Index(
            "ix_flow_run__end_time_desc",
            sa.desc("end_time"),
        ),
        sa.Index(
            "ix_flow_run__start_time",
            "start_time",
        ),
        sa.Index(
            "ix_flow_run__state_type",
            "state_type",
        ),
        sa.Index(
            "ix_flow_run__state_name",
            "state_name",
        ),
        sa.Index(
            "ix_flow_run__state_timestamp",
            "state_timestamp",
        ),
    )


class TaskRun(Run):
    """SQLAlchemy model of a task run."""

    flow_run_id = sa.Column(
        UUID(),
        sa.ForeignKey("flow_run.id", ondelete="cascade"),
        nullable=True,
        index=True,
    )

    task_key = sa.Column(sa.String, nullable=False)
    dynamic_key = sa.Column(sa.String, nullable=False)
    cache_key = sa.Column(sa.String)
    cache_expiration = sa.Column(Timestamp())
    task_version = sa.Column(sa.String)
    flow_run_run_count = sa.Column(
        sa.Integer, server_default="0", default=0, nullable=False
    )
    empirical_policy = sa.Column(
        Pydantic(schemas.core.TaskRunPolicy),
        server_default="{}",
        default=schemas.core.TaskRunPolicy,
        nullable=False,
    )
    task_inputs = sa.Column(
        Pydantic(
            Dict[
                str,
                List[
                    Union[
                        schemas.core.TaskRunResult,
                        schemas.core.Parameter,
                        schemas.core.Constant,
                    ]
                ],
            ]
        ),
        server_default="{}",
        default=dict,
        nullable=False,
    )
    tags: Mapped[List[str]] = mapped_column(
        JSON, server_default="[]", default=list, nullable=False
    )

    # TODO remove this foreign key for significant delete performance gains
    state_id = sa.Column(
        UUID(),
        sa.ForeignKey(
            "task_run_state.id",
            ondelete="SET NULL",
            use_alter=True,
        ),
        index=True,
    )

    # -------------------------- relationships

    # current states are eagerly loaded unless otherwise specified
    _state = sa.orm.relationship(
        "TaskRunState",
        lazy="selectin",
        foreign_keys=[state_id],
        primaryjoin="TaskRunState.id==TaskRun.state_id",
    )

    @hybrid_property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        # because this is a slightly non-standard SQLAlchemy relationship, we
        # prefer an explicit setter method to a setter property, because
        # user expectations about SQLAlchemy attribute assignment might not be
        # met, namely that an unrelated (from SQLAlchemy's perspective) field of
        # the provided state is also modified. However, property assignment
        # still works because the ORM model's __init__ depends on it.
        return self.set_state(value)

    def set_state(self, state):
        """
        If a state is assigned to this run, populate its run id.

        This would normally be handled by the back-populated SQLAlchemy
        relationship, but because this is a one-to-one pointer to a
        one-to-many relationship, SQLAlchemy can't figure it out.
        """
        if state is not None:
            state.task_run_id = self.id
        self._state = state

    flow_run = sa.orm.relationship(
        "FlowRun",
        back_populates="task_runs",
        lazy="raise",
        foreign_keys=[flow_run_id],
    )

    subflow_run = sa.orm.relationship(
        "FlowRun",
        back_populates="parent_task_run",
        lazy="raise",
        # foreign_keys=["FlowRun.parent_task_run_id"],
        primaryjoin="FlowRun.parent_task_run_id==TaskRun.id",
        uselist=False,
    )

    __table_args__ = (
        sa.Index(
            "uq_task_run__flow_run_id_task_key_dynamic_key",
            "flow_run_id",
            "task_key",
            "dynamic_key",
            unique=True,
        ),
        sa.Index(
            "ix_task_run__expected_start_time_desc",
            sa.desc("expected_start_time"),
        ),
        sa.Index(
            "ix_task_run__next_scheduled_start_time_asc",
            sa.asc("next_scheduled_start_time"),
        ),
        sa.Index(
            "ix_task_run__end_time_desc",
            sa.desc("end_time"),
        ),
        sa.Index(
            "ix_task_run__start_time",
            "start_time",
        ),
        sa.Index(
            "ix_task_run__state_type",
            "state_type",
        ),
        sa.Index(
            "ix_task_run__state_name",
            "state_name",
        ),
        sa.Index(
            "ix_task_run__state_timestamp",
            "state_timestamp",
        ),
    )


class DeploymentSchedule(Base):
    deployment_id = sa.Column(
        UUID(),
        sa.ForeignKey("deployment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    schedule = sa.Column(Pydantic(schemas.schedules.SCHEDULE_TYPES), nullable=False)
    active = sa.Column(sa.Boolean, nullable=False, default=True)
    max_scheduled_runs = sa.Column(sa.Integer, nullable=True)


class Deployment(Base):
    """SQLAlchemy model of a deployment."""

    name = sa.Column(sa.String, nullable=False)
    version = sa.Column(sa.String, nullable=True)
    description = sa.Column(sa.Text(), nullable=True)
    work_queue_name = sa.Column(sa.String, nullable=True, index=True)
    infra_overrides = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    path = sa.Column(sa.String, nullable=True)
    entrypoint = sa.Column(sa.String, nullable=True)

    last_polled = sa.Column(Timestamp(), nullable=True)
    status = sa.Column(
        sa.Enum(DeploymentStatus, name="deployment_status"),
        nullable=False,
        default=DeploymentStatus.NOT_READY,
        server_default="NOT_READY",
    )

    @declared_attr
    def job_variables(self):
        return synonym("infra_overrides")

    flow_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        sa.ForeignKey("flow.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    work_queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        sa.ForeignKey("work_queue.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    paused = sa.Column(
        sa.Boolean, nullable=False, server_default="0", default=False, index=True
    )

    schedules = sa.orm.relationship(
        "DeploymentSchedule",
        lazy="selectin",
        order_by=sa.desc(sa.text("updated")),
    )

    # deprecated in favor of `concurrency_limit_id` FK
    _concurrency_limit: Mapped[Union[int, None]] = mapped_column(
        sa.Integer, default=None, nullable=True, name="concurrency_limit"
    )
    concurrency_limit_id: Mapped[Union[uuid.UUID, None]] = mapped_column(
        UUID,
        sa.ForeignKey("concurrency_limit_v2.id", ondelete="SET NULL"),
        nullable=True,
    )
    global_concurrency_limit: Mapped[
        Union["ConcurrencyLimitV2", None]
    ] = sa.orm.relationship(
        lazy="selectin",
    )
    concurrency_options: Mapped[
        Union[schemas.core.ConcurrencyOptions, None]
    ] = mapped_column(
        Pydantic(schemas.core.ConcurrencyOptions),
        server_default=None,
        nullable=True,
        default=None,
    )

    tags: Mapped[List[str]] = mapped_column(
        JSON, server_default="[]", default=list, nullable=False
    )
    parameters = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    pull_steps = sa.Column(JSON, default=list, nullable=True)
    parameter_openapi_schema = sa.Column(JSON, default=dict, nullable=True)
    enforce_parameter_schema = sa.Column(
        sa.Boolean, default=True, server_default="0", nullable=False
    )
    created_by = sa.Column(
        Pydantic(schemas.core.CreatedBy),
        server_default=None,
        default=None,
        nullable=True,
    )
    updated_by = sa.Column(
        Pydantic(schemas.core.UpdatedBy),
        server_default=None,
        default=None,
        nullable=True,
    )

    infrastructure_document_id = sa.Column(
        UUID,
        sa.ForeignKey("block_document.id", ondelete="CASCADE"),
        nullable=True,
        index=False,
    )

    storage_document_id = sa.Column(
        UUID,
        sa.ForeignKey("block_document.id", ondelete="CASCADE"),
        nullable=True,
        index=False,
    )

    flow = sa.orm.relationship("Flow", back_populates="deployments", lazy="raise")

    work_queue = sa.orm.relationship(
        "WorkQueue", lazy="selectin", foreign_keys=[work_queue_id]
    )

    __table_args__ = (
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
    )


class Log(Base):
    """
    SQLAlchemy model of a logging statement.
    """

    name = sa.Column(sa.String, nullable=False)
    level = sa.Column(sa.SmallInteger, nullable=False, index=True)
    flow_run_id = sa.Column(UUID(), nullable=True, index=True)
    task_run_id = sa.Column(UUID(), nullable=True, index=True)
    message = sa.Column(sa.Text, nullable=False)

    # The client-side timestamp of this logged statement.
    timestamp = sa.Column(Timestamp(), nullable=False, index=True)

    __table_args__ = (
        sa.Index(
            "ix_log__flow_run_id_timestamp",
            "flow_run_id",
            "timestamp",
        ),
    )


class ConcurrencyLimit(Base):
    tag = sa.Column(sa.String, nullable=False)
    concurrency_limit = sa.Column(sa.Integer, nullable=False)
    active_slots: Mapped[List[str]] = mapped_column(
        JSON, server_default="[]", default=list, nullable=False
    )

    __table_args__ = (sa.Index("uq_concurrency_limit__tag", "tag", unique=True),)


class ConcurrencyLimitV2(Base):
    active = sa.Column(sa.Boolean, nullable=False, default=True)
    name = sa.Column(sa.String, nullable=False)
    limit = sa.Column(sa.Integer, nullable=False)
    active_slots = sa.Column(sa.Integer, nullable=False, default=0)
    denied_slots = sa.Column(sa.Integer, nullable=False, default=0)

    slot_decay_per_second = sa.Column(sa.Float, default=0.0, nullable=False)
    avg_slot_occupancy_seconds = sa.Column(sa.Float, default=2.0, nullable=False)

    __table_args__ = (sa.UniqueConstraint("name"),)


class BlockType(Base):
    name = sa.Column(sa.String, nullable=False)
    slug = sa.Column(sa.String, nullable=False)
    logo_url = sa.Column(sa.String, nullable=True)
    documentation_url = sa.Column(sa.String, nullable=True)
    description = sa.Column(sa.String, nullable=True)
    code_example = sa.Column(sa.String, nullable=True)
    is_protected = sa.Column(
        sa.Boolean, nullable=False, server_default="0", default=False
    )

    __table_args__ = (
        sa.Index(
            "uq_block_type__slug",
            "slug",
            unique=True,
        ),
    )


class BlockSchema(Base):
    checksum = sa.Column(sa.String, nullable=False)
    fields = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    capabilities = sa.Column(JSON, server_default="[]", default=list, nullable=False)
    version = sa.Column(
        sa.String,
        server_default=schemas.core.DEFAULT_BLOCK_SCHEMA_VERSION,
        nullable=False,
    )

    block_type_id: Mapped[UUID] = mapped_column(
        UUID(),
        sa.ForeignKey("block_type.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    block_type = sa.orm.relationship("BlockType", lazy="selectin")

    __table_args__ = (
        sa.Index(
            "uq_block_schema__checksum_version",
            "checksum",
            "version",
            unique=True,
        ),
        sa.Index("ix_block_schema__created", "created"),
    )


class BlockSchemaReference(Base):
    name = sa.Column(sa.String, nullable=False)

    parent_block_schema_id = sa.Column(
        UUID(),
        sa.ForeignKey("block_schema.id", ondelete="cascade"),
        nullable=False,
    )

    reference_block_schema_id = sa.Column(
        UUID(),
        sa.ForeignKey("block_schema.id", ondelete="cascade"),
        nullable=False,
    )


class BlockDocument(Base):
    name = sa.Column(sa.String, nullable=False, index=True)
    data = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    is_anonymous = sa.Column(sa.Boolean, server_default="0", index=True, nullable=False)

    block_type_name = sa.Column(sa.String, nullable=True)

    block_type_id = sa.Column(
        UUID(),
        sa.ForeignKey("block_type.id", ondelete="cascade"),
        nullable=False,
    )

    block_type = sa.orm.relationship("BlockType", lazy="selectin")

    block_schema_id = sa.Column(
        UUID(),
        sa.ForeignKey("block_schema.id", ondelete="cascade"),
        nullable=False,
    )

    block_schema = sa.orm.relationship("BlockSchema", lazy="selectin")

    __table_args__ = (
        sa.Index(
            "uq_block__type_id_name",
            "block_type_id",
            "name",
            unique=True,
        ),
    )

    async def encrypt_data(self, session, data):
        """
        Store encrypted data on the ORM model

        Note: will only succeed if the caller has sufficient permission.
        """
        self.data = await encrypt_fernet(session, data)

    async def decrypt_data(self, session):
        """
        Retrieve decrypted data from the ORM model.

        Note: will only succeed if the caller has sufficient permission.
        """
        return await decrypt_fernet(session, self.data)


class BlockDocumentReference(Base):
    name: Mapped[str] = mapped_column(sa.String, nullable=False)

    parent_block_document_id: Mapped[UUID] = mapped_column(
        UUID(),
        sa.ForeignKey("block_document.id", ondelete="cascade"),
        nullable=False,
    )

    reference_block_document_id: Mapped[UUID] = mapped_column(
        UUID(),
        sa.ForeignKey("block_document.id", ondelete="cascade"),
        nullable=False,
    )


class Configuration(Base):
    key = sa.Column(sa.String, nullable=False, index=True)
    value: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (sa.UniqueConstraint("key"),)


class SavedSearch(Base):
    """SQLAlchemy model of a saved search."""

    name = sa.Column(sa.String, nullable=False)
    filters = sa.Column(
        JSON,
        server_default="[]",
        default=list,
        nullable=False,
    )

    __table_args__ = (sa.UniqueConstraint("name"),)


class WorkQueue(Base):
    """SQLAlchemy model of a work queue"""

    name = sa.Column(sa.String, nullable=False)

    filter = sa.Column(
        Pydantic(schemas.core.QueueFilter),
        server_default=None,
        default=None,
        nullable=True,
    )
    description = sa.Column(sa.String, nullable=False, default="", server_default="")
    is_paused = sa.Column(sa.Boolean, nullable=False, server_default="0", default=False)
    concurrency_limit: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=True,
    )
    priority: Mapped[int] = mapped_column(sa.Integer, index=True, nullable=False)

    last_polled: Mapped[Union[pendulum.DateTime, None]] = mapped_column(
        Timestamp(),
        nullable=True,
    )
    status = sa.Column(
        sa.Enum(WorkQueueStatus, name="work_queue_status"),
        nullable=False,
        default=WorkQueueStatus.NOT_READY,
        server_default=WorkQueueStatus.NOT_READY.value,
    )

    __table_args__ = (sa.UniqueConstraint("work_pool_id", "name"),)

    work_pool_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        sa.ForeignKey("work_pool.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    work_pool = sa.orm.relationship(
        "WorkPool",
        lazy="selectin",
        foreign_keys=[work_pool_id],
    )


class WorkPool(Base):
    """SQLAlchemy model of an worker"""

    name = sa.Column(sa.String, nullable=False)
    description = sa.Column(sa.String)
    type: Mapped[str] = mapped_column(sa.String)
    base_job_template = sa.Column(JSON, nullable=False, server_default="{}", default={})
    is_paused: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default="0", default=False
    )
    default_queue_id: Mapped[UUID] = mapped_column(UUID, nullable=True)
    concurrency_limit = sa.Column(
        sa.Integer,
        nullable=True,
    )

    status: Mapped[WorkPoolStatus] = mapped_column(
        sa.Enum(WorkPoolStatus, name="work_pool_status"),
        nullable=False,
        default=WorkPoolStatus.NOT_READY,
        server_default=WorkPoolStatus.NOT_READY.value,
    )
    last_transitioned_status_at: Mapped[Union[pendulum.DateTime, None]] = mapped_column(
        Timestamp(), nullable=True
    )
    last_status_event_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=True)

    __table_args__ = (sa.UniqueConstraint("name"),)


class Worker(Base):
    """SQLAlchemy model of an worker"""

    @declared_attr
    def work_pool_id(cls):
        return sa.Column(
            UUID,
            sa.ForeignKey("work_pool.id", ondelete="cascade"),
            nullable=False,
            index=True,
        )

    name = sa.Column(sa.String, nullable=False)
    last_heartbeat_time = sa.Column(
        Timestamp(),
        nullable=False,
        server_default=now(),
        default=lambda: pendulum.now("UTC"),
        index=True,
    )
    heartbeat_interval_seconds = sa.Column(sa.Integer, nullable=True)

    status = sa.Column(
        sa.Enum(WorkerStatus, name="worker_status"),
        nullable=False,
        default=WorkerStatus.OFFLINE,
        server_default=WorkerStatus.OFFLINE.value,
    )

    __table_args__ = (sa.UniqueConstraint("work_pool_id", "name"),)


class Agent(Base):
    """SQLAlchemy model of an agent"""

    name = sa.Column(sa.String, nullable=False)

    work_queue_id = sa.Column(
        UUID,
        sa.ForeignKey("work_queue.id"),
        nullable=False,
        index=True,
    )

    last_activity_time = sa.Column(
        Timestamp(),
        nullable=False,
        server_default=now(),
        default=lambda: pendulum.now("UTC"),
    )

    __table_args__ = (sa.UniqueConstraint("name"),)


class FlowRunNotificationPolicy(Base):
    is_active = sa.Column(sa.Boolean, server_default="1", default=True, nullable=False)
    state_names = sa.Column(JSON, server_default="[]", default=[], nullable=False)
    tags: Mapped[List[str]] = mapped_column(
        JSON, server_default="[]", default=[], nullable=False
    )
    message_template = sa.Column(sa.String, nullable=True)

    block_document_id = sa.Column(
        UUID(),
        sa.ForeignKey("block_document.id", ondelete="cascade"),
        nullable=False,
    )

    block_document = sa.orm.relationship(
        "BlockDocument",
        lazy="selectin",
        foreign_keys=[block_document_id],
    )


class FlowRunNotificationQueue(Base):
    # these are both foreign keys but there is no need to enforce that constraint
    # as this is just a queue for service workers; if the keys don't match at the
    # time work is pulled, the work can be discarded
    flow_run_notification_policy_id = sa.Column(UUID, nullable=False)
    flow_run_state_id = sa.Column(UUID, nullable=False)


class Variable(Base):
    name = sa.Column(sa.String, nullable=False)
    value = sa.Column(sa.JSON, nullable=False)
    tags = sa.Column(JSON, server_default="[]", default=list, nullable=False)

    __table_args__ = (sa.UniqueConstraint("name"),)


class FlowRunInput(Base):
    flow_run_id = sa.Column(
        UUID(), sa.ForeignKey("flow_run.id", ondelete="cascade"), nullable=False
    )

    key = sa.Column(sa.String, nullable=False)
    value = sa.Column(sa.Text(), nullable=False)
    sender = sa.Column(sa.String, nullable=True)

    __table_args__ = (sa.UniqueConstraint("flow_run_id", "key"),)


class CsrfToken(Base):
    token = sa.Column(sa.String, nullable=False)
    client = sa.Column(sa.String, nullable=False, unique=True)
    expiration = sa.Column(Timestamp(), nullable=False)


class Automation(Base):
    name = sa.Column(sa.String, nullable=False)
    description = sa.Column(sa.String, nullable=False, default="")

    enabled = sa.Column(sa.Boolean, nullable=False, server_default="1", default=True)

    trigger = sa.Column(Pydantic(ServerTriggerTypes), nullable=False)

    actions = sa.Column(Pydantic(List[ServerActionTypes]), nullable=False)
    actions_on_trigger = sa.Column(
        Pydantic(List[ServerActionTypes]),
        server_default="[]",
        default=list,
        nullable=False,
    )
    actions_on_resolve = sa.Column(
        Pydantic(List[ServerActionTypes]),
        server_default="[]",
        default=list,
        nullable=False,
    )

    related_resources = sa.orm.relationship(
        "AutomationRelatedResource", back_populates="automation", lazy="raise"
    )

    @classmethod
    def sort_expression(cls, value: AutomationSort) -> ColumnElement:
        """Return an expression used to sort Automations"""
        sort_mapping = {
            AutomationSort.CREATED_DESC: cls.created.desc(),
            AutomationSort.UPDATED_DESC: cls.updated.desc(),
            AutomationSort.NAME_ASC: cast(sa.Column, cls.name).asc(),
            AutomationSort.NAME_DESC: cast(sa.Column, cls.name).desc(),
        }
        return sort_mapping[value]


class AutomationBucket(Base):
    __table_args__ = (
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

    automation_id = sa.Column(
        UUID(), sa.ForeignKey("automation.id", ondelete="CASCADE"), nullable=False
    )

    trigger_id = sa.Column(UUID, nullable=False)

    bucketing_key = sa.Column(JSON, server_default="[]", default=list, nullable=False)

    last_event = sa.Column(Pydantic(ReceivedEvent), nullable=True)

    start = sa.Column(Timestamp(), nullable=False)
    end = sa.Column(Timestamp(), nullable=False)

    count = sa.Column(sa.Integer, nullable=False)

    last_operation = sa.Column(sa.String, nullable=True)

    triggered_at = sa.Column(Timestamp(), nullable=True)


class AutomationRelatedResource(Base):
    __table_args__ = (
        sa.Index(
            "uq_automation_related_resource__automation_id__resource_id",
            "automation_id",
            "resource_id",
            unique=True,
        ),
    )

    automation_id = sa.Column(
        UUID(), sa.ForeignKey("automation.id", ondelete="CASCADE"), nullable=False
    )

    resource_id = sa.Column(sa.String, index=True)
    automation_owned_by_resource = sa.Column(
        sa.Boolean, nullable=False, default=False, server_default="0"
    )

    automation = sa.orm.relationship(
        "Automation", back_populates="related_resources", lazy="raise"
    )


class CompositeTriggerChildFiring(Base):
    __table_args__ = (
        sa.Index(
            "uq_composite_trigger_child_firing__a_id__pt_id__ct__id",
            "automation_id",
            "parent_trigger_id",
            "child_trigger_id",
            unique=True,
        ),
    )

    automation_id = sa.Column(
        UUID(), sa.ForeignKey("automation.id", ondelete="CASCADE"), nullable=False
    )

    parent_trigger_id = sa.Column(UUID(), nullable=False)

    child_trigger_id = sa.Column(UUID(), nullable=False)
    child_firing_id = sa.Column(UUID(), nullable=False)
    child_fired_at = sa.Column(Timestamp())
    child_firing = sa.Column(Pydantic(Firing), nullable=False)


class AutomationEventFollower(Base):
    __table_args__ = (
        sa.Index(
            "uq_follower_for_scope",
            "scope",
            "follower_event_id",
            unique=True,
        ),
    )
    scope = sa.Column(sa.String, nullable=False, default="", index=True)
    leader_event_id = sa.Column(UUID(), nullable=False, index=True)
    follower_event_id = sa.Column(UUID(), nullable=False)
    received = sa.Column(Timestamp(), nullable=False, index=True)
    follower = sa.Column(Pydantic(ReceivedEvent), nullable=False)


class Event(Base):
    @declared_attr
    def __tablename__(cls):
        return "events"

    __table_args__ = (
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

    occurred = sa.Column(Timestamp(), nullable=False)
    event = sa.Column(sa.Text(), nullable=False)
    resource_id = sa.Column(sa.Text(), nullable=False)
    resource = sa.Column(JSON(), nullable=False)
    related_resource_ids = sa.Column(
        JSON(), server_default="[]", default=list, nullable=False
    )
    related = sa.Column(JSON(), server_default="[]", default=list, nullable=False)
    payload = sa.Column(JSON(), nullable=False)
    received = sa.Column(Timestamp(), nullable=False)
    recorded = sa.Column(Timestamp(), nullable=False)
    follows = sa.Column(UUID(), nullable=True)


class EventResource(Base):
    @declared_attr
    def __tablename__(cls):
        return "event_resources"

    __table_args__ = (
        sa.Index(
            "ix_event_resources__resource_id__occurred",
            "resource_id",
            "occurred",
        ),
    )

    occurred = sa.Column("occurred", Timestamp(), nullable=False)
    resource_id = sa.Column("resource_id", sa.Text(), nullable=False)
    resource_role = sa.Column("resource_role", sa.Text(), nullable=False)
    resource = sa.Column("resource", sa.JSON(), nullable=False)
    event_id = sa.Column("event_id", UUID(), nullable=False)


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


class BaseORMConfiguration(ABC):
    """
    Abstract base class used to inject database-specific ORM configuration into Prefect.

    Modifications to core Prefect REST API data structures can have unintended consequences.
    Use with caution.
    """

    def _unique_key(self) -> Tuple[Hashable, ...]:
        """
        Returns a key used to determine whether to instantiate a new DB interface.
        """
        return (self.__class__, Base.metadata)

    @property
    @abstractmethod
    def versions_dir(self):
        """Directory containing migrations"""
        ...

    @property
    def deployment_unique_upsert_columns(self):
        """Unique columns for upserting a Deployment"""
        return [Deployment.flow_id, Deployment.name]

    @property
    def concurrency_limit_unique_upsert_columns(self):
        """Unique columns for upserting a ConcurrencyLimit"""
        return [ConcurrencyLimit.tag]

    @property
    def flow_run_unique_upsert_columns(self):
        """Unique columns for upserting a FlowRun"""
        return [FlowRun.flow_id, FlowRun.idempotency_key]

    @property
    def block_type_unique_upsert_columns(self):
        """Unique columns for upserting a BlockType"""
        return [BlockType.slug]

    @property
    def artifact_collection_unique_upsert_columns(self):
        """Unique columns for upserting an ArtifactCollection"""
        return [ArtifactCollection.key]

    @property
    def block_schema_unique_upsert_columns(self):
        """Unique columns for upserting a BlockSchema"""
        return [BlockSchema.checksum, BlockSchema.version]

    @property
    def flow_unique_upsert_columns(self):
        """Unique columns for upserting a Flow"""
        return [Flow.name]

    @property
    def saved_search_unique_upsert_columns(self):
        """Unique columns for upserting a SavedSearch"""
        return [SavedSearch.name]

    @property
    def task_run_unique_upsert_columns(self):
        """Unique columns for upserting a TaskRun"""
        return [
            TaskRun.flow_run_id,
            TaskRun.task_key,
            TaskRun.dynamic_key,
        ]

    @property
    def block_document_unique_upsert_columns(self):
        """Unique columns for upserting a BlockDocument"""
        return [BlockDocument.block_type_id, BlockDocument.name]


class AsyncPostgresORMConfiguration(BaseORMConfiguration):
    """Postgres specific orm configuration"""

    @property
    def versions_dir(self) -> Path:
        """Directory containing migrations"""
        return (
            Path(prefect.server.database.__file__).parent
            / "migrations"
            / "versions"
            / "postgresql"
        )


class AioSqliteORMConfiguration(BaseORMConfiguration):
    """SQLite specific orm configuration"""

    @property
    def versions_dir(self) -> Path:
        """Directory containing migrations"""
        return (
            Path(prefect.server.database.__file__).parent
            / "migrations"
            / "versions"
            / "sqlite"
        )
