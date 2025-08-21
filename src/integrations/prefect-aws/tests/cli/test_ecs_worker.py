"""Tests for ECS worker CLI commands."""

import json
import uuid
from unittest.mock import Mock, patch

import boto3
import pytest
from moto import mock_cloudformation, mock_ec2, mock_ecs, mock_sts
from prefect_aws._cli.main import app
from prefect_aws.workers import ECSWorker
from typer.testing import CliRunner

import prefect
from prefect.client.schemas.actions import WorkPoolCreate


@pytest.fixture
def aws_credentials(monkeypatch):
    """Set up AWS credentials for moto testing."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def mock_aws_resources():
    """Create common AWS resources for testing."""
    with mock_ecs(), mock_ec2(), mock_cloudformation(), mock_sts():
        # Create VPC
        ec2 = boto3.client("ec2", region_name="us-east-1")
        vpc_response = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc_response["Vpc"]["VpcId"]

        # Create subnets
        subnet1 = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
        subnet2 = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.2.0/24")

        # Create ECS cluster
        ecs = boto3.client("ecs", region_name="us-east-1")
        cluster_response = ecs.create_cluster(clusterName="test-cluster")

        yield {
            "vpc_id": vpc_id,
            "subnet_ids": [
                subnet1["Subnet"]["SubnetId"],
                subnet2["Subnet"]["SubnetId"],
            ],
            "cluster_name": "test-cluster",
            "cluster_arn": cluster_response["cluster"]["clusterArn"],
        }


class TestECSWorkerCLI:
    def setup_method(self):
        self.runner = CliRunner()

    @patch("prefect_aws._cli.ecs_worker.load_template")
    def test_deploy_service_dry_run(
        self, mock_load_template, aws_credentials, mock_aws_resources
    ):
        """Test deploy-service command with dry-run."""
        mock_load_template.return_value = {"AWSTemplateFormatVersion": "2010-09-09"}

        result = self.runner.invoke(
            app,
            [
                "ecs-worker",
                "deploy-service",
                "--work-pool-name",
                "test-pool",
                "--stack-name",
                "test-stack",
                "--prefect-api-url",
                "https://api.prefect.cloud/api",
                "--existing-cluster-identifier",
                mock_aws_resources["cluster_name"],
                "--existing-vpc-id",
                mock_aws_resources["vpc_id"],
                "--existing-subnet-ids",
                ",".join(mock_aws_resources["subnet_ids"]),
                "--prefect-api-key",
                "test-key",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout
        assert "test-stack" in result.stdout

    @patch("prefect_aws._cli.ecs_worker.load_template")
    def test_deploy_service_no_wait(
        self, mock_load_template, aws_credentials, mock_aws_resources
    ):
        """Test deploy-service command with --no-wait flag."""
        mock_load_template.return_value = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {},
        }

        result = self.runner.invoke(
            app,
            [
                "ecs-worker",
                "deploy-service",
                "--work-pool-name",
                "test-pool",
                "--stack-name",
                "test-stack",
                "--prefect-api-url",
                "https://api.prefect.cloud/api",
                "--existing-cluster-identifier",
                mock_aws_resources["cluster_name"],
                "--existing-vpc-id",
                mock_aws_resources["vpc_id"],
                "--existing-subnet-ids",
                ",".join(mock_aws_resources["subnet_ids"]),
                "--prefect-api-key",
                "test-key",
                "--no-wait",
            ],
        )

        assert result.exit_code == 0
        assert "Check status with:" in result.stdout

    @patch("prefect_aws._cli.ecs_worker.validate_aws_credentials")
    def test_deploy_service_invalid_credentials(self, mock_validate_creds):
        """Test deploy-service command with invalid credentials."""
        mock_validate_creds.return_value = False

        result = self.runner.invoke(
            app,
            [
                "ecs-worker",
                "deploy-service",
                "--work-pool-name",
                "test-pool",
                "--stack-name",
                "test-stack",
                "--prefect-api-url",
                "https://api.prefect.cloud/api",
                "--prefect-api-key",
                "test-key",
                "--existing-cluster-identifier",
                "test-cluster",
                "--existing-vpc-id",
                "vpc-12345",
                "--existing-subnet-ids",
                "subnet-1,subnet-2",
            ],
        )

        assert result.exit_code == 1
        # Check both stdout and stderr as behavior varies across Typer versions
        output = result.stdout
        try:
            output += result.stderr
        except (ValueError, AttributeError):
            pass  # stderr not separately captured
        assert "Invalid AWS credentials" in output

    @patch("prefect_aws._cli.ecs_worker.load_template")
    @patch("typer.confirm")
    def test_deploy_service_self_hosted_server(
        self, mock_confirm, mock_load_template, aws_credentials, mock_aws_resources
    ):
        """Test deploy-service command with self-hosted Prefect server."""
        mock_load_template.return_value = {"AWSTemplateFormatVersion": "2010-09-09"}
        mock_confirm.return_value = False  # No authentication needed

        result = self.runner.invoke(
            app,
            [
                "ecs-worker",
                "deploy-service",
                "--work-pool-name",
                "test-pool",
                "--stack-name",
                "test-stack",
                "--prefect-api-url",
                "http://localhost:4200/api",
                "--existing-cluster-identifier",
                mock_aws_resources["cluster_name"],
                "--existing-vpc-id",
                mock_aws_resources["vpc_id"],
                "--existing-subnet-ids",
                ",".join(mock_aws_resources["subnet_ids"]),
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout
        assert "test-stack" in result.stdout

    @patch("prefect_aws._cli.ecs_worker.load_template")
    def test_deploy_service_with_auth_string_parameters(
        self, mock_load_template, aws_credentials, mock_aws_resources
    ):
        """Test deploy-service command with auth string parameters."""
        mock_load_template.return_value = {"AWSTemplateFormatVersion": "2010-09-09"}

        result = self.runner.invoke(
            app,
            [
                "ecs-worker",
                "deploy-service",
                "--work-pool-name",
                "test-pool",
                "--stack-name",
                "test-stack",
                "--prefect-api-url",
                "http://localhost:4200/api",
                "--existing-cluster-identifier",
                mock_aws_resources["cluster_name"],
                "--existing-vpc-id",
                mock_aws_resources["vpc_id"],
                "--existing-subnet-ids",
                ",".join(mock_aws_resources["subnet_ids"]),
                "--prefect-auth-string",
                "user:pass",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout
        assert "test-stack" in result.stdout

    @patch("prefect_aws._cli.ecs_worker.load_template")
    def test_deploy_events_dry_run(
        self, mock_load_template, aws_credentials, mock_aws_resources
    ):
        """Test deploy-events command with dry-run."""
        mock_load_template.return_value = {"AWSTemplateFormatVersion": "2010-09-09"}

        result = self.runner.invoke(
            app,
            [
                "ecs-worker",
                "deploy-events",
                "--work-pool-name",
                "test-pool",
                "--stack-name",
                "test-events",
                "--existing-cluster-arn",
                mock_aws_resources["cluster_arn"],
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout
        assert "test-events" in result.stdout

    def test_list_stacks(self, aws_credentials):
        """Test list stacks command."""
        with mock_cloudformation(), mock_sts():
            # Create a test stack with CLI tags
            cf = boto3.client("cloudformation", region_name="us-east-1")
            cf.create_stack(
                StackName="test-stack",
                TemplateBody='{"AWSTemplateFormatVersion": "2010-09-09", "Resources": {}}',
                Tags=[
                    {"Key": "ManagedBy", "Value": "prefect-aws-cli"},
                    {"Key": "DeploymentType", "Value": "ecs-worker"},
                    {"Key": "StackType", "Value": "service"},
                    {"Key": "WorkPoolName", "Value": "test-pool"},
                    {"Key": "CreatedAt", "Value": "2023-01-01T00:00:00Z"},
                ],
            )

            result = self.runner.invoke(app, ["ecs-worker", "list"])

            assert result.exit_code == 0
            # Output should contain stack information
            assert "test-stack" in result.stdout

    def test_list_stacks_json_format(self, aws_credentials):
        """Test list stacks command with JSON output."""
        with mock_cloudformation(), mock_sts():
            # Create a test stack with CLI tags
            cf = boto3.client("cloudformation", region_name="us-east-1")
            cf.create_stack(
                StackName="test-stack",
                TemplateBody='{"AWSTemplateFormatVersion": "2010-09-09", "Resources": {}}',
                Tags=[
                    {"Key": "ManagedBy", "Value": "prefect-aws-cli"},
                    {"Key": "DeploymentType", "Value": "ecs-worker"},
                    {"Key": "StackType", "Value": "service"},
                    {"Key": "WorkPoolName", "Value": "test-pool"},
                    {"Key": "CreatedAt", "Value": "2023-01-01T00:00:00Z"},
                ],
            )

            result = self.runner.invoke(app, ["ecs-worker", "list", "--format", "json"])

            assert result.exit_code == 0
            # Should be valid JSON
            json.loads(result.stdout)

    def test_stack_status(self, aws_credentials):
        """Test stack status command."""
        with mock_cloudformation(), mock_sts():
            # Create a test stack with CLI tags
            cf = boto3.client("cloudformation", region_name="us-east-1")
            cf.create_stack(
                StackName="test-stack",
                TemplateBody='{"AWSTemplateFormatVersion": "2010-09-09", "Resources": {}}',
                Tags=[
                    {"Key": "ManagedBy", "Value": "prefect-aws-cli"},
                    {"Key": "DeploymentType", "Value": "ecs-worker"},
                    {"Key": "StackType", "Value": "service"},
                    {"Key": "WorkPoolName", "Value": "test-pool"},
                ],
            )

            result = self.runner.invoke(app, ["ecs-worker", "status", "test-stack"])

            assert result.exit_code == 0
            assert "test-stack" in result.stdout
            assert "CREATE_COMPLETE" in result.stdout

    def test_stack_status_not_cli_managed(self, aws_credentials):
        """Test stack status command for non-CLI managed stack."""
        with mock_cloudformation(), mock_sts():
            # Create a test stack without CLI tags
            cf = boto3.client("cloudformation", region_name="us-east-1")
            cf.create_stack(
                StackName="test-stack",
                TemplateBody='{"AWSTemplateFormatVersion": "2010-09-09", "Resources": {}}',
                Tags=[
                    {"Key": "Owner", "Value": "someone-else"},
                ],
            )

            result = self.runner.invoke(app, ["ecs-worker", "status", "test-stack"])

            assert result.exit_code == 1
            # Check both stdout and stderr as behavior varies across Typer versions
            output = result.stdout
            try:
                output += result.stderr
            except (ValueError, AttributeError):
                pass  # stderr not separately captured
            assert "not deployed by prefect-aws CLI" in output

    def test_delete_stack_force(self, aws_credentials):
        """Test delete stack command with force flag."""
        with mock_cloudformation(), mock_sts():
            # Create a test stack with CLI tags
            cf = boto3.client("cloudformation", region_name="us-east-1")
            cf.create_stack(
                StackName="test-stack",
                TemplateBody='{"AWSTemplateFormatVersion": "2010-09-09", "Resources": {}}',
                Tags=[
                    {"Key": "ManagedBy", "Value": "prefect-aws-cli"},
                    {"Key": "DeploymentType", "Value": "ecs-worker"},
                ],
            )

            result = self.runner.invoke(
                app, ["ecs-worker", "delete", "test-stack", "--force"]
            )

            assert result.exit_code == 0

            # Verify the stack was deleted
            try:
                cf.describe_stacks(StackName="test-stack")
                # If we get here, the stack wasn't deleted
                assert False, "Stack should have been deleted"
            except cf.exceptions.ClientError as e:
                # Stack should not exist anymore
                assert "does not exist" in str(e) or "DELETE_COMPLETE" in str(e)

    def test_delete_stack_no_wait(self, aws_credentials):
        """Test delete stack command with --no-wait flag."""
        with mock_cloudformation(), mock_sts():
            # Create a test stack with CLI tags
            cf = boto3.client("cloudformation", region_name="us-east-1")
            cf.create_stack(
                StackName="test-stack",
                TemplateBody='{"AWSTemplateFormatVersion": "2010-09-09", "Resources": {}}',
                Tags=[
                    {"Key": "ManagedBy", "Value": "prefect-aws-cli"},
                    {"Key": "DeploymentType", "Value": "ecs-worker"},
                ],
            )

            result = self.runner.invoke(
                app, ["ecs-worker", "delete", "test-stack", "--force", "--no-wait"]
            )

            assert result.exit_code == 0
            assert "Check status with:" in result.stdout


class TestECSWorkerUtils:
    """Test utility functions used by ECS worker commands."""

    def test_cli_tags_generation(self):
        """Test that CLI tags are generated correctly."""
        from prefect_aws._cli.utils import add_cli_tags

        tags = add_cli_tags("test-pool", "service")

        tag_dict = {tag["Key"]: tag["Value"] for tag in tags}

        assert tag_dict["ManagedBy"] == "prefect-aws-cli"
        assert tag_dict["DeploymentType"] == "ecs-worker"
        assert tag_dict["StackType"] == "service"
        assert tag_dict["WorkPoolName"] == "test-pool"
        assert "CreatedAt" in tag_dict

    @patch("prefect_aws._cli.utils.boto3.Session")
    def test_get_aws_client(self, mock_session):
        """Test AWS client creation."""
        from prefect_aws._cli.utils import get_aws_client

        mock_client = Mock()
        mock_session_instance = Mock()
        mock_session_instance.client.return_value = mock_client
        mock_session.return_value = mock_session_instance

        client = get_aws_client("cloudformation", "us-east-1", "test-profile")

        mock_session.assert_called_once_with(
            profile_name="test-profile", region_name="us-east-1"
        )
        mock_session_instance.client.assert_called_once_with("cloudformation")
        assert client == mock_client

    def test_load_template_success(self):
        """Test successful template loading."""
        from prefect_aws._cli.utils import load_template

        # This test requires the actual template files to exist
        # In a real test environment, you might want to mock this
        with patch("prefect_aws._cli.utils.files") as mock_files:
            mock_template_files = Mock()
            mock_template_file = Mock()
            mock_template_file.read_text.return_value = '{"test": "template"}'
            # Mock the / operator for pathlib-like behavior
            mock_template_files.__truediv__ = Mock(return_value=mock_template_file)
            mock_files.return_value = mock_template_files

            template = load_template("service.json")
            assert template == {"test": "template"}


class TestWorkPoolDefaults:
    """Test work pool defaults update functionality."""

    @pytest.fixture
    async def test_work_pool(self):
        """Create a test work pool with ECS base template."""
        async with prefect.get_client() as client:
            work_pool = await client.create_work_pool(
                WorkPoolCreate(
                    name=f"test-ecs-pool-{uuid.uuid4()}",
                    base_job_template=ECSWorker.get_default_base_job_template(),
                )
            )
            try:
                yield work_pool
            finally:
                await client.delete_work_pool(work_pool.name)

    async def test_update_work_pool_defaults_success(self, test_work_pool):
        """Test successful work pool defaults update."""
        from prefect_aws._cli.utils import update_work_pool_defaults

        stack_outputs = {
            "VpcId": "vpc-123456",
            "ClusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster",
            "PrefectApiKeySecretArnOutput": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-key",
            "TaskExecutionRoleArn": "arn:aws:iam::123456789012:role/test-execution-role",
            "SubnetIds": "subnet-1,subnet-2",
        }

        # Update the work pool defaults
        update_work_pool_defaults(test_work_pool.name, stack_outputs)

        # Verify the updates were applied
        async with prefect.get_client() as client:
            updated_work_pool = await client.read_work_pool(test_work_pool.name)
            properties = updated_work_pool.base_job_template["variables"]["properties"]

            assert properties["vpc_id"]["default"] == "vpc-123456"
            assert (
                properties["cluster"]["default"]
                == "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster"
            )
            assert (
                properties["prefect_api_key_secret_arn"]["default"]
                == "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-key"
            )
            assert (
                properties["execution_role_arn"]["default"]
                == "arn:aws:iam::123456789012:role/test-execution-role"
            )

            # Check network configuration subnets
            network_config = properties["network_configuration"]["properties"]
            subnets = network_config["awsvpcConfiguration"]["properties"]["subnets"]
            assert subnets["default"] == ["subnet-1", "subnet-2"]

    async def test_update_work_pool_defaults_preserves_existing(self, test_work_pool):
        """Test that existing defaults are preserved."""
        from prefect_aws._cli.utils import update_work_pool_defaults

        # First, set some existing defaults
        async with prefect.get_client() as client:
            work_pool = await client.read_work_pool(test_work_pool.name)
            base_template = work_pool.base_job_template
            base_template["variables"]["properties"]["vpc_id"]["default"] = (
                "existing-vpc"
            )
            base_template["variables"]["properties"]["execution_role_arn"][
                "default"
            ] = "existing-role"

            from prefect.client.schemas.actions import WorkPoolUpdate

            await client.update_work_pool(
                test_work_pool.name, WorkPoolUpdate(base_job_template=base_template)
            )

        stack_outputs = {
            "VpcId": "vpc-123456",
            "ClusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster",
            "TaskExecutionRoleArn": "arn:aws:iam::123456789012:role/test-execution-role",
        }

        # Update with new stack outputs
        update_work_pool_defaults(test_work_pool.name, stack_outputs)

        # Verify existing defaults were preserved and only empty ones updated
        async with prefect.get_client() as client:
            updated_work_pool = await client.read_work_pool(test_work_pool.name)
            properties = updated_work_pool.base_job_template["variables"]["properties"]

            # Existing defaults should be preserved
            assert properties["vpc_id"]["default"] == "existing-vpc"
            assert properties["execution_role_arn"]["default"] == "existing-role"

            # Empty defaults should be updated
            assert (
                properties["cluster"]["default"]
                == "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster"
            )

    async def test_update_work_pool_defaults_handles_missing_outputs(
        self, test_work_pool
    ):
        """Test handling of missing stack outputs."""
        from prefect_aws._cli.utils import update_work_pool_defaults

        # Only provide some outputs
        stack_outputs = {
            "VpcId": "vpc-123456",
            # Missing ClusterArn, TaskExecutionRoleArn, etc.
        }

        update_work_pool_defaults(test_work_pool.name, stack_outputs)

        # Should still update available outputs
        async with prefect.get_client() as client:
            updated_work_pool = await client.read_work_pool(test_work_pool.name)
            properties = updated_work_pool.base_job_template["variables"]["properties"]

            assert properties["vpc_id"]["default"] == "vpc-123456"
            # cluster should still have its original default since ClusterArn wasn't provided
            assert properties["cluster"]["default"] is None

    async def test_update_work_pool_defaults_handles_nonexistent_pool(self):
        """Test that errors for nonexistent work pools are handled gracefully."""
        from prefect_aws._cli.utils import update_work_pool_defaults

        stack_outputs = {"VpcId": "vpc-123456"}

        # Should not raise an exception for nonexistent work pool
        update_work_pool_defaults("nonexistent-pool", stack_outputs)

    async def test_deploy_service_updates_work_pool_when_wait_true(
        self, test_work_pool
    ):
        """Test that deploy-service updates work pool defaults when --wait is True."""

        def mock_deploy_and_get_status(cf_client, stack_name, **kwargs):
            """Mock deploy_stack that simulates successful deployment"""
            pass

        def mock_get_status(cf_client, stack_name):
            """Mock get_stack_status that returns outputs"""
            return {
                "StackName": stack_name,
                "StackStatus": "CREATE_COMPLETE",
                "Outputs": [
                    {"OutputKey": "VpcId", "OutputValue": "vpc-deployed"},
                    {
                        "OutputKey": "ClusterArn",
                        "OutputValue": "arn:aws:ecs:us-east-1:123456789012:cluster/deployed-cluster",
                    },
                    {
                        "OutputKey": "TaskExecutionRoleArn",
                        "OutputValue": "arn:aws:iam::123456789012:role/deployed-role",
                    },
                    {
                        "OutputKey": "SubnetIds",
                        "OutputValue": "subnet-deployed-1,subnet-deployed-2",
                    },
                ],
            }

        with (
            patch(
                "prefect_aws._cli.ecs_worker.deploy_stack",
                side_effect=mock_deploy_and_get_status,
            ),
            patch(
                "prefect_aws._cli.ecs_worker.get_stack_status",
                side_effect=mock_get_status,
            ),
            patch("prefect_aws._cli.ecs_worker.load_template") as mock_load_template,
            patch(
                "prefect_aws._cli.ecs_worker.validate_aws_credentials",
                return_value=True,
            ),
            patch(
                "prefect_aws._cli.ecs_worker.validate_ecs_cluster", return_value=True
            ),
            patch(
                "prefect_aws._cli.ecs_worker.validate_vpc_and_subnets",
                return_value=(True, ""),
            ),
        ):
            mock_load_template.return_value = {"AWSTemplateFormatVersion": "2010-09-09"}

            runner = CliRunner()
            result = runner.invoke(
                app,
                [
                    "ecs-worker",
                    "deploy-service",
                    "--work-pool-name",
                    test_work_pool.name,
                    "--stack-name",
                    "test-stack",
                    "--prefect-api-url",
                    "http://localhost:4200/api",
                    "--existing-cluster-identifier",
                    "test-cluster",
                    "--existing-vpc-id",
                    "vpc-12345",
                    "--existing-subnet-ids",
                    "subnet-1,subnet-2",
                    "--region",
                    "us-east-1",
                    "--prefect-auth-string",
                    "this-is-a-test-auth-string",
                    "--wait",  # This should trigger work pool update
                ],
            )

            assert result.exit_code == 0, result.stdout

        # Verify the work pool was updated with deployment values
        async with prefect.get_client() as client:
            updated_work_pool = await client.read_work_pool(test_work_pool.name)
            properties = updated_work_pool.base_job_template["variables"]["properties"]

            assert properties["vpc_id"]["default"] == "vpc-deployed"
            assert (
                properties["cluster"]["default"]
                == "arn:aws:ecs:us-east-1:123456789012:cluster/deployed-cluster"
            )
            assert (
                properties["execution_role_arn"]["default"]
                == "arn:aws:iam::123456789012:role/deployed-role"
            )

            # Check subnets
            network_config = properties["network_configuration"]["properties"]
            subnets = network_config["awsvpcConfiguration"]["properties"]["subnets"]
            assert subnets["default"] == ["subnet-deployed-1", "subnet-deployed-2"]

    async def test_deploy_service_skips_work_pool_update_when_no_wait(
        self, test_work_pool
    ):
        """Test that deploy-service skips work pool update when --no-wait is used."""

        def mock_deploy_no_wait(cf_client, stack_name, **kwargs):
            # Should not call get_stack_status when wait=False
            pass

        with (
            patch(
                "prefect_aws._cli.ecs_worker.deploy_stack",
                side_effect=mock_deploy_no_wait,
            ),
            patch("prefect_aws._cli.ecs_worker.load_template") as mock_load_template,
            patch(
                "prefect_aws._cli.ecs_worker.validate_aws_credentials",
                return_value=True,
            ),
            patch(
                "prefect_aws._cli.ecs_worker.validate_ecs_cluster", return_value=True
            ),
            patch(
                "prefect_aws._cli.ecs_worker.validate_vpc_and_subnets",
                return_value=(True, ""),
            ),
        ):
            mock_load_template.return_value = {"AWSTemplateFormatVersion": "2010-09-09"}

            runner = CliRunner()
            result = runner.invoke(
                app,
                [
                    "ecs-worker",
                    "deploy-service",
                    "--work-pool-name",
                    test_work_pool.name,
                    "--stack-name",
                    "test-stack",
                    "--prefect-api-url",
                    "http://localhost:4200/api",
                    "--existing-cluster-identifier",
                    "test-cluster",
                    "--existing-vpc-id",
                    "vpc-12345",
                    "--existing-subnet-ids",
                    "subnet-1,subnet-2",
                    "--region",
                    "us-east-1",
                    "--prefect-auth-string",
                    "this-is-a-test-auth-string",
                    "--no-wait",  # This should skip work pool update
                ],
            )

            assert result.exit_code == 0, result.stdout

        # Verify the work pool was NOT updated (should still have original defaults)
        async with prefect.get_client() as client:
            work_pool = await client.read_work_pool(test_work_pool.name)
            properties = work_pool.base_job_template["variables"]["properties"]

            # Should still have original None defaults, not updated values
            assert properties["vpc_id"]["default"] is None
            assert properties["cluster"]["default"] is None
            assert properties["execution_role_arn"]["default"] is None


class TestExportTemplate:
    """Test export-template command functionality."""

    @patch("prefect_aws._cli.ecs_worker.load_template")
    def test_export_template_service_json(self, mock_load_template, tmp_path):
        """Test exporting service template as JSON."""
        mock_template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {"TestResource": {"Type": "AWS::S3::Bucket"}},
        }
        mock_load_template.return_value = mock_template

        output_file = tmp_path / "test-service.json"
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "ecs-worker",
                "export-template",
                "--template-type",
                "service",
                "--output-path",
                str(output_file),
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0, result.stdout
        assert "Template exported to" in result.stdout
        assert output_file.exists()

        # Verify file content
        with open(output_file) as f:
            exported_content = json.loads(f.read())

        assert exported_content == mock_template
        mock_load_template.assert_called_once_with("service.json")

    @patch("prefect_aws._cli.ecs_worker.load_template")
    def test_export_template_events_json(self, mock_load_template, tmp_path):
        """Test exporting events-only template as JSON."""
        mock_template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {"TestQueue": {"Type": "AWS::SQS::Queue"}},
        }
        mock_load_template.return_value = mock_template

        output_file = tmp_path / "test-events.json"
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "ecs-worker",
                "export-template",
                "--template-type",
                "events-only",
                "--output-path",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

        # Verify file content
        with open(output_file) as f:
            exported_content = json.loads(f.read())

        assert exported_content == mock_template
        mock_load_template.assert_called_once_with("events-only.json")

    @patch("prefect_aws._cli.ecs_worker.load_template")
    def test_export_template_yaml_format(self, mock_load_template, tmp_path):
        """Test exporting template as YAML format."""
        mock_template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {"TestResource": {"Type": "AWS::S3::Bucket"}},
        }
        mock_load_template.return_value = mock_template

        output_file = tmp_path / "test-service.yaml"
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "ecs-worker",
                "export-template",
                "--template-type",
                "service",
                "--output-path",
                str(output_file),
                "--format",
                "yaml",
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

        # Verify file content (either YAML or JSON fallback)
        with open(output_file, "r") as f:
            content = f.read()

        # Content should be YAML if pyyaml is available, otherwise JSON
        if "AWSTemplateFormatVersion:" in content:
            # YAML format
            import yaml

            yaml_content = yaml.safe_load(content)
            assert yaml_content == mock_template
        else:
            # JSON fallback
            json_content = json.loads(content)
            assert json_content == mock_template

    @patch("prefect_aws._cli.ecs_worker.load_template")
    def test_export_template_yaml_fallback_to_json(
        self, mock_load_template, tmp_path, monkeypatch
    ):
        """Test YAML format falls back to JSON when PyYAML not available."""
        # Mock yaml import in the specific function context
        import sys

        if "yaml" in sys.modules:
            monkeypatch.setitem(sys.modules, "yaml", None)

        mock_template = {"AWSTemplateFormatVersion": "2010-09-09"}
        mock_load_template.return_value = mock_template

        output_file = tmp_path / "test-service.yaml"
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "ecs-worker",
                "export-template",
                "--template-type",
                "service",
                "--output-path",
                str(output_file),
                "--format",
                "yaml",
            ],
        )

        assert result.exit_code == 0, result.stdout
        assert "Warning: PyYAML not available" in result.stdout

        # Should create .json file due to fallback
        json_file = tmp_path / "test-service.json"
        assert json_file.exists()

    @patch("prefect_aws._cli.ecs_worker.load_template")
    def test_export_template_interactive_prompts(self, mock_load_template, tmp_path):
        """Test interactive prompts when required parameters not provided."""
        mock_template = {"AWSTemplateFormatVersion": "2010-09-09"}
        mock_load_template.return_value = mock_template

        output_file = tmp_path / "interactive-test.json"

        runner = CliRunner()
        result = runner.invoke(
            app, ["ecs-worker", "export-template"], input=f"service\n{output_file}\n"
        )

        assert result.exit_code == 0
        assert output_file.exists()

    @patch("prefect_aws._cli.ecs_worker.load_template")
    def test_export_template_creates_output_directory(
        self, mock_load_template, tmp_path
    ):
        """Test that output directories are created if they don't exist."""
        mock_template = {"AWSTemplateFormatVersion": "2010-09-09"}
        mock_load_template.return_value = mock_template

        output_dir = tmp_path / "nested" / "directory"
        output_file = output_dir / "template.json"

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "ecs-worker",
                "export-template",
                "--template-type",
                "service",
                "--output-path",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        assert output_dir.exists()

    @patch("prefect_aws._cli.ecs_worker.load_template")
    def test_export_template_load_error(self, mock_load_template):
        """Test handling of template loading errors."""
        mock_load_template.side_effect = Exception("Template not found")

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "ecs-worker",
                "export-template",
                "--template-type",
                "service",
                "--output-path",
                "/tmp/test.json",
            ],
        )

        assert result.exit_code == 1
        # Check both stdout and stderr as behavior varies across Typer versions
        output = result.stdout
        try:
            output += result.stderr
        except (ValueError, AttributeError):
            pass  # stderr not separately captured
        assert "Error exporting template" in output

    @patch("prefect_aws._cli.ecs_worker.load_template")
    def test_export_template_includes_usage_instructions(
        self, mock_load_template, tmp_path
    ):
        """Test that successful export includes helpful usage instructions."""
        mock_template = {"AWSTemplateFormatVersion": "2010-09-09"}
        mock_load_template.return_value = mock_template

        output_file = tmp_path / "template.json"

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "ecs-worker",
                "export-template",
                "--template-type",
                "events-only",
                "--output-path",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert "Next steps:" in result.stdout
        assert "aws cloudformation deploy" in result.stdout
        assert "Review and customize" in result.stdout
