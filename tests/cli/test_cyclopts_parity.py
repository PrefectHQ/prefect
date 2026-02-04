"""
Tests to verify that the cyclopts CLI produces identical output to the typer CLI.

These tests ensure that the CLI migration doesn't change user-visible behavior.
Focus is on functional parity (exit codes, data output) rather than help text formatting.
"""

import os
import re
import subprocess
import sys

import pytest


def run_cli(args: list[str], fast: bool = False) -> subprocess.CompletedProcess:
    """Run the prefect CLI with the given arguments."""
    env = os.environ.copy()
    if fast:
        env["PREFECT_CLI_FAST"] = "1"
    else:
        env.pop("PREFECT_CLI_FAST", None)

    # Use sys.executable -m prefect to ensure we run the repo code
    return subprocess.run(
        [sys.executable, "-m", "prefect"] + args,
        capture_output=True,
        text=True,
        env=env,
    )


def normalize_output(output: str) -> str:
    """Normalize output for comparison, removing known differences."""
    # Remove ANSI color codes
    output = re.sub(r"\x1b\[[0-9;]*m", "", output)

    # Normalize whitespace
    output = re.sub(r" +\n", "\n", output)
    output = re.sub(r"\n+", "\n", output)

    return output.strip()


@pytest.fixture
def skip_if_cyclopts_not_installed():
    """Skip test if cyclopts is not installed."""
    try:
        import cyclopts  # noqa: F401
    except ImportError:
        pytest.skip(
            "cyclopts not installed (install with: pip install prefect[fast-cli])"
        )


class TestConfigCommandParity:
    """Test that config commands produce equivalent output in both CLI modes."""

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    @pytest.mark.parametrize(
        "args",
        [
            ["config", "--help"],
            ["config", "view", "--help"],
            ["config", "set", "--help"],
            ["config", "unset", "--help"],
            ["config", "validate", "--help"],
        ],
    )
    def test_help_exits_successfully(self, args: list[str]):
        """Verify help commands exit successfully in both modes."""
        typer_result = run_cli(args, fast=False)
        cyclopts_result = run_cli(args, fast=True)

        assert typer_result.returncode == 0, f"Typer failed: {typer_result.stderr}"
        assert cyclopts_result.returncode == 0, (
            f"Cyclopts failed: {cyclopts_result.stderr}"
        )

        # Both should produce non-empty output
        assert typer_result.stdout.strip(), "Typer produced empty output"
        assert cyclopts_result.stdout.strip(), "Cyclopts produced empty output"

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_config_view_output_parity(self):
        """Verify config view produces equivalent settings output."""
        typer_result = run_cli(["config", "view"], fast=False)
        cyclopts_result = run_cli(["config", "view"], fast=True)

        assert typer_result.returncode == 0, f"Typer failed: {typer_result.stderr}"
        assert cyclopts_result.returncode == 0, (
            f"Cyclopts failed: {cyclopts_result.stderr}"
        )

        typer_out = normalize_output(typer_result.stdout)
        cyclopts_out = normalize_output(cyclopts_result.stdout)

        # Both should show PREFECT_PROFILE
        assert "PREFECT_PROFILE" in typer_out
        assert "PREFECT_PROFILE" in cyclopts_out

        # Extract setting names (PREFECT_*=)
        setting_pattern = re.compile(r"^(PREFECT_\w+)=", re.MULTILINE)
        typer_settings = set(setting_pattern.findall(typer_out))
        cyclopts_settings = set(setting_pattern.findall(cyclopts_out))

        assert typer_settings == cyclopts_settings, (
            f"Settings differ:\n"
            f"Typer only: {typer_settings - cyclopts_settings}\n"
            f"Cyclopts only: {cyclopts_settings - typer_settings}"
        )

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_config_validate_output_parity(self):
        """Verify config validate produces equivalent output."""
        typer_result = run_cli(["config", "validate"], fast=False)
        cyclopts_result = run_cli(["config", "validate"], fast=True)

        # Same exit code
        assert typer_result.returncode == cyclopts_result.returncode

        typer_out = normalize_output(typer_result.stdout)
        cyclopts_out = normalize_output(cyclopts_result.stdout)

        # Both should indicate validity status consistently
        if "valid" in typer_out.lower():
            assert "valid" in cyclopts_out.lower()


class TestExitCodeParity:
    """Test that exit codes match between CLI modes."""

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_help_exit_code(self):
        """--help should exit 0 in both modes."""
        typer = run_cli(["--help"], fast=False)
        cyclopts = run_cli(["--help"], fast=True)
        assert typer.returncode == 0
        assert cyclopts.returncode == 0

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_invalid_command_exit_code(self):
        """Invalid commands should exit non-zero in both modes."""
        typer = run_cli(["notarealcommand"], fast=False)
        cyclopts = run_cli(["notarealcommand"], fast=True)
        assert typer.returncode != 0
        assert cyclopts.returncode != 0

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_config_set_missing_args_exit_code(self):
        """config set without args should exit non-zero in both modes."""
        typer = run_cli(["config", "set"], fast=False)
        cyclopts = run_cli(["config", "set"], fast=True)
        # Both should fail when no settings provided
        assert typer.returncode != 0
        assert cyclopts.returncode != 0
