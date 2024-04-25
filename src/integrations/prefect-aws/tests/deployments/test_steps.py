import os
import sys
from pathlib import Path, PurePath, PurePosixPath
from unittest.mock import patch

import boto3
import pytest
from moto import mock_s3
from prefect_aws import AwsCredentials
from prefect_aws.deployments.steps import get_s3_client, pull_from_s3, push_to_s3


@pytest.fixture(scope="module", autouse=True)
def set_custom_endpoint():
    original = os.environ.get("MOTO_S3_CUSTOM_ENDPOINTS")
    os.environ["MOTO_S3_CUSTOM_ENDPOINTS"] = "http://custom.minio.endpoint:9000"
    yield
    os.environ.pop("MOTO_S3_CUSTOM_ENDPOINTS")
    if original is not None:
        os.environ["MOTO_S3_CUSTOM_ENDPOINTS"] = original


@pytest.fixture
def s3_setup():
    with mock_s3():
        bucket_name = "my-test-bucket"
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket=bucket_name)
        yield s3, bucket_name


@pytest.fixture
def tmp_files(tmp_path: Path):
    files = [
        "testfile1.txt",
        "testfile2.txt",
        "testfile3.txt",
        "testdir1/testfile4.txt",
        "testdir2/testfile5.txt",
    ]

    (tmp_path / ".prefectignore").write_text(
        """
    testdir1/*
    .prefectignore
    """
    )

    for file in files:
        filepath = tmp_path / file
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text("Sample text")

    return tmp_path


@pytest.fixture
def tmp_files_win(tmp_path: Path):
    files = [
        "testfile1.txt",
        "testfile2.txt",
        "testfile3.txt",
        r"testdir1\testfile4.txt",
        r"testdir2\testfile5.txt",
    ]

    for file in files:
        filepath = tmp_path / file
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text("Sample text")

    return tmp_path


@pytest.fixture
def mock_aws_credentials(monkeypatch):
    # Set mock environment variables for AWS credentials
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test_access_key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test_secret_key")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "test_session_token")

    # Yield control back to the test function
    yield

    # Clean up by deleting the mock environment variables
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)


def test_push_to_s3(s3_setup, tmp_files, mock_aws_credentials):
    s3, bucket_name = s3_setup
    folder = "my-project"

    os.chdir(tmp_files)

    push_to_s3(bucket_name, folder)

    s3_objects = s3.list_objects_v2(Bucket=bucket_name)
    object_keys = [PurePath(item["Key"]).as_posix() for item in s3_objects["Contents"]]

    expected_keys = [
        f"{folder}/testfile1.txt",
        f"{folder}/testfile2.txt",
        f"{folder}/testfile3.txt",
        f"{folder}/testdir2/testfile5.txt",
    ]

    assert set(object_keys) == set(expected_keys)


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
def test_push_to_s3_as_posix(s3_setup, tmp_files_win, mock_aws_credentials):
    s3, bucket_name = s3_setup
    folder = "my-project"

    os.chdir(tmp_files_win)

    push_to_s3(bucket_name, folder)

    s3_objects = s3.list_objects_v2(Bucket=bucket_name)
    object_keys = [item["Key"] for item in s3_objects["Contents"]]

    expected_keys = [
        f"{folder}/testfile1.txt",
        f"{folder}/testfile2.txt",
        f"{folder}/testfile3.txt",
        f"{folder}/testdir1/testfile4.txt",
        f"{folder}/testdir2/testfile5.txt",
    ]

    assert set(object_keys) == set(expected_keys)


def test_pull_from_s3(s3_setup, tmp_path, mock_aws_credentials):
    s3, bucket_name = s3_setup
    folder = "my-project"

    files = {
        f"{folder}/testfile1.txt": "Hello, world!",
        f"{folder}/testfile2.txt": "Test content",
        f"{folder}/testdir1/testfile3.txt": "Nested file",
    }

    for key, content in files.items():
        s3.put_object(Bucket=bucket_name, Key=key, Body=content)

    os.chdir(tmp_path)
    pull_from_s3(bucket_name, folder)

    for key, content in files.items():
        target = Path(tmp_path) / PurePosixPath(key).relative_to(folder)
        assert target.exists()
        assert target.read_text() == content


