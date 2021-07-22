import sqlalchemy as sa
from sqlalchemy import JSON, Column, String, Enum
from prefect.orion.utilities.database import UUID, Base, NowDefault
from prefect.orion.utilities.enum import StateType


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


class FlowRunState(Base):
    flow_run_id = Column(UUID(), nullable=False, index=True)
    name = Column(String)
    type = Column(Enum(StateType), nullable=False, index=True)
    timestamp = Column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=NowDefault()
    )
    message = Column(String)
    state_details = Column(JSON, server_default="{}", default=dict, nullable=False)
    run_details = Column(JSON, server_default="{}", default=dict, nullable=False)
    data_location = Column(JSON, server_default="{}", default=dict, nullable=False)


# TODO: add indexes
