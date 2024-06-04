import os
from typing import Union

import pytest
from prefect_redis.filesystem import RedisFilesystem
from pydantic.types import SecretStr


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
async def redis_from_host(redis_config: dict) -> RedisFilesystem:
    return RedisFilesystem.from_host(**redis_config)


@pytest.fixture
async def redis_from_connection_string(redis_config: dict) -> RedisFilesystem:
    connection_string = (
        f"redis://{redis_config['host']}:{redis_config['port']}/{redis_config['db']}"
    )
    return RedisFilesystem.from_connection_string(connection_string)


async def test_initialize_from_host(redis_config: dict):
    redis = RedisFilesystem.from_host(**redis_config)

    assert redis.host == redis_config["host"]
    assert redis.port == redis_config["port"]
    assert redis.db == redis_config["db"]
    assert redis.username == redis_config["username"]
    assert redis.password == redis_config["password"]


async def test_initialize_without_host_fails():
    with pytest.raises(ValueError, match="'host' is required"):
        RedisFilesystem(host=None)


async def test_initialize_with_username_but_no_password_fails():
    with pytest.raises(
        ValueError, match="'username' is provided, but 'password' is missing"
    ):
        RedisFilesystem(
            host="localhost", username=SecretStr("test_user"), password=None
        )


async def test_read_write_path_from_host(redis_from_host: RedisFilesystem):
    await redis_from_host.write_path("test_key", b"test_value")
    assert await redis_from_host.read_path("test_key") == b"test_value"


async def test_read_write_path_from_connection_string(
    redis_from_connection_string: RedisFilesystem,
):
    await redis_from_connection_string.write_path("test_key", b"test_value")
    assert await redis_from_connection_string.read_path("test_key") == b"test_value"
