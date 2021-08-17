import pendulum
import sqlalchemy as sa
from sqlalchemy import JSON, Column, String, join, ForeignKey
from sqlalchemy.orm import aliased, relationship

from prefect.orion.schemas import core, states
from prefect.orion.utilities.database import (
    UUID,
    Base,
    Now,
    Pydantic,
    Timestamp,
)
from prefect.orion.utilities.functions import ParameterSchema


class Flow(Base):
    name = Column(String, nullable=False, unique=True)
    tags = Column(JSON, server_default="[]", default=list, nullable=False)
    parameters = Column(
        Pydantic(ParameterSchema),
        server_default="{}",
        default=ParameterSchema,
        nullable=False,
    )


class FlowRunState(Base):
    # this column isn't explicitly indexed because it is included in
    # the unique compound index on (task_run_id, timestamp)
    flow_run_id = Column(
        UUID(), ForeignKey("flow_run.id", ondelete="cascade"), nullable=False
    )
    type = Column(sa.Enum(states.StateType), nullable=False, index=True)
    timestamp = Column(
        Timestamp(timezone=True),
        nullable=False,
        server_default=Now(),
        default=lambda: pendulum.now("UTC"),
    )
    name = Column(String, nullable=False)
    message = Column(String)
    state_details = Column(
        Pydantic(states.StateDetails),
        server_default="{}",
        default=states.StateDetails,
        nullable=False,
    )
    run_details = Column(
        Pydantic(states.RunDetails),
        server_default="{}",
        default=states.RunDetails,
        nullable=False,
    )
    data = Column(JSON)

    __table_args__ = (
        sa.Index(
            "ix_flow_run_state_flow_run_id_timestamp_desc",
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
    type = Column(sa.Enum(states.StateType), nullable=False, index=True)
    timestamp = Column(
        Timestamp(timezone=True),
        nullable=False,
        server_default=Now(),
        default=lambda: pendulum.now("UTC"),
    )
    name = Column(String, nullable=False)
    message = Column(String)
    state_details = Column(
        Pydantic(states.StateDetails),
        server_default="{}",
        default=states.StateDetails,
        nullable=False,
    )
    run_details = Column(
        Pydantic(states.RunDetails),
        server_default="{}",
        default=states.RunDetails,
        nullable=False,
    )
    data = Column(JSON)

    __table_args__ = (
        sa.Index(
            "ix_task_run_state_task_run_id_timestamp_desc",
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
        Timestamp(timezone=True),
        nullable=True,
    )
    task_run_state_id = Column(UUID(), nullable=False)

    __table_args__ = (
        sa.Index(
            "ix_cache_key_created_desc",
            cache_key,
            sa.desc("created"),
        ),
    )


frs = aliased(FlowRunState, name="frs")
trs = aliased(TaskRunState, name="trs")


class FlowRun(Base):
    flow_id = Column(
        UUID(), ForeignKey("flow.id", ondelete="cascade"), nullable=False, index=True
    )
    flow_version = Column(String)
    parameters = Column(JSON, server_default="{}", default=dict, nullable=False)
    idempotency_key = Column(String)
    context = Column(JSON, server_default="{}", default=dict, nullable=False)
    empirical_policy = Column(JSON, server_default="{}", default={}, nullable=False)
    empirical_config = Column(JSON, server_default="{}", default=dict, nullable=False)
    tags = Column(JSON, server_default="[]", default=list, nullable=False)
    flow_run_details = Column(
        Pydantic(core.FlowRunDetails),
        server_default="{}",
        default=core.FlowRunDetails,
        nullable=False,
    )
    parent_task_run_id = Column(
        UUID(),
        ForeignKey("task_run.id", ondelete="cascade", use_alter=True),
        index=True,
    )

    # the current state of a run is found by a "top-n-per group" query that
    # includes two joins:
    #   1. from the `Run` table to the `State` table to load states for that run
    #   2. from the `State` table to itself (aliased as `frs`) to filter all but the current state
    #
    # The second join is an outer join that only matches rows where `state.timestamp < frs.timestamp`,
    # indicating that the matched state is NOT the most recent state. We then add a primary condition
    # that `frs.timestamp IS NULL`, indicating that we only want to keep FAILED matches - in other words
    # keeping only the most recent state.
    state = relationship(
        # the self-referential join of FlowRunState to itself
        lambda: aliased(
            FlowRunState,
            join(
                FlowRunState,
                frs,
                sa.and_(
                    FlowRunState.flow_run_id == frs.flow_run_id,
                    FlowRunState.timestamp < frs.timestamp,
                ),
                isouter=True,
            ),
        ),
        # the join condition from FlowRun to FlowRunState and also including
        # only the failed matches for frs
        primaryjoin=lambda: sa.and_(
            FlowRun.id == FlowRunState.flow_run_id,
            frs.id.is_(None),
        ),
        foreign_keys=[FlowRunState.flow_run_id],
        uselist=False,
        viewonly=True,
        lazy="joined",
    )

    # unique index on flow id / idempotency key
    __table__args__ = sa.Index(
        "ix_flow_run_flow_id_idempotency_key",
        flow_id,
        idempotency_key,
        unique=True,
    )


class TaskRun(Base):
    flow_run_id = Column(
        UUID(),
        ForeignKey("flow_run.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )
    task_key = Column(String, nullable=False)
    dynamic_key = Column(String)
    cache_key = Column(String)
    cache_expiration = Column(Timestamp(timezone=True))
    task_version = Column(String)
    empirical_policy = Column(
        Pydantic(core.TaskRunPolicy),
        server_default="{}",
        default=core.TaskRunPolicy,
        nullable=False,
    )
    task_inputs = Column(
        Pydantic(ParameterSchema),
        server_default="{}",
        default=ParameterSchema,
        nullable=False,
    )
    tags = Column(JSON, server_default="[]", default=list, nullable=False)
    upstream_task_run_ids = Column(
        JSON, server_default="{}", default=dict, nullable=False
    )
    task_run_details = Column(
        Pydantic(core.TaskRunDetails),
        server_default="{}",
        default=core.TaskRunDetails,
        nullable=False,
    )

    # the current state of a run is found by a "top-n-per group" query that
    # includes two joins:
    #   1. from the `Run` table to the `State` table to load states for that run
    #   2. from the `State` table to itself (aliased as `trs`) to filter all but the current state
    #
    # The second join is an outer join that only matches rows where `state.timestamp < trs.timestamp`,
    # indicating that the matched state is NOT the most recent state. We then add a primary condition
    # that `trs.timestamp IS NULL`, indicating that we only want to keep FAILED matches - in other words
    # keeping only the most recent state.
    state = relationship(
        # the self-referential join of TaskRunState to itself
        lambda: aliased(
            TaskRunState,
            join(
                TaskRunState,
                trs,
                sa.and_(
                    TaskRunState.task_run_id == trs.task_run_id,
                    TaskRunState.timestamp < trs.timestamp,
                ),
                isouter=True,
            ),
        ),
        # the join condition from TaskRun to TaskRunState and also including
        # only the failed matches for trs
        primaryjoin=lambda: sa.and_(
            TaskRun.id == TaskRunState.task_run_id,
            trs.id.is_(None),
        ),
        foreign_keys=[TaskRunState.task_run_id],
        uselist=False,
        viewonly=True,
        lazy="joined",
    )

    __table_args__ = (
        sa.Index(
            "ix_task_run_flow_run_id_task_key_dynamic_key",
            flow_run_id,
            task_key,
            dynamic_key,
            unique=True,
        ),
    )


class Deployment(Base):
    name = Column(String, nullable=False)
    flow_id = Column(UUID, ForeignKey("flow.id"), nullable=False, index=True)

    flow = relationship(Flow, lazy="joined")
