"""Tests for text search functionality across logs storage backends"""

from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Union
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models
from prefect.server.models.logs import read_logs
from prefect.server.schemas.actions import LogCreate
from prefect.server.schemas.core import Log
from prefect.server.schemas.filters import (
    LogFilter,
    LogFilterLevel,
    LogFilterTextSearch,
)
from prefect.server.schemas.sorting import LogSort

# Define function types for our test variations
QueryLogsFn = Callable[..., Awaitable[list[Log]]]


# In-memory log search that intentionally matches read_logs() signature
async def query_logs_memory(
    session: list[Log],  # For memory tests, this will be the list of logs
    log_filter: LogFilter,
    limit: int,
    offset: int,
    sort: LogSort = LogSort.TIMESTAMP_ASC,
) -> list[Log]:
    """In-memory log filtering using LogFilter.includes() method.

    This function intentionally shares the signature of the database counterpart
    (read_logs) and is used for filtering on WebSockets and other testing use cases
    where we need to filter logs in memory rather than in the database.
    """

    # Alias for clarity - session is actually a list of logs for memory tests
    logs_list = session

    # Filter logs using the LogFilter.includes() method
    filtered_logs = []
    for log in logs_list:
        # Check each individual filter
        if log_filter.level and not _log_level_matches(log, log_filter.level):
            continue
        if log_filter.timestamp and not _log_timestamp_matches(
            log, log_filter.timestamp
        ):
            continue
        if log_filter.flow_run_id and not _log_flow_run_id_matches(
            log, log_filter.flow_run_id
        ):
            continue
        if log_filter.task_run_id and not _log_task_run_id_matches(
            log, log_filter.task_run_id
        ):
            continue
        if log_filter.text and not log_filter.text.includes(log):
            continue
        filtered_logs.append(log)

    # Apply sorting
    if sort == LogSort.TIMESTAMP_ASC:
        filtered_logs.sort(key=lambda log: log.timestamp)
    else:  # TIMESTAMP_DESC
        filtered_logs.sort(key=lambda log: log.timestamp, reverse=True)

    # Apply pagination
    start_idx = offset
    end_idx = offset + limit
    return filtered_logs[start_idx:end_idx]


def _log_level_matches(log: Log, level_filter: LogFilterLevel) -> bool:
    """Check if log matches level filter"""
    if level_filter.ge_ is not None and log.level < level_filter.ge_:
        return False
    if level_filter.le_ is not None and log.level > level_filter.le_:
        return False
    return True


def _log_timestamp_matches(log: Log, timestamp_filter) -> bool:
    """Check if log matches timestamp filter"""
    if (
        timestamp_filter.before_ is not None
        and log.timestamp > timestamp_filter.before_
    ):
        return False
    if timestamp_filter.after_ is not None and log.timestamp < timestamp_filter.after_:
        return False
    return True


def _log_flow_run_id_matches(log: Log, flow_run_id_filter) -> bool:
    """Check if log matches flow run id filter"""
    if flow_run_id_filter.any_ is not None:
        return log.flow_run_id in flow_run_id_filter.any_
    return True


def _log_task_run_id_matches(log: Log, task_run_id_filter) -> bool:
    """Check if log matches task run id filter"""
    if task_run_id_filter.any_ is not None:
        return log.task_run_id in task_run_id_filter.any_
    if task_run_id_filter.is_null_ is not None:
        if task_run_id_filter.is_null_:
            return log.task_run_id is None
        else:
            return log.task_run_id is not None
    return True


VARIATIONS: list[tuple[str, QueryLogsFn]] = [
    ("memory", query_logs_memory),
    ("database", read_logs),
]


def pytest_generate_tests(metafunc: pytest.Metafunc):
    fixtures = set(metafunc.fixturenames)

    # If the test itself includes a marker saying that it is for only one variation,
    # then honor that marker and filter the test generation down to just that
    variation_names = {v[0] for v in VARIATIONS}
    marked_variations = {
        mark.name
        for mark in metafunc.definition.own_markers
        if mark.name in variation_names
    }
    if marked_variations:
        variation_names = variation_names.intersection(marked_variations)

    def marks(variation: str) -> list[pytest.MarkDecorator]:
        return []

    if fixtures.issuperset({"logs_query_session", "query_logs"}):
        metafunc.parametrize(
            "logs_query_session, query_logs",
            [
                pytest.param(
                    *values[:2],
                    id=values[0],
                    marks=marks(values[0]),
                )
                for values in VARIATIONS
                if values[0] in variation_names
            ],
            indirect=["logs_query_session"],
        )


