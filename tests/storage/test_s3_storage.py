import io
import datetime
import textwrap
from unittest.mock import MagicMock

import pytest

pytest.importorskip("boto3")
pytest.importorskip("botocore")

from prefect import context, Flow
from prefect.storage import S3
from prefect.utilities.storage import flow_from_bytes_pickle, flow_to_bytes_pickle
from prefect.utilities.aws import _CLIENT_CACHE

from botocore.exceptions import ClientError


@pytest.fixture(autouse=True)
def clear_boto3_cache():
    _CLIENT_CACHE.clear()


@pytest.fixture
def s3_client(monkeypatch):
    client = MagicMock()
    get_boto_client = MagicMock(return_value=client)
    monkeypatch.setattr("prefect.utilities.aws.get_boto_client", get_boto_client)
    return client


def test_create_s3_storage():
    storage = S3(bucket="test")
    assert storage
    assert storage.logger


def test_create_s3_storage_init_args():
    storage = S3(
        bucket="bucket",
        key="key",
        client_options={"endpoint_url": "http://some-endpoint", "use_ssl": False},
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
        client_options={"endpoint_url": "http://some-endpoint", "use_ssl": False},
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
        region_name=None,
        endpoint_url="http://some-endpoint",
        use_ssl=False,
    )


def test_s3_storage_init_properly_result_with_boto3_args(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(client=MagicMock(return_value=client))
    monkeypatch.setattr("boto3.client", boto3)

    storage = S3(
        bucket="bucket",
        client_options={"endpoint_url": "http://some-endpoint", "use_ssl": False},
    )

    credentials = dict(
        ACCESS_KEY="id", SECRET_ACCESS_KEY="secret", SESSION_TOKEN="session"
    )
    with context(secrets=dict(AWS_CREDENTIALS=credentials)):
        result_path = storage.result.write("test")
    assert result_path
    boto3.assert_called_with(
        "s3",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="session",
        region_name=None,
        endpoint_url="http://some-endpoint",
        use_ssl=False,
    )


def test_add_flow_to_S3():
    storage = S3(bucket="bucket")

    f = Flow("test")
    assert f.name not in storage
    key = storage.add_flow(f)
    assert storage.flows[f.name] == key
    assert f.name in storage


def test_add_multiple_flows_to_S3():
    storage = S3(bucket="bucket")

    flows = [Flow("f"), Flow("g")]
    keys = [storage.add_flow(f) for f in flows]
    for flow, key in zip(flows, keys):
        assert storage.flows[flow.name] == key
        assert flow.name in storage


@pytest.mark.parametrize("key", ["mykey", None])
def test_upload_flow_to_s3(s3_client, key):
    storage = S3(bucket="bucket", key=key)

    f = Flow("test")

    key_used = storage.add_flow(f)
    if key is not None:
        assert key_used == key

    assert storage.build() is storage

    assert s3_client.upload_fileobj.called

    assert s3_client.upload_fileobj.call_args[1]["Bucket"] == "bucket"
    assert s3_client.upload_fileobj.call_args[1]["Key"] == key_used

    flow_as_bytes = s3_client.upload_fileobj.call_args[0][0]
    assert isinstance(flow_as_bytes, io.BytesIO)

    new_flow = flow_from_bytes_pickle(flow_as_bytes.read())
    assert new_flow.name == "test"

    state = new_flow.run()
    assert state.is_successful()


def test_build_no_upload_if_file_and_no_script(s3_client):
    storage = S3(bucket="bucket", stored_as_script=True)

    with pytest.raises(ValueError):
        storage.build()

    storage = S3(bucket="bucket", stored_as_script=True, key="flow.py")
    storage.build()
    assert not s3_client.upload_fileobj.called


def test_build_script_upload(s3_client):
    storage = S3(
        bucket="bucket", stored_as_script=True, local_script_path="local.py", key="key"
    )

    f = Flow("test")
    storage.add_flow(f)
    assert f.name in storage

    storage.build()
    assert s3_client.upload_file.called
    assert s3_client.upload_file.call_args[0] == ("local.py", "bucket", "key")

    s3_client.upload_file.side_effect = ClientError({}, None)

    with pytest.raises(ClientError):
        storage.build()


def test_upload_flow_to_s3_client_error(s3_client):
    s3_client.upload_fileobj.side_effect = ClientError({}, None)

    storage = S3(bucket="bucket")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f)

    with pytest.raises(ClientError):
        storage.build()
    assert s3_client.upload_fileobj.called


