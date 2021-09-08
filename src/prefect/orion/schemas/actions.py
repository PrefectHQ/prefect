"""
Reduced schemas for accepting API actions
"""
from prefect.orion import schemas

FlowCreate = schemas.core.Flow.subclass(
    name="FlowCreate",
    include_fields=["name", "tags", "parameters"],
)

DeploymentCreate = schemas.core.Deployment.subclass(
    name="DeploymentCreate",
    include_fields=["name", "flow_id", "schedule"],
)

FlowRunCreate = schemas.core.FlowRun.subclass(
    name="FlowRunCreate",
    include_fields=[
        "flow_id",
        "deployment_id",
        "flow_version",
        "parameters",
        "context",
        "tags",
        "flow_run_details",
        "parent_task_run_id",
        "idempotency_key",
        "state",
    ],
)

StateCreate = schemas.states.State.subclass(
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

TaskRunCreate = schemas.core.TaskRun.subclass(
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
        "state",
    ],
)