@pytest.fixture
def test_logs() -> list[Log]:
    """Create test logs with various text content for searching"""

    test_data = [
        # Error logs
        {
            "name": "prefect.flow_runs",
            "message": "Flow run failed with connection timeout",
            "level": 40,  # ERROR
        },
        {
            "name": "prefect.task_runs",
            "message": "Task failed to process data due to network error",
            "level": 40,  # ERROR
        },
        # Debug logs
        {
            "name": "prefect.flow_runs",
            "message": "Debug: Starting flow execution in test environment",
            "level": 10,  # DEBUG
        },
        # Info logs
        {
            "name": "prefect.deployments",
            "message": "Successfully deployed to production environment",
            "level": 20,  # INFO
        },
        # Warning logs
        {
            "name": "prefect.workers",
            "message": "Warning: high memory usage detected",
            "level": 30,  # WARNING
        },
        # Logs with quoted phrases
        {
            "name": "prefect.flow_runs",
            "message": "Unable to connect to database server",
            "level": 40,  # ERROR
        },
        # International characters - Japanese
        {
            "name": "prefect.フロー実行",
            "message": "データベース接続エラーが発生しました",
            "level": 40,  # ERROR
        },
        # International characters - French with accents
        {
            "name": "prefect.déploiements",
            "message": "Erreur de connexión à la base de données",
            "level": 40,  # ERROR
        },
    ]

    logs: list[Log] = []
    base_time = datetime.now(timezone.utc)

    for i, data in enumerate(test_data):
        logs.append(
            Log(
                id=uuid4(),
                created=base_time - timedelta(hours=i),
                updated=base_time - timedelta(hours=i),
                name=data["name"],
                level=data["level"],
                flow_run_id=uuid4(),
                task_run_id=None if i % 2 == 0 else uuid4(),
                message=data["message"],
                timestamp=base_time - timedelta(hours=i),
            )
        )

    return logs


@pytest.fixture
async def logs_query_session(
    request: pytest.FixtureRequest,
    test_logs: list[Log],
    session: AsyncSession,
):
    """Opens an appropriate session for the given backend, seeds it with the
    test logs, and returns it for use in tests"""

    backend: str = request.param
    if backend == "memory":
        yield test_logs
    elif backend == "database":
        # Write test logs to database
        log_creates = [
            LogCreate(
                name=log.name,
                level=log.level,
                flow_run_id=log.flow_run_id,
                task_run_id=log.task_run_id,
                message=log.message,
                timestamp=log.timestamp,
            )
            for log in test_logs
        ]
        await models.logs.create_logs(session=session, logs=log_creates)
        await session.commit()
        yield session
    else:
        raise NotImplementedError(f"Unknown backend: {backend}")


# Test cases for basic text search functionality


async def test_single_term_search(
    logs_query_session: Union[list[Log], AsyncSession],
    query_logs: QueryLogsFn,
):
    """Test searching for a single term that appears in log messages"""

    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(text=LogFilterTextSearch(query="error")),
        limit=100,
        offset=0,
    )

    # Should find logs with "error" in message or name
    assert len(logs) >= 1
    for log in logs:
        searchable_text = f"{log.message} {log.name}".lower()
        assert "error" in searchable_text


async def test_multiple_terms_or_logic(
    logs_query_session: list[Log],
    query_logs: QueryLogsFn,
):
    """Test space-separated terms should use OR logic"""

    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(text=LogFilterTextSearch(query="error success")),
        limit=100,
        offset=0,
    )

    # Should find logs with either "error" OR "success"
    assert len(logs) >= 2
    for log in logs:
        searchable_text = f"{log.message} {log.name}".lower()
        assert "error" in searchable_text or "success" in searchable_text


async def test_negative_terms_with_minus(
    logs_query_session: list[Log],
    query_logs: QueryLogsFn,
):
    """Test excluding terms with minus prefix"""

    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(text=LogFilterTextSearch(query="flow -debug")),
        limit=100,
        offset=0,
    )

    # Should find logs with "flow" but NOT "debug"
    assert len(logs) >= 1
    for log in logs:
        searchable_text = f"{log.message} {log.name}".lower()
        assert "flow" in searchable_text
        assert "debug" not in searchable_text


async def test_negative_terms_with_exclamation(
    logs_query_session: list[Log],
    query_logs: QueryLogsFn,
):
    """Test excluding terms with exclamation prefix"""

    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(text=LogFilterTextSearch(query="flow !test")),
        limit=100,
        offset=0,
    )

    # Should find logs with "flow" but NOT "test"
    assert len(logs) >= 1
    for log in logs:
        searchable_text = f"{log.message} {log.name}".lower()
        assert "flow" in searchable_text
        assert "test" not in searchable_text


async def test_quoted_phrase_search(
    logs_query_session: list[Log],
    query_logs: QueryLogsFn,
):
    """Test searching for exact phrases with quotes"""

    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(text=LogFilterTextSearch(query='"connection timeout"')),
        limit=100,
        offset=0,
    )

    # Should find logs with exact phrase "connection timeout"
    assert len(logs) >= 1
    for log in logs:
        searchable_text = f"{log.message} {log.name}".lower()
        assert "connection timeout" in searchable_text


