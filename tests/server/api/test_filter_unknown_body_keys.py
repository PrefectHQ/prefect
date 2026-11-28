"""
Regression tests for #23875: `/filter`, `/count`, and `/paginate` endpoints
must reject unknown top-level body keys with 422 (`extra_forbidden`) rather
than silently dropping misspelled filters and returning every row.
"""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.schemas import actions, core, filters


@pytest.mark.parametrize(
    "path,bad_key,bad_value",
    [
        ("/flow_runs/filter", "flow_run", {"name": {"any_": ["no-such-run"]}}),
        ("/flow_runs/filter", "max_rows", 1),
        ("/flow_runs/count", "flow_run", {"name": {"any_": ["no-such-run"]}}),
        ("/flow_runs/paginate", "flow_run", {"name": {"any_": ["no-such-run"]}}),
        ("/flows/filter", "flow", {"name": {"any_": ["no-such-flow"]}}),
        ("/flows/count", "flow", {"name": {"any_": ["no-such-flow"]}}),
        ("/flows/paginate", "page_num", 2),
        ("/task_runs/filter", "task_run", {"name": {"any_": ["no-such-task"]}}),
        ("/task_runs/count", "task_run", {"name": {"any_": ["no-such-task"]}}),
        ("/deployments/filter", "deployment", {"name": {"any_": ["no-such-dep"]}}),
        ("/deployments/count", "deployment", {"name": {"any_": ["no-such-dep"]}}),
        ("/work_pools/filter", "work_pool", {"name": {"any_": ["no-such-pool"]}}),
        ("/work_queues/filter", "work_queue", {"name": {"any_": ["no-such-q"]}}),
        ("/artifacts/filter", "artifact", {"key": {"any_": ["no-such-key"]}}),
        ("/artifacts/count", "artifact", {"key": {"any_": ["no-such-key"]}}),
        ("/block_documents/filter", "block_document", {"name": {"any_": ["nope"]}}),
        ("/block_documents/count", "block_document", {"name": {"any_": ["nope"]}}),
        ("/variables/filter", "max_rows", 5),
        ("/variables/count", "unknown_filter", {}),
        ("/automations/filter", "max_rows", 5),
        ("/automations/count", "automation", {}),
    ],
)
async def test_filter_and_count_endpoints_reject_unknown_top_level_keys(
    client: AsyncClient,
    path: str,
    bad_key: str,
    bad_value: Any,
):
    response = await client.post(path, json={bad_key: bad_value})

    assert response.status_code == 422, response.text
    payload = response.json()
    assert payload["exception_message"] == "Invalid request received."
    assert any(
        detail["type"] == "extra_forbidden" and detail["loc"] == ["body", bad_key]
        for detail in payload["exception_detail"]
    ), payload


async def test_misspelled_top_level_filter_does_not_return_unfiltered_rows(
    client: AsyncClient,
    session: AsyncSession,
):
    flow = await models.flows.create_flow(
        session=session,
        flow=core.Flow(name="strict-filter-repro-flow"),
    )
    await models.flow_runs.create_flow_run(
        session=session,
        flow_run=core.FlowRun(flow_id=flow.id, name="strict-run-a"),
    )
    await session.commit()

    valid_filter = {
        "flow_runs": {"name": {"any_": ["no-such-run-anywhere"]}},
    }
    valid_count = await client.post("/flow_runs/count", json=valid_filter)
    assert valid_count.status_code == 200
    assert valid_count.json() == 0

    typo_filter = {
        "flow_run": {"name": {"any_": ["no-such-run-anywhere"]}},
    }
    typo_count = await client.post("/flow_runs/count", json=typo_filter)
    assert typo_count.status_code == 422
    assert typo_count.json()["exception_detail"][0]["type"] == "extra_forbidden"
    assert typo_count.json()["exception_detail"][0]["loc"] == ["body", "flow_run"]


async def test_flows_filter_and_count_apply_work_queues_filter(
    client: AsyncClient,
    session: AsyncSession,
):
    pool = await models.workers.create_work_pool(
        session=session,
        work_pool=actions.WorkPoolCreate(name="strict-wq-pool"),
    )
    matched_flow = await models.flows.create_flow(
        session=session,
        flow=core.Flow(name="strict-wq-matched-flow"),
    )
    unmatched_flow = await models.flows.create_flow(
        session=session,
        flow=core.Flow(name="strict-wq-unmatched-flow"),
    )
    await models.deployments.create_deployment(
        session=session,
        deployment=core.Deployment(
            name="strict-wq-deployment",
            flow_id=matched_flow.id,
            work_queue_id=pool.default_queue_id,
        ),
    )
    await session.commit()

    body = {
        "flows": filters.FlowFilter(
            id=filters.FlowFilterId(any_=[matched_flow.id, unmatched_flow.id])
        ).model_dump(mode="json"),
        "work_queues": schemas.filters.WorkQueueFilter(
            id=schemas.filters.WorkQueueFilterId(any_=[pool.default_queue_id])
        ).model_dump(mode="json"),
    }

    filter_resp = await client.post("/flows/filter", json=body)
    assert filter_resp.status_code == 200, filter_resp.text
    assert [row["id"] for row in filter_resp.json()] == [str(matched_flow.id)]

    count_resp = await client.post("/flows/count", json=body)
    assert count_resp.status_code == 200, count_resp.text
    assert count_resp.json() == 1


async def test_filter_and_count_openapi_body_schemas_forbid_additional_properties(
    client: AsyncClient,
):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    openapi_schemas = response.json()["components"]["schemas"]

    for schema_name in (
        "Body_read_flow_runs",
        "Body_count_flow_runs",
        "Body_read_flows",
        "Body_count_flows",
        "Body_paginate_flows",
    ):
        assert openapi_schemas[schema_name].get("additionalProperties") is False, (
            f"{schema_name} missing additionalProperties: False: "
            f"{openapi_schemas[schema_name]}"
        )
