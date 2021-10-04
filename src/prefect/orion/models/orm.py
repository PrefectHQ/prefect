import datetime
from typing import Optional, Dict, List, Union

from coolname import generate_slug
import pendulum
import sqlalchemy as sa
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_mixin, relationship

from prefect.orion.schemas import core, data, schedules, states, filters
from prefect.orion.utilities.database import (
    JSON,
    UUID,
    Base,
    Pydantic,
    Timestamp,
    interval_add,
    get_dialect,
    date_diff,
    now,
)
from prefect.orion.utilities.functions import ParameterSchema


class Flow(Base):
    name = Column(String, nullable=False, unique=True)
    tags = Column(JSON, server_default="[]", default=list, nullable=False)
    flow_runs = relationship("FlowRun", back_populates="flow", lazy="raise")
    deployments = relationship("Deployment", back_populates="flow", lazy="raise")


class FlowRunState(Base):
    # this column isn't explicitly indexed because it is included in
    # the unique compound index on (flow_run_id, timestamp)
    flow_run_id = Column(
        UUID(), ForeignKey("flow_run.id", ondelete="cascade"), nullable=False
    )
    type = Column(
        sa.Enum(states.StateType, name="state_type"), nullable=False, index=True
    )
    timestamp = Column(
        Timestamp(),
        nullable=False,
        server_default=now(),
        default=lambda: pendulum.now("UTC"),
    )
    name = Column(String, nullable=False, index=True)
    message = Column(String)
    state_details = Column(
        Pydantic(states.StateDetails),
        server_default="{}",
        default=states.StateDetails,
        nullable=False,
    )
    data = Column(Pydantic(data.DataDocument), nullable=True)

    flow_run = relationship(
        "FlowRun",
        lazy="raise",
        foreign_keys=[flow_run_id],
    )

    __table_args__ = (
        sa.Index(
            "uq_flow_run_state__flow_run_id_timestamp_desc",
            flow_run_id,
            timestamp.desc(),
            unique=True,
        ),
    )

    def as_state(self) -> states.State:
        return states.State.from_orm(self)


class TaskRunState(Base):
    # this column isn't explicitly indexed because it is included in
    # the unique compound index on (task_run_id, timestamp)
    task_run_id = Column(
        UUID(), ForeignKey("task_run.id", ondelete="cascade"), nullable=False
    )
    type = Column(
        sa.Enum(states.StateType, name="state_type"), nullable=False, index=True
    )
    timestamp = Column(
        Timestamp(),
        nullable=False,
        server_default=now(),
        default=lambda: pendulum.now("UTC"),
    )
    name = Column(String, nullable=False, index=True)
    message = Column(String)
    state_details = Column(
        Pydantic(states.StateDetails),
        server_default="{}",
        default=states.StateDetails,
        nullable=False,
    )
    data = Column(Pydantic(data.DataDocument), nullable=True)

    task_run = relationship(
        "TaskRun",
        lazy="raise",
        foreign_keys=[task_run_id],
    )

    __table_args__ = (
        sa.Index(
            "uq_task_run_state__task_run_id_timestamp_desc",
            task_run_id,
            timestamp.desc(),
            unique=True,
        ),
    )

    def as_state(self) -> states.State:
        return states.State.from_orm(self)


class TaskRunStateCache(Base):
    cache_key = Column(String, nullable=False)
    cache_expiration = Column(
        Timestamp(),
        nullable=True,
    )
    task_run_state_id = Column(UUID(), nullable=False)

    __table_args__ = (
        sa.Index(
            "ix_task_run_state_cache__cache_key_created_desc",
            cache_key,
            sa.desc("created"),
        ),
    )


