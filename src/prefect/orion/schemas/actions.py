"""
Reduced schemas for accepting API actions
"""

import datetime
from typing import List
from uuid import UUID

from pydantic import Field

from prefect.orion.utilities.schemas import pydantic_subclass
from prefect.orion.schemas.core import State, Flow, FlowRun

FlowCreate = Flow.subclass(
    name="FlowCreate",
    include_fields=["name", "tags", "parameters"],
)

FlowRunCreate = FlowRun.subclass(
    name="FlowRunCreate",
    include_fields=[
        "flow_id",
        "flow_version",
        "parameters",
        "parent_task_run_id",
        "context",
        "tags",
        "flow_run_metadata",
    ],
)

StateCreate = State.subclass(
    name="StateCreate",
    include_fields=[
        "type",
        "name",
        "timestamp",
        "message",
        "data",
        "state_details",
    ],
)
