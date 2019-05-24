from prefect.tasks.redis import RedisSet, RedisGet, RedisExecute

import pytest


class TestRedisSet:
    def test_construction(self):
        task = RedisSet()
        assert task.host == "localhost"

    def test_raises_key_val_not_provided(self):
        task = RedisSet()

        ## raises if neither provided
        with pytest.raises(ValueError) as exc:
            task.run()
        assert "redis_key and redis_val must be provided" == str(exc.value)

        ## raises if only one arg is missing
        with pytest.raises(ValueError) as exc:
            task.run(redis_key="foo")
        assert "redis_key and redis_val must be provided" == str(exc.value)
        with pytest.raises(ValueError) as exc:
            task.run(redis_val="bar")
        assert "redis_key and redis_val must be provided" == str(exc.value)


class TestRedisGet:
    def test_construction(self):
        task = RedisGet()
        assert task.host == "localhost"

    def test_raises_key_val_not_provided(self):
        task = RedisGet()
        with pytest.raises(ValueError) as exc:
            task.run()
        assert "redis_key must be provided" == str(exc.value)


class TestRedisExecute:
    def test_construction(self):
        task = RedisExecute()
        assert task.host == "localhost"

    def test_raises_if_command_not_provided(self):
        task = RedisExecute()
        with pytest.raises(ValueError) as exc:
            task.run()
        assert "A redis command must be specified" == str(exc.value)
