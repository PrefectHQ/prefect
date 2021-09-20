import json
import os
import tempfile

import pytest

import prefect
from prefect import storage
from prefect.serialization.storage import (
    AzureSchema,
    DockerSchema,
    GCSSchema,
    LocalSchema,
    S3Schema,
    WebhookSchema,
    GitHubSchema,
    GitLabSchema,
    BitbucketSchema,
)


def test_all_storage_subclasses_have_schemas():
    "Test that ensures we don't forget to include a Schema for every subclass we implement"

    subclasses = {c.__name__ for c in storage.Storage.__subclasses__()}
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
    assert serialized["secrets"] == []


def test_docker_full_serialize():
    docker = storage.Docker(
        registry_url="url",
        image_name="name",
        image_tag="tag",
        prefect_version="0.5.2",
        secrets=["bar", "creds"],
        labels=["foo"],
        add_default_labels=False,
    )
    serialized = DockerSchema().dump(docker)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["image_name"] == "name"
    assert serialized["image_tag"] == "tag"
    assert serialized["registry_url"] == "url"
    assert serialized["flows"] == dict()
    assert serialized["prefect_version"] == "0.5.2"
    assert serialized["secrets"] == ["bar", "creds"]


def test_docker_serialize_with_flows():
    docker = storage.Docker(
        registry_url="url", image_name="name", image_tag="tag", secrets=["FOO"]
    )
    f = prefect.Flow("test")
    docker.add_flow(f)
    serialized = DockerSchema().dump(docker)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["image_name"] == "name"
    assert serialized["image_tag"] == "tag"
    assert serialized["registry_url"] == "url"
    assert serialized["flows"] == {"test": "/opt/prefect/flows/test.prefect"}
    assert serialized["secrets"] == ["FOO"]

    deserialized = DockerSchema().load(serialized)
    assert f.name in deserialized
    assert deserialized.secrets == ["FOO"]


def test_docker_serialize_with_flow_and_custom_prefect_dir():
    docker = storage.Docker(
        registry_url="url",
        image_name="name",
        image_tag="tag",
        secrets=["FOO"],
        prefect_directory="/tmp/something",
    )
    f = prefect.Flow("test")
    docker.add_flow(f)
    serialized = DockerSchema().dump(docker)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["image_name"] == "name"
    assert serialized["image_tag"] == "tag"
    assert serialized["registry_url"] == "url"
    assert serialized["flows"] == {"test": "/tmp/something/flows/test.prefect"}
    assert serialized["secrets"] == ["FOO"]

    deserialized = DockerSchema().load(serialized)
    assert f.name in deserialized
    assert deserialized.secrets == ["FOO"]


def test_s3_empty_serialize():
    s3 = storage.S3(bucket="bucket")
    serialized = S3Schema().dump(s3)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["bucket"]
    assert not serialized["key"]
    assert serialized["secrets"] == []


def test_s3_full_serialize():
    s3 = storage.S3(
        bucket="bucket",
        key="key",
        secrets=["hidden", "auth"],
        labels=["foo", "bar"],
        add_default_labels=False,
    )
    serialized = S3Schema().dump(s3)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["bucket"] == "bucket"
    assert serialized["key"] == "key"
    assert serialized["secrets"] == ["hidden", "auth"]


def test_s3_serialize_with_flows():
    s3 = storage.S3(bucket="bucket", key="key", secrets=["hidden", "auth"])
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
    assert deserialized.secrets == ["hidden", "auth"]


def test_azure_empty_serialize():
    azure = storage.Azure(container="container")
    serialized = AzureSchema().dump(azure)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["container"] == "container"
    assert serialized["blob_name"] is None
    assert serialized["secrets"] == []


def test_azure_full_serialize():
    azure = storage.Azure(
        container="container",
        connection_string_secret="conn",
        blob_name="name",
        secrets=["foo"],
        labels=["bar", "baz"],
        add_default_labels=False,
    )
    serialized = AzureSchema().dump(azure)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["container"] == "container"
    assert serialized["connection_string_secret"] == "conn"
    assert serialized["blob_name"] == "name"
    assert serialized["secrets"] == ["foo"]


