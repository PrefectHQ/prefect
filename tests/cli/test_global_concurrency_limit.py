import sys
from typing import Generator, List
from unittest import mock
from uuid import UUID

import pytest
from typer import Exit

from prefect.client.schemas.actions import GlobalConcurrencyLimitUpdate
from prefect.client.schemas.objects import GlobalConcurrencyLimit
from prefect.server import models
from prefect.server.schemas.core import ConcurrencyLimitV2
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@pytest.fixture(autouse=True)
def interactive_console(monkeypatch):
    monkeypatch.setattr(
        "prefect.cli.global_concurrency_limit.is_interactive", lambda: True
    )

    # `readchar` does not like the fake stdin provided by typer isolation so we provide
    # a version that does not require a fd to be attached
    def readchar():
        sys.stdin.flush()
        position = sys.stdin.tell()
        if not sys.stdin.read():
            print("TEST ERROR: CLI is attempting to read input but stdin is empty.")
            raise Exit(-2)
        else:
            sys.stdin.seek(position)
        return sys.stdin.read(1)

    monkeypatch.setattr("readchar._posix_read.readchar", readchar)


@pytest.fixture
def read_global_concurrency_limits() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.read_global_concurrency_limits",
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
        "prefect.client.orchestration.PrefectClient.read_global_concurrency_limit_by_name",
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


def test_inspecting_gcl_with_json_output(
    global_concurrency_limit: ConcurrencyLimitV2,
):
    """Test global-concurrency-limit inspect command with JSON output flag."""
    import json

    result = invoke_and_assert(
        [
            "global-concurrency-limit",
            "inspect",
            global_concurrency_limit.name,
            "--output",
            "json",
        ],
        expected_code=0,
    )

    # Parse JSON output and verify it's valid JSON
    output_data = json.loads(result.stdout.strip())

    # Verify key fields are present
    assert "id" in output_data
    assert "name" in output_data
    assert "limit" in output_data
    assert output_data["name"] == global_concurrency_limit.name
    assert output_data["limit"] == global_concurrency_limit.limit


@pytest.fixture
def delete_global_concurrency_limit_by_name() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.delete_global_concurrency_limit_by_name",
    ) as m:
        yield m


def test_deleting_gcl_succeeds(
    delete_global_concurrency_limit_by_name: mock.AsyncMock,
    global_concurrency_limit: ConcurrencyLimitV2,
):
    invoke_and_assert(
        [
            "global-concurrency-limit",
            "delete",
            global_concurrency_limit.name,
        ],
        prompts_and_responses=[
            (
                f"Are you sure you want to delete global concurrency limit with name '{global_concurrency_limit.name}'?",
                "y",
            )
        ],
        expected_output_contains=f"Deleted global concurrency limit with name '{global_concurrency_limit.name}'.",
        expected_code=0,
    )
    delete_global_concurrency_limit_by_name.assert_called_once_with(
        name=global_concurrency_limit.name
    )


def test_deleting_gcl_not_found():
    invoke_and_assert(
        "global-concurrency-limit delete not-found",
        expected_output_contains="Global concurrency limit 'not-found' not found.",
        expected_output_does_not_contain="Are you sure you want to delete global concurrency limit with name 'non-found'?",
        expected_code=1,
    )


@pytest.fixture
def update_global_concurrency_limit() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.update_global_concurrency_limit",
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
        concurrency_limit=GlobalConcurrencyLimitUpdate(active=True),
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


@pytest.fixture
async def global_concurrency_limit(session):
    gcl_schema = ConcurrencyLimitV2(
        name="test",
        limit=1,
        active_slots=1,
        slot_decay_per_second=0.1,
    )
    model = await models.concurrency_limits_v2.create_concurrency_limit(
        session=session, concurrency_limit=gcl_schema
    )

    await session.commit()
    return model


