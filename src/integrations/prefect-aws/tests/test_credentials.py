from unittest.mock import patch

import pytest
from boto3.session import Session
from botocore.client import BaseClient
from moto import mock_aws
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

    with mock_aws():
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
    with mock_aws():
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
def test_aws_credentials_region_properly_passed_to_client(client_type):
    """
    Test to ensure that region_name is properly passed to the client.
    """
    region_name = "mock-region-us-east-1"
    credentials = AwsCredentials(region_name=region_name)
    client = credentials.get_client(client_type)
    assert client.meta.region_name == region_name


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

    assert initial_client is not new_client, (
        "Client should be different after configuration change"
    )

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

    assert initial_client is not new_client, (
        "Client should be different after configuration change"
    )

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


def test_minio_credentials_nested_client_parameters_are_hashable():
    """
    Test to ensure that MinIOCredentials with nested client parameters are hashable.
    Regression test for issue #18748.
    """

    creds = MinIOCredentials(
        minio_root_user="test_user",
        minio_root_password="test_password",
        region_name="us-east-1",
        aws_client_parameters=dict(
            config=dict(
                request_checksum_calculation="when_required",
                connect_timeout=5,
                read_timeout=5,
                retries=dict(max_attempts=10, mode="standard"),
            )
        ),
    )

    # This should not raise TypeError: unhashable type: 'dict'
    assert hash(creds) is not None

    # Test that caching works properly
    _get_client_cached.cache_clear()

    client = creds.get_client("s3")
    _client = creds.get_client("s3")

    assert client is _client
    assert _get_client_cached.cache_info().hits == 1


def test_aws_credentials_without_assume_role_arn_works():
    """
    Test that AwsCredentials works normally when assume_role_arn is not provided.
    This ensures backward compatibility.
    """
    with mock_aws():
        credentials = AwsCredentials(region_name="us-east-1")
        session = credentials.get_boto3_session()
        assert isinstance(session, Session)
        assert session.region_name == "us-east-1"


def test_aws_credentials_assume_role_basic():
    """
    Test that AwsCredentials can assume a role when assume_role_arn is provided.
    """
    assume_role_arn = "arn:aws:iam::123456789012:role/TestRole"

    # Create credentials with assume_role_arn
    credentials = AwsCredentials(
        assume_role_arn=assume_role_arn, region_name="us-east-1"
    )

    with mock_aws():
        # Mock the base session and STS client
        with patch("prefect_aws.credentials.boto3.Session") as mock_session_class:
            mock_base_session = mock_session_class.return_value
            mock_sts_client = mock_base_session.client.return_value
            mock_sts_client.assume_role.return_value = {
                "Credentials": {
                    "AccessKeyId": "ASIAEXAMPLE",
                    "SecretAccessKey": "secret",
                    "SessionToken": "token",
                    "Expiration": "2024-01-01T00:00:00Z",
                }
            }

            # Create a real session for the assumed role
            def session_side_effect(*args, **kwargs):
                return Session(*args, **kwargs)

            mock_session_class.side_effect = session_side_effect

            session = credentials.get_boto3_session()
            assert isinstance(session, Session)
            assert session.region_name == "us-east-1"

            # Verify we can create a client with the assumed role session
            s3_client = session.client("s3")
            assert isinstance(s3_client, BaseClient)


def test_aws_credentials_assume_role_with_custom_session_name():
    """
    Test that AwsCredentials uses custom RoleSessionName when provided.
    """
    assume_role_arn = "arn:aws:iam::123456789012:role/TestRole"
    custom_session_name = "my-custom-session"

    credentials = AwsCredentials(
        assume_role_arn=assume_role_arn,
        region_name="us-east-1",
        assume_role_kwargs={"RoleSessionName": custom_session_name},
    )

    with mock_aws():
        # Mock the base session and STS client
        with patch("prefect_aws.credentials.boto3.Session") as mock_session_class:
            mock_base_session = mock_session_class.return_value
            mock_sts_client = mock_base_session.client.return_value
            mock_sts_client.assume_role.return_value = {
                "Credentials": {
                    "AccessKeyId": "ASIAEXAMPLE",
                    "SecretAccessKey": "secret",
                    "SessionToken": "token",
                    "Expiration": "2024-01-01T00:00:00Z",
                }
            }

            credentials.get_boto3_session()

            # Verify assume_role was called with the custom session name
            mock_sts_client.assume_role.assert_called_once()
            call_args = mock_sts_client.assume_role.call_args
            assert call_args.kwargs["RoleArn"] == assume_role_arn
            assert call_args.kwargs["RoleSessionName"] == custom_session_name


def test_aws_credentials_assume_role_with_static_key_credentials():
    """
    Test that AwsCredentials can assume a role when static AWS credentials are provided.
    """
    assume_role_arn = "arn:aws:iam::123456789012:role/TestRole"

    # Create credentials with static keys and assume_role_arn
    credentials = AwsCredentials(
        aws_access_key_id="AKIAEXAMPLE",
        aws_secret_access_key="secret",
        assume_role_arn=assume_role_arn,
        region_name="us-east-1",
    )

    with mock_aws():
        session = credentials.get_boto3_session()
        credentials = session.get_credentials()

        # Verify that the assumed role credentials are used
        assert credentials.access_key.startswith("ASIA")


