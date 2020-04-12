import datetime
from typing import Any

import marshmallow
import pytest

from prefect.serialization.task import EnvVarSecretSchema, PrefectSecretSchema
from prefect.tasks.secrets import EnvVarSecret, PrefectSecret


@pytest.mark.parametrize("schema", [EnvVarSecretSchema(), PrefectSecretSchema()])
def test_serialize_empty_dict(schema):
    assert schema.dump({})


class TestPrefectSecretSchema:
    def test_serialize_task(self):
        schema = PrefectSecretSchema()
        t = PrefectSecret(name="foo")
        serialized = schema.dump(t)
        assert serialized["name"] == "foo"

    def test_deserialize_task(self):
        schema = PrefectSecretSchema()
        t = PrefectSecret(name="bar")
        serialized = schema.dump(t)
        assert serialized["name"] == "bar"

        s = schema.load(serialized)
        assert isinstance(s, PrefectSecret)
        assert s.name == "bar"


class TestEnvVarSecretSchema:
    def test_serialize_task(self):
        schema = EnvVarSecretSchema()
        t = EnvVarSecret(name="foo")
        serialized = schema.dump(t)
        assert serialized["name"] == "foo"
        assert serialized["raise_if_missing"] is False

    def test_deserialize_task(self):
        schema = EnvVarSecretSchema()
        t = EnvVarSecret(name="bar", raise_if_missing=True)
        serialized = schema.dump(t)
        assert serialized["name"] == "bar"
        assert serialized["raise_if_missing"] is True

        s = schema.load(serialized)
        assert isinstance(s, EnvVarSecret)
        assert s.name == "bar"
        assert s.raise_if_missing is True

    def test_cast_is_ignored(self):
        schema = EnvVarSecretSchema()
        t = EnvVarSecret(name="bar", cast=int)
        serialized = schema.dump(t)
        assert serialized["name"] == "bar"
        assert serialized["raise_if_missing"] is False
        assert "cast" not in serialized

        s = schema.load(serialized)
        assert isinstance(s, EnvVarSecret)
        assert s.name == "bar"
        assert s.raise_if_missing is False
        assert s.cast is None
