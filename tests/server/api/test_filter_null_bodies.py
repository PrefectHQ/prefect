"""
Released Prefect clients serialize every filter field of a body, including the
ones they are not using, so a request like `read_flows()` sends explicit
`null` values. FastAPI 0.151 and newer validate an explicit `null` against
the parameter annotation instead of treating it as a missing field, so these
requests fail with a 422 unless the endpoint accepts nullable body parameters.
"""

import pytest

# Payloads mirror what the client sends when every optional filter is unset.
NULL_BODIES = [
    (
        "/flows/filter",
        {
            "flows": None,
            "flow_runs": None,
            "task_runs": None,
            "deployments": None,
            "work_pools": None,
            "work_queues": None,
            "sort": None,
            "limit": None,
            "offset": 0,
        },
    ),
    (
        "/flow_runs/filter",
        {
            "flows": None,
            "flow_runs": None,
            "task_runs": None,
            "deployments": None,
            "work_pools": None,
            "work_pool_queues": None,
            "sort": None,
            "limit": None,
            "offset": 0,
        },
    ),
    (
        "/task_runs/filter",
        {
            "flows": None,
            "flow_runs": None,
            "task_runs": None,
            "deployments": None,
            "sort": None,
            "limit": None,
            "offset": 0,
        },
    ),
    (
        "/deployments/filter",
        {
            "flows": None,
            "flow_runs": None,
            "task_runs": None,
            "deployments": None,
            "work_pools": None,
            "work_pool_queues": None,
            "sort": None,
            "limit": None,
            "offset": 0,
        },
    ),
    ("/work_pools/filter", {"work_pools": None, "limit": None, "offset": 0}),
    ("/work_queues/filter", {"work_queues": None, "limit": None, "offset": None}),
    ("/variables/filter", {"limit": None}),
    (
        "/artifacts/filter",
        {
            "artifacts": None,
            "flow_runs": None,
            "task_runs": None,
            "limit": None,
            "offset": None,
            "sort": None,
        },
    ),
    (
        "/artifacts/latest/filter",
        {
            "artifacts": None,
            "flow_runs": None,
            "task_runs": None,
            "limit": None,
            "offset": 0,
            "sort": None,
        },
    ),
    (
        "/automations/filter",
        {"automations": None, "sort": None, "limit": None, "offset": 0},
    ),
    (
        "/block_documents/filter",
        {
            "block_schema_type": None,
            "offset": None,
            "limit": None,
            "include_secrets": True,
            "sort": None,
        },
    ),
    (
        "/logs/filter",
        {"logs": None, "limit": None, "offset": None, "sort": "TIMESTAMP_ASC"},
    ),
    (
        "/flows/count",
        {
            "flows": None,
            "flow_runs": None,
            "task_runs": None,
            "deployments": None,
            "work_pools": None,
        },
    ),
    (
        "/task_runs/count",
        {
            "flows": None,
            "flow_runs": None,
            "task_runs": None,
            "deployments": None,
        },
    ),
    (
        "/flow_runs/count",
        {
            "flows": None,
            "flow_runs": None,
            "task_runs": None,
            "deployments": None,
            "work_pools": None,
            "work_pool_queues": None,
        },
    ),
    (
        "/artifacts/count",
        {
            "artifacts": None,
            "flow_runs": None,
            "task_runs": None,
            "flows": None,
            "deployments": None,
        },
    ),
    (
        "/artifacts/latest/count",
        {
            "artifacts": None,
            "flow_runs": None,
            "task_runs": None,
            "flows": None,
            "deployments": None,
        },
    ),
    (
        "/task_runs/history",
        {
            "history_start": "2024-01-01T00:00:00Z",
            "history_end": "2024-01-01T01:00:00Z",
            "history_interval_seconds": 3600,
            "flows": None,
            "flow_runs": None,
            "task_runs": None,
            "deployments": None,
        },
    ),
]


@pytest.mark.parametrize(
    "path,body", NULL_BODIES, ids=[case[0] for case in NULL_BODIES]
)
async def test_filter_endpoints_accept_explicit_nulls(client, path, body):
    response = await client.post(path, json=body)

    assert response.status_code == 200, response.text


async def test_work_pool_queue_filter_accepts_explicit_nulls(client, work_pool):
    response = await client.post(
        f"/work_pools/{work_pool.name}/queues/filter",
        json={"work_queues": None, "limit": None, "offset": None},
    )

    assert response.status_code == 200, response.text


async def test_work_pool_worker_filter_accepts_explicit_nulls(client, work_pool):
    response = await client.post(
        f"/work_pools/{work_pool.name}/workers/filter",
        json={"workers": None, "limit": None, "offset": None},
    )

    assert response.status_code == 200, response.text
