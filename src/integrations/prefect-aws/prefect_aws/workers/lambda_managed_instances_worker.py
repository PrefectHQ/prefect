"""
Prefect worker for executing flow runs on AWS Lambda Managed Instances.

Lambda Managed Instances allows running Lambda functions on EC2 instances with
full EC2 flexibility while maintaining Lambda's operational simplicity. This worker
creates Lambda functions configured to run on capacity providers, which manage
the underlying EC2 infrastructure.

Get started by creating a work pool:

```
$ prefect work-pool create --type lambda-managed-instances my-lambda-pool
```

Then, you can start a worker for the pool:

```
$ prefect worker start --pool my-lambda-pool
```

Requirements:
- A Lambda capacity provider configured with VPC and instance settings
- An IAM role for the Lambda functions (execution role)
- A deployment package (code) for running Prefect flows (can use container image)

The worker will:
1. Create a Lambda function (or update existing) with the capacity provider
2. Publish a function version to deploy to managed instances
3. Invoke the function synchronously to run the flow
4. Monitor execution status and report results
"""

from __future__ import annotations

import base64
import json
import logging
import zipfile
from copy import deepcopy
from io import BytesIO
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, cast
from uuid import UUID

import anyio
import anyio.abc
from pydantic import BaseModel, Field, model_validator
from slugify import slugify
from typing_extensions import Self

from prefect.client.schemas.objects import FlowRun
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
    BaseWorkerResult,
)
from prefect_aws.credentials import AwsCredentials
from prefect_aws.lambda_managed_instances_api import (
    LambdaManagedInstancesClient,
    LambdaManagedInstancesError,
)

if TYPE_CHECKING:
    from mypy_boto3_lambda import LambdaClient

    from prefect.client.schemas.objects import APIFlow, DeploymentResponse, WorkPool


LAMBDA_DEFAULT_MEMORY_MB = 2048  # Lambda MI requires minimum 2048 MB
LAMBDA_DEFAULT_TIMEOUT_SECONDS = 900  # 15 minutes max
LAMBDA_DEFAULT_EXECUTION_ENV_MEMORY_GB_PER_VCPU = 2.0
LAMBDA_DEFAULT_PER_EXECUTION_ENV_MAX_CONCURRENCY = 1
LAMBDA_DEFAULT_FUNCTION_PREFIX = "prefect-flow-"
LAMBDA_DEFAULT_HANDLER = "prefect_lambda_handler.handler"

# Create function retry settings
MAX_CREATE_FUNCTION_ATTEMPTS = 3
CREATE_FUNCTION_MIN_DELAY_SECONDS = 1
CREATE_FUNCTION_MIN_DELAY_JITTER_SECONDS = 0
CREATE_FUNCTION_MAX_DELAY_JITTER_SECONDS = 3

# Function definition cache to avoid re-creating functions
_FUNCTION_CACHE: dict[UUID, str] = {}
_TAG_REGEX = r"[^a-zA-Z0-9_./=+:@-]"


class LambdaManagedInstancesIdentifier(NamedTuple):
    """
    The identifier for a Lambda function invocation.
    """

    function_arn: str
    request_id: str


# No templates needed - function configuration is built dynamically
# based on job configuration fields


def _drop_empty_keys_from_dict(d: dict) -> None:
    """
    Recursively drop keys with 'empty' values from a dict.
    Mutates the dict in place.
    """
    for key, value in tuple(d.items()):
        if value is None or value == "" or value == []:
            d.pop(key)
        elif isinstance(value, dict):
            _drop_empty_keys_from_dict(value)
        elif isinstance(value, list):
            for v in value:
                if isinstance(v, dict):
                    _drop_empty_keys_from_dict(v)


