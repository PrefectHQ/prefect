"""
Tests for the transfer CLI command.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from prefect.cli.transfer import ResourceType, transfer_app


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing."""
    return CliRunner()


class TestTransferCommand:
    """Tests for the transfer command."""

    def test_transfer_help(self, cli_runner):
        """Test that transfer help displays correctly."""
        result = cli_runner.invoke(transfer_app, ["--help"])
        assert result.exit_code == 0
        assert "Transfer resources between Prefect profiles" in result.output
        assert "--from" in result.output
        assert "--to" in result.output
        assert "--exclude" in result.output
        assert "--dry-run" in result.output
        assert "--force" in result.output

    def test_transfer_requires_from_and_to(self, cli_runner):
        """Test that transfer requires both --from and --to options."""
        # Missing both
        result = cli_runner.invoke(transfer_app, [])
        assert result.exit_code != 0

        # Missing --to
        result = cli_runner.invoke(transfer_app, ["--from", "staging"])
        assert result.exit_code != 0

        # Missing --from
        result = cli_runner.invoke(transfer_app, ["--to", "prod"])
        assert result.exit_code != 0

    @patch("prefect.cli.transfer.load_profiles")
    def test_transfer_validates_profile_existence(self, mock_load_profiles, cli_runner):
        """Test that transfer validates that profiles exist."""
        mock_load_profiles.return_value = {"staging": MagicMock(), "prod": MagicMock()}

        # Non-existent source profile
        result = cli_runner.invoke(
            transfer_app,
            ["--from", "nonexistent", "--to", "prod", "--force"],
        )
        assert result.exit_code != 0
        assert "Source profile 'nonexistent' not found" in result.output

        # Non-existent target profile
        result = cli_runner.invoke(
            transfer_app,
            ["--from", "staging", "--to", "nonexistent", "--force"],
        )
        assert result.exit_code != 0
        assert "Target profile 'nonexistent' not found" in result.output

    @patch("prefect.cli.transfer.load_profiles")
    def test_transfer_prevents_same_profile(self, mock_load_profiles, cli_runner):
        """Test that transfer prevents using the same profile as source and target."""
        mock_load_profiles.return_value = {"staging": MagicMock()}

        result = cli_runner.invoke(
            transfer_app,
            ["--from", "staging", "--to", "staging", "--force"],
        )
        assert result.exit_code != 0
        assert "Source and target profiles must be different" in result.output

    @patch("prefect.cli.transfer.load_profiles")
    def test_transfer_exclude_all_resources(self, mock_load_profiles, cli_runner):
        """Test that transfer fails when all resource types are excluded."""
        mock_load_profiles.return_value = {"staging": MagicMock(), "prod": MagicMock()}

        # Exclude all resource types
        exclude_args = []
        for resource_type in ResourceType:
            exclude_args.extend(["--exclude", resource_type.value])

        result = cli_runner.invoke(
            transfer_app,
            ["--from", "staging", "--to", "prod", "--force"] + exclude_args,
        )
        assert result.exit_code != 0
        assert "All resource types have been excluded" in result.output

    @patch("prefect.cli.transfer.load_profiles")
    @patch("prefect.cli.transfer.use_profile")
    @patch("prefect.cli.transfer.get_client")
    def test_transfer_dry_run_mode(
        self,
        mock_get_client,
        mock_use_profile,
        mock_load_profiles,
        cli_runner,
    ):
        """Test that dry run mode displays preview without making changes."""
        mock_load_profiles.return_value = {"staging": MagicMock(), "prod": MagicMock()}
        mock_use_profile.return_value.__aenter__ = AsyncMock()
        mock_use_profile.return_value.__aexit__ = AsyncMock()
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_client.return_value.__aexit__ = AsyncMock()

        result = cli_runner.invoke(
            transfer_app,
            ["--from", "staging", "--to", "prod", "--dry-run"],
        )

        # In dry run mode, it should complete successfully and show the dry run message
        assert "DRY RUN MODE" in result.output
        assert "Dry run completed successfully" in result.output

    @patch("prefect.cli.transfer.load_profiles")
    def test_transfer_confirmation_prompt(self, mock_load_profiles, cli_runner):
        """Test that transfer shows confirmation prompt without --force."""
        mock_load_profiles.return_value = {"staging": MagicMock(), "prod": MagicMock()}

        # Simulate user saying "no" to confirmation
        result = cli_runner.invoke(
            transfer_app,
            ["--from", "staging", "--to", "prod"],
            input="n\n",
        )

        assert result.exit_code != 0
        assert "Do you want to proceed with the transfer?" in result.output
        assert "Transfer cancelled" in result.output

    @patch("prefect.cli.transfer.load_profiles")
    @patch("prefect.cli.transfer.use_profile")
    @patch("prefect.cli.transfer.get_client")
    def test_transfer_skips_confirmation_with_force(
        self,
        mock_get_client,
        mock_use_profile,
        mock_load_profiles,
        cli_runner,
    ):
        """Test that --force flag skips confirmation prompt."""
        mock_load_profiles.return_value = {"staging": MagicMock(), "prod": MagicMock()}
        mock_use_profile.return_value.__aenter__ = AsyncMock()
        mock_use_profile.return_value.__aexit__ = AsyncMock()
        mock_client = AsyncMock()
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_client.return_value.__aexit__ = AsyncMock()

        result = cli_runner.invoke(
            transfer_app,
            ["--from", "staging", "--to", "prod", "--force"],
        )

        # Should not contain confirmation prompt
        assert "Do you want to proceed with the transfer?" not in result.output


class TestResourceType:
    """Tests for the ResourceType enum."""

    def test_resource_type_values(self):
        """Test that ResourceType has expected values."""
        assert ResourceType.BLOCKS.value == "blocks"
        assert ResourceType.DEPLOYMENTS.value == "deployments"
        assert ResourceType.WORK_POOLS.value == "work-pools"
        assert ResourceType.VARIABLES.value == "variables"
        assert ResourceType.CONCURRENCY_LIMITS.value == "concurrency-limits"
        assert ResourceType.AUTOMATIONS.value == "automations"

    def test_resource_type_is_string_enum(self):
        """Test that ResourceType values can be used as strings."""
        assert str(ResourceType.BLOCKS) == "blocks"
        assert ResourceType("blocks") == ResourceType.BLOCKS