def test_aws_credentials_assume_role_generates_default_session_name():
    """
    Test that AwsCredentials generates a default RoleSessionName when not provided.
    """
    assume_role_arn = "arn:aws:iam::123456789012:role/TestRole"

    # Create credentials with assume_role_arn but no RoleSessionName
    credentials = AwsCredentials(
        assume_role_arn=assume_role_arn, region_name="us-east-1"
    )

    with mock_aws():
        # Mock the base session and STS client
        with patch("prefect_aws.credentials.boto3.Session") as mock_session_class:
            mock_base_session = mock_session_class.return_value
            mock_sts_client = mock_base_session.client.return_value
            mock_sts_client.assume_role.return_value = {
                "Credentials": {
                    "AccessKeyId": "ASIAEXAMPLE",
                    "SecretAccessKey": "secret",
                    "SessionToken": "token",
                    "Expiration": "2024-01-01T00:00:00Z",
                }
            }

            credentials.get_boto3_session()

            # Verify assume_role was called with a generated session name
            mock_sts_client.assume_role.assert_called_once()
            call_args = mock_sts_client.assume_role.call_args
            assert call_args.kwargs["RoleArn"] == assume_role_arn
            assert "RoleSessionName" in call_args.kwargs
            assert call_args.kwargs["RoleSessionName"].startswith("prefect-session-")


def test_aws_credentials_assume_role_with_additional_kwargs():
    """
    Test that AwsCredentials passes additional assume_role_kwargs to assume_role.
    """
    assume_role_arn = "arn:aws:iam::123456789012:role/TestRole"

    # Create credentials with additional assume_role_kwargs
    credentials = AwsCredentials(
        assume_role_arn=assume_role_arn,
        region_name="us-east-1",
        assume_role_kwargs={
            "RoleSessionName": "my-session",
            "DurationSeconds": 3600,
            "ExternalId": "unique-external-id",
        },
    )

    # Mock the base session and STS client
    with patch("prefect_aws.credentials.boto3.Session") as mock_session_class:
        mock_base_session = mock_session_class.return_value
        mock_sts_client = mock_base_session.client.return_value
        mock_sts_client.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "ASIAEXAMPLE",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
                "Expiration": "2024-01-01T00:00:00Z",
            }
        }

        credentials.get_boto3_session()

        # Verify assume_role was called with all parameters
        mock_sts_client.assume_role.assert_called_once()
        call_args = mock_sts_client.assume_role.call_args
        assert call_args.kwargs["RoleArn"] == assume_role_arn
        assert call_args.kwargs["RoleSessionName"] == "my-session"
        assert call_args.kwargs["DurationSeconds"] == 3600
        assert call_args.kwargs["ExternalId"] == "unique-external-id"


def test_aws_credentials_hash_includes_assume_role_arn():
    """
    Test that hash changes when assume_role_arn changes.
    """
    credentials1 = AwsCredentials(
        assume_role_arn="arn:aws:iam::123456789012:role/Role1"
    )
    credentials2 = AwsCredentials(
        assume_role_arn="arn:aws:iam::123456789012:role/Role2"
    )

    assert hash(credentials1) != hash(credentials2)


def test_aws_credentials_hash_includes_assume_role_kwargs():
    """
    Test that hash changes when assume_role_kwargs changes.
    """
    credentials1 = AwsCredentials(
        assume_role_arn="arn:aws:iam::123456789012:role/Role1",
        assume_role_kwargs={"DurationSeconds": 3600},
    )
    credentials2 = AwsCredentials(
        assume_role_arn="arn:aws:iam::123456789012:role/Role1",
        assume_role_kwargs={"DurationSeconds": 7200},
    )

    assert hash(credentials1) != hash(credentials2)


def test_aws_credentials_hash_with_nested_assume_role_kwargs():
    """
    Test that hash works with nested structures in assume_role_kwargs (e.g., Tags, PolicyArns).
    """
    credentials = AwsCredentials(
        assume_role_arn="arn:aws:iam::123456789012:role/Role1",
        assume_role_kwargs={
            "Tags": [
                {"Key": "Project", "Value": "MyProject"},
                {"Key": "Environment", "Value": "Production"},
            ],
            "PolicyArns": [
                {"arn": "arn:aws:iam::aws:policy/ReadOnlyAccess"},
            ],
        },
    )

    # Should not raise TypeError: unhashable type
    assert hash(credentials) is not None


def test_aws_credentials_assume_role_hash_changes_cause_cache_invalidation():
    """
    Test that changing assume_role_arn causes hash to change, which will cause cache invalidation.
    """
    credentials1 = AwsCredentials(
        assume_role_arn="arn:aws:iam::123456789012:role/Role1",
        region_name="us-east-1",
    )
    credentials2 = AwsCredentials(
        assume_role_arn="arn:aws:iam::123456789012:role/Role2",
        region_name="us-east-1",
    )

    # Different assume_role_arn should result in different hashes
    assert hash(credentials1) != hash(credentials2)

    # This ensures that cache will be invalidated when assume_role_arn changes
    # because the hash is used as part of the cache key