def test_azure_creds_not_serialized():
    azure = storage.Azure(
        container="container", connection_string_secret="conn", blob_name="name"
    )
    serialized = AzureSchema().dump(azure)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["container"] == "container"
    assert serialized["blob_name"] == "name"
    assert serialized["connection_string_secret"] == "conn"
    assert serialized.get("connection_string") is None


def test_azure_serialize_with_flows():
    azure = storage.Azure(
        container="container",
        connection_string_secret="conn",
        blob_name="name",
        secrets=["foo"],
    )
    f = prefect.Flow("test")
    azure.flows["test"] = "key"
    serialized = AzureSchema().dump(azure)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["container"] == "container"
    assert serialized["blob_name"] == "name"
    assert serialized["flows"] == {"test": "key"}

    deserialized = AzureSchema().load(serialized)
    assert f.name in deserialized
    assert deserialized.secrets == ["foo"]


def test_local_empty_serialize():
    b = storage.Local()
    serialized = LocalSchema().dump(b)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["flows"] == dict()
    assert serialized["directory"].endswith(os.path.join(".prefect", "flows"))
    assert serialized["secrets"] == []


def test_local_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = storage.Local(directory=tmpdir, secrets=["AUTH"])
        s.add_flow(prefect.Flow("test"))
        serialized = LocalSchema().dump(s)
        deserialized = LocalSchema().load(serialized)

        assert "test" in deserialized
        runner = deserialized.get_flow("test")

    assert runner.run().is_successful()
    assert deserialized.secrets == ["AUTH"]


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
    assert serialized["secrets"] == []


def test_gcs_full_serialize():
    gcs = storage.GCS(
        bucket="bucket",
        key="key",
        project="project",
        secrets=["CREDS"],
        labels=["foo", "bar"],
        add_default_labels=False,
    )
    serialized = GCSSchema().dump(gcs)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["bucket"] == "bucket"
    assert serialized["key"] == "key"
    assert serialized["project"] == "project"
    assert serialized["secrets"] == ["CREDS"]


def test_gcs_serialize_with_flows():
    gcs = storage.GCS(project="project", bucket="bucket", key="key", secrets=["CREDS"])
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
    assert deserialized.secrets == ["CREDS"]


def test_webhook_full_serialize():
    test_file = "/Apps/test-app.flow"
    content_type = "application/octet-stream"
    base_url = "https://content.dropboxapi.com/2/files"
    build_url = f"{base_url}/upload"
    get_url = f"{base_url}/download"

    webhook = storage.Webhook(
        build_request_kwargs={
            "url": build_url,
            "headers": {
                "Content-Type": content_type,
                "Dropbox-API-Arg": json.dumps({"path": test_file}),
            },
        },
        build_request_http_method="POST",
        get_flow_request_kwargs={
            "url": get_url,
            "headers": {
                "Accept": content_type,
                "Dropbox-API-Arg": json.dumps({"path": test_file}),
            },
        },
        get_flow_request_http_method="POST",
        secrets=["CREDS"],
    )
    f = prefect.Flow("test")
    webhook.add_flow(f)

    serialized = WebhookSchema().dump(webhook)

    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["secrets"] == ["CREDS"]
    assert serialized["build_request_kwargs"] == {
        "url": build_url,
        "headers": {
            "Content-Type": content_type,
            "Dropbox-API-Arg": json.dumps({"path": test_file}),
        },
    }
    assert serialized["build_request_http_method"] == "POST"
    assert serialized["get_flow_request_kwargs"] == {
        "url": get_url,
        "headers": {
            "Accept": content_type,
            "Dropbox-API-Arg": json.dumps({"path": test_file}),
        },
    }
    assert serialized["get_flow_request_http_method"] == "POST"
    assert serialized["stored_as_script"] is False


