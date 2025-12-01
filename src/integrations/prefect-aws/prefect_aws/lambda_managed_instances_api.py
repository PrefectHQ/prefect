"""
Raw API client for AWS Lambda Managed Instances.

This module provides direct access to the Lambda Managed Instances API
(version 2025-11-30) since boto3 doesn't have support yet.

The API endpoints for capacity providers are:
- POST /2025-11-30/capacity-providers (CreateCapacityProvider)
- GET /2025-11-30/capacity-providers (ListCapacityProviders)
- GET /2025-11-30/capacity-providers/{name} (GetCapacityProvider)
- DELETE /2025-11-30/capacity-providers/{name} (DeleteCapacityProvider)
- PUT /2025-11-30/capacity-providers/{name} (UpdateCapacityProvider)

This client also provides function creation with CapacityProviderConfig
which is not yet supported in boto3.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

if TYPE_CHECKING:
    from boto3 import Session


LAMBDA_MI_API_VERSION = "2025-11-30"
# Standard Lambda API version for function operations
LAMBDA_FUNCTIONS_API_VERSION = "2015-03-31"


class LambdaManagedInstancesClient:
    """
    Client for Lambda Managed Instances API operations.

    This provides access to capacity provider operations that aren't
    yet available in boto3.
    """

    def __init__(
        self,
        session: "Session",
        region_name: str = "us-east-1",
    ):
        self.session = session
        self.region_name = region_name
        self.endpoint = f"https://lambda.{region_name}.amazonaws.com"
        self.credentials = session.get_credentials()

    def _make_request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a signed request to the Lambda API."""
        url = f"{self.endpoint}/{LAMBDA_MI_API_VERSION}/{path}"

        headers = {
            "Content-Type": "application/json",
        }

        data = json.dumps(body) if body else None

        request = AWSRequest(
            method=method,
            url=url,
            data=data,
            headers=headers,
        )
        SigV4Auth(self.credentials, "lambda", self.region_name).add_auth(request)

        response = requests.request(
            method=method,
            url=url,
            headers=dict(request.headers),
            data=data,
        )

        if response.status_code >= 400:
            error_body = response.json() if response.text else {}
            raise LambdaManagedInstancesError(
                status_code=response.status_code,
                error_type=error_body.get("Type", "Unknown"),
                message=error_body.get("Message", response.text),
            )

        return response.json() if response.text else {}

    def list_capacity_providers(
        self,
        max_items: int | None = None,
        next_marker: str | None = None,
    ) -> dict[str, Any]:
        """
        List all capacity providers.

        Returns:
            dict with 'CapacityProviders' list and optional 'NextMarker'
        """
        params = []
        if max_items:
            params.append(f"MaxItems={max_items}")
        if next_marker:
            params.append(f"Marker={next_marker}")

        path = "capacity-providers"
        if params:
            path += "?" + "&".join(params)

        return self._make_request("GET", path)

    def get_capacity_provider(self, name: str) -> dict[str, Any]:
        """
        Get a specific capacity provider by name or ARN.

        Args:
            name: The capacity provider name or ARN

        Returns:
            The capacity provider configuration
        """
        return self._make_request("GET", f"capacity-providers/{name}")

    def create_capacity_provider(
        self,
        name: str,
        operator_role_arn: str,
        subnet_ids: list[str],
        security_group_ids: list[str],
        instance_profile_arn: str | None = None,
        allowed_instance_types: list[str] | None = None,
        excluded_instance_types: list[str] | None = None,
        architectures: list[str] | None = None,
        max_vcpu_count: int | None = None,
        scaling_mode: str | None = None,
        kms_key_arn: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new capacity provider.

        Args:
            name: Unique name for the capacity provider (1-140 chars)
            operator_role_arn: IAM role ARN for capacity provider operations
            subnet_ids: List of VPC subnet IDs
            security_group_ids: List of security group IDs
            instance_profile_arn: IAM instance profile ARN for EC2 instances
            allowed_instance_types: Optional list of allowed EC2 instance types
            excluded_instance_types: Optional list of excluded instance types
            architectures: Optional list of CPU architectures (x86_64, arm64)
            max_vcpu_count: Optional maximum vCPU count
            scaling_mode: Optional scaling mode (STANDARD, RESPONSIVE)
            kms_key_arn: Optional KMS key ARN for encryption
            tags: Optional tags for the capacity provider

        Returns:
            The created capacity provider configuration
        """
        permissions_config: dict[str, Any] = {
            "CapacityProviderOperatorRoleArn": operator_role_arn,
        }
        if instance_profile_arn:
            permissions_config["InstanceProfileArn"] = instance_profile_arn

        body: dict[str, Any] = {
            "CapacityProviderName": name,
            "PermissionsConfig": permissions_config,
            "VpcConfig": {
                "SubnetIds": subnet_ids,
                "SecurityGroupIds": security_group_ids,
            },
        }

        # Add instance requirements if specified
        instance_requirements = {}
        if allowed_instance_types:
            instance_requirements["AllowedInstanceTypes"] = allowed_instance_types
        if excluded_instance_types:
            instance_requirements["ExcludedInstanceTypes"] = excluded_instance_types
        if architectures:
            instance_requirements["Architectures"] = architectures
        if instance_requirements:
            body["InstanceRequirements"] = instance_requirements

        # Add scaling config if specified
        scaling_config = {}
        if max_vcpu_count:
            scaling_config["MaxVCpuCount"] = max_vcpu_count
        if scaling_mode:
            scaling_config["ScalingMode"] = scaling_mode
        if scaling_config:
            body["CapacityProviderScalingConfig"] = scaling_config

        if kms_key_arn:
            body["KmsKeyArn"] = kms_key_arn

        if tags:
            body["Tags"] = tags

        return self._make_request("POST", "capacity-providers", body)

    def delete_capacity_provider(self, name: str) -> None:
        """
        Delete a capacity provider.

        Args:
            name: The capacity provider name or ARN
        """
        self._make_request("DELETE", f"capacity-providers/{name}")

    def update_capacity_provider(
        self,
        name: str,
        max_vcpu_count: int | None = None,
        scaling_mode: str | None = None,
    ) -> dict[str, Any]:
        """
        Update a capacity provider's scaling configuration.

        Args:
            name: The capacity provider name or ARN
            max_vcpu_count: New maximum vCPU count
            scaling_mode: New scaling mode

        Returns:
            The updated capacity provider configuration
        """
        body: dict[str, Any] = {}

        scaling_config = {}
        if max_vcpu_count is not None:
            scaling_config["MaxVCpuCount"] = max_vcpu_count
        if scaling_mode is not None:
            scaling_config["ScalingMode"] = scaling_mode

        if scaling_config:
            body["CapacityProviderScalingConfig"] = scaling_config

        return self._make_request("PUT", f"capacity-providers/{name}", body)

    def _make_function_request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a signed request to the Lambda Functions API."""
        url = f"{self.endpoint}/{LAMBDA_FUNCTIONS_API_VERSION}/{path}"

        headers = {
            "Content-Type": "application/json",
        }

        data = json.dumps(body) if body else None

        request = AWSRequest(
            method=method,
            url=url,
            data=data,
            headers=headers,
        )
        SigV4Auth(self.credentials, "lambda", self.region_name).add_auth(request)

        response = requests.request(
            method=method,
            url=url,
            headers=dict(request.headers),
            data=data,
        )

        if response.status_code >= 400:
            error_body = response.json() if response.text else {}
            raise LambdaManagedInstancesError(
                status_code=response.status_code,
                error_type=error_body.get("Type", "Unknown"),
                message=error_body.get("Message", response.text),
            )

        return response.json() if response.text else {}

    def create_function(
        self,
        function_name: str,
        role: str,
        code: dict[str, Any],
        capacity_provider_arn: str,
        execution_env_memory_gb_per_vcpu: float = 2.0,
        per_execution_env_max_concurrency: int = 1,
        timeout: int = 900,
        memory_size: int = 1024,
        handler: str | None = None,
        runtime: str | None = None,
        package_type: str = "Image",
        environment: dict[str, str] | None = None,
        vpc_config: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Create a Lambda function with capacity provider configuration.

        This uses raw API calls because boto3 doesn't support CapacityProviderConfig yet.

        Args:
            function_name: Name of the function
            role: Execution role ARN
            code: Code configuration (ImageUri for container, S3Bucket/S3Key for zip)
            capacity_provider_arn: ARN of the capacity provider
            execution_env_memory_gb_per_vcpu: Memory per vCPU ratio
            per_execution_env_max_concurrency: Max concurrent invocations per environment
            timeout: Function timeout in seconds
            memory_size: Memory in MB
            handler: Handler for zip packages (not needed for containers)
            runtime: Runtime for zip packages (not needed for containers)
            package_type: "Image" or "Zip"
            environment: Environment variables
            vpc_config: VPC configuration
            tags: Tags for the function

        Returns:
            The created function configuration
        """
        body: dict[str, Any] = {
            "FunctionName": function_name,
            "Role": role,
            "Code": code,
            "Timeout": timeout,
            "MemorySize": memory_size,
            "PackageType": package_type,
            "CapacityProviderConfig": {
                "LambdaManagedInstancesCapacityProviderConfig": {
                    "CapacityProviderArn": capacity_provider_arn,
                    "ExecutionEnvironmentMemoryGiBPerVCpu": execution_env_memory_gb_per_vcpu,
                    "PerExecutionEnvironmentMaxConcurrency": per_execution_env_max_concurrency,
                }
            },
        }

        if handler and package_type == "Zip":
            body["Handler"] = handler
        if runtime and package_type == "Zip":
            body["Runtime"] = runtime
        if environment:
            body["Environment"] = {"Variables": environment}
        if vpc_config:
            body["VpcConfig"] = vpc_config
        if tags:
            body["Tags"] = tags

        return self._make_function_request("POST", "functions", body)

    def get_function(self, function_name: str) -> dict[str, Any]:
        """Get a function by name."""
        return self._make_function_request("GET", f"functions/{function_name}")

    def invoke_function(
        self,
        function_name: str,
        payload: dict[str, Any] | None = None,
        invocation_type: str = "RequestResponse",
        log_type: str = "Tail",
    ) -> dict[str, Any]:
        """
        Invoke a Lambda function.

        Args:
            function_name: Function name or ARN (can include version qualifier)
            payload: JSON payload to send
            invocation_type: "RequestResponse" (sync), "Event" (async), or "DryRun"
            log_type: "Tail" to include logs, "None" to skip

        Returns:
            Invocation response
        """
        url = f"{self.endpoint}/{LAMBDA_FUNCTIONS_API_VERSION}/functions/{function_name}/invocations"

        headers = {
            "Content-Type": "application/json",
            "X-Amz-Invocation-Type": invocation_type,
            "X-Amz-Log-Type": log_type,
        }

        data = json.dumps(payload) if payload else None

        request = AWSRequest(
            method="POST",
            url=url,
            data=data,
            headers=headers,
        )
        SigV4Auth(self.credentials, "lambda", self.region_name).add_auth(request)

        response = requests.post(
            url,
            headers=dict(request.headers),
            data=data,
        )

        result: dict[str, Any] = {
            "StatusCode": response.status_code,
            "Payload": response.content,
            "ResponseMetadata": {
                "RequestId": response.headers.get("x-amzn-requestid", "")
            },
        }

        if "x-amz-function-error" in response.headers:
            result["FunctionError"] = response.headers["x-amz-function-error"]
        if "x-amz-log-result" in response.headers:
            result["LogResult"] = response.headers["x-amz-log-result"]

        return result

    def publish_version(
        self,
        function_name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """
        Publish a new version of a function.

        Args:
            function_name: Function name
            description: Version description

        Returns:
            The published version configuration
        """
        body: dict[str, Any] = {}
        if description:
            body["Description"] = description

        return self._make_function_request(
            "POST", f"functions/{function_name}/versions", body
        )

    def delete_function(self, function_name: str) -> None:
        """Delete a function."""
        self._make_function_request("DELETE", f"functions/{function_name}")


class LambdaManagedInstancesError(Exception):
    """Error from the Lambda Managed Instances API."""

    def __init__(self, status_code: int, error_type: str, message: str):
        self.status_code = status_code
        self.error_type = error_type
        self.message = message
        super().__init__(f"{error_type}: {message} (HTTP {status_code})")