def test_push_pull_empty_folders(s3_setup, tmp_path, mock_aws_credentials):
    s3, bucket_name = s3_setup
    folder = "my-project"

    # Create empty folders
    (tmp_path / "empty1").mkdir()
    (tmp_path / "empty2").mkdir()

    # Create test files
    (tmp_path / "testfile1.txt").write_text("Sample text")
    (tmp_path / "testfile2.txt").write_text("Sample text")

    os.chdir(tmp_path)

    # Push to S3
    push_to_s3(bucket_name, folder)

    # Check if the empty folders are not uploaded
    s3_objects = s3.list_objects_v2(Bucket=bucket_name)
    object_keys = [item["Key"] for item in s3_objects["Contents"]]

    assert f"{folder}/empty1/" not in object_keys
    assert f"{folder}/empty2/" not in object_keys

    # Pull from S3
    pull_from_s3(bucket_name, folder)

    # Check if the empty folders are not created
    assert not (tmp_path / "empty1_copy").exists()
    assert not (tmp_path / "empty2_copy").exists()


@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires Python 3.8+")
def test_s3_session_with_params():
    with patch("boto3.Session") as mock_session:
        get_s3_client(
            credentials={
                "aws_access_key_id": "THE_KEY",
                "aws_secret_access_key": "SHHH!",
                "profile_name": "foo",
                "region_name": "us-weast-1",
                "aws_client_parameters": {
                    "api_version": "v1",
                    "config": {"connect_timeout": 300},
                },
            }
        )
        get_s3_client(
            credentials={
                "aws_access_key_id": "THE_KEY",
                "aws_secret_access_key": "SHHH!",
            },
            client_parameters={
                "region_name": "us-west-1",
                "config": {"signature_version": "s3v4"},
            },
        )
        creds_block = AwsCredentials(
            aws_access_key_id="BlockKey",
            aws_secret_access_key="BlockSecret",
            aws_session_token="BlockToken",
            profile_name="BlockProfile",
            region_name="BlockRegion",
            aws_client_parameters={
                "api_version": "v1",
                "use_ssl": True,
                "verify": True,
                "endpoint_url": "BlockEndpoint",
                "config": {"connect_timeout": 123},
            },
        )
        get_s3_client(credentials=creds_block.dict())
        get_s3_client(
            credentials={
                "minio_root_user": "MY_USER",
                "minio_root_password": "MY_PASSWORD",
            },
            client_parameters={"endpoint_url": "http://custom.minio.endpoint:9000"},
        )
        all_calls = mock_session.mock_calls
        assert len(all_calls) == 8
        assert all_calls[0].kwargs == {
            "aws_access_key_id": "THE_KEY",
            "aws_secret_access_key": "SHHH!",
            "aws_session_token": None,
            "profile_name": "foo",
            "region_name": "us-weast-1",
        }
        assert all_calls[1].args[0] == "s3"
        assert {
            "api_version": "v1",
            "endpoint_url": None,
            "use_ssl": True,
            "verify": None,
        }.items() <= all_calls[1].kwargs.items()
        assert all_calls[1].kwargs.get("config").connect_timeout == 300
        assert all_calls[1].kwargs.get("config").signature_version is None
        assert all_calls[2].kwargs == {
            "aws_access_key_id": "THE_KEY",
            "aws_secret_access_key": "SHHH!",
            "aws_session_token": None,
            "profile_name": None,
            "region_name": "us-west-1",
        }
        assert all_calls[3].args[0] == "s3"
        assert {
            "api_version": None,
            "endpoint_url": None,
            "use_ssl": True,
            "verify": None,
        }.items() <= all_calls[3].kwargs.items()
        assert all_calls[3].kwargs.get("config").connect_timeout == 60
        assert all_calls[3].kwargs.get("config").signature_version == "s3v4"
        assert all_calls[4].kwargs == {
            "aws_access_key_id": "BlockKey",
            "aws_secret_access_key": creds_block.aws_secret_access_key,
            "aws_session_token": "BlockToken",
            "profile_name": "BlockProfile",
            "region_name": "BlockRegion",
        }
        assert all_calls[5].args[0] == "s3"
        assert {
            "api_version": "v1",
            "use_ssl": True,
            "verify": True,
            "endpoint_url": "BlockEndpoint",
        }.items() <= all_calls[5].kwargs.items()
        assert all_calls[5].kwargs.get("config").connect_timeout == 123
        assert all_calls[5].kwargs.get("config").signature_version is None
        assert all_calls[6].kwargs == {
            "aws_access_key_id": "MY_USER",
            "aws_secret_access_key": "MY_PASSWORD",
            "aws_session_token": None,
            "profile_name": None,
            "region_name": None,
        }
        assert all_calls[7].args[0] == "s3"
        assert {
            "api_version": None,
            "use_ssl": True,
            "verify": None,
            "endpoint_url": "http://custom.minio.endpoint:9000",
        }.items() <= all_calls[7].kwargs.items()


