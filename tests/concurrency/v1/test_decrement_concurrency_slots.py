import uuid
from unittest import mock

from httpx import Response

from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse
from prefect.concurrency.v1._asyncio import release_concurrency_slots


async def test_calls_release_client_method():
    task_run_id = uuid.UUID("00000000-0000-0000-0000-000000000000")

    limits = [
        MinimalConcurrencyLimitResponse(id=uuid.uuid4(), name=f"test-{i}", limit=i)
        for i in range(1, 3)
    ]

    with mock.patch(
        "prefect.client.orchestration.PrefectClient.decrement_v1_concurrency_slots"
    ) as client_decrement_v1_concurrency_slots:
        response = Response(
            200, json=[limit.model_dump(mode="json") for limit in limits]
        )
        client_decrement_v1_concurrency_slots.return_value = response

        await release_concurrency_slots(
            names=["test-1", "test-2"], task_run_id=task_run_id, occupancy_seconds=1.0
        )
        client_decrement_v1_concurrency_slots.assert_called_once_with(
            names=["test-1", "test-2"],
            task_run_id=task_run_id,
            occupancy_seconds=1.0,
        )


async def test_returns_minimal_concurrency_limit():
    task_run_id = uuid.UUID("00000000-0000-0000-0000-000000000000")

    limits = [
        MinimalConcurrencyLimitResponse(id=uuid.uuid4(), name=f"test-{i}", limit=i)
        for i in range(1, 3)
    ]

    with mock.patch(
        "prefect.client.orchestration.PrefectClient.decrement_v1_concurrency_slots"
    ) as client_decrement_v1_concurrency_slots:
        response = Response(
            200, json=[limit.model_dump(mode="json") for limit in limits]
        )
        client_decrement_v1_concurrency_slots.return_value = response

        result = await release_concurrency_slots(
            ["test-1", "test-2"],
            task_run_id,
            1.0,
        )
        assert result == limits
