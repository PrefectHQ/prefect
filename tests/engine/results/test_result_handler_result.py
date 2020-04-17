import os
import json
import tempfile
import uuid
from typing import Union

import cloudpickle
import pytest

import prefect
from prefect import config
from prefect.engine.results import (
    ConstantResult,
    GCSResult,
    LocalResult,
    PrefectResult,
    S3Result,
    SecretResult,
    ResultHandlerResult,
)
from prefect.engine.result_handlers import (
    ConstantResultHandler,
    GCSResultHandler,
    LocalResultHandler,
    JSONResultHandler,
    ResultHandler,
    S3ResultHandler,
    SecretResultHandler,
)
from prefect.tasks.core.constants import Constant
from prefect.tasks.secrets import PrefectSecret


def test_basic_conversion_secret_result():
    task = PrefectSecret("foo")
    result_handler = SecretResultHandler(task)
    result = ResultHandlerResult.from_result_handler(result_handler)
    assert isinstance(result, SecretResult)
    assert result.secret_task is task


def test_basic_conversion_json_result():
    result_handler = JSONResultHandler()
    result = ResultHandlerResult.from_result_handler(result_handler)
    assert isinstance(result, PrefectResult)
    assert result.write(42).location == "42"


def test_basic_conversion_constant_result():
    result_handler = ConstantResultHandler(value=42)
    result = ResultHandlerResult.from_result_handler(result_handler)
    assert isinstance(result, ConstantResult)
    assert result.value == 42


def test_basic_conversion_local_result(tmpdir):
    result_handler = LocalResultHandler(dir=str(tmpdir))
    result = ResultHandlerResult.from_result_handler(result_handler)
    assert isinstance(result, LocalResult)
    assert result.dir == str(tmpdir)


def test_basic_conversion_gcs_result():
    result_handler = GCSResultHandler(bucket="foo")
    result = ResultHandlerResult.from_result_handler(result_handler)
    assert isinstance(result, GCSResult)
    assert result.bucket == "foo"


def test_basic_conversion_s3_result():
    result_handler = S3ResultHandler(bucket="foo", boto3_kwargs=dict(x=42, y=[1, 2, 3]))
    result = ResultHandlerResult.from_result_handler(result_handler)
    assert isinstance(result, S3Result)
    assert result.bucket == "foo"
    assert result.boto3_kwargs == dict(x=42, y=[1, 2, 3])


class TestCustomResultHandler:
    @pytest.fixture
    def handler(self):
        class MyHandler(ResultHandler):
            stuff = dict()

            def read(self, loc):
                return self.stuff[loc]

            def write(self, result):
                key = str(uuid.uuid4())
                self.stuff[key] = result
                return key

        return MyHandler()

    def test_conversion_type(self, handler):
        result = ResultHandlerResult.from_result_handler(handler)
        assert isinstance(result, ResultHandlerResult)
        assert isinstance(result.result_handler, type(handler))

    def test_converted_result_writes_and_reads(self, handler):
        result = ResultHandlerResult.from_result_handler(handler)
        new = result.write(42)

        assert new is not result
        assert new.value == 42
        assert new.location
        assert new.result_handler.stuff[new.location] == 42

        another = new.read(new.location)
        assert another is not new
        assert another.value == 42
        assert another.location == new.location
