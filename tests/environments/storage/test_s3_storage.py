import io
from unittest.mock import MagicMock

import cloudpickle
import pytest

from prefect import context, Flow
from prefect.environments.storage import S3

pytest.importorskip("boto3")
pytest.importorskip("botocore")

from botocore.exceptions import ClientError


def test_create_s3_storage():
    storage = S3(bucket="test")
    assert storage
    assert storage.logger


def test_create_s3_storage_init_args():
    storage = S3(
        bucket="bucket",
        key="key",
        client_options={"endpoint_url": "http://some-endpoint", "use_ssl": False,},
        secrets=["auth"],
    )
    assert storage
    assert storage.flows == dict()
    assert storage.bucket == "bucket"
    assert storage.key == "key"
    assert storage.client_options == {
        "endpoint_url": "http://some-endpoint",
        "use_ssl": False,
    }
    assert storage.secrets == ["auth"]


def test_serialize_s3_storage():
    storage = S3(
        bucket="bucket",
        client_options={"endpoint_url": "http://some-endpoint", "use_ssl": False},
    )
    serialized_storage = storage.serialize()

    assert serialized_storage["type"] == "S3"
    assert serialized_storage["bucket"] == "bucket"
    assert serialized_storage["client_options"] == {
        "endpoint_url": "http://some-endpoint",
        "use_ssl": False,
    }


def test_boto3_client_property(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(client=MagicMock(return_value=client))
    monkeypatch.setattr("boto3.client", boto3)

    storage = S3(
        bucket="bucket",
        client_options={"endpoint_url": "http://some-endpoint", "use_ssl": False,},
    )

    credentials = dict(
        ACCESS_KEY="id", SECRET_ACCESS_KEY="secret", SESSION_TOKEN="session"
    )
    with context(secrets=dict(AWS_CREDENTIALS=credentials)):
        boto3_client = storage._boto3_client
    assert boto3_client
    boto3.assert_called_with(
        "s3",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="session",
        endpoint_url="http://some-endpoint",
        use_ssl=False,
    )


def test_add_flow_to_S3(bucket="bucket"):
    storage = S3(bucket="bucket")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f)
    assert f.name in storage


def test_add_multiple_flows_to_S3(bucket="bucket"):
    storage = S3(bucket="bucket")

    f = Flow("test")
    g = Flow("testg")
    assert f.name not in storage
    assert storage.add_flow(f)
    assert storage.add_flow(g)
    assert f.name in storage
    assert g.name in storage


def test_upload_flow_to_s3(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(upload_fileobj=MagicMock(return_value=client))
    monkeypatch.setattr("prefect.environments.storage.S3._boto3_client", boto3)

    storage = S3(bucket="bucket")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f)
    assert storage.build()
    assert boto3.upload_fileobj.called
    assert f.name in storage


def test_upload_flow_to_s3_client_error(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(upload_fileobj=MagicMock(return_value=client))
    boto3.upload_fileobj.side_effect = ClientError({}, None)
    monkeypatch.setattr("prefect.environments.storage.S3._boto3_client", boto3)

    storage = S3(bucket="bucket")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f)

    with pytest.raises(ClientError):
        storage.build()
    assert boto3.upload_fileobj.called


