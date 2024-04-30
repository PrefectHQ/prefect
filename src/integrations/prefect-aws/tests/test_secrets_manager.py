from datetime import datetime, timedelta

import boto3
import pytest
from moto import mock_secretsmanager
from prefect_aws.secrets_manager import (
    AwsSecret,
    create_secret,
    delete_secret,
    read_secret,
    update_secret,
)

from prefect import flow


@pytest.fixture
def secretsmanager_client():
    with mock_secretsmanager():
        yield boto3.client("secretsmanager", "us-east-1")


@pytest.fixture(
    params=[
        dict(Name="secret_string_no_version", SecretString="1"),
        dict(
            Name="secret_string_with_version_id", SecretString="2", should_version=True
        ),
        dict(Name="secret_binary_no_version", SecretBinary=b"3"),
        dict(
            Name="secret_binary_with_version_id", SecretBinary=b"4", should_version=True
        ),
    ]
)
def secret_under_test(secretsmanager_client, request):
    should_version = request.param.pop("should_version", False)
    secretsmanager_client.create_secret(**request.param)

    update_result = None
    if should_version:
        if "SecretString" in request.param:
            request.param["SecretString"] = request.param["SecretString"] + "-versioned"
        elif "SecretBinary" in request.param:
            request.param["SecretBinary"] = (
                request.param["SecretBinary"] + b"-versioned"
            )
        update_secret_kwargs = request.param.copy()
        update_secret_kwargs["SecretId"] = update_secret_kwargs.pop("Name")
        update_result = secretsmanager_client.update_secret(**update_secret_kwargs)

    return dict(
        secret_name=request.param.get("Name"),
        version_id=update_result.get("VersionId") if update_result else None,
        expected_value=request.param.get("SecretString")
        or request.param.get("SecretBinary"),
    )


async def test_read_secret(secret_under_test, aws_credentials):
    expected_value = secret_under_test.pop("expected_value")

    @flow
    async def test_flow():
        return await read_secret(
            aws_credentials=aws_credentials,
            **secret_under_test,
        )

    assert (await test_flow()) == expected_value


async def test_update_secret(secret_under_test, aws_credentials, secretsmanager_client):
    current_secret_value = secret_under_test["expected_value"]
    new_secret_value = (
        current_secret_value + "2"
        if isinstance(current_secret_value, str)
        else current_secret_value + b"2"
    )

    @flow
    async def test_flow():
        return await update_secret(
            aws_credentials=aws_credentials,
            secret_name=secret_under_test["secret_name"],
            secret_value=new_secret_value,
        )

    flow_state = await test_flow()
    assert flow_state.get("Name") == secret_under_test["secret_name"]

    updated_secret = secretsmanager_client.get_secret_value(
        SecretId=secret_under_test["secret_name"]
    )
    assert (
        updated_secret.get("SecretString") == new_secret_value
        or updated_secret.get("SecretBinary") == new_secret_value
    )


@pytest.mark.parametrize(
    ["secret_name", "secret_value"], [["string_secret", "42"], ["binary_secret", b"42"]]
)
async def test_create_secret(
    aws_credentials, secret_name, secret_value, secretsmanager_client
):
    @flow
    async def test_flow():
        return await create_secret(
            secret_name=secret_name,
            secret_value=secret_value,
            aws_credentials=aws_credentials,
        )

    flow_state = await test_flow()
    assert flow_state.get("Name") == secret_name

    updated_secret = secretsmanager_client.get_secret_value(SecretId=secret_name)
    assert (
        updated_secret.get("SecretString") == secret_value
        or updated_secret.get("SecretBinary") == secret_value
    )


@pytest.mark.parametrize(
    ["recovery_window_in_days", "force_delete_without_recovery"],
    [
        [30, False],
        [20, False],
        [7, False],
        [8, False],
        [10, False],
        [15, True],
        [29, True],
    ],
)
async def test_delete_secret(
    aws_credentials,
    secret_under_test,
    recovery_window_in_days,
    force_delete_without_recovery,
):
    @flow
    async def test_flow():
        return await delete_secret(
            secret_name=secret_under_test["secret_name"],
            aws_credentials=aws_credentials,
            recovery_window_in_days=recovery_window_in_days,
            force_delete_without_recovery=force_delete_without_recovery,
        )

    result = await test_flow()
    if not force_delete_without_recovery and not 7 <= recovery_window_in_days <= 30:
        with pytest.raises(ValueError):
            result.get()
    else:
        assert result.get("Name") == secret_under_test["secret_name"]
        deletion_date = result.get("DeletionDate")

        if not force_delete_without_recovery:
            assert deletion_date.date() == (
                datetime.utcnow().date() + timedelta(days=recovery_window_in_days)
            )
        else:
            assert deletion_date.date() == datetime.utcnow().date()


class TestAwsSecret:
    @pytest.fixture
    def aws_secret(self, aws_credentials, secretsmanager_client):
        yield AwsSecret(aws_credentials=aws_credentials, secret_name="my-test")

    def test_roundtrip_read_write_delete(self, aws_secret):
        arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret"
        assert aws_secret.write_secret("my-secret").startswith(arn)
        assert aws_secret.read_secret() == b"my-secret"
        assert aws_secret.write_secret("my-updated-secret").startswith(arn)
        assert aws_secret.read_secret() == b"my-updated-secret"
        assert aws_secret.delete_secret().startswith(arn)

    def test_read_secret_version_id(self, aws_secret: AwsSecret):
        client = aws_secret.aws_credentials.get_secrets_manager_client()
        client.create_secret(Name="my-test", SecretBinary="my-secret")
        response = client.update_secret(
            SecretId="my-test", SecretBinary="my-updated-secret"
        )
        assert (
            aws_secret.read_secret(version_id=response["VersionId"])
            == b"my-updated-secret"
        )

    def test_delete_secret_conflict(self, aws_secret: AwsSecret):
        with pytest.raises(ValueError, match="Cannot specify recovery window"):
            aws_secret.delete_secret(
                force_delete_without_recovery=True, recovery_window_in_days=10
            )

    def test_delete_secret_recovery_window(self, aws_secret: AwsSecret):
        with pytest.raises(
            ValueError, match="Recovery window must be between 7 and 30 days"
        ):
            aws_secret.delete_secret(recovery_window_in_days=42)

    async def test_read_secret(self, secret_under_test, aws_credentials):
        secret = AwsSecret(
            aws_credentials=aws_credentials,
            secret_name=secret_under_test["secret_name"],
        )
        assert await secret.read_secret() == secret_under_test["expected_value"]
