"""Test Redis tasks"""

import os
import random
import string
from typing import Dict

import pytest
from prefect_redis import (
    RedisDatabase,
    redis_execute,
    redis_get,
    redis_get_binary,
    redis_set,
    redis_set_binary,
)


@pytest.fixture
def environ_credentials() -> Dict:
    """Get redis credentials from environment

    Returns:
        Redis credentials as a dict, can be piped directly into `RedisCredentials`
    """
    return {
        "host": os.environ.get("TEST_REDIS_HOST", "localhost"),
        "port": int(os.environ.get("TEST_REDIS_PORT", 6379)),
        "db": int(os.environ.get("TEST_REDIS_DB", 0)),
        "username": os.environ.get("TEST_REDIS_USERNAME"),
        "password": os.environ.get("TEST_REDIS_PASSWORD"),
    }


@pytest.fixture
def redis_credentials(environ_credentials: Dict) -> RedisDatabase:
    """Get `RedisCredentials` object from environment

    Returns:
        `RedisCredentials` object
    """
    return RedisDatabase(**environ_credentials)


@pytest.fixture
def random_key() -> str:
    """Generate a random key

    Returns:
        A random string of length 10
    """
    return "".join(random.sample(string.ascii_lowercase, 10))


async def test_from_credentials(redis_credentials: RedisDatabase):
    """Test instantiating credentials"""
    client = redis_credentials.get_async_client()
    await client.ping()

    await client.aclose()


async def test_from_credentials_sync(redis_credentials: RedisDatabase):
    """Test instantiating credentials"""
    client = redis_credentials.get_client()
    client.ping()

    client.close()


async def test_from_connection_string(environ_credentials: Dict):
    """Test instantiating from connection string"""

    connection_string = "redis://@{host}:{port}/{db}".format(**environ_credentials)
    redis_credentials = RedisDatabase.from_connection_string(connection_string)

    client = redis_credentials.get_async_client()
    await client.ping()

    await client.aclose()


async def test_from_connection_string_sync(environ_credentials: Dict):
    """Test instantiating from connection string"""

    connection_string = "redis://@{host}:{port}/{db}".format(**environ_credentials)
    redis_credentials = RedisDatabase.from_connection_string(connection_string)

    client = redis_credentials.get_client()
    client.ping()

    client.close()


async def test_set_get_bytes(redis_credentials: RedisDatabase, random_key: str):
    """Test writing and reading back a byte-string"""

    ref_string = b"hello world"

    await redis_set_binary.fn(redis_credentials, random_key, ref_string, ex=60)
    test_value = await redis_get_binary.fn(redis_credentials, random_key)

    assert test_value == ref_string


async def test_set_get(redis_credentials: RedisDatabase, random_key: str):
    """Test writing and reading back a string"""

    ref_string = "hello world"

    await redis_set.fn(redis_credentials, random_key, ref_string, ex=60)
    test_value = await redis_get.fn(redis_credentials, random_key)

    assert test_value == ref_string


async def test_set_obj(redis_credentials: RedisDatabase, random_key: str):
    """Test writing and reading back an object"""

    ref_obj = ("foobar", 123, {"hello": "world"})

    await redis_set.fn(redis_credentials, random_key, ref_obj, ex=60)
    test_value = await redis_get.fn(redis_credentials, random_key)

    assert type(ref_obj) is type(test_value)
    assert len(ref_obj) == len(test_value)

    assert ref_obj[0] == test_value[0]
    assert ref_obj[1] == test_value[1]

    ref_dct = ref_obj[2]
    test_dct = test_value[2]

    for ref_key, test_key in zip(ref_dct, test_dct):
        assert ref_key == test_key
        assert ref_dct[ref_key] == test_dct[test_key]


async def test_execute(redis_credentials: RedisDatabase):
    """Test executing a command"""

    await redis_execute.fn(redis_credentials, "ping")
