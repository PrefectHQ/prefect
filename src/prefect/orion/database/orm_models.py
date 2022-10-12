import datetime
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Hashable, List, Tuple, Union

import pendulum
import sqlalchemy as sa
from sqlalchemy import FetchedValue
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import as_declarative, declarative_mixin, declared_attr

import prefect
import prefect.orion.schemas as schemas
from prefect.orion.utilities.database import (
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
from prefect.orion.utilities.encryption import decrypt_fernet, encrypt_fernet
from prefect.orion.utilities.names import generate_slug


class ORMBase:
    """
    Base SQLAlchemy model that automatically infers the table name
    and provides ID, created, and updated columns
    """

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

    id = sa.Column(
        UUID(),
        primary_key=True,
        server_default=GenerateUUID(),
        default=uuid.uuid4,
    )

    created = sa.Column(
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


@declarative_mixin
class ORMFlow:
    """SQLAlchemy mixin of a flow."""

    name = sa.Column(sa.String, nullable=False)
    tags = sa.Column(JSON, server_default="[]", default=list, nullable=False)

    @declared_attr
    def flow_runs(cls):
        return sa.orm.relationship("FlowRun", back_populates="flow", lazy="raise")

    @declared_attr
    def deployments(cls):
        return sa.orm.relationship("Deployment", back_populates="flow", lazy="raise")

    @declared_attr
    def __table_args__(cls):
        return (sa.UniqueConstraint("name"), sa.Index("ix_flow__created", "created"))


@declarative_mixin
class ORMFlowRunState:
    """SQLAlchemy mixin of a flow run state."""

    # this column isn't explicitly indexed because it is included in
    # the unique compound index on (flow_run_id, timestamp)
    @declared_attr
    def flow_run_id(cls):
        return sa.Column(
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
    data = sa.Column(sa.JSON, nullable=True)

    @declared_attr
    def flow_run(cls):
        return sa.orm.relationship(
            "FlowRun",
            lazy="raise",
            foreign_keys=[cls.flow_run_id],
        )

    def as_state(self) -> schemas.states.State:
        return schemas.states.State.from_orm(self)

    @declared_attr
    def __table_args__(cls):
        return (
            sa.Index(
                "uq_flow_run_state__flow_run_id_timestamp_desc",
                "flow_run_id",
                sa.desc("timestamp"),
                unique=True,
            ),
        )


@declarative_mixin
class ORMTaskRunState:
    """SQLAlchemy model of a task run state."""

    # this column isn't explicitly indexed because it is included in
    # the unique compound index on (task_run_id, timestamp)
    @declared_attr
    def task_run_id(cls):
        return sa.Column(
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
    data = sa.Column(sa.JSON, nullable=True)

    @declared_attr
    def task_run(cls):
        return sa.orm.relationship(
            "TaskRun",
            lazy="raise",
            foreign_keys=[cls.task_run_id],
        )

    def as_state(self) -> schemas.states.State:
        return schemas.states.State.from_orm(self)

    @declared_attr
    def __table_args__(cls):
        return (
            sa.Index(
                "uq_task_run_state__task_run_id_timestamp_desc",
                "task_run_id",
                sa.desc("timestamp"),
                unique=True,
            ),
        )


class ORMTaskRunStateCache:
    """
    SQLAlchemy model of a task run state cache.
    """

    cache_key = sa.Column(sa.String, nullable=False)
    cache_expiration = sa.Column(
        Timestamp(),
        nullable=True,
    )
    task_run_state_id = sa.Column(UUID(), nullable=False)

    @declared_attr
    def __table_args__(cls):
        return (
            sa.Index(
                "ix_task_run_state_cache__cache_key_created_desc",
                "cache_key",
                sa.desc("created"),
            ),
        )


@declarative_mixin
class ORMRun:
    """
    Common columns and logic for FlowRun and TaskRun models
    """

    name = sa.Column(
        sa.String,
        default=lambda: generate_slug(2),
        nullable=False,
        index=True,
    )
    state_type = sa.Column(sa.Enum(schemas.states.StateType, name="state_type"))
    state_name = sa.Column(sa.String, nullable=True)
    state_timestamp = sa.Column(Timestamp(), nullable=True)
    run_count = sa.Column(sa.Integer, server_default="0", default=0, nullable=False)
    expected_start_time = sa.Column(Timestamp())
    next_scheduled_start_time = sa.Column(Timestamp())
    start_time = sa.Column(Timestamp())
    end_time = sa.Column(Timestamp())
    total_run_time = sa.Column(
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
            return self.total_run_time + (pendulum.now() - self.state_timestamp)
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
            .correlate(cls).label("estimated_run_time")
        )

    @hybrid_property
    def estimated_start_time_delta(self) -> datetime.timedelta:
        """The delta to the expected start time (or "lateness") is computed as
        the difference between the actual start time and expected start time. To
        give up-to-date estimates, we estimate lateness for any runs that don't
        have a start time and are not in a final state and were expected to
        start already."""
        if self.start_time and self.start_time > self.expected_start_time:
            return (self.start_time - self.expected_start_time).as_interval()
        elif (
            self.start_time is None
            and self.expected_start_time
            and self.expected_start_time < pendulum.now("UTC")
            and self.state_type not in schemas.states.TERMINAL_STATES
        ):
            return (pendulum.now("UTC") - self.expected_start_time).as_interval()
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


@declarative_mixin
class ORMFlowRun(ORMRun):
    """SQLAlchemy model of a flow run."""

    @declared_attr
    def flow_id(cls):
        return sa.Column(
            UUID(),
            sa.ForeignKey("flow.id", ondelete="cascade"),
            nullable=False,
            index=True,
        )

    @declared_attr
    def deployment_id(cls):
        return sa.Column(
            UUID(), sa.ForeignKey("deployment.id", ondelete="set null"), index=True
        )

    work_queue_name = sa.Column(sa.String, index=True)
    flow_version = sa.Column(sa.String, index=True)
    parameters = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    idempotency_key = sa.Column(sa.String)
    context = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    empirical_policy = sa.Column(
        Pydantic(schemas.core.FlowRunPolicy),
        server_default="{}",
        default=schemas.core.FlowRunPolicy,
        nullable=False,
    )
    tags = sa.Column(JSON, server_default="[]", default=list, nullable=False)

    @declared_attr
    def infrastructure_document_id(cls):
        return sa.Column(
            UUID,
            sa.ForeignKey("block_document.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        )

    @declared_attr
    def parent_task_run_id(cls):
        return sa.Column(
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
    @declared_attr
    def state_id(cls):
        return sa.Column(
            UUID(),
            sa.ForeignKey(
                "flow_run_state.id",
                ondelete="SET NULL",
                use_alter=True,
            ),
            index=True,
        )

    # -------------------------- relationships

    # current states are eagerly loaded unless otherwise specified
    @declared_attr
    def _state(cls):
        return sa.orm.relationship(
            "FlowRunState",
            lazy="joined",
            foreign_keys=[cls.state_id],
            primaryjoin="FlowRunState.id==%s.state_id" % cls.__name__,
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

    @declared_attr
    def flow(cls):
        return sa.orm.relationship("Flow", back_populates="flow_runs", lazy="raise")

    @declared_attr
    def task_runs(cls):
        return sa.orm.relationship(
            "TaskRun",
            back_populates="flow_run",
            lazy="raise",
            # foreign_keys=lambda: [cls.flow_run_id],
            primaryjoin="TaskRun.flow_run_id==%s.id" % cls.__name__,
        )

    @declared_attr
    def parent_task_run(cls):
        return sa.orm.relationship(
            "TaskRun",
            back_populates="subflow_run",
            lazy="raise",
            foreign_keys=lambda: [cls.parent_task_run_id],
        )

    @declared_attr
    def __table_args__(cls):
        return (
            sa.Index(
                "uq_flow_run__flow_id_idempotency_key",
                "flow_id",
                "idempotency_key",
                unique=True,
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


@declarative_mixin
class ORMTaskRun(ORMRun):
    """SQLAlchemy model of a task run."""

    @declared_attr
    def flow_run_id(cls):
        return sa.Column(
            UUID(),
            sa.ForeignKey("flow_run.id", ondelete="cascade"),
            nullable=False,
            index=True,
        )

    task_key = sa.Column(sa.String, nullable=False)
    dynamic_key = sa.Column(sa.String, nullable=False)
    cache_key = sa.Column(sa.String)
    cache_expiration = sa.Column(Timestamp())
    task_version = sa.Column(sa.String)
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
    tags = sa.Column(JSON, server_default="[]", default=list, nullable=False)

    # TODO remove this foreign key for significant delete performance gains
    @declared_attr
    def state_id(cls):
        return sa.Column(
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
    @declared_attr
    def _state(cls):
        return sa.orm.relationship(
            "TaskRunState",
            lazy="joined",
            foreign_keys=[cls.state_id],
            primaryjoin="TaskRunState.id==%s.state_id" % cls.__name__,
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

    @declared_attr
    def flow_run(cls):
        return sa.orm.relationship(
            "FlowRun",
            back_populates="task_runs",
            lazy="raise",
            foreign_keys=[cls.flow_run_id],
        )

    @declared_attr
    def subflow_run(cls):
        return sa.orm.relationship(
            "FlowRun",
            back_populates="parent_task_run",
            lazy="raise",
            # foreign_keys=["FlowRun.parent_task_run_id"],
            primaryjoin="FlowRun.parent_task_run_id==%s.id" % cls.__name__,
            uselist=False,
        )

    @declared_attr
    def __table_args__(cls):
        return (
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
        )


@declarative_mixin
class ORMDeployment:
    """SQLAlchemy model of a deployment."""

    name = sa.Column(sa.String, nullable=False)
    version = sa.Column(sa.String, nullable=True)
    description = sa.Column(sa.Text(), nullable=True)
    manifest_path = sa.Column(sa.String, nullable=True)
    work_queue_name = sa.Column(sa.String, nullable=True, index=True)
    infra_overrides = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    path = sa.Column(sa.String, nullable=True)
    entrypoint = sa.Column(sa.String, nullable=True)

    @declared_attr
    def flow_id(cls):
        return sa.Column(
            UUID,
            sa.ForeignKey("flow.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )

    schedule = sa.Column(Pydantic(schemas.schedules.SCHEDULE_TYPES))
    is_schedule_active = sa.Column(
        sa.Boolean, nullable=False, server_default="1", default=True
    )
    tags = sa.Column(JSON, server_default="[]", default=list, nullable=False)
    parameters = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    parameter_openapi_schema = sa.Column(JSON, default=dict, nullable=True)

    @declared_attr
    def infrastructure_document_id(cls):
        return sa.Column(
            UUID,
            sa.ForeignKey("block_document.id", ondelete="CASCADE"),
            nullable=True,
            index=False,
        )

    @declared_attr
    def storage_document_id(cls):
        return sa.Column(
            UUID,
            sa.ForeignKey("block_document.id", ondelete="CASCADE"),
            nullable=True,
            index=False,
        )

    @declared_attr
    def flow(cls):
        return sa.orm.relationship("Flow", back_populates="deployments", lazy="raise")

    @declared_attr
    def __table_args__(cls):
        return (
            sa.Index(
                "uq_deployment__flow_id_name",
                "flow_id",
                "name",
                unique=True,
            ),
        )


@declarative_mixin
class ORMLog:
    """
    SQLAlchemy model of a logging statement.
    """

    name = sa.Column(sa.String, nullable=False)
    level = sa.Column(sa.SmallInteger, nullable=False, index=True)
    flow_run_id = sa.Column(UUID(), nullable=False, index=True)
    task_run_id = sa.Column(UUID(), nullable=True, index=True)
    message = sa.Column(sa.Text, nullable=False)

    # The client-side timestamp of this logged statement.
    timestamp = sa.Column(Timestamp(), nullable=False, index=True)


@declarative_mixin
class ORMConcurrencyLimit:
    tag = sa.Column(sa.String, nullable=False)
    concurrency_limit = sa.Column(sa.Integer, nullable=False)
    active_slots = sa.Column(JSON, server_default="[]", default=list, nullable=False)

    @declared_attr
    def __table_args__(cls):
        return (sa.Index("uq_concurrency_limit__tag", "tag", unique=True),)


@declarative_mixin
class ORMBlockType:
    name = sa.Column(sa.String, nullable=False)
    slug = sa.Column(sa.String, nullable=False)
    logo_url = sa.Column(sa.String, nullable=True)
    documentation_url = sa.Column(sa.String, nullable=True)
    description = sa.Column(sa.String, nullable=True)
    code_example = sa.Column(sa.String, nullable=True)
    is_protected = sa.Column(
        sa.Boolean, nullable=False, server_default="0", default=False
    )

    @declared_attr
    def __table_args__(cls):
        return (
            sa.Index(
                "uq_block_type__slug",
                "slug",
                unique=True,
            ),
        )


@declarative_mixin
class ORMBlockSchema:
    checksum = sa.Column(sa.String, nullable=False)
    fields = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    capabilities = sa.Column(JSON, server_default="[]", default=list, nullable=False)
    version = sa.Column(
        sa.String,
        server_default=schemas.core.DEFAULT_BLOCK_SCHEMA_VERSION,
        nullable=False,
    )

    @declared_attr
    def block_type_id(cls):
        return sa.Column(
            UUID(),
            sa.ForeignKey("block_type.id", ondelete="cascade"),
            nullable=False,
            index=True,
        )

    @declared_attr
    def block_type(cls):
        return sa.orm.relationship("BlockType", lazy="joined")

    @declared_attr
    def __table_args__(cls):
        return (
            sa.Index(
                "uq_block_schema__checksum_version",
                "checksum",
                "version",
                unique=True,
            ),
            sa.Index("ix_block_schema__created", "created"),
        )


@declarative_mixin
class ORMBlockSchemaReference:
    name = sa.Column(sa.String, nullable=False)

    @declared_attr
    def parent_block_schema_id(cls):
        return sa.Column(
            UUID(),
            sa.ForeignKey("block_schema.id", ondelete="cascade"),
            nullable=False,
        )

    @declared_attr
    def reference_block_schema_id(cls):
        return sa.Column(
            UUID(),
            sa.ForeignKey("block_schema.id", ondelete="cascade"),
            nullable=False,
        )


@declarative_mixin
class ORMBlockDocument:
    name = sa.Column(sa.String, nullable=False, index=True)
    data = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    is_anonymous = sa.Column(sa.Boolean, server_default="0", index=True, nullable=False)

    @declared_attr
    def block_type_id(cls):
        return sa.Column(
            UUID(),
            sa.ForeignKey("block_type.id", ondelete="cascade"),
            nullable=False,
        )

    @declared_attr
    def block_type(cls):
        return sa.orm.relationship("BlockType", lazy="joined")

    @declared_attr
    def block_schema_id(cls):
        return sa.Column(
            UUID(),
            sa.ForeignKey("block_schema.id", ondelete="cascade"),
            nullable=False,
        )

    @declared_attr
    def block_schema(cls):
        return sa.orm.relationship("BlockSchema", lazy="joined")

    @declared_attr
    def __table_args__(cls):
        return (
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


@declarative_mixin
class ORMBlockDocumentReference:
    name = sa.Column(sa.String, nullable=False)

    @declared_attr
    def parent_block_document_id(cls):
        return sa.Column(
            UUID(),
            sa.ForeignKey("block_document.id", ondelete="cascade"),
            nullable=False,
        )

    @declared_attr
    def reference_block_document_id(cls):
        return sa.Column(
            UUID(),
            sa.ForeignKey("block_document.id", ondelete="cascade"),
            nullable=False,
        )


@declarative_mixin
class ORMConfiguration:
    key = sa.Column(sa.String, nullable=False, index=True)
    value = sa.Column(JSON, nullable=False)

    @declared_attr
    def __table_args__(cls):
        return (sa.UniqueConstraint("key"),)


@declarative_mixin
class ORMSavedSearch:
    """SQLAlchemy model of a saved search."""

    name = sa.Column(sa.String, nullable=False)
    filters = sa.Column(
        JSON,
        server_default="[]",
        default=list,
        nullable=False,
    )

    @declared_attr
    def __table_args__(cls):
        return (sa.UniqueConstraint("name"),)


@declarative_mixin
class ORMWorkQueue:
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
    concurrency_limit = sa.Column(
        sa.Integer,
        nullable=True,
    )

    @declared_attr
    def __table_args__(cls):
        return (sa.UniqueConstraint("name"),)


@declarative_mixin
class ORMAgent:
    """SQLAlchemy model of an agent"""

    name = sa.Column(sa.String, nullable=False)

    @declared_attr
    def work_queue_id(cls):
        return sa.Column(
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

    @declared_attr
    def __table_args__(cls):
        return (sa.UniqueConstraint("name"),)


@declarative_mixin
class ORMFlowRunNotificationPolicy:
    is_active = sa.Column(sa.Boolean, server_default="1", default=True, nullable=False)
    state_names = sa.Column(JSON, server_default="[]", default=[], nullable=False)
    tags = sa.Column(JSON, server_default="[]", default=[], nullable=False)
    message_template = sa.Column(sa.String, nullable=True)

    @declared_attr
    def block_document_id(cls):
        return sa.Column(
            UUID(),
            sa.ForeignKey("block_document.id", ondelete="cascade"),
            nullable=False,
        )

    @declared_attr
    def block_document(cls):
        return sa.orm.relationship(
            "BlockDocument",
            lazy="joined",
            foreign_keys=[cls.block_document_id],
        )


@declarative_mixin
class ORMFlowRunNotificationQueue:
    # these are both foreign keys but there is no need to enforce that constraint
    # as this is just a queue for service workers; if the keys don't match at the
    # time work is pulled, the work can be discarded
    flow_run_notification_policy_id = sa.Column(UUID, nullable=False)
    flow_run_state_id = sa.Column(UUID, nullable=False)


class BaseORMConfiguration(ABC):
    """
    Abstract base class used to inject database-specific ORM configuration into Orion.

    Modifications to core Orion data structures can have unintended consequences.
    Use with caution.

    Args:
        base_metadata: sqlalchemy.schema.Metadata used to create the Base orm class
        base_model_mixins: a list of mixins to add to the Base orm model
        flow_mixin: flow orm mixin, combined with Base orm class
        flow_run_mixin: flow run orm mixin, combined with Base orm class
        flow_run_state_mixin: flow run state mixin, combined with Base orm class
        task_run_mixin: task run mixin, combined with Base orm class
        task_run_state_mixin: task run state, combined with Base orm class
        task_run_state_cache_mixin: task run state cache orm mixin, combined with Base orm class
        deployment_mixin: deployment orm mixin, combined with Base orm class
        saved_search_mixin: saved search orm mixin, combined with Base orm class
        log_mixin: log orm mixin, combined with Base orm class
        concurrency_limit_mixin: concurrency limit orm mixin, combined with Base orm class
        block_type_mixin: block_type orm mixin, combined with Base orm class
        block_schema_mixin: block_schema orm mixin, combined with Base orm class
        block_schema_reference_mixin: block_schema_reference orm mixin, combined with Base orm class
        block_document_mixin: block_document orm mixin, combined with Base orm class
        block_document_reference_mixin: block_document_reference orm mixin, combined with Base orm class
        configuration_mixin: configuration orm mixin, combined with Base orm class

    """

    def __init__(
        self,
        base_metadata: sa.schema.MetaData = None,
        base_model_mixins: List = None,
        flow_mixin=ORMFlow,
        flow_run_mixin=ORMFlowRun,
        flow_run_state_mixin=ORMFlowRunState,
        task_run_mixin=ORMTaskRun,
        task_run_state_mixin=ORMTaskRunState,
        task_run_state_cache_mixin=ORMTaskRunStateCache,
        deployment_mixin=ORMDeployment,
        saved_search_mixin=ORMSavedSearch,
        log_mixin=ORMLog,
        concurrency_limit_mixin=ORMConcurrencyLimit,
        work_queue_mixin=ORMWorkQueue,
        agent_mixin=ORMAgent,
        block_type_mixin=ORMBlockType,
        block_schema_mixin=ORMBlockSchema,
        block_schema_reference_mixin=ORMBlockSchemaReference,
        block_document_mixin=ORMBlockDocument,
        block_document_reference_mixin=ORMBlockDocumentReference,
        configuration_mixin=ORMConfiguration,
    ):
        self.base_metadata = base_metadata or sa.schema.MetaData(
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
        )
        self.base_model_mixins = base_model_mixins or []

        self._create_base_model()
        self._create_orm_models(
            flow_mixin=flow_mixin,
            flow_run_mixin=flow_run_mixin,
            flow_run_state_mixin=flow_run_state_mixin,
            task_run_mixin=task_run_mixin,
            task_run_state_mixin=task_run_state_mixin,
            task_run_state_cache_mixin=task_run_state_cache_mixin,
            deployment_mixin=deployment_mixin,
            saved_search_mixin=saved_search_mixin,
            log_mixin=log_mixin,
            concurrency_limit_mixin=concurrency_limit_mixin,
            work_queue_mixin=work_queue_mixin,
            agent_mixin=agent_mixin,
            block_type_mixin=block_type_mixin,
            block_schema_mixin=block_schema_mixin,
            block_schema_reference_mixin=block_schema_reference_mixin,
            block_document_mixin=block_document_mixin,
            block_document_reference_mixin=block_document_reference_mixin,
            configuration_mixin=configuration_mixin,
        )

    def _unique_key(self) -> Tuple[Hashable, ...]:
        """
        Returns a key used to determine whether to instantiate a new DB interface.
        """
        return (self.__class__, self.base_metadata, tuple(self.base_model_mixins))

    def _create_base_model(self):
        """
        Defines the base ORM model and binds it to `self`. The base model will be
        extended by mixins specified in the database configuration. This method only
        runs on instantiation.
        """

        @as_declarative(metadata=self.base_metadata)
        class Base(*self.base_model_mixins, ORMBase):
            pass

        self.Base = Base

    def _create_orm_models(
        self,
        flow_mixin=ORMFlow,
        flow_run_mixin=ORMFlowRun,
        flow_run_state_mixin=ORMFlowRunState,
        task_run_mixin=ORMTaskRun,
        task_run_state_mixin=ORMTaskRunState,
        task_run_state_cache_mixin=ORMTaskRunStateCache,
        deployment_mixin=ORMDeployment,
        saved_search_mixin=ORMSavedSearch,
        log_mixin=ORMLog,
        concurrency_limit_mixin=ORMConcurrencyLimit,
        work_queue_mixin=ORMWorkQueue,
        agent_mixin=ORMAgent,
        block_type_mixin=ORMBlockType,
        block_schema_mixin=ORMBlockSchema,
        block_schema_reference_mixin=ORMBlockSchemaReference,
        block_document_mixin=ORMBlockDocument,
        block_document_reference_mixin=ORMBlockDocumentReference,
        flow_run_notification_policy_mixin=ORMFlowRunNotificationPolicy,
        flow_run_notification_queue_mixin=ORMFlowRunNotificationQueue,
        configuration_mixin=ORMConfiguration,
    ):
        """
        Defines the ORM models used in Orion and binds them to the `self`. This method
        only runs on instantiation.
        """

        class Flow(flow_mixin, self.Base):
            pass

        class FlowRunState(flow_run_state_mixin, self.Base):
            pass

        class TaskRunState(task_run_state_mixin, self.Base):
            pass

        class TaskRunStateCache(task_run_state_cache_mixin, self.Base):
            pass

        class FlowRun(flow_run_mixin, self.Base):
            pass

        class TaskRun(task_run_mixin, self.Base):
            pass

        class Deployment(deployment_mixin, self.Base):
            pass

        class SavedSearch(saved_search_mixin, self.Base):
            pass

        class Log(log_mixin, self.Base):
            pass

        class ConcurrencyLimit(concurrency_limit_mixin, self.Base):
            pass

        class WorkQueue(work_queue_mixin, self.Base):
            pass

        class Agent(agent_mixin, self.Base):
            pass

        class BlockType(block_type_mixin, self.Base):
            pass

        class BlockSchema(block_schema_mixin, self.Base):
            pass

        class BlockSchemaReference(block_schema_reference_mixin, self.Base):
            pass

        class BlockDocument(block_document_mixin, self.Base):
            pass

        class BlockDocumentReference(block_document_reference_mixin, self.Base):
            pass

        class FlowRunNotificationPolicy(flow_run_notification_policy_mixin, self.Base):
            pass

        class FlowRunNotificationQueue(flow_run_notification_queue_mixin, self.Base):
            pass

        class Configuration(configuration_mixin, self.Base):
            pass

        self.Flow = Flow
        self.FlowRunState = FlowRunState
        self.TaskRunState = TaskRunState
        self.TaskRunStateCache = TaskRunStateCache
        self.FlowRun = FlowRun
        self.TaskRun = TaskRun
        self.Deployment = Deployment
        self.SavedSearch = SavedSearch
        self.Log = Log
        self.ConcurrencyLimit = ConcurrencyLimit
        self.WorkQueue = WorkQueue
        self.Agent = Agent
        self.BlockType = BlockType
        self.BlockSchema = BlockSchema
        self.BlockSchemaReference = BlockSchemaReference
        self.BlockDocument = BlockDocument
        self.BlockDocumentReference = BlockDocumentReference
        self.FlowRunNotificationPolicy = FlowRunNotificationPolicy
        self.FlowRunNotificationQueue = FlowRunNotificationQueue
        self.Configuration = Configuration

    @property
    @abstractmethod
    def versions_dir(self):
        """Directory containing migrations"""
        ...

    @property
    def deployment_unique_upsert_columns(self):
        """Unique columns for upserting a Deployment"""
        return [self.Deployment.flow_id, self.Deployment.name]

    @property
    def concurrency_limit_unique_upsert_columns(self):
        """Unique columns for upserting a ConcurrencyLimit"""
        return [self.ConcurrencyLimit.tag]

    @property
    def flow_run_unique_upsert_columns(self):
        """Unique columns for upserting a FlowRun"""
        return [self.FlowRun.flow_id, self.FlowRun.idempotency_key]

    @property
    def block_type_unique_upsert_columns(self):
        """Unique columns for upserting a BlockType"""
        return [self.BlockType.slug]

    @property
    def block_schema_unique_upsert_columns(self):
        """Unique columns for upserting a BlockSchema"""
        return [self.BlockSchema.checksum, self.BlockSchema.version]

    @property
    def flow_unique_upsert_columns(self):
        """Unique columns for upserting a Flow"""
        return [self.Flow.name]

    @property
    def saved_search_unique_upsert_columns(self):
        """Unique columns for upserting a SavedSearch"""
        return [self.SavedSearch.name]

    @property
    def task_run_unique_upsert_columns(self):
        """Unique columns for upserting a TaskRun"""
        return [
            self.TaskRun.flow_run_id,
            self.TaskRun.task_key,
            self.TaskRun.dynamic_key,
        ]

    @property
    def block_document_unique_upsert_columns(self):
        """Unique columns for upserting a BlockDocument"""
        return [self.BlockDocument.block_type_id, self.BlockDocument.name]


class AsyncPostgresORMConfiguration(BaseORMConfiguration):
    """Postgres specific orm configuration"""

    @property
    def versions_dir(self) -> Path:
        """Directory containing migrations"""
        return (
            Path(prefect.orion.database.__file__).parent
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
            Path(prefect.orion.database.__file__).parent
            / "migrations"
            / "versions"
            / "sqlite"
        )
