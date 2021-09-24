"""
Reduced schemas for accepting API actions
"""
from prefect.orion import schemas

FlowCreate = schemas.core.Flow.subclass(
    name="FlowCreate",
    include_fields=["name", "tags"],
)

FlowUpdate = schemas.core.Flow.subclass(name="FlowUpdate", include_fields=["tags"])

DeploymentCreate = schemas.core.Deployment.subclass(
    name="DeploymentCreate",
    include_fields=[
        "name",
        "flow_id",
        "schedule",
        "is_schedule_active",
        "tags",
        "flow_data",
    ],
)

FlowRunUpdate = schemas.core.FlowRun.subclass(
    name="FlowRunUpdate", include_fields=["flow_version", "parameters"]
)

StateCreate = schemas.states.State.subclass(
    name="StateCreate",
    include_fields=[
        "type",
        "name",
        "message",
        "data",
        "state_details",
    ],
)


class TaskRunCreate(
    schemas.core.TaskRun.subclass(
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
        ],
    )
):
    # TaskRunCreate states must be provided as StateCreate objects
    state: StateCreate = None


class FlowRunCreate(
    schemas.core.FlowRun.subclass(
        name="FlowRunCreate",
        include_fields=[
            "flow_id",
            "deployment_id",
            "flow_version",
            "parameters",
            "context",
            "tags",
            "idempotency_key",
            "parent_task_run_id",
        ],
    )
):
    # FlowRunCreate states must be provided as StateCreate objects
    state: StateCreate = None