def parse_identifier(identifier: str) -> LambdaManagedInstancesIdentifier:
    """
    Splits identifier into function ARN and request ID.
    Input: "function_arn::request_id" outputs ("function_arn", "request_id")
    """
    parts = identifier.split("::", maxsplit=1)
    if len(parts) != 2:
        raise ValueError(f"Invalid identifier format: {identifier}")
    return LambdaManagedInstancesIdentifier(parts[0], parts[1])


def mask_sensitive_env_values(
    env: dict, values: list[str], keep_length: int = 3, replace_with: str = "***"
) -> dict:
    """Mask sensitive environment variable values."""
    masked = deepcopy(env)
    for key, value in masked.items():
        if key in values and value and len(value) > keep_length:
            masked[key] = value[:keep_length] + replace_with
    return masked


def mask_api_key(env: dict) -> dict:
    """Mask API key and auth string in environment variables."""
    return mask_sensitive_env_values(
        env,
        ["PREFECT_API_KEY", "PREFECT_API_AUTH_STRING"],
        keep_length=6,
    )


class InstanceRequirements(BaseModel):
    """Instance requirements for the capacity provider."""

    AllowedInstanceTypes: list[str] | None = Field(
        default=None,
        description="List of allowed EC2 instance types (e.g., ['m5.large', 'c5.xlarge'])",
    )
    ExcludedInstanceTypes: list[str] | None = Field(
        default=None,
        description="List of excluded EC2 instance types",
    )
    Architectures: list[Literal["x86_64", "arm64"]] | None = Field(
        default=None,
        description="List of CPU architectures to use",
    )


class ScalingPolicy(BaseModel):
    """Scaling policy for the capacity provider."""

    PredefinedMetricType: str = Field(
        default="LambdaProvisionedConcurrencyUtilization",
        description="The predefined metric type for scaling",
    )
    TargetValue: float = Field(
        default=0.7,
        description="The target value for the metric",
    )


class CapacityProviderScalingConfig(BaseModel):
    """Scaling configuration for the capacity provider."""

    MaxVCpuCount: int | None = Field(
        default=None,
        description="Maximum vCPU count for the capacity provider",
    )
    ScalingMode: Literal["STANDARD", "RESPONSIVE"] | None = Field(
        default=None,
        description="The scaling mode for the capacity provider",
    )
    ScalingPolicies: list[ScalingPolicy] | None = Field(
        default=None,
        description="List of scaling policies",
    )


