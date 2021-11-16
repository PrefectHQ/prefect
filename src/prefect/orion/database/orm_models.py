import datetime
import uuid
from abc import ABC, abstractmethod
from typing import List, Union, Dict, Tuple, Hashable
from coolname import generate_slug

import pendulum
import sqlalchemy as sa
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declared_attr, declarative_mixin, as_declarative
from prefect.orion.schemas import core, data, schedules, states
from prefect.orion.utilities.database import (
    UUID,
    Timestamp,
    now,
    GenerateUUID,
    camel_to_snake,
    JSON,
    Pydantic,
    interval_add,
    date_diff,
)


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
    )


@declarative_mixin
class ORMFlow:
    """SQLAlchemy mixin of a flow."""

    name = sa.Column(sa.String, nullable=False, unique=True)
    tags = sa.Column(JSON, server_default="[]", default=list, nullable=False)

    @declared_attr
    def flow_runs(cls):
        return sa.orm.relationship("FlowRun", back_populates="flow", lazy="raise")

    @declared_attr
    def deployments(cls):
        return sa.orm.relationship("Deployment", back_populates="flow", lazy="raise")


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
        sa.Enum(states.StateType, name="state_type"), nullable=False, index=True
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
        Pydantic(states.StateDetails),
        server_default="{}",
        default=states.StateDetails,
        nullable=False,
    )
    data = sa.Column(Pydantic(data.DataDocument), nullable=True)

    @declared_attr
    def flow_run(cls):
        return sa.orm.relationship(
            "FlowRun",
            lazy="raise",
            foreign_keys=[cls.flow_run_id],
        )

    def as_state(self) -> states.State:
        return states.State.from_orm(self)


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
        sa.Enum(states.StateType, name="state_type"), nullable=False, index=True
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
        Pydantic(states.StateDetails),
        server_default="{}",
        default=states.StateDetails,
        nullable=False,
    )
    data = sa.Column(Pydantic(data.DataDocument), nullable=True)

    @declared_attr
    def task_run(cls):
        return sa.orm.relationship(
            "TaskRun",
            lazy="raise",
            foreign_keys=[cls.task_run_id],
        )

    def as_state(self) -> states.State:
        return states.State.from_orm(self)


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
    state_type = sa.Column(sa.Enum(states.StateType, name="state_type"))
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
        if self.state and self.state_type == states.StateType.RUNNING:
            return self.total_run_time + (pendulum.now() - self.state.timestamp)
        else:
            return self.total_run_time

    @estimated_run_time.expression
    def estimated_run_time(cls):
        # use a correlated subquery to retrieve details from the state table
        state_table = cls.state.property.target
        return (
            sa.select(
                sa.case(
                    (
                        cls.state_type == states.StateType.RUNNING,
                        interval_add(
                            cls.total_run_time,
                            date_diff(now(), state_table.c.timestamp),
                        ),
                    ),
                    else_=cls.total_run_time,
                )
            )
            .select_from(state_table)
            .where(cls.state_id == state_table.c.id)
            # add a correlate statement so this can reuse the `FROM` clause
            # of any parent query
            .correlate(cls, state_table)
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
            return (self.start_time - self.expected_start_time).as_interval()
        elif (
            self.start_time is None
            and self.expected_start_time
            and self.expected_start_time < pendulum.now("UTC")
            and self.state_type not in states.TERMINAL_STATES
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
                    cls.state_type.not_in(states.TERMINAL_STATES),
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

    flow_version = sa.Column(sa.String, index=True)
    parameters = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    idempotency_key = sa.Column(sa.String)
    context = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    empirical_policy = sa.Column(JSON, server_default="{}", default={}, nullable=False)
    empirical_config = sa.Column(
        JSON, server_default="{}", default=dict, nullable=False
    )
    tags = sa.Column(JSON, server_default="[]", default=list, nullable=False)

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
        Pydantic(core.TaskRunPolicy),
        server_default="{}",
        default=core.TaskRunPolicy,
        nullable=False,
    )
    task_inputs = sa.Column(
        Pydantic(
            Dict[str, List[Union[core.TaskRunResult, core.Parameter, core.Constant]]]
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


@declarative_mixin
class ORMDeployment:
    """SQLAlchemy model of a deployment."""

    name = sa.Column(sa.String, nullable=False)

    @declared_attr
    def flow_id(cls):
        return sa.Column(UUID, sa.ForeignKey("flow.id"), nullable=False, index=True)

    schedule = sa.Column(Pydantic(schedules.SCHEDULE_TYPES))
    is_schedule_active = sa.Column(
        sa.Boolean, nullable=False, server_default="1", default=True
    )
    tags = sa.Column(JSON, server_default="[]", default=list, nullable=False)
    parameters = sa.Column(JSON, server_default="{}", default=dict, nullable=False)
    flow_data = sa.Column(Pydantic(data.DataDocument))

    @declared_attr
    def flow(cls):
        return sa.orm.relationship("Flow", back_populates="deployments", lazy="raise")


@declarative_mixin
class ORMSavedSearch:
    """SQLAlchemy model of a saved search."""

    name = sa.Column(sa.String, nullable=False, unique=True)
    filters = sa.Column(
        JSON,
        server_default="{}",
        default=dict,
        nullable=False,
    )


class BaseORMConfiguration(ABC):
    """
    Abstract base class used to inject database-specific ORM configuration into Orion.
    """

    def __init__(
        self,
        base_metadata: sa.schema.MetaData = None,
        base_model_mixins: List = None,
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
        self._create_orm_models()

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

    def _create_orm_models(self):
        """
        Defines the ORM models used in Orion and binds them to the `self`. This method
        only runs on instantiation.
        """

        class Flow(ORMFlow, self.Base):
            pass

        class FlowRunState(ORMFlowRunState, self.Base):
            pass

        class TaskRunState(ORMTaskRunState, self.Base):
            pass

        class TaskRunStateCache(ORMTaskRunStateCache, self.Base):
            pass

        class FlowRun(ORMFlowRun, self.Base):
            pass

        class TaskRun(ORMTaskRun, self.Base):
            pass

        class Deployment(ORMDeployment, self.Base):
            pass

        class SavedSearch(ORMSavedSearch, self.Base):
            pass

        # TODO - move these to proper migrations
        sa.Index(
            "uq_flow_run_state__flow_run_id_timestamp_desc",
            "flow_run_id",
            FlowRunState.timestamp.desc(),
            unique=True,
        )

        sa.Index(
            "uq_task_run_state__task_run_id_timestamp_desc",
            TaskRunState.task_run_id,
            TaskRunState.timestamp.desc(),
            unique=True,
        )

        sa.Index(
            "ix_task_run_state_cache__cache_key_created_desc",
            TaskRunStateCache.cache_key,
            sa.desc("created"),
        )

        sa.Index(
            "uq_flow_run__flow_id_idempotency_key",
            FlowRun.flow_id,
            FlowRun.idempotency_key,
            unique=True,
        )

        sa.Index(
            "ix_flow_run__expected_start_time_desc",
            FlowRun.expected_start_time.desc(),
        )
        sa.Index(
            "ix_flow_run__next_scheduled_start_time_asc",
            FlowRun.next_scheduled_start_time.asc(),
        )
        sa.Index(
            "ix_flow_run__end_time_desc",
            FlowRun.end_time.desc(),
        )
        sa.Index(
            "ix_flow_run__start_time",
            FlowRun.start_time,
        )
        sa.Index(
            "ix_flow_run__state_type",
            FlowRun.state_type,
        )

        sa.Index(
            "uq_task_run__flow_run_id_task_key_dynamic_key",
            TaskRun.flow_run_id,
            TaskRun.task_key,
            TaskRun.dynamic_key,
            unique=True,
        )

        sa.Index(
            "ix_task_run__expected_start_time_desc",
            TaskRun.expected_start_time.desc(),
        )
        sa.Index(
            "ix_task_run__next_scheduled_start_time_asc",
            TaskRun.next_scheduled_start_time.asc(),
        )
        sa.Index(
            "ix_task_run__end_time_desc",
            TaskRun.end_time.desc(),
        )
        sa.Index(
            "ix_task_run__start_time",
            TaskRun.start_time,
        )
        sa.Index(
            "ix_task_run__state_type",
            TaskRun.state_type,
        )

        sa.Index(
            "uq_deployment__flow_id_name",
            Deployment.flow_id,
            Deployment.name,
            unique=True,
        )

        self.Flow = Flow
        self.FlowRunState = FlowRunState
        self.TaskRunState = TaskRunState
        self.TaskRunStateCache = TaskRunStateCache
        self.FlowRun = FlowRun
        self.TaskRun = TaskRun
        self.Deployment = Deployment
        self.SavedSearch = SavedSearch

    @abstractmethod
    def run_migrations(self):
        """Run database migrations"""
        ...

    @property
    def deployment_unique_upsert_columns(self):
        """Unique columns for upserting a Deployment"""
        return [self.Deployment.flow_id, self.Deployment.name]

    @property
    def flow_run_unique_upsert_columns(self):
        """Unique columns for upserting a FlowRun"""
        return [self.FlowRun.flow_id, self.FlowRun.idempotency_key]

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


class AsyncPostgresORMConfiguration(BaseORMConfiguration):
    """Postgres specific orm configuration"""

    def run_migrations(self):
        ...


class AioSqliteORMConfiguration(BaseORMConfiguration):
    """SQLite specific orm configuration"""

    def run_migrations(self):
        ...