async def test_update_gcl_limit(
    global_concurrency_limit: ConcurrencyLimitV2,
    prefect_client,
):
    assert global_concurrency_limit.limit == 1
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "global-concurrency-limit",
            "update",
            global_concurrency_limit.name,
            "--limit",
            "10",
        ],
        expected_output=f"Updated global concurrency limit with name '{global_concurrency_limit.name}'.",
        expected_code=0,
    )

    client_res = await prefect_client.read_global_concurrency_limit_by_name(
        name=global_concurrency_limit.name
    )

    assert client_res.limit == 10, f"Expected limit to be 10, got {client_res.limit}"


async def test_update_gcl_active_slots(
    global_concurrency_limit: ConcurrencyLimitV2,
    prefect_client,
):
    assert global_concurrency_limit.active_slots == 1
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "global-concurrency-limit",
            "update",
            global_concurrency_limit.name,
            "--active-slots",
            "10",
        ],
        expected_output=f"Updated global concurrency limit with name '{global_concurrency_limit.name}'.",
        expected_code=0,
    )

    client_res = await prefect_client.read_global_concurrency_limit_by_name(
        name=global_concurrency_limit.name
    )

    assert client_res.active_slots == 10, (
        f"Expected active slots to be 10, got {client_res.active_slots}"
    )


async def test_update_gcl_slot_decay_per_second(
    global_concurrency_limit: ConcurrencyLimitV2,
    prefect_client,
):
    assert global_concurrency_limit.slot_decay_per_second == 0.1
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "global-concurrency-limit",
            "update",
            global_concurrency_limit.name,
            "--slot-decay-per-second",
            "0.5",
        ],
        expected_output=f"Updated global concurrency limit with name '{global_concurrency_limit.name}'.",
        expected_code=0,
    )

    client_res = await prefect_client.read_global_concurrency_limit_by_name(
        name=global_concurrency_limit.name
    )

    assert client_res.slot_decay_per_second == 0.5, (
        f"Expected slot decay per second to be 0.5, got {client_res.slot_decay_per_second}"
    )


async def test_update_gcl_multiple_fields(
    global_concurrency_limit: ConcurrencyLimitV2,
    prefect_client,
):
    assert global_concurrency_limit.active_slots == 1
    assert global_concurrency_limit.slot_decay_per_second == 0.1

    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "global-concurrency-limit",
            "update",
            global_concurrency_limit.name,
            "--active-slots",
            "10",
            "--slot-decay-per-second",
            "0.5",
        ],
        expected_output=f"Updated global concurrency limit with name '{global_concurrency_limit.name}'.",
        expected_code=0,
    )

    client_res = await prefect_client.read_global_concurrency_limit_by_name(
        name=global_concurrency_limit.name
    )

    assert client_res.active_slots == 10, (
        f"Expected active slots to be 10, got {client_res.active_slots}"
    )
    assert client_res.slot_decay_per_second == 0.5, (
        f"Expected slot decay per second to be 0.5, got {client_res.slot_decay_per_second}"
    )


async def test_update_gcl_to_inactive(
    global_concurrency_limit: ConcurrencyLimitV2,
    prefect_client,
):
    assert global_concurrency_limit.active is True
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "global-concurrency-limit",
            "update",
            global_concurrency_limit.name,
            "--disable",
        ],
        expected_output=f"Updated global concurrency limit with name '{global_concurrency_limit.name}'.",
        expected_code=0,
    )

    client_res = await prefect_client.read_global_concurrency_limit_by_name(
        name=global_concurrency_limit.name
    )

    assert client_res.active is False, (
        f"Expected active to be False, got {client_res.active}"
    )


async def test_update_gcl_to_active(
    global_concurrency_limit: ConcurrencyLimitV2,
    prefect_client,
):
    global_concurrency_limit.active = False
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "global-concurrency-limit",
            "update",
            global_concurrency_limit.name,
            "--enable",
        ],
        expected_output=f"Updated global concurrency limit with name '{global_concurrency_limit.name}'.",
        expected_code=0,
    )

    client_res = await prefect_client.read_global_concurrency_limit_by_name(
        name=global_concurrency_limit.name
    )

    assert client_res.active is True, (
        f"Expected active to be True, got {client_res.active}"
    )


