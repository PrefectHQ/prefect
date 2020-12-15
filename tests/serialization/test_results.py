import pytest

import prefect
from prefect.engine import results
from prefect.engine.result import Result
from prefect.serialization.result import StateResultSchema


def test_constant_result():
    """
    Because ConstantResult objects have no implemented write method,
    and therefore will never have an interesting "safe" representation,
    we don't actually expect these to ever be serialized between Core
    and any backend
    """
    schema = StateResultSchema()
    result = results.ConstantResult(value=42)
    serialized = schema.dump(result)

    assert serialized["type"] == "ConstantResult"
    assert serialized["location"] is None

    new_result = schema.load(serialized)
    assert isinstance(new_result, results.ConstantResult)
    assert new_result.location is None
    assert new_result.value is None


def test_azure_result():
    schema = StateResultSchema()
    result = results.AzureResult(value=42, container="foo", location="bar")
    serialized = schema.dump(result)

    assert serialized["type"] == "AzureResult"
    assert serialized["location"] == "bar"

    new_result = schema.load(serialized)
    assert isinstance(new_result, results.AzureResult)
    assert new_result.container == "foo"
    assert new_result.location == "bar"
    assert new_result.value is None


def test_gcs_result():
    schema = StateResultSchema()
    result = results.GCSResult(value=42, bucket="foo", location="bar")
    serialized = schema.dump(result)

    assert serialized["type"] == "GCSResult"
    assert serialized["location"] == "bar"

    new_result = schema.load(serialized)
    assert isinstance(new_result, results.GCSResult)
    assert new_result.bucket == "foo"
    assert new_result.location == "bar"
    assert new_result.value is None


def test_local_result():
    schema = StateResultSchema()
    result = results.LocalResult(value=42, location="bar")
    serialized = schema.dump(result)

    assert serialized["type"] == "LocalResult"
    assert serialized["dir"] is not None
    assert serialized["location"] == "bar"

    new_result = schema.load(serialized)
    assert isinstance(new_result, results.LocalResult)
    assert new_result.dir == result.dir
    assert new_result.location == "bar"
    assert new_result.value is None


def test_local_result_doesnt_validate_on_deserialization():
    schema = StateResultSchema()
    result = results.LocalResult(validate_dir=True)
    serialized = schema.dump(result)

    assert serialized["type"] == "LocalResult"
    serialized["dir"] = r"C:\Windows\paths\are\weird"

    new_result = schema.load(serialized)
    assert isinstance(new_result, results.LocalResult)
    assert new_result.dir == r"C:\Windows\paths\are\weird"


def test_prefect_result():
    schema = StateResultSchema()
    result = results.PrefectResult(value=42, location="42")
    serialized = schema.dump(result)

    assert serialized["type"] == "PrefectResult"
    assert "value" not in serialized
    assert serialized["location"] == "42"

    new_result = schema.load(serialized)
    assert isinstance(new_result, results.PrefectResult)
    assert new_result.location == "42"
    assert new_result.value is None


def test_s3_result():
    schema = StateResultSchema()
    result = results.S3Result(value=42, bucket="foo", location="bar")
    serialized = schema.dump(result)

    assert serialized["type"] == "S3Result"
    assert serialized["location"] == "bar"

    new_result = schema.load(serialized)
    assert isinstance(new_result, results.S3Result)
    assert new_result.bucket == "foo"
    assert new_result.location == "bar"
    assert new_result.value is None


def test_secret_result():
    schema = StateResultSchema()
    result = results.SecretResult(
        secret_task=prefect.tasks.secrets.EnvVarSecret(name="OS")
    )
    serialized = schema.dump(result)

    assert serialized["type"] == "SecretResult"
    assert serialized["location"] == "OS"
    assert serialized["secret_type"] == "EnvVarSecret"

    new_result = schema.load(serialized)
    assert isinstance(new_result, results.SecretResult)
    assert new_result.location == "OS"
    assert new_result.value is None


def test_custom_result():
    class MySuperAwesomeAmazingTopOfTheLineCustomResult(Result):
        def __init__(self, test_kwarg=None, **kwargs):
            self.test_kwarg = test_kwarg
            self.read_result = False
            self.write_result = False
            self.exists_result = False
            super().__init__(**kwargs)

        def read(self, location) -> Result:
            new = self.copy()
            new.read_result = True
            return new

        def write(self, value, **kwargs) -> Result:
            new = self.copy()
            new.write_result = True
            return new

        def exists(self, location, **kwargs) -> Result:
            new = self.copy()
            new.exists_result = True
            return new

    schema = StateResultSchema()
    result = MySuperAwesomeAmazingTopOfTheLineCustomResult(
        test_kwarg="yes", value=42, location="bar"
    )
    serialized = schema.dump(result)

    assert serialized["type"] == "CustomResult"
    assert serialized["location"] == "bar"
    assert serialized["__version__"]

    new_result = schema.load(serialized)
    assert isinstance(new_result, Result)
    assert new_result.location == "bar"
    assert new_result.value is None
