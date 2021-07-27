import sqlalchemy as sa
from sqlalchemy import JSON, Column, String
from sqlalchemy.sql.schema import Index

from prefect.orion.utilities.database import UUID, Base
from sqlalchemy import JSON, Column, String, Enum
from prefect.orion.utilities.database import UUID, Base, NowDefault
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


class FlowRunState(Base):
    flow_run_id = Column(UUID(), nullable=False, index=True)
    type = Column(Enum(StateType), nullable=False, index=True)
    timestamp = Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=NowDefault()
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
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=NowDefault()
    )
    name = Column(String)
    message = Column(String)
    state_details = Column(JSON, server_default="{}", default=dict, nullable=False)
    run_details = Column(JSON, server_default="{}", default=dict, nullable=False)
    data_location = Column(JSON, server_default="{}", default=dict, nullable=False)

    __table__args__ = sa.Index(
        "ix_task_run_state_task_run_id_timestamp_desc", task_run_id, timestamp.desc()
    )


# TODO: add indexes
