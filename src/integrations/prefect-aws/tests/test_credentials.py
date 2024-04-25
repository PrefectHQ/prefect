import pytest
from boto3.session import Session
from botocore.client import BaseClient
from moto import mock_s3
from prefect_aws.credentials import (
    AwsCredentials,
    ClientType,
    MinIOCredentials,
    _get_client_cached,
)


def test_aws_credentials_get_boto3_session():
    """
    Asserts that instantiated AwsCredentials block creates an
    authenticated boto3 session.
    """

    with mock_s3():
        aws_credentials_block = AwsCredentials()
        boto3_session = aws_credentials_block.get_boto3_session()
        assert isinstance(boto3_session, Session)


def test_minio_credentials_get_boto3_session():
    """
    Asserts that instantiated MinIOCredentials block creates
    an authenticated boto3 session.
    """

    minio_credentials_block = MinIOCredentials(
        minio_root_user="root_user", minio_root_password="root_password"
    )
    boto3_session = minio_credentials_block.get_boto3_session()
    assert isinstance(boto3_session, Session)


@pytest.mark.parametrize(
    "credentials",
    [
        AwsCredentials(),
        MinIOCredentials(
            minio_root_user="root_user", minio_root_password="root_password"
        ),
    ],
)
@pytest.mark.parametrize("client_type", ["s3", ClientType.S3])
def test_credentials_get_client(credentials, client_type):
    with mock_s3():
        assert isinstance(credentials.get_client(client_type), BaseClient)


@pytest.mark.parametrize(
    "credentials",
    [
        AwsCredentials(region_name="us-east-1"),
        MinIOCredentials(
            minio_root_user="root_user",
            minio_root_password="root_password",
            region_name="us-east-1",
        ),
    ],
)
@pytest.mark.parametrize("client_type", [member.value for member in ClientType])
def test_get_client_cached(credentials, client_type):
    """
    Test to ensure that _get_client_cached function returns the same instance
    for multiple calls with the same parameters and properly utilizes lru_cache.
    """

    _get_client_cached.cache_clear()

    assert _get_client_cached.cache_info().hits == 0, "Initial call count should be 0"

    credentials.get_client(client_type)
    credentials.get_client(client_type)
    credentials.get_client(client_type)

    assert _get_client_cached.cache_info().misses == 1
    assert _get_client_cached.cache_info().hits == 2


@pytest.mark.parametrize("client_type", [member.value for member in ClientType])
def test_aws_credentials_change_causes_cache_miss(client_type):
    """
    Test to ensure that changing configuration on an AwsCredentials instance
    after fetching a client causes a cache miss.
    """

    _get_client_cached.cache_clear()

    credentials = AwsCredentials(region_name="us-east-1")

    initial_client = credentials.get_client(client_type)

    credentials.region_name = "us-west-2"

    new_client = credentials.get_client(client_type)

    assert (
        initial_client is not new_client
    ), "Client should be different after configuration change"

    assert _get_client_cached.cache_info().misses == 2, "Cache should miss twice"


@pytest.mark.parametrize("client_type", [member.value for member in ClientType])
def test_minio_credentials_change_causes_cache_miss(client_type):
    """
    Test to ensure that changing configuration on an AwsCredentials instance
    after fetching a client causes a cache miss.
    """

    _get_client_cached.cache_clear()

    credentials = MinIOCredentials(
        minio_root_user="root_user",
        minio_root_password="root_password",
        region_name="us-east-1",
    )

    initial_client = credentials.get_client(client_type)

    credentials.region_name = "us-west-2"

    new_client = credentials.get_client(client_type)

    assert (
        initial_client is not new_client
    ), "Client should be different after configuration change"

    assert _get_client_cached.cache_info().misses == 2, "Cache should miss twice"


@pytest.mark.parametrize(
    "credentials_type, initial_field, new_field",
    [
        (
            AwsCredentials,
            {"region_name": "us-east-1"},
            {"region_name": "us-east-2"},
        ),
        (
            MinIOCredentials,
            {
                "region_name": "us-east-1",
                "minio_root_user": "root_user",
                "minio_root_password": "root_password",
            },
            {
                "region_name": "us-east-2",
                "minio_root_user": "root_user",
                "minio_root_password": "root_password",
            },
        ),
    ],
)
def test_aws_credentials_hash_changes(credentials_type, initial_field, new_field):
    credentials = credentials_type(**initial_field)
    initial_hash = hash(credentials)

    setattr(credentials, list(new_field.keys())[0], list(new_field.values())[0])
    new_hash = hash(credentials)

    assert initial_hash != new_hash, "Hash should change when region_name changes"


def test_aws_credentials_nested_client_parameters_are_hashable():
    """
    Test to ensure that nested client parameters are hashable.
    """

    creds = AwsCredentials(
        region_name="us-east-1",
        aws_client_parameters=dict(
            config=dict(
                connect_timeout=5,
                read_timeout=5,
                retries=dict(max_attempts=10, mode="standard"),
            )
        ),
    )

    assert hash(creds) is not None

    client = creds.get_client("s3")

    _client = creds.get_client("s3")

    assert client is _client
