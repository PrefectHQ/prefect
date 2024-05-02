from typing import Generator, List
from unittest import mock
from uuid import UUID

import pytest

from prefect.client.schemas.actions import GlobalConcurrencyLimitUpdate
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
            # name check is truncated during tests as we can't match the full name without changing the width of the column
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


@pytest.fixture
def delete_global_concurrency_limit_by_name() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.PrefectClient.delete_global_concurrency_limit_by_name",
    ) as m:
        yield m


def test_deleting_gcl(
    delete_global_concurrency_limit_by_name: mock.AsyncMock,
    various_global_concurrency_limits: List[GlobalConcurrencyLimit],
):
    invoke_and_assert(
        [
            "global-concurrency-limit",
            "delete",
            various_global_concurrency_limits[0].name,
        ],
        prompts_and_responses=[
            (
                f"Are you sure you want to delete global concurrency limit '{various_global_concurrency_limits[0].name}'?",
                "y",
            )
        ],
        expected_output_contains=f"Deleted global concurrency limit with name '{various_global_concurrency_limits[0].name}'.",
        expected_code=0,
    )
    delete_global_concurrency_limit_by_name.assert_called_once_with(
        name=various_global_concurrency_limits[0].name
    )


def test_deleting_gcl_not_found():
    invoke_and_assert(
        ["global-concurrency-limit", "delete", "not-found"],
        prompts_and_responses=[
            (
                "Are you sure you want to delete global concurrency limit 'not-found'?",
                "y",
            )
        ],
        expected_output_contains="Global concurrency limit 'not-found' not found.",
        expected_code=1,
    )


@pytest.fixture
def update_global_concurrency_limit() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.PrefectClient.update_global_concurrency_limit",
    ) as m:
        yield m


def test_enable_inactive_gcl(
    read_global_concurrency_limit_by_name: mock.AsyncMock,
    update_global_concurrency_limit: mock.AsyncMock,
    various_global_concurrency_limits: List[GlobalConcurrencyLimit],
):
    various_global_concurrency_limits[0].active = False
    read_global_concurrency_limit_by_name.return_value = (
        various_global_concurrency_limits[0]
    )
    update_global_concurrency_limit.return_value = various_global_concurrency_limits[0]

    invoke_and_assert(
        [
            "global-concurrency-limit",
            "enable",
            various_global_concurrency_limits[0].name,
        ],
        expected_output=f"Enabled global concurrency limit with name '{various_global_concurrency_limits[0].name}'.",
        expected_code=0,
    )
    update_global_concurrency_limit.assert_called_once_with(
        name=various_global_concurrency_limits[0].name,
        concurrency_limit=GlobalConcurrencyLimitUpdate(
            active=True,
        ),
    )


def test_enable_already_active_gcl(
    read_global_concurrency_limit_by_name: mock.AsyncMock,
    various_global_concurrency_limits: List[GlobalConcurrencyLimit],
):
    read_global_concurrency_limit_by_name.return_value = (
        various_global_concurrency_limits[0]
    )

    invoke_and_assert(
        [
            "global-concurrency-limit",
            "enable",
            various_global_concurrency_limits[0].name,
        ],
        expected_output=f"Global concurrency limit with name '{various_global_concurrency_limits[0].name}' is already enabled.",
        expected_code=1,
    )


def test_enable_gcl_not_found():
    invoke_and_assert(
        ["global-concurrency-limit", "enable", "not-found"],
        expected_output="Global concurrency limit 'not-found' not found.",
        expected_code=1,
    )


def test_disable_active_gcl(
    read_global_concurrency_limit_by_name: mock.AsyncMock,
    update_global_concurrency_limit: mock.AsyncMock,
    various_global_concurrency_limits: List[GlobalConcurrencyLimit],
):
    various_global_concurrency_limits[0].active = True
    read_global_concurrency_limit_by_name.return_value = (
        various_global_concurrency_limits[0]
    )
    update_global_concurrency_limit.return_value = various_global_concurrency_limits[0]

    invoke_and_assert(
        [
            "global-concurrency-limit",
            "disable",
            various_global_concurrency_limits[0].name,
        ],
        expected_output=f"Disabled global concurrency limit with name '{various_global_concurrency_limits[0].name}'.",
        expected_code=0,
    )
    update_global_concurrency_limit.assert_called_once_with(
        name=various_global_concurrency_limits[0].name,
        concurrency_limit=GlobalConcurrencyLimitUpdate(
            active=False,
        ),
    )


def test_disable_already_inactive_gcl(
    read_global_concurrency_limit_by_name: mock.AsyncMock,
    various_global_concurrency_limits: List[GlobalConcurrencyLimit],
):
    various_global_concurrency_limits[0].active = False
    read_global_concurrency_limit_by_name.return_value = (
        various_global_concurrency_limits[0]
    )

    invoke_and_assert(
        [
            "global-concurrency-limit",
            "disable",
            various_global_concurrency_limits[0].name,
        ],
        expected_output=f"Global concurrency limit with name '{various_global_concurrency_limits[0].name}' is already disabled.",
        expected_code=1,
    )