def test_upload_multiple_flows_to_s3_bucket(s3_client):
    storage = S3(bucket="bucket")

    f1 = Flow("test1")
    f2 = Flow("test2")
    assert storage.add_flow(f1)
    assert storage.add_flow(f2)
    assert storage.build()

    assert s3_client.upload_fileobj.call_count == 2
    assert s3_client.upload_fileobj.call_args[1]["Bucket"] == "bucket"


def test_add_flow_to_s3_already_added():
    storage = S3(bucket="bucket")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f)
    assert f.name in storage

    with pytest.raises(ValueError):
        storage.add_flow(f)


@pytest.mark.parametrize("key", ["mykey", None])
def test_get_flow_s3_pickle(s3_client, key):
    f = Flow("test")
    storage = S3(bucket="bucket", key=key)
    key_used = storage.add_flow(f)

    data = flow_to_bytes_pickle(f)

    s3_client.get_object.return_value = {
        "ETag": "my-etag",
        "LastModified": datetime.datetime.now(),
        "Body": io.BytesIO(data),
    }

    f2 = storage.get_flow(f.name)

    assert s3_client.get_object.called
    assert s3_client.get_object.call_args[1]["Bucket"] == "bucket"
    assert s3_client.get_object.call_args[1]["Key"] == key_used

    assert f2.name == f.name
    state = f2.run()
    assert state.is_successful()


@pytest.mark.parametrize("key", ["mykey", None])
def test_get_flow_s3_script(s3_client, key):
    f = Flow("test")
    storage = S3(bucket="bucket", key=key, stored_as_script=True)
    key_used = storage.add_flow(f)

    data = textwrap.dedent(
        """
        from prefect import Flow
        flow = Flow("test")
        """
    ).encode("utf-8")

    s3_client.get_object.return_value = {
        "ETag": "my-etag",
        "LastModified": datetime.datetime.now(),
        "Body": io.BytesIO(data),
    }

    f2 = storage.get_flow(f.name)

    assert s3_client.get_object.called
    assert s3_client.get_object.call_args[1]["Bucket"] == "bucket"
    assert s3_client.get_object.call_args[1]["Key"] == key_used

    assert f2.name == f.name
    state = f2.run()
    assert state.is_successful()


@pytest.mark.parametrize("version_id", ["my-version-id", None])
def test_get_flow_s3_logs(s3_client, caplog, version_id):
    f = Flow("test")
    storage = S3(bucket="mybucket")
    key_used = storage.add_flow(f)

    data = flow_to_bytes_pickle(f)

    etag = "my-etag"
    t = datetime.datetime.now()

    s3_client.get_object.return_value = {
        "ETag": etag,
        "LastModified": t,
        "Body": io.BytesIO(data),
    }
    if version_id:
        s3_client.get_object.return_value["VersionId"] = version_id

    storage.get_flow(f.name)
    logs = [l.getMessage() for l in caplog.records]
    assert f"s3://mybucket/{key_used}" in logs[0]
    assert (
        f"ETag: {etag}, LastModified: {t.isoformat()}, VersionId: {version_id}"
        in logs[1]
    )


def test_get_flow_s3_client_error(s3_client):
    s3_client.get_object.side_effect = ClientError({}, None)

    f = Flow("test")

    storage = S3(bucket="bucket")
    storage.add_flow(f)

    with pytest.raises(ClientError):
        storage.get_flow(f.name)


def test_get_flow_s3_download_error(s3_client):
    class BadReader:
        def __init__(self):
            self.closed = False

        def read(self):
            raise ValueError("Oh no!")

        def close(self):
            self.closed = True

    reader = BadReader()

    s3_client.get_object.return_value = {
        "ETag": "my-etag",
        "LastModified": datetime.datetime.now(),
        "Body": reader,
    }

    f = Flow("test")
    storage = S3(bucket="bucket")
    storage.add_flow(f)

    with pytest.raises(ValueError, match="Oh no!"):
        storage.get_flow(f.name)

    assert reader.closed


def test_get_flow_s3_not_in_storage():
    f = Flow("test")
    storage = S3(bucket="bucket", key="test")

    with pytest.raises(ValueError):
        storage.get_flow(f.name)