class LambdaManagedInstancesJobConfiguration(BaseJobConfiguration):
    """
    Job configuration for a Lambda Managed Instances worker.
    """

    aws_credentials: AwsCredentials | None = Field(default_factory=AwsCredentials)

    # Capacity Provider settings
    capacity_provider_arn: str | None = Field(
        default=None,
        description=(
            "The ARN of an existing Lambda capacity provider. If not provided, "
            "you must provide capacity_provider_name to create one."
        ),
    )

    # Core function settings
    execution_role_arn: str = Field(
        title="Execution Role ARN",
        description=(
            "The ARN of the IAM role that Lambda assumes when it executes your function. "
            "This role must have permissions to run the function and access required resources."
        ),
    )

    runtime: str | None = Field(
        default=None,
        description=(
            "The Lambda runtime to use (e.g., 'python3.12'). "
            "If using a container image, set this to None."
        ),
    )

    handler: str = Field(
        default=LAMBDA_DEFAULT_HANDLER,
        description="The function handler (e.g., 'module.function')",
    )

    image_uri: str | None = Field(
        default=None,
        description=(
            "The URI of a container image in ECR to use for the function. "
            "If provided, runtime and handler are ignored. This is the recommended "
            "approach for running Prefect flows."
        ),
    )

    memory: int = Field(
        default=LAMBDA_DEFAULT_MEMORY_MB,
        description="The amount of memory available to the function (in MB). Lambda MI requires minimum 2048 MB.",
        ge=2048,
        le=10240,
    )

    timeout: int = Field(
        default=LAMBDA_DEFAULT_TIMEOUT_SECONDS,
        description="The function timeout in seconds",
        ge=1,
        le=900,
    )

    # Lambda Managed Instances specific settings
    execution_env_memory_gb_per_vcpu: float = Field(
        default=LAMBDA_DEFAULT_EXECUTION_ENV_MEMORY_GB_PER_VCPU,
        description=(
            "Memory allocation per vCPU for the execution environment. "
            "Higher values provide more memory relative to compute."
        ),
    )

    per_execution_env_max_concurrency: int = Field(
        default=LAMBDA_DEFAULT_PER_EXECUTION_ENV_MAX_CONCURRENCY,
        description=(
            "Maximum concurrent executions per execution environment. "
            "Lambda Managed Instances supports multiple concurrent invocations "
            "per environment, unlike standard Lambda."
        ),
        ge=1,
    )

    # VPC configuration (for Lambda networking)
    vpc_config: dict[str, Any] | None = Field(
        default=None,
        description=(
            "VPC configuration for the Lambda function. Include SubnetIds and "
            "SecurityGroupIds if the function needs VPC access."
        ),
    )

    # AWS Secrets Manager integration for API keys
    prefect_api_key_secret_arn: str | None = Field(
        default=None,
        description=(
            "ARN of an AWS Secrets Manager secret containing the Prefect API key. "
            "If provided, the key will be retrieved at runtime instead of being "
            "passed via environment variables."
        ),
    )

    prefect_api_auth_string_secret_arn: str | None = Field(
        default=None,
        description=(
            "ARN of an AWS Secrets Manager secret containing the Prefect API auth string."
        ),
    )

    # Optional code package for non-container deployments
    code_s3_bucket: str | None = Field(
        default=None,
        description="S3 bucket containing the Lambda deployment package",
    )

    code_s3_key: str | None = Field(
        default=None,
        description="S3 key for the Lambda deployment package",
    )

    @classmethod
    def json_template(cls) -> dict[str, Any]:
        """Returns a dict with job configuration as keys and templates as values."""
        configuration: dict[str, Any] = {}
        properties = cls.model_json_schema()["properties"]
        for k, v in properties.items():
            if v.get("template") is not None:
                template = v["template"]
            else:
                template = "{{ " + k + " }}"
            configuration[k] = template
        return configuration

    def prepare_for_flow_run(
        self,
        flow_run: "FlowRun",
        deployment: "DeploymentResponse | None" = None,
        flow: "APIFlow | None" = None,
        work_pool: "WorkPool | None" = None,
        worker_name: str | None = None,
    ) -> None:
        super().prepare_for_flow_run(flow_run, deployment, flow, work_pool, worker_name)
        if self.prefect_api_key_secret_arn:
            # Remove the PREFECT_API_KEY from env - it will be retrieved from secrets
            self.env.pop("PREFECT_API_KEY", None)
        if self.prefect_api_auth_string_secret_arn:
            self.env.pop("PREFECT_API_AUTH_STRING", None)

    @model_validator(mode="after")
    def validate_code_source(self) -> Self:
        """Ensure either image_uri or code location is provided."""
        if not self.image_uri and not (self.code_s3_bucket and self.code_s3_key):
            if not self.runtime:
                raise ValueError(
                    "Either image_uri (recommended) or runtime with code_s3_bucket "
                    "and code_s3_key must be provided."
                )
        return self

    @model_validator(mode="after")
    def validate_capacity_provider(self) -> Self:
        """Ensure capacity provider is configured."""
        if not self.capacity_provider_arn:
            raise ValueError(
                "capacity_provider_arn is required for Lambda Managed Instances. "
                "Create a capacity provider in the Lambda console or via the API first."
            )
        return self


