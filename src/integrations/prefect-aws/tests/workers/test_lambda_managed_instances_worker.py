"""Tests for the Lambda Managed Instances worker."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from prefect_aws.credentials import AwsCredentials
from prefect_aws.lambda_managed_instances_api import LambdaManagedInstancesError
from prefect_aws.workers.lambda_managed_instances_worker import (
    _FUNCTION_CACHE,
    LAMBDA_DEFAULT_HANDLER,
    LAMBDA_DEFAULT_MEMORY_MB,
    LAMBDA_DEFAULT_TIMEOUT_SECONDS,
    LambdaManagedInstancesJobConfiguration,
    LambdaManagedInstancesVariables,
    LambdaManagedInstancesWorker,
    LambdaManagedInstancesWorkerResult,
    mask_api_key,
    parse_identifier,
)
from pydantic import ValidationError

from prefect.client.schemas.objects import FlowRun


@pytest.fixture
def flow_run():
    return FlowRun(flow_id=uuid4(), deployment_id=uuid4())


@pytest.fixture
def flow_run_no_deployment():
    return FlowRun(flow_id=uuid4())


@pytest.fixture(autouse=True)
def reset_function_cache():
    _FUNCTION_CACHE.clear()
    yield


@pytest.fixture
def aws_credentials():
    return AwsCredentials(
        aws_access_key_id="test-access-key",
        aws_secret_access_key="test-secret-key",
        region_name="us-east-1",
    )


@pytest.fixture
def mock_lambda_client():
    """Create a mock Lambda client (boto3)."""
    client = MagicMock()

    # Mock get_function to raise ResourceNotFoundException (function doesn't exist)
    client.exceptions.ResourceNotFoundException = type(
        "ResourceNotFoundException", (Exception,), {}
    )

    # Mock successful create_function
    client.create_function.return_value = {
        "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function",
        "FunctionName": "test-function",
        "Runtime": "python3.12",
        "Handler": LAMBDA_DEFAULT_HANDLER,
    }

    # Mock publish_version
    client.publish_version.return_value = {
        "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function:1",
        "Version": "1",
    }

    # Mock invoke
    payload_response = MagicMock()
    payload_response.read.return_value = b'{"statusCode": 0}'
    client.invoke.return_value = {
        "StatusCode": 200,
        "ResponseMetadata": {"RequestId": "test-request-id"},
        "Payload": payload_response,
    }

    # Mock waiter
    waiter = MagicMock()
    client.get_waiter.return_value = waiter

    return client


@pytest.fixture
def mock_mi_client():
    """Create a mock LambdaManagedInstancesClient (raw API)."""
    client = MagicMock()

    # Mock get_function (returns 404 by default)
    client.get_function.side_effect = LambdaManagedInstancesError(
        status_code=404,
        error_type="ResourceNotFoundException",
        message="Function not found",
    )

    # Mock successful create_function
    client.create_function.return_value = {
        "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function",
        "FunctionName": "test-function",
        "Runtime": "python3.12",
        "Handler": LAMBDA_DEFAULT_HANDLER,
    }

    # Mock publish_version
    client.publish_version.return_value = {
        "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function:1",
        "Version": "1",
    }

    # Mock invoke_function
    client.invoke_function.return_value = {
        "StatusCode": 200,
        "ResponseMetadata": {"RequestId": "test-request-id"},
        "Payload": b'{"statusCode": 0}',
    }

    return client


class TestParseIdentifier:
    def test_valid_identifier(self):
        identifier = "arn:aws:lambda:us-east-1:123456789012:function:test::request-123"
        result = parse_identifier(identifier)
        assert (
            result.function_arn == "arn:aws:lambda:us-east-1:123456789012:function:test"
        )
        assert result.request_id == "request-123"

    def test_invalid_identifier_no_separator(self):
        with pytest.raises(ValueError, match="Invalid identifier format"):
            parse_identifier("no-separator-here")


class TestMaskSensitiveEnvValues:
    def test_mask_api_key(self):
        env = {
            "PREFECT_API_KEY": "test-key-12345",
            "OTHER_VAR": "value",
        }
        result = mask_api_key(env)
        assert result["PREFECT_API_KEY"] == "test-k***"
        assert result["OTHER_VAR"] == "value"

    def test_mask_multiple_values(self):
        env = {
            "PREFECT_API_KEY": "test-key-12345",
            "PREFECT_API_AUTH_STRING": "auth-string-12345",
            "NORMAL_VAR": "normal",
        }
        result = mask_api_key(env)
        assert result["PREFECT_API_KEY"] == "test-k***"
        assert result["PREFECT_API_AUTH_STRING"] == "auth-s***"
        assert result["NORMAL_VAR"] == "normal"

    def test_mask_short_value(self):
        env = {"PREFECT_API_KEY": "ab"}
        result = mask_api_key(env)
        # Short values should remain unchanged
        assert result["PREFECT_API_KEY"] == "ab"


class TestLambdaManagedInstancesJobConfiguration:
    def test_minimal_valid_configuration(self):
        config = LambdaManagedInstancesJobConfiguration(
            capacity_provider_arn="arn:aws:lambda:us-east-1:123456789012:capacity-provider:test",
            execution_role_arn="arn:aws:iam::123456789012:role/lambda-role",
            image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/my-image:latest",
        )
        assert config.capacity_provider_arn is not None
        assert config.execution_role_arn is not None
        assert config.image_uri is not None

    def test_requires_capacity_provider(self):
        with pytest.raises(ValidationError) as exc_info:
            LambdaManagedInstancesJobConfiguration(
                execution_role_arn="arn:aws:iam::123456789012:role/lambda-role",
                image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/my-image:latest",
            )
        assert "capacity_provider_arn" in str(exc_info.value)

    def test_requires_code_source(self):
        with pytest.raises(ValidationError) as exc_info:
            LambdaManagedInstancesJobConfiguration(
                capacity_provider_arn="arn:aws:lambda:us-east-1:123456789012:capacity-provider:test",
                execution_role_arn="arn:aws:iam::123456789012:role/lambda-role",
                # No image_uri and no runtime
            )
        assert "image_uri" in str(exc_info.value) or "runtime" in str(exc_info.value)

    def test_accepts_s3_code_with_runtime(self):
        config = LambdaManagedInstancesJobConfiguration(
            capacity_provider_arn="arn:aws:lambda:us-east-1:123456789012:capacity-provider:test",
            execution_role_arn="arn:aws:iam::123456789012:role/lambda-role",
            runtime="python3.12",
            code_s3_bucket="my-bucket",
            code_s3_key="my-code.zip",
        )
        assert config.runtime == "python3.12"
        assert config.code_s3_bucket == "my-bucket"
        assert config.code_s3_key == "my-code.zip"

    def test_default_values(self):
        config = LambdaManagedInstancesJobConfiguration(
            capacity_provider_arn="arn:aws:lambda:us-east-1:123456789012:capacity-provider:test",
            execution_role_arn="arn:aws:iam::123456789012:role/lambda-role",
            image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/my-image:latest",
        )
        assert config.memory == LAMBDA_DEFAULT_MEMORY_MB
        assert config.timeout == LAMBDA_DEFAULT_TIMEOUT_SECONDS
        assert config.handler == LAMBDA_DEFAULT_HANDLER

    def test_prepare_for_flow_run_removes_api_key_when_secret_provided(self):
        config = LambdaManagedInstancesJobConfiguration(
            capacity_provider_arn="arn:aws:lambda:us-east-1:123456789012:capacity-provider:test",
            execution_role_arn="arn:aws:iam::123456789012:role/lambda-role",
            image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/my-image:latest",
            prefect_api_key_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:api-key",
        )
        config.env = {"PREFECT_API_KEY": "test-key", "OTHER": "value"}

        flow_run = FlowRun(flow_id=uuid4())
        config.prepare_for_flow_run(flow_run)

        assert "PREFECT_API_KEY" not in config.env
        assert config.env.get("OTHER") == "value"


class TestLambdaManagedInstancesVariables:
    def test_default_values(self):
        vars = LambdaManagedInstancesVariables(
            capacity_provider_arn="arn:aws:lambda:us-east-1:123456789012:capacity-provider:test",
            execution_role_arn="arn:aws:iam::123456789012:role/lambda-role",
        )
        assert vars.memory == LAMBDA_DEFAULT_MEMORY_MB
        assert vars.timeout == LAMBDA_DEFAULT_TIMEOUT_SECONDS
        assert vars.handler == LAMBDA_DEFAULT_HANDLER

    def test_custom_values(self):
        vars = LambdaManagedInstancesVariables(
            capacity_provider_arn="arn:aws:lambda:us-east-1:123456789012:capacity-provider:test",
            execution_role_arn="arn:aws:iam::123456789012:role/lambda-role",
            memory=2048,
            timeout=600,
            per_execution_env_max_concurrency=5,
        )
        assert vars.memory == 2048
        assert vars.timeout == 600
        assert vars.per_execution_env_max_concurrency == 5


class TestLambdaManagedInstancesWorker:
    def test_worker_type(self):
        assert LambdaManagedInstancesWorker.type == "lambda-managed-instances"

    def test_get_default_base_job_template(self):
        template = LambdaManagedInstancesWorker.get_default_base_job_template()
        assert "job_configuration" in template
        assert "variables" in template

    @pytest.mark.usefixtures("aws_credentials")
    async def test_construct_configuration(self, aws_credentials):
        variables = LambdaManagedInstancesVariables(
            aws_credentials=aws_credentials,
            capacity_provider_arn="arn:aws:lambda:us-east-1:123456789012:capacity-provider:test",
            execution_role_arn="arn:aws:iam::123456789012:role/lambda-role",
            image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/my-image:latest",
        )

        configuration = await LambdaManagedInstancesJobConfiguration.from_template_and_values(
            base_job_template=LambdaManagedInstancesWorker.get_default_base_job_template(),
            values=variables.model_dump(exclude_none=True),
        )

        assert configuration.capacity_provider_arn == variables.capacity_provider_arn
        assert configuration.execution_role_arn == variables.execution_role_arn
        assert configuration.image_uri == variables.image_uri


class TestLambdaManagedInstancesWorkerRun:
    @pytest.fixture
    def configuration(self, aws_credentials):
        return LambdaManagedInstancesJobConfiguration(
            aws_credentials=aws_credentials,
            capacity_provider_arn="arn:aws:lambda:us-east-1:123456789012:capacity-provider:test",
            execution_role_arn="arn:aws:iam::123456789012:role/lambda-role",
            image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/my-image:latest",
            command="python -m prefect.engine",
        )

    @pytest.mark.asyncio
    async def test_run_creates_function_and_invokes(
        self, flow_run, configuration, mock_mi_client, mock_lambda_client
    ):
        # Setup mock_mi_client - function doesn't exist (default in fixture)
        # After create_function, get_function should succeed
        def get_function_side_effect(name):
            # First call raises 404, subsequent calls return the function
            if not hasattr(get_function_side_effect, "called"):
                get_function_side_effect.called = True
                raise LambdaManagedInstancesError(
                    status_code=404,
                    error_type="ResourceNotFoundException",
                    message="Function not found",
                )
            return {
                "Configuration": {
                    "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function",
                    "FunctionName": "test-function",
                    "State": "Active",
                }
            }

        mock_mi_client.get_function.side_effect = get_function_side_effect

        with (
            patch.object(
                configuration.aws_credentials,
                "get_boto3_session",
                return_value=MagicMock(),
            ),
            patch.object(
                configuration.aws_credentials,
                "get_client",
                return_value=mock_lambda_client,
            ),
            patch(
                "prefect_aws.workers.lambda_managed_instances_worker.LambdaManagedInstancesClient",
                return_value=mock_mi_client,
            ),
        ):
            async with LambdaManagedInstancesWorker(
                work_pool_name="test-pool"
            ) as worker:
                result = await worker.run(flow_run, configuration)

        assert isinstance(result, LambdaManagedInstancesWorkerResult)
        assert result.status_code == 0
        assert "test-request-id" in result.identifier

        # Verify create_function was called on raw API client
        mock_mi_client.create_function.assert_called_once()

        # Verify publish_version was called
        mock_mi_client.publish_version.assert_called_once()

        # Verify invoke_function was called
        mock_mi_client.invoke_function.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_updates_existing_function(
        self, flow_run, configuration, mock_mi_client, mock_lambda_client
    ):
        # Setup mock to simulate function exists
        mock_mi_client.get_function.side_effect = None
        mock_mi_client.get_function.return_value = {
            "Configuration": {
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test",
                "FunctionName": "test",
                "State": "Active",
            }
        }

        with (
            patch.object(
                configuration.aws_credentials,
                "get_boto3_session",
                return_value=MagicMock(),
            ),
            patch.object(
                configuration.aws_credentials,
                "get_client",
                return_value=mock_lambda_client,
            ),
            patch(
                "prefect_aws.workers.lambda_managed_instances_worker.LambdaManagedInstancesClient",
                return_value=mock_mi_client,
            ),
        ):
            async with LambdaManagedInstancesWorker(
                work_pool_name="test-pool"
            ) as worker:
                result = await worker.run(flow_run, configuration)

        assert isinstance(result, LambdaManagedInstancesWorkerResult)
        assert result.status_code == 0

        # Verify create_function was NOT called
        mock_mi_client.create_function.assert_not_called()

        # Verify update_function_configuration was called (via boto3 client)
        mock_lambda_client.update_function_configuration.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_handles_function_error(
        self, flow_run, configuration, mock_mi_client, mock_lambda_client
    ):
        # Setup mock - function doesn't exist, needs to be created
        def get_function_side_effect(name):
            if not hasattr(get_function_side_effect, "called"):
                get_function_side_effect.called = True
                raise LambdaManagedInstancesError(
                    status_code=404,
                    error_type="ResourceNotFoundException",
                    message="Function not found",
                )
            return {
                "Configuration": {
                    "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function",
                    "FunctionName": "test-function",
                    "State": "Active",
                }
            }

        mock_mi_client.get_function.side_effect = get_function_side_effect

        # Setup invoke to return an error
        mock_mi_client.invoke_function.return_value = {
            "StatusCode": 200,
            "FunctionError": "Unhandled",
            "ResponseMetadata": {"RequestId": "test-request-id"},
            "Payload": b'{"errorMessage": "Test error"}',
        }

        with (
            patch.object(
                configuration.aws_credentials,
                "get_boto3_session",
                return_value=MagicMock(),
            ),
            patch.object(
                configuration.aws_credentials,
                "get_client",
                return_value=mock_lambda_client,
            ),
            patch(
                "prefect_aws.workers.lambda_managed_instances_worker.LambdaManagedInstancesClient",
                return_value=mock_mi_client,
            ),
        ):
            async with LambdaManagedInstancesWorker(
                work_pool_name="test-pool"
            ) as worker:
                result = await worker.run(flow_run, configuration)

        assert result.status_code == 1  # Error status

    @pytest.mark.asyncio
    async def test_run_caches_function_arn(
        self, flow_run, configuration, mock_mi_client, mock_lambda_client
    ):
        def get_function_side_effect(name):
            if not hasattr(get_function_side_effect, "called"):
                get_function_side_effect.called = True
                raise LambdaManagedInstancesError(
                    status_code=404,
                    error_type="ResourceNotFoundException",
                    message="Function not found",
                )
            return {
                "Configuration": {
                    "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function",
                    "FunctionName": "test-function",
                    "State": "Active",
                }
            }

        mock_mi_client.get_function.side_effect = get_function_side_effect

        with (
            patch.object(
                configuration.aws_credentials,
                "get_boto3_session",
                return_value=MagicMock(),
            ),
            patch.object(
                configuration.aws_credentials,
                "get_client",
                return_value=mock_lambda_client,
            ),
            patch(
                "prefect_aws.workers.lambda_managed_instances_worker.LambdaManagedInstancesClient",
                return_value=mock_mi_client,
            ),
        ):
            async with LambdaManagedInstancesWorker(
                work_pool_name="test-pool"
            ) as worker:
                await worker.run(flow_run, configuration)

        # Verify function was cached
        assert flow_run.deployment_id in _FUNCTION_CACHE


class TestLambdaManagedInstancesWorkerResult:
    def test_status_code_zero_is_success(self):
        result = LambdaManagedInstancesWorkerResult(
            identifier="arn:aws:lambda:test::request-id",
            status_code=0,
        )
        # BaseWorkerResult returns True for status_code == 0
        assert result.status_code == 0

    def test_non_zero_status_code_is_failure(self):
        result = LambdaManagedInstancesWorkerResult(
            identifier="arn:aws:lambda:test::request-id",
            status_code=1,
        )
        assert result.status_code != 0
