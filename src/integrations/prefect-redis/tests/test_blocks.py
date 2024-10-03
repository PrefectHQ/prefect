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