@pytest.mark.parametrize("ref", [None, "testref"])
@pytest.mark.parametrize("access_token_secret", [None, "secret"])
@pytest.mark.parametrize("base_url", [None, "https://some-url"])
def test_github_serialize(ref, access_token_secret, base_url):
    github = storage.GitHub(
        repo="test/repo",
        path="flow.py",
        access_token_secret=access_token_secret,
        base_url=base_url,
    )
    if ref is not None:
        github.ref = ref
    serialized = GitHubSchema().dump(github)
    assert serialized["__version__"] == prefect.__version__
    assert serialized["repo"] == "test/repo"
    assert serialized["path"] == "flow.py"
    assert serialized["ref"] == ref
    assert serialized["secrets"] == []
    assert serialized["access_token_secret"] == access_token_secret
    assert serialized["base_url"] == base_url


def test_gitlab_empty_serialize():
    gitlab = storage.GitLab(repo="test/repo")
    serialized = GitLabSchema().dump(gitlab)
    assert serialized["__version__"] == prefect.__version__
    assert serialized["repo"] == "test/repo"
    assert not serialized["host"]
    assert not serialized["path"]
    assert not serialized["ref"]
    assert serialized["secrets"] == []


@pytest.mark.parametrize("access_token_secret", [None, "secret"])
def test_gitlab_full_serialize(access_token_secret):
    gitlab = storage.GitLab(
        repo="test/repo",
        path="path/to/flow.py",
        host="http://localhost:1234",
        ref="test-branch",
        secrets=["token"],
        access_token_secret=access_token_secret,
    )

    serialized = GitLabSchema().dump(gitlab)
    assert serialized["__version__"] == prefect.__version__
    assert serialized["repo"] == "test/repo"
    assert serialized["host"] == "http://localhost:1234"
    assert serialized["path"] == "path/to/flow.py"
    assert serialized["ref"] == "test-branch"
    assert serialized["secrets"] == ["token"]
    assert serialized["access_token_secret"] == access_token_secret


def test_bitbucket_empty_serialize():
    # Testing that empty serialization occurs without error or weirdness in attributes.
    bitbucket = storage.Bitbucket(project="PROJECT", repo="test-repo")
    serialized = BitbucketSchema().dump(bitbucket)
    assert serialized["__version__"] == prefect.__version__
    assert serialized["project"] == "PROJECT"
    assert serialized["repo"] == "test-repo"
    assert not serialized["host"]
    assert not serialized["path"]
    assert not serialized["ref"]
    assert serialized["secrets"] == []


@pytest.mark.parametrize("access_token_secret", [None, "secret"])
def test_bitbucket_full_serialize(access_token_secret):
    bitbucket = storage.Bitbucket(
        project="PROJECT",
        repo="test-repo",
        path="test-flow.py",
        host="http://localhost:7990",
        ref="develop",
        secrets=["token"],
        access_token_secret=access_token_secret,
    )

    serialized = BitbucketSchema().dump(bitbucket)
    assert serialized["__version__"] == prefect.__version__
    assert serialized["project"] == "PROJECT"
    assert serialized["repo"] == "test-repo"
    assert serialized["path"] == "test-flow.py"
    assert serialized["host"] == "http://localhost:7990"
    assert serialized["ref"] == "develop"
    assert serialized["secrets"] == ["token"]
    assert serialized["access_token_secret"] == access_token_secret


def test_bitbucket_incorrect_secret():
    with pytest.raises(ValueError):
        storage.Bitbucket(
            project="PROJECT",
            repo="test-repo",
            workspace="test-workspace",
            path="test-flow.py",
            host="http://localhost:7990",
            ref="develop",
            secrets=["token"],
            access_token_secret="secret",
        )


def test_module_serialize():
    module = storage.Module("test")
    serialized = module.serialize()
    assert serialized["module"] == "test"
