import asyncio
import sqlite3
import threading
from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy as sa

from prefect.server import models
from prefect.server.database import provide_database_interface
from prefect.server.utilities.messaging import create_cache
from prefect.server.utilities.messaging.memory import Topic
from prefect.settings import (
    PREFECT_MESSAGING_BROKER,
    PREFECT_MESSAGING_CACHE,
    temporary_settings,
)
from tests.server import ConcurrentCommits

# Use the in-memory implementation of the cache and message broker for server testing


@pytest.fixture(autouse=True)
def events_configuration():
    with temporary_settings(
        {
            PREFECT_MESSAGING_CACHE: "prefect.server.utilities.messaging.memory",
            PREFECT_MESSAGING_BROKER: "prefect.server.utilities.messaging.memory",
        }
    ):
        yield


@pytest.fixture(autouse=True)
def clear_topics(events_configuration: None):
    Topic.clear_all()
    yield
    Topic.clear_all()


@pytest.fixture(autouse=True)
async def reset_recently_seen_messages(events_configuration: None):
    cache = create_cache()
    await cache.clear_recently_seen_messages()
    yield
    await cache.clear_recently_seen_messages()


@pytest.fixture
def commit_after_run_read(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[ConcurrentCommits]:
    """Once armed, have another connection commit a write right after each flow
    run or task run read.

    A deferred SQLite transaction that reads and then writes fails with
    "database is locked" (`SQLITE_BUSY_SNAPSHOT`) if another connection commits
    in between. A transaction started with `BEGIN IMMEDIATE` makes the other
    writer wait until it commits instead.
    """
    db = provide_database_interface()
    if db.dialect.name != "sqlite":
        pytest.skip("Covers SQLite write-lock upgrade behavior")

    database = sa.engine.make_url(db.database_config.connection_url).database
    assert database is not None
    commits = ConcurrentCommits()

    def commit_write(table: str, run_id: str, settled: threading.Event) -> None:
        # With no busy timeout, `BEGIN IMMEDIATE` either commits right away or
        # fails because the transaction under test already holds the write lock.
        connection = sqlite3.connect(database, timeout=0, isolation_level=None)
        try:
            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError:
                settled.set()
                connection.execute("PRAGMA busy_timeout = 60000")
                connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"UPDATE {table} SET updated = updated WHERE id = ?", (run_id,)
            )
            connection.execute("COMMIT")
        finally:
            settled.set()
            connection.close()

    def commit_after(module: Any, name: str, table: str) -> None:
        original = getattr(module, name)

        async def read_then_commit_elsewhere(*args: Any, **kwargs: Any) -> Any:
            run = await original(*args, **kwargs)
            if commits.armed and run is not None:
                settled = threading.Event()
                writer = threading.Thread(
                    target=commit_write, args=(table, str(run.id), settled)
                )
                commits.writers.append(writer)
                writer.start()
                assert await asyncio.to_thread(settled.wait, 60)
            return run

        monkeypatch.setattr(module, name, read_then_commit_elsewhere)

    commit_after(models.flow_runs, "read_flow_run", "flow_run")
    commit_after(models.task_runs, "read_task_run", "task_run")
    yield commits
    for writer in commits.writers:
        writer.join(timeout=60)
        assert not writer.is_alive()
