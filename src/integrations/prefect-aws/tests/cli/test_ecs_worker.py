"""Tests for ECS worker CLI commands."""

import json
from unittest.mock import Mock, patch

import boto3
import pytest
from moto import mock_cloudformation, mock_ec2, mock_ecs, mock_sts
from prefect_aws.cli.main import app
from typer.testing import CliRunner


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

    @patch("prefect_aws.cli.ecs_worker.load_template")
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

    @patch("prefect_aws.cli.ecs_worker.validate_aws_credentials")
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

    @patch("prefect_aws.cli.ecs_worker.load_template")
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

    @patch("prefect_aws.cli.ecs_worker.load_template")
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

    @patch("prefect_aws.cli.ecs_worker.load_template")
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


class TestECSWorkerUtils:
    """Test utility functions used by ECS worker commands."""

    def test_cli_tags_generation(self):
        """Test that CLI tags are generated correctly."""
        from prefect_aws.cli.utils import add_cli_tags

        tags = add_cli_tags({}, "test-pool", "service")

        tag_dict = {tag["Key"]: tag["Value"] for tag in tags}

        assert tag_dict["ManagedBy"] == "prefect-aws-cli"
        assert tag_dict["DeploymentType"] == "ecs-worker"
        assert tag_dict["StackType"] == "service"
        assert tag_dict["WorkPoolName"] == "test-pool"
        assert "CreatedAt" in tag_dict

    @patch("prefect_aws.cli.utils.boto3.Session")
    def test_get_aws_client(self, mock_session):
        """Test AWS client creation."""
        from prefect_aws.cli.utils import get_aws_client

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
        from prefect_aws.cli.utils import load_template

        # This test requires the actual template files to exist
        # In a real test environment, you might want to mock this
        with patch("prefect_aws.cli.utils.files") as mock_files:
            mock_template_files = Mock()
            mock_template_file = Mock()
            mock_template_file.read_text.return_value = '{"test": "template"}'
            # Mock the / operator for pathlib-like behavior
            mock_template_files.__truediv__ = Mock(return_value=mock_template_file)
            mock_files.return_value = mock_template_files

            template = load_template("service-only.json")
            assert template == {"test": "template"}