class LambdaManagedInstancesVariables(BaseVariables):
    """
    Variables for templating a Lambda Managed Instances job.
    """

    env: dict[str, str | None] = Field(
        title="Environment Variables",
        default_factory=dict,
        description=(
            "Environment variables to provide to the Lambda function. "
            "These are set on the function at creation time."
        ),
    )

    aws_credentials: AwsCredentials = Field(
        title="AWS Credentials",
        default_factory=AwsCredentials,
        description=(
            "The AWS credentials to use to connect to Lambda. If not provided, "
            "credentials will be inferred from the local environment."
        ),
    )

    capacity_provider_arn: str = Field(
        title="Capacity Provider ARN",
        description=(
            "The ARN of the Lambda capacity provider to use. This must be created "
            "before using this worker type."
        ),
    )

    execution_role_arn: str = Field(
        title="Execution Role ARN",
        description=(
            "The ARN of the IAM role that Lambda assumes when executing functions."
        ),
    )

    image_uri: str | None = Field(
        default=None,
        description=(
            "The URI of a container image in ECR. This is the recommended approach "
            "for Prefect flows. The image should include Prefect and flow dependencies."
        ),
    )

    runtime: str | None = Field(
        default=None,
        description=(
            "The Lambda runtime (e.g., 'python3.12'). Not needed if using image_uri."
        ),
    )

    handler: str = Field(
        default=LAMBDA_DEFAULT_HANDLER,
        description="The function handler entry point.",
    )

    memory: int = Field(
        default=LAMBDA_DEFAULT_MEMORY_MB,
        description="Memory for the function in MB (128-10240).",
    )

    timeout: int = Field(
        default=LAMBDA_DEFAULT_TIMEOUT_SECONDS,
        description="Function timeout in seconds (1-900).",
    )

    execution_env_memory_gb_per_vcpu: float = Field(
        default=LAMBDA_DEFAULT_EXECUTION_ENV_MEMORY_GB_PER_VCPU,
        description="Memory per vCPU for managed instances.",
    )

    per_execution_env_max_concurrency: int = Field(
        default=LAMBDA_DEFAULT_PER_EXECUTION_ENV_MAX_CONCURRENCY,
        description="Max concurrent invocations per execution environment.",
    )

    vpc_config: dict[str, Any] | None = Field(
        default=None,
        description="VPC configuration (SubnetIds, SecurityGroupIds).",
    )

    prefect_api_key_secret_arn: str | None = Field(
        default=None,
        description="Secrets Manager ARN for Prefect API key.",
    )

    prefect_api_auth_string_secret_arn: str | None = Field(
        default=None,
        description="Secrets Manager ARN for Prefect API auth string.",
    )

    code_s3_bucket: str | None = Field(
        default=None,
        description="S3 bucket for deployment package (if not using container image).",
    )

    code_s3_key: str | None = Field(
        default=None,
        description="S3 key for deployment package (if not using container image).",
    )


class LambdaManagedInstancesWorkerResult(BaseWorkerResult):
    """
    The result of a Lambda Managed Instances job.
    """


