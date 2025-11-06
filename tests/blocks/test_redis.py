import os
from pathlib import Path
from typing import Union
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic.types import SecretStr

from prefect.blocks.redis import RedisStorageContainer


@pytest.fixture
async def redis_config() -> dict[str, Union[str, int, None]]:
    return {
        "host": os.environ.get("TEST_REDIS_HOST", "localhost"),
        "port": int(os.environ.get("TEST_REDIS_PORT", 6379)),
        "db": int(os.environ.get("TEST_REDIS_DB", 0)),
        "username": os.environ.get("TEST_REDIS_USERNAME"),
        "password": os.environ.get("TEST_REDIS_PASSWORD"),
    }


@pytest.fixture
async def redis_from_host(redis_config: dict) -> RedisStorageContainer:
    return RedisStorageContainer.from_host(**redis_config)


@pytest.fixture
async def redis_from_connection_string(redis_config: dict) -> RedisStorageContainer:
    connection_string = (
        f"redis://{redis_config['host']}:{redis_config['port']}/{redis_config['db']}"
    )
    return RedisStorageContainer.from_connection_string(connection_string)


async def test_initialize_from_host(redis_config: dict):
    redis = RedisStorageContainer.from_host(**redis_config)

    assert redis.host == redis_config["host"]
    assert redis.port == redis_config["port"]
    assert redis.db == redis_config["db"]
    assert redis.username == redis_config["username"]
    assert redis.password == redis_config["password"]


async def test_initialize_without_host_fails():
    with pytest.raises(ValueError, match="'host' is required"):
        RedisStorageContainer(host=None)


async def test_initialize_with_username_but_no_password_fails():
    with pytest.raises(
        ValueError, match="'username' is provided, but 'password' is missing"
    ):
        RedisStorageContainer(
            host="localhost", username=SecretStr("test_user"), password=None
        )


async def test_read_write_path_from_host(redis_from_host: RedisStorageContainer):
    await redis_from_host.write_path("test_key", b"test_value")
    assert await redis_from_host.read_path("test_key") == b"test_value"


async def test_read_write_path_from_connection_string(
    redis_from_connection_string: RedisStorageContainer,
):
    await redis_from_connection_string.write_path("test_key", b"test_value")
    assert await redis_from_connection_string.read_path("test_key") == b"test_value"


async def test_read_write_path_pathlib(redis_from_host: RedisStorageContainer):
    path = Path("hello/world.txt")
    await redis_from_host.write_path(path, b"Hi there!")
    assert await redis_from_host.read_path(path) == b"Hi there!"


class TestAsyncDispatch:
    async def test_aread_path_async_context(self):
        redis = RedisStorageContainer.from_host(host="localhost")

        with patch("redis.asyncio.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = b"test_value"
            mock_client.aclose = AsyncMock()
            mock_redis_class.return_value = mock_client

            result = await redis.aread_path("test_key")

            assert result == b"test_value"
            mock_client.get.assert_called_once_with("test_key")

    async def test_awrite_path_async_context(self):
        redis = RedisStorageContainer.from_host(host="localhost")

        with patch("redis.asyncio.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.set.return_value = True
            mock_client.aclose = AsyncMock()
            mock_redis_class.return_value = mock_client

            result = await redis.awrite_path("test_key", b"test_value")

            assert result is True
            mock_client.set.assert_called_once_with("test_key", b"test_value")

    async def test_read_path_async_context(self):
        redis = RedisStorageContainer.from_host(host="localhost")

        with patch("redis.asyncio.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = b"async_value"
            mock_client.aclose = AsyncMock()
            mock_redis_class.return_value = mock_client

            result = await redis.read_path("test_key")

            assert result == b"async_value"
            mock_client.get.assert_called_once_with("test_key")

    async def test_write_path_async_context(self):
        redis = RedisStorageContainer.from_host(host="localhost")

        with patch("redis.asyncio.Redis") as mock_redis_class:
            mock_client = AsyncMock()
            mock_client.set.return_value = True
            mock_client.aclose = AsyncMock()
            mock_redis_class.return_value = mock_client

            result = await redis.write_path("test_key", b"test_value")

            assert result is True
            mock_client.set.assert_called_once_with("test_key", b"test_value")

    def test_read_path_sync_context(self):
        redis = RedisStorageContainer.from_host(host="localhost")

        with patch("redis.Redis") as mock_redis_class:
            mock_client = MagicMock()
            mock_client.get.return_value = b"sync_value"
            mock_redis_class.return_value = mock_client

            result = redis.read_path("test_key")

            assert result == b"sync_value"
            mock_client.get.assert_called_once_with("test_key")

    def test_write_path_sync_context(self):
        redis = RedisStorageContainer.from_host(host="localhost")

        with patch("redis.Redis") as mock_redis_class:
            mock_client = MagicMock()
            mock_client.set.return_value = True
            mock_redis_class.return_value = mock_client

            result = redis.write_path("test_key", b"test_value")

            assert result is True
            mock_client.set.assert_called_once_with("test_key", b"test_value")
