import pendulum
import sqlalchemy as sa
from sqlalchemy import JSON, Column, Enum, String, join
from sqlalchemy.orm import aliased, relationship

from prefect.orion.schemas import core, states
from prefect.orion.utilities.database import UUID, Base, Now, Pydantic


class Flow(Base):
    name = Column(String, nullable=False, unique=True)
    tags = Column(JSON, server_default="[]", default=list, nullable=False)
    parameters = Column(
        Pydantic(core.ParameterSchema),
        server_default="{}",
        default=dict,
        nullable=False,
    )


class FlowRun(Base):
    flow_id = Column(UUID(), nullable=False, index=True)
    flow_version = Column(String)
    parameters = Column(JSON, server_default="{}", default=dict, nullable=False)
    parent_task_run_id = Column(UUID(), nullable=True)
    context = Column(JSON, server_default="{}", default=dict, nullable=False)
    empirical_policy = Column(JSON, server_default="{}", default=dict, nullable=False)
    empirical_config = Column(JSON, server_default="{}", default=dict, nullable=False)
    tags = Column(JSON, server_default="[]", default=list, nullable=False)
    flow_run_metadata = Column(
        Pydantic(core.FlowRunMetadata),
        server_default="{}",
        default=dict,
        nullable=False,
    )


class TaskRun(Base):
    flow_run_id = Column(UUID(), nullable=False, index=True)
    task_key = Column(String, nullable=False)
    dynamic_key = Column(String)
    cache_key = Column(String)
    cache_expiration = Column(sa.TIMESTAMP(timezone=True))
    task_version = Column(String)
    empirical_policy = Column(JSON, server_default="{}", default=dict, nullable=False)
    task_inputs = Column(JSON, server_default="{}", default=dict, nullable=False)
    tags = Column(JSON, server_default="[]", default=list, nullable=False)
    upstream_task_run_ids = Column(
        JSON, server_default="{}", default=dict, nullable=False
    )
    task_run_metadata = Column(
        Pydantic(core.TaskRunMetadata),
        server_default="{}",
        default=dict,
        nullable=False,
    )

    __table__args__ = sa.Index(
        "ix_task_run_flow_run_id_task_key_dynamic_key",
        flow_run_id,
        task_key,
        dynamic_key,
        unique=True,
    )


class FlowRunState(Base):
    flow_run_id = Column(UUID(), nullable=False, index=True)
    type = Column(Enum(states.StateType), nullable=False, index=True)
    timestamp = Column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=Now(),
        default=lambda: pendulum.now("UTC"),
    )
    name = Column(String)
    message = Column(String)
    state_details = Column(
        Pydantic(states.StateDetails), server_default="{}", default=dict, nullable=False
    )
    run_details = Column(
        Pydantic(states.RunDetails), server_default="{}", default=dict, nullable=False
    )
    data = Column(JSON)

    __table__args__ = sa.Index(
        "ix_flow_run_state_flow_run_id_timestamp_desc", flow_run_id, timestamp.desc()
    )


class TaskRunState(Base):
    task_run_id = Column(UUID(), nullable=False, index=True)
    type = Column(Enum(states.StateType), nullable=False, index=True)
    timestamp = Column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=Now(),
        default=lambda: pendulum.now("UTC"),
    )
    name = Column(String)
    message = Column(String)
    state_details = Column(
        Pydantic(states.StateDetails), server_default="{}", default=dict, nullable=False
    )
    run_details = Column(
        Pydantic(states.RunDetails), server_default="{}", default=dict, nullable=False
    )
    data = Column(JSON)

    __table__args__ = sa.Index(
        "ix_task_run_state_task_run_id_timestamp_desc", task_run_id, timestamp.desc()
    )


# the current state of a run is found by a "top-n-per group" query that joins
# the run table to the state table, and then joins the state table to itself.
# The second state join only includes rows where state2's timestamp is greater
# than state1's timestamp, and the final where clause excludes any rows that
# successfully matched against state2. This leaves only rows in state1 that
# have the maximum timestamp (in other words, the current state.)
#
# this approach works across all SQL databases.


# --------------------------------------------------------------
# Flow run current state

frs_alias = aliased(FlowRunState)
frs_query = aliased(
    FlowRunState,
    join(
        FlowRunState,
        frs_alias,
        sa.and_(
            FlowRunState.flow_run_id == frs_alias.flow_run_id,
            FlowRunState.timestamp < frs_alias.timestamp,
        ),
        isouter=True,
    ),
)

FlowRun.state = relationship(
    frs_query,
    primaryjoin=sa.and_(
        FlowRun.id == FlowRunState.flow_run_id,
        frs_alias.id == None,
    ),
    foreign_keys=[frs_query.flow_run_id],
    viewonly=True,
    uselist=False,
    lazy="joined",
)

# --------------------------------------------------------------
# Task run current state

trs_alias = aliased(TaskRunState)
trs_query = aliased(
    TaskRunState,
    join(
        TaskRunState,
        trs_alias,
        sa.and_(
            TaskRunState.task_run_id == trs_alias.task_run_id,
            TaskRunState.timestamp < trs_alias.timestamp,
        ),
        isouter=True,
    ),
)

TaskRun.state = relationship(
    trs_query,
    primaryjoin=sa.and_(
        TaskRun.id == TaskRunState.task_run_id,
        trs_alias.id == None,
    ),
    foreign_keys=[trs_query.task_run_id],
    viewonly=True,
    uselist=False,
    lazy="joined",
)
