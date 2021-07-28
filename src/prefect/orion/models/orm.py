import sqlalchemy as sa
from sqlalchemy import JSON, Column, Enum, String, select, join
from sqlalchemy.orm import relationship, aliased
from sqlalchemy.sql.schema import Index
from sqlalchemy.ext.hybrid import hybrid_property


from sqlalchemy import JSON, Column, String, Enum
from prefect.orion.utilities.database import UUID, Base, Now
from prefect.orion.schemas.core import StateType


class Flow(Base):
    name = Column(String, nullable=False, unique=True)
    tags = Column(JSON, server_default="[]", default=list, nullable=False)
    parameters = Column(JSON, server_default="{}", default=dict, nullable=False)


class FlowRun(Base):
    flow_id = Column(UUID(), nullable=False, index=True)
    flow_version = Column(String)
    parameters = Column(JSON, server_default="{}", default=dict, nullable=False)
    parent_task_run_id = Column(UUID(), nullable=True)
    context = Column(JSON, server_default="{}", default=dict, nullable=False)
    empirical_policy = Column(JSON, server_default="{}", default=dict, nullable=False)
    empirical_config = Column(JSON, server_default="{}", default=dict, nullable=False)
    tags = Column(JSON, server_default="[]", default=list, nullable=False)
    flow_run_metadata = Column(JSON, server_default="{}", default=dict, nullable=False)

    states = relationship(
        "FlowRunState",
        foreign_keys=lambda: [FlowRunState.flow_run_id],
        primaryjoin="FlowRun.id == FlowRunState.flow_run_id",
        order_by="FlowRunState.timestamp",
        lazy="joined",
    )

    @property
    def state(self):
        """The current state"""
        if self.states:
            return self.states[-1]


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
    task_run_metadata = Column(JSON, server_default="{}", default=dict, nullable=False)
    # TODO index this

    states = relationship(
        "TaskRunState",
        foreign_keys=lambda: [TaskRunState.task_run_id],
        primaryjoin="TaskRun.id == TaskRunState.task_run_id",
        order_by="TaskRunState.timestamp",
        lazy="joined",
    )

    @property
    def state(self):
        """The current state"""
        if self.states:
            return self.states[-1]


class FlowRunState(Base):
    flow_run_id = Column(UUID(), nullable=False, index=True)
    type = Column(Enum(StateType), nullable=False, index=True)
    timestamp = Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=Now()
    )
    name = Column(String)
    message = Column(String)
    state_details = Column(JSON, server_default="{}", default=dict, nullable=False)
    run_details = Column(JSON, server_default="{}", default=dict, nullable=False)
    data_location = Column(JSON, server_default="{}", default=dict, nullable=False)

    __table__args__ = sa.Index(
        "ix_flow_run_state_flow_run_id_timestamp_desc", flow_run_id, timestamp.desc()
    )


class TaskRunState(Base):
    task_run_id = Column(UUID(), nullable=False, index=True)
    type = Column(Enum(StateType), nullable=False, index=True)
    timestamp = Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=Now()
    )
    name = Column(String)
    message = Column(String)
    state_details = Column(JSON, server_default="{}", default=dict, nullable=False)
    run_details = Column(JSON, server_default="{}", default=dict, nullable=False)
    data_location = Column(JSON, server_default="{}", default=dict, nullable=False)

    __table__args__ = sa.Index(
        "ix_task_run_state_task_run_id_timestamp_desc", task_run_id, timestamp.desc()
    )
