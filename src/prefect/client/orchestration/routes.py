from typing import Any, Literal, Optional

from httpx import AsyncClient, Client, Response

ServerRoutes = Literal[
    "/admin/version",
    "/artifacts/",
    "/artifacts/filter",
    "/artifacts/latest/filter",
    "/artifacts/{artifact_id}",
    "/automations/",
    "/automations/filter",
    "/automations/owned",
    "/automations/related",
    "/automations/{automation_id}",
    "/block_documents/",
    "/block_documents/filter",
    "/block_documents/{block_document_id}",
    "/block_schemas/",
    "/block_schemas/checksum/{checksum}",
    "/block_schemas/filter",
    "/block_types/",
    "/block_types/filter",
    "/block_types/slug/{block_type_slug}/block_documents",
    "/block_types/slug/{block_type_slug}/block_documents/name/{name}",
    "/block_types/slug/{slug}",
    "/block_types/{block_type_id}",
    "/concurrency_limits/",
    "/concurrency_limits/decrement",
    "/concurrency_limits/filter",
    "/concurrency_limits/increment",
    "/concurrency_limits/tag/{tag}",
    "/concurrency_limits/tag/{tag}/reset",
    "/deployments/",
    "/deployments/filter",
    "/deployments/get_scheduled_flow_runs",
    "/deployments/name/{name}",
    "/deployments/{deployment_id}",
    "/deployments/{deployment_id}/create_flow_run",
    "/deployments/{deployment_id}/schedules",
    "/deployments/{deployment_id}/schedules/{schedule_id}",
    "/flow_run_notification_policies/",
    "/flow_run_notification_policies/filter",
    "/flow_run_notification_policies/{id}",
    "/flow_run_states/",
    "/flow_runs/",
    "/flow_runs/filter",
    "/flow_runs/{flow_run_id}",
    "/flow_runs/{flow_run_id}/input",
    "/flow_runs/{flow_run_id}/input/filter",
    "/flow_runs/{flow_run_id}/input/{key}",
    "/flow_runs/{flow_run_id}/labels",
    "/flow_runs/{flow_run_id}/resume",
    "/flow_runs/{flow_run_id}/set_state",
    "/flows/",
    "/flows/filter",
    "/flows/name/{flow_name}",
    "/flows/{flow_id}",
    "/health",
    "/hello",
    "/logs/",
    "/logs/filter",
    "/task_run_states/",
    "/task_runs/",
    "/task_runs/filter",
    "/task_runs/{task_run_id}",
    "/task_runs/{task_run_id}/set_state",
    "/v2/concurrency_limits/",
    "/v2/concurrency_limits/decrement",
    "/v2/concurrency_limits/filter",
    "/v2/concurrency_limits/increment",
    "/v2/concurrency_limits/{name}",
    "/variables/",
    "/variables/filter",
    "/variables/name/{name}",
    "/variables/name/{variable",
    "/work_pools/",
    "/work_pools/filter",
    "/work_pools/{work_pool",
    "/work_pools/{work_pool_name}",
    "/work_pools/{work_pool_name}/get_scheduled_flow_runs",
    "/work_pools/{work_pool_name}/queues",
    "/work_pools/{work_pool_name}/queues/filter",
    "/work_pools/{work_pool_name}/queues/{name}",
    "/work_pools/{work_pool_name}/workers/filter",
    "/work_pools/{work_pool_name}/workers/heartbeat",
    "/work_queues/",
    "/work_queues/filter",
    "/work_queues/name/{name}",
    "/work_queues/{id}",
    "/work_queues/{id}/get_runs",
    "/work_queues/{id}/status",
]

SERVER_ROUTE_METHODS: dict[
    ServerRoutes, list[Literal["GET", "POST", "PUT", "DELETE"]]
] = {}


def request(
    client: Client,
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"],
    path: ServerRoutes,
    path_params: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> Response:
    if path_params:
        path = path.format(**path_params)  # type: ignore
    return client.request(method, path, **kwargs)


async def arequest(
    client: AsyncClient,
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"],
    path: ServerRoutes,
    path_params: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> Response:
    if path_params:
        path = path.format(**path_params)  # type: ignore
    return await client.request(method, path, **kwargs)
