from datetime import timedelta

import boto3
import pytest
from moto import mock_secretsmanager
from prefect_aws.secrets_manager import (
    AwsSecret,
    create_secret,
    delete_secret,
)

from prefect import flow
from prefect.types import DateTime


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


class TestAwsSecretSync:
    """Test synchronous AwsSecret methods"""

    async def test_read_secret(self, secret_under_test, aws_credentials):
        expected_value = secret_under_test.pop("expected_value")
        secret_name = secret_under_test.pop(
            "secret_name"
        )  # Remove secret_name from kwargs

        @flow
        async def test_flow():
            secret = AwsSecret(
                aws_credentials=aws_credentials,
                secret_name=secret_name,  # Use for AwsSecret initialization
            )
            # Pass remaining kwargs (version_id, version_stage) if present
            return await secret.read_secret(**secret_under_test)

        assert (await test_flow()) == expected_value

    async def test_write_secret(self, aws_credentials, secretsmanager_client):
        secret = AwsSecret(aws_credentials=aws_credentials, secret_name="my-test")
        secret_value = b"test-secret-value"

        @flow
        async def test_flow():
            return await secret.write_secret(secret_value)

        arn = await test_flow()
        assert arn.startswith("arn:aws:secretsmanager")

        # Verify the secret was written correctly
        response = secretsmanager_client.get_secret_value(SecretId="my-test")
        assert response["SecretBinary"] == secret_value

    async def test_delete_secret(self, aws_credentials, secretsmanager_client):
        # First create a secret to delete
        secret = AwsSecret(aws_credentials=aws_credentials, secret_name="test-delete")
        secret_value = b"delete-me"

        @flow
        async def setup_flow():
            return await secret.write_secret(secret_value)

        arn = await setup_flow()

        # Now test deletion
        @flow
        async def test_flow():
            return await secret.delete_secret(
                recovery_window_in_days=7, force_delete_without_recovery=False
            )

        deleted_arn = await test_flow()
        assert deleted_arn == arn

        # Verify the secret is scheduled for deletion
        with pytest.raises(secretsmanager_client.exceptions.InvalidRequestException):
            secretsmanager_client.get_secret_value(SecretId="test-delete")

    async def test_delete_secret_validation(self, aws_credentials):
        secret = AwsSecret(
            aws_credentials=aws_credentials, secret_name="test-validation"
        )

        with pytest.raises(ValueError, match="Cannot specify recovery window"):
            await secret.delete_secret(
                force_delete_without_recovery=True, recovery_window_in_days=10
            )

        with pytest.raises(
            ValueError, match="Recovery window must be between 7 and 30 days"
        ):
            await secret.delete_secret(recovery_window_in_days=42)


class TestAwsSecretAsync:
    """Test asynchronous AwsSecret methods"""

    async def test_read_secret(self, secret_under_test, aws_credentials):
        expected_value = secret_under_test.pop("expected_value")
        secret_name = secret_under_test.pop(
            "secret_name"
        )  # Remove secret_name from kwargs

        @flow
        async def test_flow():
            secret = AwsSecret(
                aws_credentials=aws_credentials,
                secret_name=secret_name,  # Use for AwsSecret initialization
            )
            # Pass remaining kwargs (version_id, version_stage) if present
            return await secret.aread_secret(**secret_under_test)

        assert (await test_flow()) == expected_value

    async def test_write_secret(self, aws_credentials, secretsmanager_client):
        secret = AwsSecret(aws_credentials=aws_credentials, secret_name="my-test")
        secret_value = b"test-secret-value"

        @flow
        async def test_flow():
            return await secret.awrite_secret(secret_value)

        arn = await test_flow()
        assert arn.startswith("arn:aws:secretsmanager")

        # Verify the secret was written correctly
        response = secretsmanager_client.get_secret_value(SecretId="my-test")
        assert response["SecretBinary"] == secret_value

    async def test_delete_secret(self, aws_credentials, secretsmanager_client):
        # First create a secret to delete
        secret = AwsSecret(aws_credentials=aws_credentials, secret_name="test-delete")
        secret_value = b"delete-me"

        @flow
        async def setup_flow():
            return await secret.awrite_secret(secret_value)

        arn = await setup_flow()

        # Now test deletion
        @flow
        async def test_flow():
            return await secret.adelete_secret(
                recovery_window_in_days=7, force_delete_without_recovery=False
            )

        deleted_arn = await test_flow()
        assert deleted_arn == arn

        # Verify the secret is scheduled for deletion
        with pytest.raises(secretsmanager_client.exceptions.InvalidRequestException):
            secretsmanager_client.get_secret_value(SecretId="test-delete")

    async def test_delete_secret_validation(self, aws_credentials):
        secret = AwsSecret(
            aws_credentials=aws_credentials, secret_name="test-validation"
        )

        with pytest.raises(ValueError, match="Cannot specify recovery window"):
            await secret.adelete_secret(
                force_delete_without_recovery=True, recovery_window_in_days=10
            )

        with pytest.raises(
            ValueError, match="Recovery window must be between 7 and 30 days"
        ):
            await secret.adelete_secret(recovery_window_in_days=42)


# Keep existing task-based tests
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
async def test_delete_secret_task(
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
                DateTime.now("UTC").date() + timedelta(days=recovery_window_in_days)
            )
        else:
            assert deletion_date.date() == DateTime.now("UTC").date()
