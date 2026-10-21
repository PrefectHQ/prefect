from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database import orm_models

pytestmark = pytest.mark.clear_db


async def test_empty(client: httpx.AsyncClient):
    response = await client.get("/observed-states")
    assert response.status_code == 200
    assert response.json() == []


async def test_cloud_compatible_schema(client: httpx.AsyncClient):
    response = await client.get("/openapi.json")
    schema = response.json()
    observed = schema["components"]["schemas"]["ObservedState"]
    assert set(observed["required"]) == {
        "state_type",
        "state_name",
        "first_seen",
        "last_seen",
    }
    assert observed["properties"]["state_type"]["type"] == "string"
    assert observed["properties"]["state_name"]["type"] == "string"
    for field in ("first_seen", "last_seen"):
        assert observed["properties"][field]["format"] == "date-time"
    endpoint = schema["paths"]["/observed-states"]["get"]
    assert (
        endpoint["responses"]["200"]["content"]["application/json"]["schema"]["type"]
        == "array"
    )
    parameters = {param["name"]: param["schema"] for param in endpoint["parameters"]}
    assert parameters["limit"]["default"] == 200
    assert parameters["limit"]["minimum"] == 1
    assert parameters["limit"]["maximum"] == 200
    assert parameters["order_by"]["default"] == "LAST_SEEN_DESC"
    assert schema["components"]["schemas"]["ObservedStateSort"]["enum"] == [
        "NAME_ASC",
        "LAST_SEEN_DESC",
    ]


@pytest.fixture
async def observations(
    session: AsyncSession,
    flow_run: orm_models.FlowRun,
    task_run: orm_models.TaskRun,
) -> list[dict[str, str]]:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    transitions = [
        (schemas.states.Scheduled(name="custom schedule"), 0, False),
        (schemas.states.Failed(name="Baseline NOT Met"), 1, False),
        (schemas.states.Running(name="Baseline NOT Met"), 2, False),
        (schemas.states.Failed(name="Baseline NOT Met"), 3, True),
        (schemas.states.Failed(name="baseline NOT Met"), 4, True),
    ]
    for state, seconds, task in transitions:
        state.timestamp = start + timedelta(seconds=seconds)
        if task:
            await models.task_runs.set_task_run_state(
                session=session, task_run_id=task_run.id, state=state, force=True
            )
        else:
            await models.flow_runs.set_flow_run_state(
                session=session, flow_run_id=flow_run.id, state=state, force=True
            )
    await session.commit()
    return [
        {
            "state_type": "FAILED",
            "state_name": "baseline NOT Met",
            "first_seen": "2020-01-01T00:00:04Z",
            "last_seen": "2020-01-01T00:00:04Z",
        },
        {
            "state_type": "FAILED",
            "state_name": "Baseline NOT Met",
            "first_seen": "2020-01-01T00:00:01Z",
            "last_seen": "2020-01-01T00:00:03Z",
        },
        {
            "state_type": "RUNNING",
            "state_name": "Baseline NOT Met",
            "first_seen": "2020-01-01T00:00:02Z",
            "last_seen": "2020-01-01T00:00:02Z",
        },
        {
            "state_type": "SCHEDULED",
            "state_name": "custom schedule",
            "first_seen": "2020-01-01T00:00:00Z",
            "last_seen": "2020-01-01T00:00:00Z",
        },
    ]


async def test_retained_transition_timestamps(
    client: httpx.AsyncClient, observations: list[dict[str, str]]
):
    response = await client.get("/observed-states")
    assert response.status_code == 200
    # Ignore fixture-created initial states, which are more recent.
    assert [
        row
        for row in response.json()
        if "NOT Met" in row["state_name"] or row["state_name"] == "custom schedule"
    ] == observations


@pytest.mark.parametrize("query", [" bAsE ", "fAiL", "", "   ", "no match"])
async def test_prefix_search(
    client: httpx.AsyncClient, observations: list[dict[str, str]], query: str
):
    response = await client.get("/observed-states", params={"query": query})
    assert response.status_code == 200
    expected = [
        row
        for row in observations
        if not query.strip()
        or row["state_type"].lower().startswith(query.strip().lower())
        or row["state_name"].lower().startswith(query.strip().lower())
    ]
    actual = [
        row
        for row in response.json()
        if "NOT Met" in row["state_name"] or row["state_name"] == "custom schedule"
    ]
    assert actual == expected


async def test_name_order_and_limit(
    client: httpx.AsyncClient,
    session: AsyncSession,
    flow_run: orm_models.FlowRun,
):
    for name in ("ordering c", "ordering a", "ordering b"):
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=schemas.states.Failed(name=name),
            force=True,
        )
    await session.commit()

    response = await client.get(
        "/observed-states",
        params={"query": "ordering", "order_by": "NAME_ASC", "limit": 2},
    )
    assert response.status_code == 200
    assert [row["state_name"] for row in response.json()] == [
        "ordering a",
        "ordering b",
    ]


async def test_deleted_runs_remove_observations(
    client: httpx.AsyncClient,
    session: AsyncSession,
    flow_run: orm_models.FlowRun,
    observations: list[dict[str, str]],
):
    await models.flow_runs.delete_flow_run(session=session, flow_run_id=flow_run.id)
    await session.commit()
    response = await client.get("/observed-states", params={"query": "base"})
    assert response.json() == []


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 201}, {"order_by": "bad"}, {"query": "a" * 101}]
)
async def test_invalid_query(client: httpx.AsyncClient, params: dict[str, str | int]):
    response = await client.get("/observed-states", params=params)
    assert response.status_code == 422
