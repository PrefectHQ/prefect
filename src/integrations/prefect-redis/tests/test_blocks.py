import pytest
from prefect_redis.blocks import RedisDatabase
from pydantic import SecretStr, ValidationError

from prefect import flow, task
from prefect.cache_policies import INPUTS


@pytest.fixture
def redis_block(isolated_redis_db_number: int) -> RedisDatabase:
    return RedisDatabase(host="localhost", port=6379, db=isolated_redis_db_number)


def test_as_connection_params():
    # Test with all fields set
    redis_db = RedisDatabase(
        host="localhost",
        port=6379,
        db=0,
        username=SecretStr("user"),
        password=SecretStr("pass"),
        ssl=True,
    )
    params = redis_db.as_connection_params()
    assert params == {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "username": "user",
        "password": "pass",
        "ssl": True,
    }

    # Test with optional fields omitted
    redis_db = RedisDatabase(host="localhost", port=6379, db=0)
    params = redis_db.as_connection_params()
    assert params == {"host": "localhost", "port": 6379, "db": 0, "ssl": False}
    assert "username" not in params
    assert "password" not in params
    assert "key_ttl" not in params  # write behavior, not a connection param


async def test_key_ttl_sets_expiry_on_written_keys(isolated_redis_db_number, redis):
    block = RedisDatabase(
        host="localhost", port=6379, db=isolated_redis_db_number, key_ttl=100
    )
    await block.write_path("ttl-key", b"value")
    assert 0 < await redis.ttl("ttl-key") <= 100


async def test_no_key_ttl_leaves_keys_without_expiry(isolated_redis_db_number, redis):
    block = RedisDatabase(host="localhost", port=6379, db=isolated_redis_db_number)
    await block.write_path("no-ttl-key", b"value")
    assert await redis.ttl("no-ttl-key") == -1


@pytest.mark.parametrize("bad_ttl", [0, -1])
def test_key_ttl_must_be_positive(bad_ttl):
    # Redis rejects SET ... EX <= 0; fail fast at construction, not at write time.
    with pytest.raises(ValidationError):
        RedisDatabase(host="localhost", port=6379, key_ttl=bad_ttl)



async def test_awrite_then_aread_round_trip(redis_block: RedisDatabase):
    await redis_block.awrite_path("my-key", b"hello")
    assert await redis_block.aread_path("my-key") == b"hello"


def test_write_then_read_round_trip_sync(redis_block: RedisDatabase):
    redis_block.write_path("my-key", b"hello")
    assert redis_block.read_path("my-key") == b"hello"


def test_write_path_accepts_sync_kwarg(redis_block: RedisDatabase):
    # Regression for #22393: core persists results via
    # `call_explicitly_sync_block_method`, which invokes the block method with
    # `_sync=True`. The plain `async def` overrides used to raise TypeError here.
    redis_block.write_path("my-key", b"hello", _sync=True)
    assert redis_block.read_path("my-key", _sync=True) == b"hello"


def test_usable_as_sync_result_storage(redis_block: RedisDatabase):
    # End-to-end regression for #22393: `RedisDatabase` works as `result_storage`
    # from a synchronous flow, so a repeated call is served from cache.
    redis_block.save("test-sync-result-storage", overwrite=True)
    executions = {"n": 0}

    @task(
        persist_result=True,
        result_storage="redis-database/test-sync-result-storage",
        cache_policy=INPUTS,
    )
    def add(a: int, b: int) -> int:
        executions["n"] += 1
        return a + b

    @flow
    def demo() -> int:
        return add(2, 3) + add(2, 3)

    assert demo() == 10
    assert executions["n"] == 1  # second call is a cache hit
