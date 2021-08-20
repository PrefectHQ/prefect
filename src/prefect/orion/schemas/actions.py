"""
Reduced schemas for accepting API actions
"""
from prefect.orion.schemas.core import Flow, FlowRun, TaskRun
from prefect.orion.schemas.states import State
from prefect.orion.schemas.data import DataDocument

FlowCreate = Flow.subclass(
    name="FlowCreate",
    include_fields=["name", "tags", "parameters"],
)

FlowRunCreate = FlowRun.subclass(
    name="FlowRunCreate",
    include_fields=[
        "id",
        "flow_id",
        "flow_version",
        "parameters",
        "context",
        "tags",
        "flow_run_details",
        "parent_task_run_id",
        "idempotency_key",
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
        "run_details",
    ],
)

TaskRunCreate = TaskRun.subclass(
    name="TaskRunCreate",
    include_fields=[
        "flow_run_id",
        "task_key",
        "dynamic_key",
        "cache_key",
        "cache_expiration",
        "task_version",
        "empirical_policy",
        "tags",
        "task_inputs",
        "upstream_task_run_ids",
        "task_run_details",
    ],
)

DataDocumentCreate = DataDocument.subclass(
    name="DataDocumentCreate",
    include_fields=[
        "name",
        "tags",
        "blob",
        "format",
    ],
)
