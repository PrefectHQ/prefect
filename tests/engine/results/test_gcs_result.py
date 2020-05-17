import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import cloudpickle
import pendulum
import pytest

import prefect
from prefect.client import Client
from prefect.utilities.configuration import set_temporary_config
from prefect.engine.results import GCSResult


pytest.importorskip("google.cloud")


class TestGCSResult:
    @pytest.fixture
    def google_client(self, monkeypatch):
        from prefect.utilities.gcp import get_storage_client

        client_util = MagicMock()
        monkeypatch.setattr("prefect.utilities.gcp.get_storage_client", client_util)
        yield client_util

    def test_gcs_init(self, google_client):
        result = GCSResult(bucket="bob")
        assert result.value is None
        assert result.bucket == "bob"
        assert google_client.called is False
        result.gcs_bucket()
        assert google_client.return_value.bucket.call_args[0][0] == "bob"

    def test_gcs_init_with_value(self):
        result = GCSResult(value=3, bucket="bob")
        assert result.value == 3

    def test_gcs_writes_to_blob_using_rendered_template_name(self, google_client):
        bucket = MagicMock()
        google_client.return_value.bucket = MagicMock(return_value=bucket)
        result = GCSResult(bucket="foo", location="{thing}/here.txt")
        new_result = result.write("so-much-data", thing=42)

        assert new_result.location == "42/here.txt"
        assert bucket.blob.called
        assert bucket.blob.call_args[0][0] == "42/here.txt"

    def test_gcs_reads_and_updates_location(self, google_client):
        bucket = MagicMock()
        bucket.blob.return_value.download_as_string.return_value = ""
        google_client.return_value.bucket = MagicMock(return_value=bucket)
        result = GCSResult(bucket="foo", location="{thing}/here.txt")
        new_result = result.read("path/to/my/stuff.txt")

        assert new_result.location == "path/to/my/stuff.txt"
        assert new_result.value is None

    def test_gcs_writes_binary_string(self, google_client):
        blob = MagicMock()
        google_client.return_value.bucket = MagicMock(
            return_value=MagicMock(blob=MagicMock(return_value=blob))
        )
        result = GCSResult(bucket="foo", location="nothing/here.txt")
        new_result = result.write(None)
        assert blob.upload_from_string.called
        assert isinstance(blob.upload_from_string.call_args[0][0], str)

    def test_gcs_result_is_pickleable(self, google_client, monkeypatch):
        class gcs_bucket:
            def __init__(self, *args, **kwargs):
                pass

            def __getstate__(self):
                raise ValueError("I cannot be pickled.")

        result = GCSResult("foo")
        res = cloudpickle.loads(cloudpickle.dumps(result))
        assert isinstance(res, GCSResult)