def test_update_gcl_not_found():
    invoke_and_assert(
        ["global-concurrency-limit", "update", "not-found", "--limit", "10"],
        expected_output_contains="Global concurrency limit 'not-found' not found.",
        expected_code=1,
    )


def test_update_gcl_no_fields():
    invoke_and_assert(
        ["global-concurrency-limit", "update", "test"],
        expected_output_contains="No update arguments provided.",
        expected_code=1,
    )


async def test_create_gcl(
    prefect_client,
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "global-concurrency-limit",
            "create",
            "test",
            "--limit",
            "10",
            "--active-slots",
            "10",
            "--slot-decay-per-second",
            "0.5",
        ],
        expected_output_contains="Created global concurrency limit with name 'test' and ID",
        expected_code=0,
    )

    client_res = await prefect_client.read_global_concurrency_limit_by_name(name="test")

    assert client_res.name == "test", (
        f"Expected name to be 'test', got {client_res.name}"
    )
    assert client_res.limit == 10, f"Expected limit to be 10, got {client_res.limit}"
    assert client_res.active_slots == 10, (
        f"Expected active slots to be 10, got {client_res.active_slots}"
    )
    assert client_res.slot_decay_per_second == 0.5, (
        f"Expected slot decay per second to be 0.5, got {client_res.slot_decay_per_second}"
    )


async def test_create_gcl_no_fields():
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "global-concurrency-limit",
            "create",
            "test",
        ],
        expected_code=2,
    )


async def test_create_gcl_invalid_limit():
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "global-concurrency-limit",
            "create",
            "test",
            "--limit",
            "-1",
        ],
        expected_output_contains="Invalid arguments provided",
        expected_code=1,
    )


async def test_create_gcl_invalid_active_slots():
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "global-concurrency-limit",
            "create",
            "test",
            "--limit",
            "1",
            "--active-slots",
            "-1",
        ],
        expected_output_contains="Invalid arguments provided",
        expected_code=1,
    )


async def test_create_gcl_invalid_slot_decay_per_second():
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "global-concurrency-limit",
            "create",
            "test",
            "--limit",
            "1",
            "--active-slots",
            "1",
            "--slot-decay-per-second",
            "-1",
        ],
        expected_output_contains="Invalid arguments provided",
        expected_code=1,
    )


async def test_create_gcl_duplicate_name(
    global_concurrency_limit: ConcurrencyLimitV2,
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "global-concurrency-limit",
            "create",
            global_concurrency_limit.name,
            "--limit",
            "10",
            "--active-slots",
            "10",
            "--slot-decay-per-second",
            "0.5",
        ],
        expected_output_contains=f"Global concurrency limit '{global_concurrency_limit.name}' already exists.",
        expected_code=1,
    )


async def test_create_gcl_succeeds(
    prefect_client,
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "global-concurrency-limit",
            "create",
            "test",
            "--limit",
            "10",
            "--active-slots",
            "10",
            "--slot-decay-per-second",
            "0.5",
        ],
        expected_output_contains="Created global concurrency limit with name 'test' and ID",
        expected_code=0,
    )

    client_res = await prefect_client.read_global_concurrency_limit_by_name(name="test")

    assert client_res.name == "test", (
        f"Expected name to be 'test', got {client_res.name}"
    )
    assert client_res.limit == 10, f"Expected limit to be 10, got {client_res.limit}"
    assert client_res.active_slots == 10, (
        f"Expected active slots to be 10, got {client_res.active_slots}"
    )
    assert client_res.slot_decay_per_second == 0.5, (
        f"Expected slot decay per second to be 0.5, got {client_res.slot_decay_per_second}"
    )
