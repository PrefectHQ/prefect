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


@pytest.mark.xfail(raises=ImportError, reason="google extras not installed.")
class TestGCSResult:
    @pytest.fixture
    def google_client(self, monkeypatch):
        from prefect.utilities.gcp import get_storage_client

        client_util = MagicMock()
        monkeypatch.setattr("prefect.utilities.gcp.get_storage_client", client_util)
        yield client_util

    def test_gcs_init(self, google_client):
        result = GCSResult(bucket="bob")
        assert result.value == None
        assert result.bucket == "bob"
        assert result.credentials_secret == None
        assert google_client.called is False
        result.gcs_bucket()
        assert google_client.return_value.bucket.call_args[0][0] == "bob"

    def test_gcs_init_with_value(self):
        result = GCSResult(3, bucket="bob")
        assert result.value == 3

    def test_gcs_writes_to_blob_using_rendered_template_name(self, google_client):
        bucket = MagicMock()
        google_client.return_value.bucket = MagicMock(return_value=bucket)
        result = GCSResult(bucket="foo", filepath_template="{thing}/here.txt")
        result.value = "so-much-data"
        new_result = result.format(thing=42)
        new_result.write()
        assert bucket.blob.called
        assert bucket.blob.call_args[0][0] == "42/here.txt"

    def test_gcs_uses_custom_secret_name(self, google_client):
        result = GCSResult(bucket="foo", credentials_secret="TEST_SECRET")

        with prefect.context(secrets=dict(TEST_SECRET=94611)):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                result.gcs_bucket()

        assert google_client.call_args[1]["credentials"] == 94611

    def test_gcs_writes_binary_string(self, google_client):
        blob = MagicMock()
        google_client.return_value.bucket = MagicMock(
            return_value=MagicMock(blob=MagicMock(return_value=blob))
        )
        result = GCSResult(bucket="foo", filepath_template="nothing/here.txt")
        result.value = None
        new_result = result.format()
        new_result.write()
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

    def test_gcs_write_fails_if_format_not_called_first(self, google_client):
        result = GCSResult(bucket="foo", filepath_template="nothing/here.txt")
        with pytest.raises(ValueError):
            result.write()

    def test_gcs_read_fails_if_format_not_called_first(self, google_client):
        result = GCSResult(bucket="foo", filepath_template="nothing/here.txt")
        with pytest.raises(ValueError):
            result.read()

    def test_gcs_exists_fails_if_format_not_called_first(self, google_client):
        result = GCSResult(bucket="foo", filepath_template="nothing/here.txt")
        with pytest.raises(ValueError):
            result.exists()
