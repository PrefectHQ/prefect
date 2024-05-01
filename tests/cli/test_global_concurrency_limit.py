from typing import Generator, List
from unittest import mock
from uuid import UUID

import pytest

from prefect.client.schemas.objects import GlobalConcurrencyLimit
from prefect.testing.cli import invoke_and_assert


@pytest.fixture
def read_global_concurrency_limits() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.PrefectClient.read_global_concurrency_limits",
    ) as m:
        yield m


def test_listing_gcl_empty(read_global_concurrency_limits: mock.AsyncMock):
    read_global_concurrency_limits.return_value = []

    invoke_and_assert(
        ["global-concurrency-limit", "ls"],
        expected_output="No global concurrency limits found.",
    )


@pytest.fixture
def various_global_concurrency_limits(
    read_global_concurrency_limits: mock.AsyncMock,
) -> List[GlobalConcurrencyLimit]:
    global_concurrency_limits = [
        GlobalConcurrencyLimit(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            created="2021-01-01T00:00:00Z",
            updated="2021-01-01T00:00:00Z",
            active=True,
            name="the-buck-stops-here",
            limit=1,
            active_slots=1,
            slot_decay_per_second=0.1,
        ),
        GlobalConcurrencyLimit(
            id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            created="2021-01-01T00:00:00Z",
            updated="2021-01-01T00:00:00Z",
            active=True,
            name="the-buck-stops-there",
            limit=2,
            active_slots=2,
            slot_decay_per_second=0.1,
        ),
        GlobalConcurrencyLimit(
            id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            created="2021-01-01T00:00:00Z",
            updated="2021-01-01T00:00:00Z",
            active=True,
            name="the-buck-stops-everywhere",
            limit=3,
            active_slots=3,
            slot_decay_per_second=0.1,
        ),
    ]
    read_global_concurrency_limits.return_value = global_concurrency_limits
    return global_concurrency_limits


def test_listing_gcl(various_global_concurrency_limits: List[GlobalConcurrencyLimit]):
    invoke_and_assert(
        ["global-concurrency-limit", "ls"],
        expected_output_contains=(
            str(various_global_concurrency_limits[0].name),
            str(various_global_concurrency_limits[1].name),
            str(various_global_concurrency_limits[2].name),
        ),
        expected_code=0,
    )