def test_upload_flow_to_s3_bucket_key(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(upload_fileobj=MagicMock(return_value=client))
    monkeypatch.setattr("prefect.environments.storage.S3._boto3_client", boto3)

    storage = S3(bucket="bucket", key="key")

    f = Flow("test")
    assert storage.add_flow(f)
    assert storage.build()

    assert boto3.upload_fileobj.call_args[1]["Bucket"] == "bucket"
    assert boto3.upload_fileobj.call_args[1]["Key"] == "key"


def test_upload_multiple_flows_to_s3_bucket_key(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(upload_fileobj=MagicMock(return_value=client))
    monkeypatch.setattr("prefect.environments.storage.S3._boto3_client", boto3)

    storage = S3(bucket="bucket")

    f1 = Flow("test1")
    f2 = Flow("test2")
    assert storage.add_flow(f1)
    assert storage.add_flow(f2)
    assert storage.build()

    assert boto3.upload_fileobj.call_args[1]["Bucket"] == "bucket"


def test_upload_flow_to_s3_flow_byte_stream(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(upload_fileobj=MagicMock(return_value=client))
    monkeypatch.setattr("prefect.environments.storage.S3._boto3_client", boto3)

    storage = S3(bucket="bucket")

    f = Flow("test")
    assert storage.add_flow(f)
    assert storage.build()

    flow_as_bytes = boto3.upload_fileobj.call_args[0][0]
    assert isinstance(flow_as_bytes, io.BytesIO)

    new_flow = cloudpickle.loads(flow_as_bytes.read())
    assert new_flow.name == "test"

    state = new_flow.run()
    assert state.is_successful()


def test_upload_flow_to_s3_key_format(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(upload_fileobj=MagicMock(return_value=client))
    monkeypatch.setattr("prefect.environments.storage.S3._boto3_client", boto3)

    storage = S3(bucket="bucket")

    f = Flow("test")
    assert storage.add_flow(f)
    assert storage.build()

    assert boto3.upload_fileobj.call_args[1]["Bucket"] == "bucket"
    key = boto3.upload_fileobj.call_args[1]["Key"].split("/")

    assert key[0] == "test"
    assert key[1]


def test_add_flow_to_s3_already_added(monkeypatch):
    storage = S3(bucket="bucket")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f)
    assert f.name in storage

    with pytest.raises(ValueError):
        storage.add_flow(f)


def test_get_flow_s3(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(download_fileobj=MagicMock(return_value=client))
    monkeypatch.setattr("prefect.environments.storage.S3._boto3_client", boto3)

    f = Flow("test")

    monkeypatch.setattr("cloudpickle.loads", MagicMock(return_value=f))

    storage = S3(bucket="bucket")

    assert f.name not in storage
    flow_location = storage.add_flow(f)

    assert storage.get_flow(flow_location)
    assert boto3.download_fileobj.called
    assert f.name in storage


def test_get_flow_s3_client_error(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(download_fileobj=MagicMock(return_value=client))
    boto3.download_fileobj.side_effect = ClientError({}, None)
    monkeypatch.setattr("prefect.environments.storage.S3._boto3_client", boto3)

    f = Flow("test")

    storage = S3(bucket="bucket")

    assert f.name not in storage
    flow_location = storage.add_flow(f)

    with pytest.raises(ClientError):
        storage.get_flow(flow_location)

    assert boto3.download_fileobj.called


def test_get_flow_s3_bucket_key(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(download_fileobj=MagicMock(return_value=client))
    monkeypatch.setattr("prefect.environments.storage.S3._boto3_client", boto3)

    f = Flow("test")

    monkeypatch.setattr("cloudpickle.loads", MagicMock(return_value=f))

    storage = S3(bucket="bucket", key="key")

    assert f.name not in storage
    flow_location = storage.add_flow(f)

    assert storage.get_flow(flow_location)
    assert boto3.download_fileobj.call_args[1]["Bucket"] == "bucket"
    assert boto3.download_fileobj.call_args[1]["Key"] == "key"


def test_get_flow_s3_not_in_storage(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(download_fileobj=MagicMock(return_value=client))
    monkeypatch.setattr("prefect.environments.storage.S3._boto3_client", boto3)

    f = Flow("test")

    monkeypatch.setattr("cloudpickle.loads", MagicMock(return_value=f))

    storage = S3(bucket="bucket", key="test")

    assert f.name not in storage

    with pytest.raises(ValueError):
        storage.get_flow("test/test")


def test_get_flow_s3_runs(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(download_fileobj=MagicMock(return_value=client))
    monkeypatch.setattr("prefect.environments.storage.S3._boto3_client", boto3)

    f = Flow("test")

    monkeypatch.setattr("cloudpickle.loads", MagicMock(return_value=f))

    storage = S3(bucket="bucket")

    assert f.name not in storage
    flow_location = storage.add_flow(f)

    new_flow = storage.get_flow(flow_location)
    assert boto3.download_fileobj.called
    assert f.name in storage

    assert isinstance(new_flow, Flow)
    assert new_flow.name == "test"
    assert len(new_flow.tasks) == 0

    state = new_flow.run()
    assert state.is_successful()
