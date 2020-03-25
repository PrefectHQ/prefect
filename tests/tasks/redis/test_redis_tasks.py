from unittest.mock import MagicMock

import pytest

import prefect
from prefect.tasks.redis import RedisExecute, RedisGet, RedisSet
from prefect.utilities.configuration import set_temporary_config


class TestRedisSet:
    def test_construction(self):
        task = RedisSet()
        assert task.host == "localhost"

    def test_raises_key_val_not_provided(self):
        task = RedisSet()

        ## raises if neither provided
        with pytest.raises(
            ValueError, match="redis_key and redis_val must be provided"
        ):
            task.run()

        ## raises if only one arg is missing
        with pytest.raises(
            ValueError, match="redis_key and redis_val must be provided"
        ):
            task.run(redis_key="foo")
        with pytest.raises(
            ValueError, match="redis_key and redis_val must be provided"
        ):
            task.run(redis_val="bar")

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = RedisSet()
        redis = MagicMock()
        monkeypatch.setattr("prefect.tasks.redis.redis_tasks.redis.Redis", redis)
        with set_temporary_config({"use_local_secrets": True}):
            with prefect.context(secrets=dict(REDIS_PASSWORD="42")):
                task.run(redis_key="foo", redis_val="bar")
        assert redis.call_args[1]["password"] == 42

    def test_redis_params_passed_to_connection(self, monkeypatch):
        redis_params = {"custom_parameter": "value"}
        task = RedisSet(redis_connection_params=redis_params)
        redis = MagicMock()
        monkeypatch.setattr("prefect.tasks.redis.redis_tasks.redis.Redis", redis)
        with set_temporary_config({"use_local_secrets": True}):
            with prefect.context(secrets=dict(REDIS_PASSWORD="42")):
                task.run(redis_key="foo", redis_val="bar")
        assert redis.call_args[1]["custom_parameter"] == "value"


class TestRedisGet:
    def test_construction(self):
        task = RedisGet()
        assert task.host == "localhost"

    def test_raises_key_val_not_provided(self):
        task = RedisGet()
        with pytest.raises(ValueError, match="redis_key must be provided"):
            task.run()

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = RedisGet()
        redis = MagicMock()
        monkeypatch.setattr("prefect.tasks.redis.redis_tasks.redis.Redis", redis)
        with set_temporary_config({"use_local_secrets": True}):
            with prefect.context(secrets=dict(REDIS_PASSWORD="42")):
                task.run(redis_key="foo")
        assert redis.call_args[1]["password"] == 42

    def test_redis_params_passed_to_connection(self, monkeypatch):
        redis_params = {"custom_parameter": "value"}
        task = RedisGet(redis_connection_params=redis_params)
        redis = MagicMock()
        monkeypatch.setattr("prefect.tasks.redis.redis_tasks.redis.Redis", redis)
        with set_temporary_config({"use_local_secrets": True}):
            with prefect.context(secrets=dict(REDIS_PASSWORD="42")):
                task.run(redis_key="foo")
        assert redis.call_args[1]["custom_parameter"] == "value"


class TestRedisExecute:
    def test_construction(self):
        task = RedisExecute()
        assert task.host == "localhost"

    def test_raises_if_command_not_provided(self):
        task = RedisExecute()
        with pytest.raises(ValueError, match="A redis command must be specified"):
            task.run()

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = RedisExecute()
        redis = MagicMock()
        monkeypatch.setattr("prefect.tasks.redis.redis_tasks.redis.Redis", redis)
        with set_temporary_config({"use_local_secrets": True}):
            with prefect.context(secrets=dict(REDIS_PASSWORD="42")):
                task.run(redis_cmd="GET foo")
        assert redis.call_args[1]["password"] == 42

    def test_redis_params_passed_to_connection(self, monkeypatch):
        redis_params = {"custom_parameter": "value"}
        task = RedisExecute(redis_connection_params=redis_params)
        redis = MagicMock()
        monkeypatch.setattr("prefect.tasks.redis.redis_tasks.redis.Redis", redis)
        with set_temporary_config({"use_local_secrets": True}):
            with prefect.context(secrets=dict(REDIS_PASSWORD="42")):
                task.run(redis_cmd="GET foo")
        assert redis.call_args[1]["custom_parameter"] == "value"