def test_custom_credentials_and_client_parameters(s3_setup, tmp_files):
    s3, bucket_name = s3_setup
    folder = "my-project"

    # Custom credentials and client parameters
    custom_credentials = {
        "aws_access_key_id": "fake_access_key",
        "aws_secret_access_key": "fake_secret_key",
    }

    custom_client_parameters = {
        "region_name": "us-west-1",
        "config": {"signature_version": "s3v4"},
    }

    os.chdir(tmp_files)

    # Test push_to_s3 with custom credentials and client parameters
    push_to_s3(
        bucket_name,
        folder,
        credentials=custom_credentials,
        client_parameters=custom_client_parameters,
    )

    # Test pull_from_s3 with custom credentials and client parameters
    tmp_path = tmp_files / "test_pull"
    tmp_path.mkdir(parents=True, exist_ok=True)
    os.chdir(tmp_path)

    pull_from_s3(
        bucket_name,
        folder,
        credentials=custom_credentials,
        client_parameters=custom_client_parameters,
    )

    for file in tmp_files.iterdir():
        if file.is_file() and file.name != ".prefectignore":
            assert (tmp_path / file.name).exists()


def test_custom_credentials_and_client_parameters_minio(s3_setup, tmp_files):
    s3, bucket_name = s3_setup
    folder = "my-project"

    # Custom credentials and client parameters
    custom_credentials = {
        "minio_root_user": "fake_user",
        "minio_root_password": "fake_password",
    }

    custom_client_parameters = {
        "endpoint_url": "http://custom.minio.endpoint:9000",
    }

    os.chdir(tmp_files)

    # Test push_to_s3 with custom credentials and client parameters
    push_to_s3(
        bucket_name,
        folder,
        credentials=custom_credentials,
        client_parameters=custom_client_parameters,
    )

    # Test pull_from_s3 with custom credentials and client parameters
    tmp_path = tmp_files / "test_pull"
    tmp_path.mkdir(parents=True, exist_ok=True)
    os.chdir(tmp_path)

    pull_from_s3(
        bucket_name,
        folder,
        credentials=custom_credentials,
        client_parameters=custom_client_parameters,
    )

    for file in tmp_files.iterdir():
        if file.is_file() and file.name != ".prefectignore":
            assert (tmp_path / file.name).exists()


def test_without_prefectignore_file(s3_setup, tmp_files: Path, mock_aws_credentials):
    s3, bucket_name = s3_setup
    folder = "my-project"

    # Remove the .prefectignore file
    (tmp_files / ".prefectignore").unlink()

    os.chdir(tmp_files)

    # Test push_to_s3 without .prefectignore file
    push_to_s3(bucket_name, folder)

    # Test pull_from_s3 without .prefectignore file
    tmp_path = tmp_files / "test_pull"
    tmp_path.mkdir(parents=True, exist_ok=True)
    os.chdir(tmp_path)

    pull_from_s3(bucket_name, folder)

    for file in tmp_files.iterdir():
        if file.is_file():
            assert (tmp_path / file.name).exists()


def test_prefectignore_with_comments_and_empty_lines(
    s3_setup, tmp_files: Path, mock_aws_credentials
):
    s3, bucket_name = s3_setup
    folder = "my-project"

    # Update the .prefectignore file with comments and empty lines
    (tmp_files / ".prefectignore").write_text(
        """
        # This is a comment
        testdir1/*

        .prefectignore
        """
    )

    os.chdir(tmp_files)

    # Test push_to_s3
    push_to_s3(bucket_name, folder)

    # Test pull_from_s3
    tmp_path = tmp_files / "test_pull"
    tmp_path.mkdir(parents=True, exist_ok=True)
    os.chdir(tmp_path)

    pull_from_s3(bucket_name, folder)

    for file in tmp_files.iterdir():
        if file.is_file() and file.name != ".prefectignore":
            assert (tmp_path / file.name).exists()