async def test_quoted_phrase_exclusion(
    logs_query_session: list[Log],
    query_logs: QueryLogsFn,
):
    """Test excluding exact phrases with quotes and minus"""

    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(
            text=LogFilterTextSearch(query='flow -"connection timeout"')
        ),
        limit=100,
        offset=0,
    )

    # Should find logs with "flow" but NOT the exact phrase "connection timeout"
    for log in logs:
        searchable_text = f"{log.message} {log.name}".lower()
        assert "flow" in searchable_text
        assert "connection timeout" not in searchable_text


async def test_case_insensitive_search(
    logs_query_session: list[Log],
    query_logs: QueryLogsFn,
):
    """Test that searches are case insensitive"""

    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(text=LogFilterTextSearch(query="FAILED")),
        limit=100,
        offset=0,
    )

    # Should find logs with "failed" (lowercase in message)
    assert len(logs) >= 1
    for log in logs:
        searchable_text = f"{log.message} {log.name}".lower()
        assert "failed" in searchable_text


async def test_searches_message_content(
    logs_query_session: list[Log],
    query_logs: QueryLogsFn,
):
    """Test that search covers log message content"""

    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(text=LogFilterTextSearch(query="database")),
        limit=100,
        offset=0,
    )

    assert len(logs) >= 1
    # Should find logs with "database" in message
    assert any("database" in log.message.lower() for log in logs)


async def test_searches_logger_name(
    logs_query_session: list[Log],
    query_logs: QueryLogsFn,
):
    """Test that search covers logger names"""

    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(text=LogFilterTextSearch(query="deployments")),
        limit=100,
        offset=0,
    )

    assert len(logs) >= 1
    # Should find logs with "deployments" in logger name
    assert any("deployments" in log.name.lower() for log in logs)


async def test_complex_combined_search(
    logs_query_session: list[Log],
    query_logs: QueryLogsFn,
):
    """Test complex query combining multiple features"""

    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(
            text=LogFilterTextSearch(query='flow error -debug -"connection timeout"')
        ),
        limit=100,
        offset=0,
    )

    # Should find logs with "flow" OR "error" but NOT "debug" or "connection timeout"
    for log in logs:
        searchable_text = f"{log.message} {log.name}".lower()
        assert "flow" in searchable_text or "error" in searchable_text
        assert "debug" not in searchable_text
        assert "connection timeout" not in searchable_text


async def test_empty_query_returns_all(
    logs_query_session: list[Log],
    query_logs: QueryLogsFn,
    test_logs: list[Log],
):
    """Test that empty query returns all results like no text filter"""

    # Query with empty text
    logs_with_empty_text = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(text=LogFilterTextSearch(query="")),
        limit=100,
        offset=0,
    )

    # Query without text filter
    logs_no_text = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(),
        limit=100,
        offset=0,
    )

    # Should return same results
    assert len(logs_with_empty_text) == len(logs_no_text)


async def test_no_matches_returns_empty(
    logs_query_session: list[Log],
    query_logs: QueryLogsFn,
):
    """Test that searches with no matches return empty results"""

    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(text=LogFilterTextSearch(query="nonexistentterm12345")),
        limit=100,
        offset=0,
    )

    assert len(logs) == 0


async def test_text_filter_composable_with_other_filters(
    logs_query_session: list[Log],
    query_logs: QueryLogsFn,
):
    """Test that text filter works with other existing filters"""

    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(
            text=LogFilterTextSearch(query="flow"),
            level=LogFilterLevel(ge_=30),  # WARNING level and above
        ),
        limit=100,
        offset=0,
    )

    # Should find logs with "flow" AND level >= 30 (WARNING/ERROR)
    for log in logs:
        searchable_text = f"{log.message} {log.name}".lower()
        assert "flow" in searchable_text
        assert log.level >= 30


async def test_multilingual_character_search(
    logs_query_session: list[Log],
    query_logs: QueryLogsFn,
):
    """Test that international characters work through the full stack"""

    # Test Japanese characters in logger name
    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(text=LogFilterTextSearch(query="フロー実行")),
        limit=100,
        offset=0,
    )

    assert len(logs) >= 1
    # Should find logs with Japanese characters in logger name
    assert any("フロー実行" in log.name for log in logs)

    # Test French accents in message content
    logs = await query_logs(
        session=logs_query_session,
        log_filter=LogFilter(text=LogFilterTextSearch(query="connexión")),
        limit=100,
        offset=0,
    )

    assert len(logs) >= 1
    # Should find logs with French accented characters
    assert any("connexión" in log.message for log in logs)
