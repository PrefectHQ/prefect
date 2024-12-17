import asyncio
import sys
from typing import AsyncGenerator, Generator

import pytest
from prefect_redis.client import close_all_cached_connections, get_async_redis_client
from pytest_asyncio import is_async_test
from redis.asyncio import Redis

from prefect.testing.utilities import prefect_test_harness


def pytest_collection_modifyitems(items: list[pytest.Item]):
    # Ensure that all async tests are run with the session loop scope
    pytest_asyncio_tests = [item for item in items if is_async_test(item)]
    session_scope_marker = pytest.mark.asyncio(loop_scope="session")
    for async_test in pytest_asyncio_tests:
        async_test.add_marker(session_scope_marker, append=False)


@pytest.fixture(scope="session")
def event_loop_policy():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    return asyncio.get_event_loop_policy()


@pytest.fixture(scope="session", autouse=True)
def prefect_db():
    """
    Sets up test harness for temporary DB during test runs.
    """
    with prefect_test_harness():
        yield


@pytest.fixture(scope="function", autouse=True)
def isolated_redis_db_number(worker_id, monkeypatch) -> Generator[int, None, None]:
    """
    Isolates redis db number for xdist workers.
    """
    # Assign a unique DB per xdist worker
    if not worker_id or "gw" not in worker_id:
        db_num = 1
    else:
        db_num = 2 + int(worker_id.replace("gw", ""))

    # Update settings so that get_async_redis_client()
    # creates clients connected to this db_num
    monkeypatch.setenv("PREFECT_REDIS_MESSAGING_DB", str(db_num))
    yield db_num


@pytest.fixture(autouse=True)
async def redis(isolated_redis_db_number: None) -> AsyncGenerator[Redis, None]:
    client: Redis = get_async_redis_client()
    assert client.get_connection_kwargs()["db"] == isolated_redis_db_number
    yield client
    await client.aclose()


@pytest.fixture(autouse=True)
async def flush_redis_database(redis: Redis):
    """
    Flush the redis database before and after each test.
    """
    await redis.flushdb()
    yield
    await redis.flushdb()


@pytest.fixture(autouse=True, scope="session")
def close_global_redises_after_tests() -> Generator[None, None, None]:
    yield
    close_all_cached_connections()
