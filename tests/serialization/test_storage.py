import os
import tempfile

import pytest

import prefect
from prefect.environments import storage
from prefect.serialization.storage import (
    AzureSchema,
    BaseStorageSchema,
    BytesSchema,
    DockerSchema,
    GCSSchema,
    LocalSchema,
    MemorySchema,
    S3Schema,
)


def test_all_storage_subclasses_have_schemas():
    "Test that ensures we don't forget to include a Schema for every subclass we implement"

    subclasses = set(c.__name__ for c in storage.Storage.__subclasses__())
    subclasses.add(storage.Storage.__name__)  # add base storage, not a subclass
    schemas = set(prefect.serialization.storage.StorageSchema().type_schemas.keys())
    assert subclasses == schemas


def test_docker_empty_serialize():
    docker = storage.Docker()
    serialized = DockerSchema().dump(docker)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert "prefect_version" in serialized
    assert not serialized["image_name"]
    assert not serialized["image_tag"]
    assert not serialized["registry_url"]


def test_memory_serialize():
    s = storage.Memory()
    serialized = MemorySchema().dump(s)

    assert serialized == {"__version__": prefect.__version__}


def test_memory_roundtrip():
    s = storage.Memory()
    s.add_flow(prefect.Flow("test"))
    serialized = MemorySchema().dump(s)

    assert serialized == {"__version__": prefect.__version__}
    deserialized = MemorySchema().load(serialized)
    assert deserialized.flows == dict()


def test_docker_full_serialize():
    docker = storage.Docker(
        registry_url="url", image_name="name", image_tag="tag", prefect_version="0.5.2"
    )
    serialized = DockerSchema().dump(docker)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["image_name"] == "name"
    assert serialized["image_tag"] == "tag"
    assert serialized["registry_url"] == "url"
    assert serialized["flows"] == dict()
    assert serialized["prefect_version"] == "0.5.2"


def test_docker_serialize_with_flows():
    docker = storage.Docker(registry_url="url", image_name="name", image_tag="tag")
    f = prefect.Flow("test")
    docker.add_flow(f)
    serialized = DockerSchema().dump(docker)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["image_name"] == "name"
    assert serialized["image_tag"] == "tag"
    assert serialized["registry_url"] == "url"
    assert serialized["flows"] == {"test": "/root/.prefect/flows/test.prefect"}

    deserialized = DockerSchema().load(serialized)
    assert f.name in deserialized


def test_s3_empty_serialize():
    s3 = storage.S3(bucket="bucket")
    serialized = S3Schema().dump(s3)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["bucket"]
    assert not serialized["key"]


def test_s3_full_serialize():
    s3 = storage.S3(
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="session",
        bucket="bucket",
        key="key",
    )
    serialized = S3Schema().dump(s3)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["bucket"] == "bucket"
    assert serialized["key"] == "key"


def test_s3_aws_creds_not_serialized():
    s3 = storage.S3(
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="session",
        bucket="bucket",
        key="key",
    )
    serialized = S3Schema().dump(s3)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["bucket"] == "bucket"
    assert serialized["key"] == "key"
    assert serialized.get("aws_access_key_id") is None
    assert serialized.get("aws_secret_access_key") is None
    assert serialized.get("aws_session_token") is None


def test_s3_serialize_with_flows():
    s3 = storage.S3(
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="session",
        bucket="bucket",
        key="key",
    )
    f = prefect.Flow("test")
    s3.flows["test"] = "key"
    serialized = S3Schema().dump(s3)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["bucket"] == "bucket"
    assert serialized["key"] == "key"
    assert serialized["flows"] == {"test": "key"}

    deserialized = S3Schema().load(serialized)
    assert f.name in deserialized


def test_azure_empty_serialize():
    azure = storage.Azure(container="container")
    serialized = AzureSchema().dump(azure)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["container"] == "container"
    assert serialized["blob_name"] is None


def test_azure_full_serialize():
    azure = storage.Azure(
        container="container", connection_string="conn", blob_name="name"
    )
    serialized = AzureSchema().dump(azure)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["container"] == "container"
    assert serialized["blob_name"] == "name"


def test_azure_creds_not_serialized():
    azure = storage.Azure(
        container="container", connection_string="conn", blob_name="name"
    )
    serialized = AzureSchema().dump(azure)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["container"] == "container"
    assert serialized["blob_name"] == "name"
    assert serialized.get("connection_string") is None


def test_azure_serialize_with_flows():
    azure = storage.Azure(
        container="container", connection_string="conn", blob_name="name"
    )
    f = prefect.Flow("test")
    azure.flows["test"] = "key"
    serialized = AzureSchema().dump(azure)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["container"] == "container"
    assert serialized["blob_name"] == "name"
    assert serialized.get("connection_string") is None
    assert serialized["flows"] == {"test": "key"}

    deserialized = AzureSchema().load(serialized)
    assert f.name in deserialized


def test_bytes_empty_serialize():
    b = storage.Bytes()
    serialized = BytesSchema().dump(b)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["flows"] == dict()


def test_bytes_roundtrip():
    s = storage.Bytes()
    s.add_flow(prefect.Flow("test"))
    serialized = BytesSchema().dump(s)
    deserialized = BytesSchema().load(serialized)

    assert "test" in deserialized
    runner = deserialized.get_flow("test")
    assert runner.run().is_successful()


def test_local_empty_serialize():
    b = storage.Local()
    serialized = LocalSchema().dump(b)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["flows"] == dict()
    assert serialized["directory"].endswith(os.path.join(".prefect", "flows"))


def test_local_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = storage.Local(directory=tmpdir)
        flow_loc = s.add_flow(prefect.Flow("test"))
        serialized = LocalSchema().dump(s)
        deserialized = LocalSchema().load(serialized)

        assert "test" in deserialized
        runner = deserialized.get_flow(flow_loc)

    assert runner.run().is_successful()


def test_local_storage_doesnt_validate_on_deserialization():
    payload = {
        "directory": "C:\\Users\\chris\\.prefect\\flows",
        "flows": {"hello": "C:\\Users\\chris\\.prefect\\flows\\hello.prefect"},
        "__version__": "0.7.3",
        "type": "Local",
    }
    storage = LocalSchema().load(payload)
    assert storage.directory == "C:\\Users\\chris\\.prefect\\flows"


def test_gcs_empty_serialize():
    gcs = storage.GCS(bucket="bucket")
    serialized = GCSSchema().dump(gcs)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["bucket"]
    assert not serialized["key"]


def test_gcs_full_serialize():
    gcs = storage.GCS(bucket="bucket", key="key", project="project")
    serialized = GCSSchema().dump(gcs)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["bucket"] == "bucket"
    assert serialized["key"] == "key"
    assert serialized["project"] == "project"


def test_gcs_serialize_with_flows():
    gcs = storage.GCS(project="project", bucket="bucket", key="key")
    f = prefect.Flow("test")
    gcs.flows["test"] = "key"
    serialized = GCSSchema().dump(gcs)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["bucket"] == "bucket"
    assert serialized["key"] == "key"
    assert serialized["project"] == "project"
    assert serialized["flows"] == {"test": "key"}

    deserialized = GCSSchema().load(serialized)
    assert f.name in deserialized
