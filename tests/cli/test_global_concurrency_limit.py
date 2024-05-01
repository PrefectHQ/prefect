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
            name="here-the-buck-stops",
            limit=1,
            active_slots=1,
            slot_decay_per_second=0.1,
        ),
        GlobalConcurrencyLimit(
            id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            created="2021-01-01T00:00:00Z",
            updated="2021-01-01T00:00:00Z",
            active=True,
            name="there-the-buck-stops",
            limit=2,
            active_slots=2,
            slot_decay_per_second=0.1,
        ),
        GlobalConcurrencyLimit(
            id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            created="2021-01-01T00:00:00Z",
            updated="2021-01-01T00:00:00Z",
            active=True,
            name="everywhere-the-buck-stops",
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
            # name is truncated during tests so we can't match the full name without changing the width of the column
            str(various_global_concurrency_limits[0].name[:14]),
            str(various_global_concurrency_limits[1].name[:14]),
            str(various_global_concurrency_limits[2].name[:14]),
        ),
        expected_code=0,
    )


@pytest.fixture
def read_global_concurrency_limit_by_name() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.PrefectClient.read_global_concurrency_limit_by_name",
    ) as m:
        yield m


def test_inspecting_gcl(
    read_global_concurrency_limit_by_name: mock.AsyncMock,
    various_global_concurrency_limits: List[GlobalConcurrencyLimit],
):
    read_global_concurrency_limit_by_name.return_value = (
        various_global_concurrency_limits[0]
    )

    invoke_and_assert(
        [
            "global-concurrency-limit",
            "inspect",
            various_global_concurrency_limits[0].name,
        ],
        expected_output_contains=(
            str(various_global_concurrency_limits[0].name),
            str(various_global_concurrency_limits[0].limit),
            str(various_global_concurrency_limits[0].active_slots),
            str(various_global_concurrency_limits[0].slot_decay_per_second),
        ),
        expected_code=0,
    )


def test_inspecting_gcl_not_found():
    invoke_and_assert(
        ["global-concurrency-limit", "inspect", "not-found"],
        expected_output="Global concurrency limit 'not-found' not found.",
        expected_code=1,
    )
