import json
from typing import Generator, List
from unittest import mock
from uuid import UUID

import pytest

from prefect.client.schemas.objects import ConcurrencyLimit
from prefect.testing.cli import invoke_and_assert


@pytest.fixture
def read_concurrency_limits() -> Generator[mock.AsyncMock, None, None]:
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.read_concurrency_limits",
    ) as m:
        yield m


@pytest.fixture
def various_concurrency_limits(
    read_concurrency_limits: mock.AsyncMock,
) -> List[ConcurrencyLimit]:
    concurrency_limits = [
        ConcurrencyLimit(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            created="2021-01-01T00:00:00Z",
            updated="2021-01-02T00:00:00Z",
            tag="tag-1",
            concurrency_limit=5,
            active_slots=[],
        ),
        ConcurrencyLimit(
            id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            created="2021-01-01T00:00:00Z",
            updated="2021-01-03T00:00:00Z",
            tag="tag-2",
            concurrency_limit=10,
            active_slots=[],
        ),
    ]
    read_concurrency_limits.return_value = concurrency_limits
    return concurrency_limits


def test_ls(various_concurrency_limits: List[ConcurrencyLimit]):
    invoke_and_assert(
        ["concurrency-limit", "ls"],
        expected_output_contains=(
            "tag-1",
            "tag-2",
        ),
        expected_code=0,
    )


def test_ls_json_output(various_concurrency_limits: List[ConcurrencyLimit]):
    """Test concurrency-limit ls command with JSON output flag."""
    result = invoke_and_assert(
        ["concurrency-limit", "ls", "-o", "json"],
        expected_code=0,
    )

    output_data = json.loads(result.stdout.strip())
    assert isinstance(output_data, list)
    assert len(output_data) == 2

    output_ids = {item["id"] for item in output_data}
    assert str(various_concurrency_limits[0].id) in output_ids
    assert str(various_concurrency_limits[1].id) in output_ids

    # Verify key fields are present
    for item in output_data:
        assert "tag" in item
        assert "concurrency_limit" in item
        assert "active_slots" in item


def test_ls_json_output_empty(read_concurrency_limits: mock.AsyncMock):
    """Test concurrency-limit ls with JSON output when no limits exist."""
    read_concurrency_limits.return_value = []

    result = invoke_and_assert(
        ["concurrency-limit", "ls", "-o", "json"],
        expected_code=0,
    )

    output_data = json.loads(result.stdout.strip())
    assert output_data == []


def test_ls_invalid_output_format():
    """Test concurrency-limit ls with invalid output format."""
    invoke_and_assert(
        ["concurrency-limit", "ls", "-o", "xml"],
        expected_code=1,
        expected_output_contains="Only 'json' output format is supported.",
    )