class LambdaManagedInstancesWorker(
    BaseWorker[
        LambdaManagedInstancesJobConfiguration,
        LambdaManagedInstancesVariables,
        LambdaManagedInstancesWorkerResult,
    ]
):
    """
    A Prefect worker to run flow runs on AWS Lambda Managed Instances.

    Lambda Managed Instances provides EC2-like compute with Lambda's operational
    simplicity. Functions run on your EC2 instances with AWS handling provisioning,
    scaling, and management.
    """

    type: str = "lambda-managed-instances"
    job_configuration: type[LambdaManagedInstancesJobConfiguration] = (
        LambdaManagedInstancesJobConfiguration
    )
    job_configuration_variables: type[LambdaManagedInstancesVariables] | None = (
        LambdaManagedInstancesVariables
    )
    _description: str = (
        "Execute flow runs on AWS Lambda Managed Instances. Provides EC2 compute "
        "power with Lambda's serverless experience. Requires a capacity provider "
        "and ECR container image."
    )
    _display_name = "AWS Lambda Managed Instances"
    _documentation_url = "https://docs.prefect.io/integrations/prefect-aws/"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/d74b16fe84ce626345adf235a47008fea2869a60-225x225.png"  # noqa

    async def run(
        self,
        flow_run: "FlowRun",
        configuration: LambdaManagedInstancesJobConfiguration,
        task_status: anyio.abc.TaskStatus | None = None,
    ) -> LambdaManagedInstancesWorkerResult:
        """
        Runs a given flow run on Lambda Managed Instances.
        """
        # Get boto3 session for the raw API client
        boto_session = await run_sync_in_worker_thread(
            configuration.aws_credentials.get_boto3_session
        )
        region = configuration.aws_credentials.region_name or "us-east-1"

        # Create raw API client (supports CapacityProviderConfig)
        mi_client = LambdaManagedInstancesClient(boto_session, region_name=region)

        # Also get boto3 client for operations that don't need CapacityProviderConfig
        lambda_client = await run_sync_in_worker_thread(
            configuration.aws_credentials.get_client, "lambda"
        )

        logger = cast(logging.Logger, self.get_flow_run_logger(flow_run))

        # Create or update the Lambda function
        function_arn, version_arn = await run_sync_in_worker_thread(
            self._prepare_and_create_function,
            logger,
            mi_client,
            lambda_client,
            configuration,
            flow_run,
        )

        logger.info(f"Invoking Lambda function {function_arn} (version: {version_arn})")

        # Invoke the function and wait for result
        # For Lambda Managed Instances, we use synchronous invocation
        response = await run_sync_in_worker_thread(
            self._invoke_function,
            mi_client,
            version_arn,
            configuration,
            flow_run,
        )

        request_id = response.get("ResponseMetadata", {}).get("RequestId", "unknown")
        identifier = f"{function_arn}::{request_id}"

        if task_status:
            task_status.started(identifier)

        # Check for function errors
        function_error = response.get("FunctionError")
        status_code = 0 if not function_error else 1

        if function_error:
            payload = response.get("Payload")
            if payload:
                if isinstance(payload, bytes):
                    error_body = payload.decode("utf-8")
                else:
                    error_body = payload.read().decode("utf-8")
                logger.error(f"Lambda function error: {function_error}\n{error_body}")
            else:
                logger.error(f"Lambda function error: {function_error}")

        # Get logs if available
        if log_result := response.get("LogResult"):
            logs = base64.b64decode(log_result).decode("utf-8")
            logger.debug(f"Lambda logs:\n{logs}")

        return LambdaManagedInstancesWorkerResult(
            identifier=identifier,
            status_code=status_code,
        )

    def _get_or_generate_function_name(
        self, configuration: LambdaManagedInstancesJobConfiguration, flow_run: FlowRun
    ) -> str:
        """Generate a unique function name for the flow run."""
        if flow_run.deployment_id:
            base_name = f"{LAMBDA_DEFAULT_FUNCTION_PREFIX}{flow_run.deployment_id}"
        else:
            base_name = f"{LAMBDA_DEFAULT_FUNCTION_PREFIX}{flow_run.flow_id}"

        # Lambda function names: 1-64 chars, [a-zA-Z0-9-_]
        sanitized = slugify(
            base_name,
            max_length=64,
            regex_pattern=r"[^a-zA-Z0-9-_]+",
        )
        return sanitized

    def _prepare_and_create_function(
        self,
        logger: logging.Logger,
        mi_client: LambdaManagedInstancesClient,
        lambda_client: "LambdaClient",
        configuration: LambdaManagedInstancesJobConfiguration,
        flow_run: FlowRun,
    ) -> tuple[str, str]:
        """
        Create or update a Lambda function and publish a version.

        Returns a tuple of:
        - The function ARN
        - The published version ARN
        """
        function_name = self._get_or_generate_function_name(configuration, flow_run)

        # Check if function exists using raw API (to handle both old and new functions)
        try:
            existing_function = mi_client.get_function(function_name)
            function_arn = existing_function["Configuration"]["FunctionArn"]
            logger.info(f"Found existing Lambda function {function_name}")

            # Update the function configuration if needed (can use boto3 for this)
            self._update_function_configuration(
                logger, lambda_client, function_name, configuration, flow_run
            )

        except LambdaManagedInstancesError as e:
            if e.status_code == 404:
                # Create new function using raw API (supports CapacityProviderConfig)
                logger.info(f"Creating new Lambda function {function_name}")
                function_arn = self._create_function(
                    logger, mi_client, function_name, configuration, flow_run
                )
            else:
                raise

        # Publish a new version to deploy to managed instances
        logger.info(f"Publishing new version for {function_name}")
        version_response = mi_client.publish_version(
            function_name=function_name,
            description=f"Prefect flow run {flow_run.id}",
        )
        version_arn = version_response["FunctionArn"]
        version = version_response["Version"]
        logger.info(f"Published version {version} ({version_arn})")

        # Cache the function for future use
        if flow_run.deployment_id:
            _FUNCTION_CACHE[flow_run.deployment_id] = function_arn
        else:
            _FUNCTION_CACHE[flow_run.flow_id] = function_arn

        return function_arn, version_arn

    def _create_function(
        self,
        logger: logging.Logger,
        mi_client: LambdaManagedInstancesClient,
        function_name: str,
        configuration: LambdaManagedInstancesJobConfiguration,
        flow_run: FlowRun,
    ) -> str:
        """Create a new Lambda function using raw API (supports CapacityProviderConfig)."""
        # Set code source
        if configuration.image_uri:
            code = {"ImageUri": configuration.image_uri}
            package_type = "Image"
        else:
            package_type = "Zip"
            if configuration.code_s3_bucket and configuration.code_s3_key:
                code = {
                    "S3Bucket": configuration.code_s3_bucket,
                    "S3Key": configuration.code_s3_key,
                }
            else:
                # Create a minimal deployment package (placeholder)
                # Note: Raw API requires base64 encoding for ZipFile
                import base64

                zip_bytes = self._create_minimal_deployment_package()
                code = {"ZipFile": base64.b64encode(zip_bytes).decode("utf-8")}

        # Set tags
        tags = {
            "prefect.io/flow-run-id": str(flow_run.id),
            "prefect.io/flow-id": str(flow_run.flow_id),
            "prefect.io/managed-by": "prefect",
        }
        if flow_run.deployment_id:
            tags["prefect.io/deployment-id"] = str(flow_run.deployment_id)
        tags.update(configuration.labels)

        # Sanitize tags
        sanitized_tags = {}
        for k, v in tags.items():
            sanitized_k = slugify(
                k, regex_pattern=_TAG_REGEX, allow_unicode=True, lowercase=False
            )
            sanitized_v = slugify(
                str(v), regex_pattern=_TAG_REGEX, allow_unicode=True, lowercase=False
            )
            sanitized_tags[sanitized_k] = sanitized_v

        # Filter None values from env
        env_vars = {k: v for k, v in configuration.env.items() if v is not None}

        logger.debug(
            f"Creating function {function_name} with capacity provider {configuration.capacity_provider_arn}"
        )

        response = mi_client.create_function(
            function_name=function_name,
            role=configuration.execution_role_arn,
            code=code,
            capacity_provider_arn=configuration.capacity_provider_arn,
            execution_env_memory_gb_per_vcpu=configuration.execution_env_memory_gb_per_vcpu,
            per_execution_env_max_concurrency=configuration.per_execution_env_max_concurrency,
            timeout=configuration.timeout,
            memory_size=configuration.memory,
            handler=configuration.handler if package_type == "Zip" else None,
            runtime=configuration.runtime if package_type == "Zip" else None,
            package_type=package_type,
            environment=env_vars if env_vars else None,
            vpc_config=configuration.vpc_config,
            tags=sanitized_tags,
        )

        function_arn = response["FunctionArn"]
        logger.info(f"Created function {function_name} ({function_arn})")

        # Wait for function to be active (poll using raw API)
        import time

        for _ in range(60):  # Wait up to 60 seconds
            fn_response = mi_client.get_function(function_name)
            state = fn_response.get("Configuration", {}).get("State")
            if state == "Active":
                break
            elif state == "Failed":
                raise RuntimeError(f"Function creation failed: {fn_response}")
            time.sleep(1)
        else:
            logger.warning("Timed out waiting for function to become active")

        return function_arn

    def _update_function_configuration(
        self,
        logger: logging.Logger,
        lambda_client: "LambdaClient",
        function_name: str,
        configuration: LambdaManagedInstancesJobConfiguration,
        flow_run: FlowRun,
    ) -> None:
        """Update an existing Lambda function's configuration."""
        update_params: dict[str, Any] = {
            "FunctionName": function_name,
            "Timeout": configuration.timeout,
            "MemorySize": configuration.memory,
        }

        # Update environment variables
        if configuration.env:
            update_params["Environment"] = {"Variables": configuration.env}

        # Update VPC config if provided
        if configuration.vpc_config:
            update_params["VpcConfig"] = configuration.vpc_config

        logger.debug(
            f"Updating function configuration: {json.dumps(update_params, indent=2, default=str)}"
        )

        lambda_client.update_function_configuration(**update_params)

        # Wait for update to complete
        waiter = lambda_client.get_waiter("function_updated")
        waiter.wait(FunctionName=function_name)

        # Update code if using container image
        if configuration.image_uri:
            logger.debug(
                f"Updating function code with image: {configuration.image_uri}"
            )
            lambda_client.update_function_code(
                FunctionName=function_name,
                ImageUri=configuration.image_uri,
            )
            # Wait for code update
            waiter = lambda_client.get_waiter("function_updated")
            waiter.wait(FunctionName=function_name)

    def _invoke_function(
        self,
        mi_client: LambdaManagedInstancesClient,
        function_arn: str,
        configuration: LambdaManagedInstancesJobConfiguration,
        flow_run: FlowRun,
    ) -> dict[str, Any]:
        """Invoke the Lambda function using raw API."""
        # The payload contains information for the flow run
        payload = {
            "flow_run_id": str(flow_run.id),
            "prefect_command": configuration.command or "python -m prefect.engine",
        }

        # Note: Lambda Managed Instances doesn't support LogType: Tail
        # Logs must be retrieved from CloudWatch separately
        return mi_client.invoke_function(
            function_name=function_arn,
            payload=payload,
            invocation_type="RequestResponse",  # Synchronous
            log_type="None",  # Lambda MI doesn't support Tail logs
        )

    def _create_minimal_deployment_package(self) -> bytes:
        """
        Create a minimal deployment package for Lambda.
        This is used as a placeholder when no code is provided.
        The actual execution should use a container image.
        """
        handler_code = '''
import subprocess
import sys
import os
import json

def handler(event, context):
    """
    Prefect Lambda handler for running flow runs.

    The event should contain:
    - flow_run_id: The ID of the flow run to execute
    - prefect_command: The command to run (default: python -m prefect.engine)
    """
    flow_run_id = event.get("flow_run_id")
    command = event.get("prefect_command", "python -m prefect.engine")

    if not flow_run_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "flow_run_id is required"})
        }

    # Set the flow run ID for the engine
    os.environ["PREFECT__FLOW_RUN_ID"] = flow_run_id

    # Run the Prefect engine
    result = subprocess.run(
        command.split(),
        capture_output=True,
        text=True,
    )

    return {
        "statusCode": 0 if result.returncode == 0 else 1,
        "body": json.dumps({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        })
    }
'''

        # Create in-memory zip file
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("prefect_lambda_handler.py", handler_code)
        buffer.seek(0)
        return buffer.read()