@declarative_mixin
class RunMixin:
    """
    Common columns and logic for FlowRun and TaskRun models
    """

    name = Column(
        String,
        default=lambda: generate_slug(2),
        nullable=False,
        index=True,
    )
    state_type = Column(sa.Enum(states.StateType, name="state_type"))
    run_count = Column(Integer, server_default="0", default=0, nullable=False)
    expected_start_time = Column(Timestamp())
    next_scheduled_start_time = Column(Timestamp())
    start_time = Column(Timestamp())
    end_time = Column(Timestamp())
    total_run_time = Column(
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


class FlowRun(Base, RunMixin):
    flow_id = Column(
        UUID(), ForeignKey("flow.id", ondelete="cascade"), nullable=False, index=True
    )
    deployment_id = Column(
        UUID(), ForeignKey("deployment.id", ondelete="set null"), index=True
    )
    flow_version = Column(String, index=True)
    parameters = Column(JSON, server_default="{}", default=dict, nullable=False)
    idempotency_key = Column(String)
    context = Column(JSON, server_default="{}", default=dict, nullable=False)
    empirical_policy = Column(JSON, server_default="{}", default={}, nullable=False)
    empirical_config = Column(JSON, server_default="{}", default=dict, nullable=False)
    tags = Column(JSON, server_default="[]", default=list, nullable=False)
    parent_task_run_id = Column(
        UUID(),
        ForeignKey(
            "task_run.id",
            ondelete="SET NULL",
            use_alter=True,
        ),
        index=True,
    )
    auto_scheduled = Column(Boolean, server_default="0", default=False, nullable=False)

    # TODO remove this foreign key for significant delete performance gains
    state_id = Column(
        UUID(),
        ForeignKey(
            "flow_run_state.id",
            ondelete="SET NULL",
            use_alter=True,
        ),
        index=True,
    )

    # -------------------------- relationships

    # current states are eagerly loaded unless otherwise specified
    _state = relationship(
        "FlowRunState",
        lazy="joined",
        foreign_keys=[state_id],
        primaryjoin=lambda: FlowRun.state_id == FlowRunState.id,
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

    def set_state(self, state: Optional[FlowRunState]):
        """
        If a state is assigned to this run, populate its run id.

        This would normally be handled by the back-populated SQLAlchemy
        relationship, but because this is a one-to-one pointer to a
        one-to-many relationship, SQLAlchemy can't figure it out.
        """
        if state is not None:
            state.flow_run_id = self.id
        self._state = state

    flow = relationship("Flow", back_populates="flow_runs", lazy="raise")
    task_runs = relationship(
        "TaskRun",
        back_populates="flow_run",
        lazy="raise",
        foreign_keys=lambda: [TaskRun.flow_run_id],
    )
    parent_task_run = relationship(
        "TaskRun",
        back_populates="subflow_run",
        lazy="raise",
        foreign_keys=lambda: [FlowRun.parent_task_run_id],
    )

    __table_args__ = (
        sa.Index(
            "uq_flow_run__flow_id_idempotency_key",
            flow_id,
            idempotency_key,
            unique=True,
        ),
    )


# add indexes after table creation to use mixin columns
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


class TaskRun(Base, RunMixin):
    flow_run_id = Column(
        UUID(),
        ForeignKey("flow_run.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    task_key = Column(String, nullable=False)
    dynamic_key = Column(String, nullable=False)
    cache_key = Column(String)
    cache_expiration = Column(Timestamp())
    task_version = Column(String)
    empirical_policy = Column(
        Pydantic(core.TaskRunPolicy),
        server_default="{}",
        default=core.TaskRunPolicy,
        nullable=False,
    )
    task_inputs = Column(
        Pydantic(
            Dict[str, List[Union[core.TaskRunResult, core.Parameter, core.Constant]]]
        ),
        server_default="{}",
        default=dict,
        nullable=False,
    )
    tags = Column(JSON, server_default="[]", default=list, nullable=False)

    # TODO remove this foreign key for significant delete performance gains
    state_id = Column(
        UUID(),
        ForeignKey(
            "task_run_state.id",
            ondelete="SET NULL",
            use_alter=True,
        ),
        index=True,
    )
    # -------------------------- relationships

    # current states are eagerly loaded unless otherwise specified
    _state = relationship(
        "TaskRunState",
        lazy="joined",
        foreign_keys=[state_id],
        primaryjoin=lambda: TaskRun.state_id == TaskRunState.id,
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

    def set_state(self, state: Optional[TaskRunState]):
        """
        If a state is assigned to this run, populate its run id.

        This would normally be handled by the back-populated SQLAlchemy
        relationship, but because this is a one-to-one pointer to a
        one-to-many relationship, SQLAlchemy can't figure it out.
        """
        if state is not None:
            state.task_run_id = self.id
        self._state = state

    flow_run = relationship(
        FlowRun,
        back_populates="task_runs",
        lazy="raise",
        foreign_keys=[flow_run_id],
    )

    subflow_run = relationship(
        FlowRun,
        back_populates="parent_task_run",
        lazy="raise",
        foreign_keys=[FlowRun.parent_task_run_id],
        uselist=False,
    )

    __table_args__ = (
        sa.Index(
            "uq_task_run__flow_run_id_task_key_dynamic_key",
            flow_run_id,
            task_key,
            dynamic_key,
            unique=True,
        ),
    )


# add indexes after table creation to use mixin columns
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


class Deployment(Base):
    name = Column(String, nullable=False)
    flow_id = Column(UUID, ForeignKey("flow.id"), nullable=False, index=True)
    schedule = Column(Pydantic(schedules.SCHEDULE_TYPES))
    is_schedule_active = Column(
        sa.Boolean, nullable=False, server_default="1", default=True
    )
    tags = Column(JSON, server_default="[]", default=list, nullable=False)
    parameters = Column(JSON, server_default="{}", default=dict, nullable=False)
    flow_data = Column(Pydantic(data.DataDocument))

    flow = relationship(Flow, back_populates="deployments", lazy="raise")

    __table_args__ = (
        sa.Index(
            "uq_deployment__flow_id_name",
            flow_id,
            name,
            unique=True,
        ),
    )


class SavedSearch(Base):
    name = Column(String, nullable=False, unique=True)
    flow_filter_criteria = Column(
        Pydantic(filters.FlowFilterCriteria),
        server_default="{}",
        default=filters.FlowFilterCriteria,
        nullable=False,
    )
    flow_run_filter_criteria = Column(
        Pydantic(filters.FlowRunFilterCriteria),
        server_default="{}",
        default=filters.FlowRunFilterCriteria,
        nullable=False,
    )
    task_run_filter_criteria = Column(
        Pydantic(filters.TaskRunFilterCriteria),
        server_default="{}",
        default=filters.TaskRunFilterCriteria,
        nullable=False,
    )
    deployment_filter_criteria = Column(
        Pydantic(filters.DeploymentFilterCriteria),
        server_default="{}",
        default=filters.DeploymentFilterCriteria,
        nullable=False,
    )
