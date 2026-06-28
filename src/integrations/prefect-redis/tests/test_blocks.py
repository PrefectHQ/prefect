from prefect_redis.blocks import RedisDatabase
from pydantic import SecretStr


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