def test_disable_gcl_not_found():
    invoke_and_assert(
        ["global-concurrency-limit", "disable", "not-found"],
        expected_output="Global concurrency limit 'not-found' not found.",
        expected_code=1,
    )


def test_update_gcl_limit(
    update_global_concurrency_limit: mock.AsyncMock,
    various_global_concurrency_limits: List[GlobalConcurrencyLimit],
):
    update_global_concurrency_limit.return_value = various_global_concurrency_limits[0]

    invoke_and_assert(
        [
            "global-concurrency-limit",
            "update",
            various_global_concurrency_limits[0].name,
            "--limit",
            "10",
        ],
        expected_output=f"Updated global concurrency limit with name '{various_global_concurrency_limits[0].name}'.",
        expected_code=0,
    )
    update_global_concurrency_limit.assert_called_once_with(
        name=various_global_concurrency_limits[0].name,
        concurrency_limit=GlobalConcurrencyLimitUpdate(
            limit=10,
        ),
    )


def test_update_gcl_active_slots(
    update_global_concurrency_limit: mock.AsyncMock,
    various_global_concurrency_limits: List[GlobalConcurrencyLimit],
):
    update_global_concurrency_limit.return_value = various_global_concurrency_limits[0]

    invoke_and_assert(
        [
            "global-concurrency-limit",
            "update",
            various_global_concurrency_limits[0].name,
            "--active-slots",
            "5",
        ],
        expected_output=f"Updated global concurrency limit with name '{various_global_concurrency_limits[0].name}'.",
        expected_code=0,
    )
    update_global_concurrency_limit.assert_called_once_with(
        name=various_global_concurrency_limits[0].name,
        concurrency_limit=GlobalConcurrencyLimitUpdate(
            active_slots=5,
        ),
    )


def test_update_gcl_slot_decay_per_second(
    update_global_concurrency_limit: mock.AsyncMock,
    various_global_concurrency_limits: List[GlobalConcurrencyLimit],
):
    update_global_concurrency_limit.return_value = various_global_concurrency_limits[0]

    invoke_and_assert(
        [
            "global-concurrency-limit",
            "update",
            various_global_concurrency_limits[0].name,
            "--slot-decay-per-second",
            "0.5",
        ],
        expected_output=f"Updated global concurrency limit with name '{various_global_concurrency_limits[0].name}'.",
        expected_code=0,
    )
    update_global_concurrency_limit.assert_called_once_with(
        name=various_global_concurrency_limits[0].name,
        concurrency_limit=GlobalConcurrencyLimitUpdate(
            slot_decay_per_second=0.5,
        ),
    )


def test_update_gcl_multiple_fields(
    update_global_concurrency_limit: mock.AsyncMock,
    various_global_concurrency_limits: List[GlobalConcurrencyLimit],
):
    update_global_concurrency_limit.return_value = various_global_concurrency_limits[0]

    invoke_and_assert(
        [
            "global-concurrency-limit",
            "update",
            various_global_concurrency_limits[0].name,
            "--limit",
            "10",
            "--active-slots",
            "5",
            "--slot-decay-per-second",
            "0.5",
        ],
        expected_output=f"Updated global concurrency limit with name '{various_global_concurrency_limits[0].name}'.",
        expected_code=0,
    )
    update_global_concurrency_limit.assert_called_once_with(
        name=various_global_concurrency_limits[0].name,
        concurrency_limit=GlobalConcurrencyLimitUpdate(
            limit=10,
            active_slots=5,
            slot_decay_per_second=0.5,
        ),
    )


def test_update_gcl_to_inactive(
    update_global_concurrency_limit: mock.AsyncMock,
    various_global_concurrency_limits: List[GlobalConcurrencyLimit],
):
    update_global_concurrency_limit.return_value = various_global_concurrency_limits[0]

    invoke_and_assert(
        [
            "global-concurrency-limit",
            "update",
            various_global_concurrency_limits[0].name,
            "--disable",
        ],
        expected_output=f"Updated global concurrency limit with name '{various_global_concurrency_limits[0].name}'.",
        expected_code=0,
    )
    update_global_concurrency_limit.assert_called_once_with(
        name=various_global_concurrency_limits[0].name,
        concurrency_limit=GlobalConcurrencyLimitUpdate(
            active=False,
        ),
    )


def test_update_gcl_to_active(
    update_global_concurrency_limit: mock.AsyncMock,
    various_global_concurrency_limits: List[GlobalConcurrencyLimit],
):
    various_global_concurrency_limits[0].active = False
    update_global_concurrency_limit.return_value = various_global_concurrency_limits[0]

    invoke_and_assert(
        [
            "global-concurrency-limit",
            "update",
            various_global_concurrency_limits[0].name,
            "--enable",
        ],
        expected_output=f"Updated global concurrency limit with name '{various_global_concurrency_limits[0].name}'.",
        expected_code=0,
    )
    update_global_concurrency_limit.assert_called_once_with(
        name=various_global_concurrency_limits[0].name,
        concurrency_limit=GlobalConcurrencyLimitUpdate(
            active=True,
        ),
    )


def test_update_gcl_not_found():
    invoke_and_assert(
        ["global-concurrency-limit", "update", "not-found"],
        expected_output="Global concurrency limit 'not-found' not found.",
        expected_code=1,
    )
