"""Tests for ECS worker CLI commands."""

import json
from unittest.mock import Mock, patch

from prefect_aws.cli.main import app
from typer.testing import CliRunner


class TestECSWorkerCLI:
    def setup_method(self):
        self.runner = CliRunner()

    @patch("prefect_aws.cli.ecs_worker.validate_aws_credentials")
    @patch("prefect_aws.cli.ecs_worker.get_aws_client")
    @patch("prefect_aws.cli.ecs_worker.load_template")
    @patch("prefect_aws.cli.ecs_worker.validate_ecs_cluster")
    @patch("prefect_aws.cli.ecs_worker.validate_vpc_and_subnets")
    def test_deploy_service_dry_run(
        self,
        mock_validate_vpc,
        mock_validate_cluster,
        mock_load_template,
        mock_get_client,
        mock_validate_creds,
    ):
        """Test deploy-service command with dry-run."""
        mock_validate_creds.return_value = True
        mock_validate_cluster.return_value = True
        mock_validate_vpc.return_value = (True, "")
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
                "test-cluster",
                "--existing-vpc-id",
                "vpc-12345",
                "--existing-subnet-ids",
                "subnet-1,subnet-2",
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
            app, ["ecs-worker", "deploy-service", "--work-pool-name", "test-pool"]
        )

        assert result.exit_code == 1
        assert "Invalid AWS credentials" in result.stdout

    @patch("prefect_aws.cli.ecs_worker.validate_aws_credentials")
    @patch("prefect_aws.cli.ecs_worker.get_aws_client")
    @patch("prefect_aws.cli.ecs_worker.load_template")
    @patch("prefect_aws.cli.ecs_worker.validate_ecs_cluster")
    @patch("prefect_aws.cli.ecs_worker.validate_vpc_and_subnets")
    @patch("typer.confirm")
    def test_deploy_service_self_hosted_server(
        self,
        mock_confirm,
        mock_validate_vpc,
        mock_validate_cluster,
        mock_load_template,
        mock_get_client,
        mock_validate_creds,
    ):
        """Test deploy-service command with self-hosted Prefect server."""
        mock_validate_creds.return_value = True
        mock_validate_cluster.return_value = True
        mock_validate_vpc.return_value = (True, "")
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
                "test-cluster",
                "--existing-vpc-id",
                "vpc-12345",
                "--existing-subnet-ids",
                "subnet-1,subnet-2",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout
        assert "test-stack" in result.stdout

    @patch("prefect_aws.cli.ecs_worker.validate_aws_credentials")
    @patch("prefect_aws.cli.ecs_worker.get_aws_client")
    @patch("prefect_aws.cli.ecs_worker.load_template")
    @patch("prefect_aws.cli.ecs_worker.validate_ecs_cluster")
    @patch("prefect_aws.cli.ecs_worker.validate_vpc_and_subnets")
    def test_deploy_service_with_auth_string_parameters(
        self,
        mock_validate_vpc,
        mock_validate_cluster,
        mock_load_template,
        mock_get_client,
        mock_validate_creds,
    ):
        """Test deploy-service command with auth string parameters."""
        mock_validate_creds.return_value = True
        mock_validate_cluster.return_value = True
        mock_validate_vpc.return_value = (True, "")
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
                "test-cluster",
                "--existing-vpc-id",
                "vpc-12345",
                "--existing-subnet-ids",
                "subnet-1,subnet-2",
                "--prefect-auth-string",
                "user:pass",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout
        assert "test-stack" in result.stdout

    @patch("prefect_aws.cli.ecs_worker.validate_aws_credentials")
    @patch("prefect_aws.cli.ecs_worker.get_aws_client")
    @patch("prefect_aws.cli.ecs_worker.load_template")
    @patch("prefect_aws.cli.ecs_worker.validate_ecs_cluster")
    def test_deploy_events_dry_run(
        self,
        mock_validate_cluster,
        mock_load_template,
        mock_get_client,
        mock_validate_creds,
    ):
        """Test deploy-events command with dry-run."""
        mock_validate_creds.return_value = True
        mock_validate_cluster.return_value = True
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
                "arn:aws:ecs:us-east-1:123456789012:cluster/test",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout
        assert "test-events" in result.stdout

    @patch("prefect_aws.cli.ecs_worker.validate_aws_credentials")
    @patch("prefect_aws.cli.ecs_worker.get_aws_client")
    @patch("prefect_aws.cli.ecs_worker.list_cli_deployed_stacks")
    def test_list_stacks(self, mock_list_stacks, mock_get_client, mock_validate_creds):
        """Test list stacks command."""
        from datetime import datetime

        mock_validate_creds.return_value = True
        mock_list_stacks.return_value = [
            {
                "StackName": "test-stack",
                "StackStatus": "CREATE_COMPLETE",
                "CreationTime": datetime(2023, 1, 1),
                "WorkPoolName": "test-pool",
                "StackType": "service",
                "Description": "Test stack",
            }
        ]

        result = self.runner.invoke(app, ["ecs-worker", "list"])

        assert result.exit_code == 0
        # Output should contain stack information

    @patch("prefect_aws.cli.ecs_worker.validate_aws_credentials")
    @patch("prefect_aws.cli.ecs_worker.get_aws_client")
    @patch("prefect_aws.cli.ecs_worker.list_cli_deployed_stacks")
    def test_list_stacks_json_format(
        self, mock_list_stacks, mock_get_client, mock_validate_creds
    ):
        """Test list stacks command with JSON output."""
        from datetime import datetime

        mock_validate_creds.return_value = True
        mock_list_stacks.return_value = [
            {
                "StackName": "test-stack",
                "StackStatus": "CREATE_COMPLETE",
                "CreationTime": datetime(2023, 1, 1),
                "WorkPoolName": "test-pool",
                "StackType": "service",
                "Description": "Test stack",
            }
        ]

        result = self.runner.invoke(app, ["ecs-worker", "list", "--format", "json"])

        assert result.exit_code == 0
        # Should be valid JSON
        json.loads(result.stdout)

    @patch("prefect_aws.cli.ecs_worker.validate_aws_credentials")
    @patch("prefect_aws.cli.ecs_worker.get_aws_client")
    @patch("prefect_aws.cli.ecs_worker.validate_stack_is_cli_managed")
    @patch("prefect_aws.cli.ecs_worker.get_stack_status")
    def test_stack_status(
        self,
        mock_get_status,
        mock_validate_managed,
        mock_get_client,
        mock_validate_creds,
    ):
        """Test stack status command."""
        mock_validate_creds.return_value = True
        mock_validate_managed.return_value = True
        mock_get_status.return_value = {
            "StackName": "test-stack",
            "StackStatus": "CREATE_COMPLETE",
            "CreationTime": "2023-01-01T00:00:00Z",
        }

        result = self.runner.invoke(app, ["ecs-worker", "status", "test-stack"])

        assert result.exit_code == 0
        assert "test-stack" in result.stdout
        assert "CREATE_COMPLETE" in result.stdout

    @patch("prefect_aws.cli.ecs_worker.validate_aws_credentials")
    @patch("prefect_aws.cli.ecs_worker.get_aws_client")
    @patch("prefect_aws.cli.ecs_worker.validate_stack_is_cli_managed")
    def test_stack_status_not_cli_managed(
        self, mock_validate_managed, mock_get_client, mock_validate_creds
    ):
        """Test stack status command for non-CLI managed stack."""
        mock_validate_creds.return_value = True
        mock_validate_managed.return_value = False

        result = self.runner.invoke(app, ["ecs-worker", "status", "test-stack"])

        assert result.exit_code == 1
        assert "not deployed by prefect-aws CLI" in result.stdout

    @patch("prefect_aws.cli.ecs_worker.validate_aws_credentials")
    @patch("prefect_aws.cli.ecs_worker.get_aws_client")
    @patch("prefect_aws.cli.ecs_worker.delete_stack")
    def test_delete_stack_force(
        self, mock_delete_stack, mock_get_client, mock_validate_creds
    ):
        """Test delete stack command with force flag."""
        mock_validate_creds.return_value = True

        result = self.runner.invoke(
            app, ["ecs-worker", "delete", "test-stack", "--force"]
        )

        assert result.exit_code == 0
        mock_delete_stack.assert_called_once()


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
