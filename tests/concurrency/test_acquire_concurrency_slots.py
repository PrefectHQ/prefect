import uuid
from unittest import mock

from httpx import Response

from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse
from prefect.concurrency.asyncio import _acquire_concurrency_slots


async def test_calls_increment_client_method():
    limits = [
        MinimalConcurrencyLimitResponse(id=uuid.uuid4(), name=f"test-{i}", limit=i)
        for i in range(1, 3)
    ]

    with mock.patch(
        "prefect.client.orchestration.PrefectClient.increment_concurrency_slots"
    ) as increment_concurrency_slots:
        response = Response(
            200, json=[limit.model_dump(mode="json") for limit in limits]
        )
        increment_concurrency_slots.return_value = response

        await _acquire_concurrency_slots(
            names=["test-1", "test-2"], slots=1, mode="concurrency"
        )
        increment_concurrency_slots.assert_called_once_with(
            names=["test-1", "test-2"],
            slots=1,
            mode="concurrency",
            create_if_missing=None,
        )


async def test_returns_minimal_concurrency_limit():
    limits = [
        MinimalConcurrencyLimitResponse(id=uuid.uuid4(), name=f"test-{i}", limit=i)
        for i in range(1, 3)
    ]

    with mock.patch(
        "prefect.client.orchestration.PrefectClient.increment_concurrency_slots"
    ) as increment_concurrency_slots:
        response = Response(
            200, json=[limit.model_dump(mode="json") for limit in limits]
        )
        increment_concurrency_slots.return_value = response

        result = await _acquire_concurrency_slots(["test-1", "test-2"], 1)
        assert result == limits
