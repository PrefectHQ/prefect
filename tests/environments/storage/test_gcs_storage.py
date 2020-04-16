import io
from unittest.mock import MagicMock, patch, call
import warnings

import cloudpickle
import pytest

from prefect import Flow
from prefect.environments.storage import GCS
from prefect.utilities.exceptions import StorageError


class TestGCSStorage:
    @pytest.fixture
    def google_client(self, monkeypatch):
        with patch.dict(
            "sys.modules",
            {
                "google.cloud": MagicMock(),
                "google.oauth2.service_account": MagicMock(),
            },
        ):
            from prefect.utilities.gcp import get_storage_client

            client_util = MagicMock()
            monkeypatch.setattr("prefect.utilities.gcp.get_storage_client", client_util)
            yield client_util

    def test_create_gcs_storage(self):
        storage = GCS(
            bucket="awesome-bucket",
            key="the-best-key",
            project="mayhem",
            secrets=["boo"],
        )

        assert storage
        assert len(storage._flows) == 0
        assert storage.bucket == "awesome-bucket"
        assert storage.key == "the-best-key"
        assert storage.project == "mayhem"
        assert storage.secrets == ["boo"]

    def test_create_gcs_client_go_case(self, google_client):
        storage = GCS(bucket="bucket", project="a_project")

        client = storage._gcs_client
        assert client

        google_client.assert_called_with(project="a_project")

    def test_create_gcs_client_no_project(self, google_client):
        storage = GCS(bucket="bucket", project=None)

        client = storage._gcs_client
        assert client

        google_client.assert_called_with(project=None)

    def test_add_flow_to_gcs(self):
        storage = GCS(bucket="awesome-bucket")

        f = Flow("awesome-flow")
        assert f.name not in storage
        key = storage.add_flow(f)

        # ensures that our auto-generation of key name
        # is Windows compatible
        assert key.startswith("awesome-flow/")
        assert f.name in storage

    def test_add_multiple_flows_to_gcs(self):
        storage = GCS(bucket="awesome-bucket")

        flows = (Flow("awesome-flow-1"), Flow("awesome-flow-2"))

        for f in flows:
            assert f.name not in storage
            assert storage.add_flow(f)
            assert f.name in storage

        assert len(storage.flows) == 2
        assert len(storage._flows) == 2

    def test_add_duplicate_flow_to_gcs(self):
        storage = GCS(bucket="awesome-bucket")

        f = Flow("awesome-flow")
        assert storage.add_flow(f)
        with pytest.raises(ValueError):
            storage.add_flow(f)

    def test_get_flow_from_gcs(self, google_client):
        f = Flow("awesome-flow")
        flow_content = cloudpickle.dumps(f)

        blob_mock = MagicMock(download_as_string=MagicMock(return_value=flow_content))
        bucket_mock = MagicMock(get_blob=MagicMock(return_value=blob_mock))
        google_client.return_value.get_bucket = MagicMock(return_value=bucket_mock)

        storage = GCS(bucket="awesome-bucket", key="a-place")
        storage.add_flow(f)

        fetched_flow = storage.get_flow("a-place")

        assert fetched_flow.name == f.name
        bucket_mock.get_blob.assert_called_with("a-place")
        assert blob_mock.download_as_string.call_count == 1

    def test_upload_single_flow_to_gcs(self, google_client):
        blob_mock = MagicMock()
        bucket_mock = MagicMock(blob=MagicMock(return_value=blob_mock))
        google_client.return_value.get_bucket = MagicMock(return_value=bucket_mock)

        storage = GCS(bucket="awesome-bucket")

        f = Flow("awesome-flow")
        assert f.name not in storage
        assert storage.add_flow(f)
        assert f.name in storage
        assert storage.build()

        bucket_mock.blob.assert_called_with(blob_name=storage.flows[f.name])
        blob_mock.upload_from_string.assert_called_with(cloudpickle.dumps(f))

    def test_upload_single_flow_with_custom_key_to_gcs(self, google_client):
        blob_mock = MagicMock()
        bucket_mock = MagicMock(blob=MagicMock(return_value=blob_mock))
        google_client.return_value.get_bucket = MagicMock(return_value=bucket_mock)

        storage = GCS(bucket="awesome-bucket", key="the-best-key")

        f = Flow("awesome-flow")
        assert f.name not in storage
        assert storage.add_flow(f)
        assert f.name in storage
        assert storage.build()

        bucket_mock.blob.assert_called_with(blob_name="the-best-key")
        blob_mock.upload_from_string.assert_called_with(cloudpickle.dumps(f))

    def test_upload_multiple_flows_to_gcs(self, google_client):
        blob_mock = MagicMock()
        bucket_mock = MagicMock(blob=MagicMock(return_value=blob_mock))
        google_client.return_value.get_bucket = MagicMock(return_value=bucket_mock)

        storage = GCS(bucket="awesome-bucket")

        flows = (Flow("awesome-flow-1"), Flow("awesome-flow-2"))
        for f in flows:
            storage.add_flow(f)

        assert storage.build()
        assert bucket_mock.blob.call_count == 2
        assert blob_mock.upload_from_string.call_count == 2

        expected_blob_calls = []
        expected_upload_calls = []
        for f in flows:
            expected_blob_calls.append(call(blob_name=storage.flows[f.name]))
            expected_upload_calls.append(call(cloudpickle.dumps(f)))

        # note, we don't upload until build() is called, which iterates on a dictionary, which is not ordered older versions of python
        bucket_mock.blob.assert_has_calls(expected_blob_calls, any_order=True)
        blob_mock.upload_from_string.assert_has_calls(
            expected_upload_calls, any_order=True
        )

    def test_put_get_and_run_single_flow_to_gcs(self, google_client):
        blob_mock = MagicMock()
        bucket_mock = MagicMock(blob=MagicMock(return_value=blob_mock))
        google_client.return_value.get_bucket = MagicMock(return_value=bucket_mock)

        storage = GCS(bucket="awesome-bucket")

        f = Flow("awesome-flow")
        assert f.name not in storage
        assert storage.add_flow(f)
        assert f.name in storage
        assert storage.build()

        flow_as_bytes = blob_mock.upload_from_string.call_args[0][0]
        new_flow = cloudpickle.loads(flow_as_bytes)
        assert new_flow.name == "awesome-flow"

        state = new_flow.run()
        assert state.is_successful()
