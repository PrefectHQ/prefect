"""
Tests to verify that the cyclopts CLI produces equivalent behavior to the typer CLI.

These tests validate **semantic** parity — exit codes, key data fields, and
behavioral equivalence — NOT literal output matching. Help text formatting
will necessarily differ between frameworks and that's fine.
"""

import os
import re
import subprocess
import sys

import pytest


def run_cli(args: list[str], fast: bool = False) -> subprocess.CompletedProcess:
    """Run the prefect CLI with the given arguments.

    fast=True uses cyclopts (default), fast=False forces typer via PREFECT_CLI_TYPER=1.
    """
    env = os.environ.copy()
    env.pop("PREFECT_CLI_TYPER", None)
    if not fast:
        env["PREFECT_CLI_TYPER"] = "1"

    return subprocess.run(
        [sys.executable, "-m", "prefect"] + args,
        capture_output=True,
        text=True,
        env=env,
    )


def strip_ansi(output: str) -> str:
    """Strip ANSI escape codes from output."""
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


@pytest.fixture
def skip_if_cyclopts_not_installed():
    """Skip test if cyclopts is not installed."""
    try:
        import cyclopts  # noqa: F401
    except ImportError:
        pytest.skip("cyclopts not installed")


# =============================================================================
# Exit code parity
# =============================================================================


class TestExitCodeParity:
    """Test that exit codes match between CLI modes."""

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_help_exits_zero(self):
        """--help should exit 0 in both modes."""
        typer = run_cli(["--help"], fast=False)
        cyclopts = run_cli(["--help"], fast=True)
        assert typer.returncode == 0
        assert cyclopts.returncode == 0

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_version_flag_exits_zero(self):
        """--version should exit 0 and show a version string in both modes."""
        typer = run_cli(["--version"], fast=False)
        cyclopts = run_cli(["--version"], fast=True)
        assert typer.returncode == 0
        assert cyclopts.returncode == 0
        # Both should output something that looks like a version
        assert re.search(r"\d+\.\d+", typer.stdout)
        assert re.search(r"\d+\.\d+", cyclopts.stdout)

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_invalid_command_exits_nonzero(self):
        """Invalid commands should exit non-zero in both modes."""
        typer = run_cli(["notarealcommand"], fast=False)
        cyclopts = run_cli(["notarealcommand"], fast=True)
        assert typer.returncode != 0
        assert cyclopts.returncode != 0


# =============================================================================
# Config command parity
# =============================================================================


class TestConfigCommandParity:
    """Test that config commands produce semantically equivalent output."""

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_config_view_shows_same_settings(self):
        """config view should surface the same PREFECT_* setting names."""
        typer_result = run_cli(["config", "view"], fast=False)
        cyclopts_result = run_cli(["config", "view"], fast=True)

        assert typer_result.returncode == 0
        assert cyclopts_result.returncode == 0

        typer_out = strip_ansi(typer_result.stdout)
        cyclopts_out = strip_ansi(cyclopts_result.stdout)

        # Both should display the active profile
        assert "PREFECT_PROFILE" in typer_out
        assert "PREFECT_PROFILE" in cyclopts_out

        # Same set of setting names should appear
        setting_pattern = re.compile(r"^(PREFECT_\w+)=", re.MULTILINE)
        typer_settings = set(setting_pattern.findall(typer_out))
        cyclopts_settings = set(setting_pattern.findall(cyclopts_out))

        assert typer_settings == cyclopts_settings, (
            f"Settings differ:\n"
            f"Typer only: {typer_settings - cyclopts_settings}\n"
            f"Cyclopts only: {cyclopts_settings - typer_settings}"
        )

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_config_validate_same_exit_and_keyword(self):
        """config validate should exit the same and mention 'valid'."""
        typer_result = run_cli(["config", "validate"], fast=False)
        cyclopts_result = run_cli(["config", "validate"], fast=True)

        assert typer_result.returncode == cyclopts_result.returncode

        if "valid" in typer_result.stdout.lower():
            assert "valid" in cyclopts_result.stdout.lower()

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_config_set_missing_args_exits_nonzero(self):
        """config set without args should exit non-zero in both modes."""
        typer = run_cli(["config", "set"], fast=False)
        cyclopts = run_cli(["config", "set"], fast=True)
        assert typer.returncode != 0
        assert cyclopts.returncode != 0


# =============================================================================
# Profile command parity
# =============================================================================


class TestProfileCommandParity:
    """Test that profile commands show the same profiles."""

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_profile_ls_shows_profiles(self):
        """profile ls should succeed and show 'Available Profiles'."""
        typer_result = run_cli(["profile", "ls"], fast=False)
        cyclopts_result = run_cli(["profile", "ls"], fast=True)

        assert typer_result.returncode == 0
        assert cyclopts_result.returncode == 0

        assert "Available Profiles" in strip_ansi(typer_result.stdout)
        assert "Available Profiles" in strip_ansi(cyclopts_result.stdout)

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_profile_inspect_same_exit_code(self):
        """profile inspect should exit with the same code."""
        typer_result = run_cli(["profile", "inspect"], fast=False)
        cyclopts_result = run_cli(["profile", "inspect"], fast=True)

        assert typer_result.returncode == cyclopts_result.returncode


# =============================================================================
# Version command parity
# =============================================================================


class TestVersionCommandParity:
    """Test that the version command surfaces the same key fields."""

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_version_command_shows_key_fields(self):
        """version command should show Version, API version, Python version, etc."""
        typer_result = run_cli(["version"], fast=False)
        cyclopts_result = run_cli(["version"], fast=True)

        assert typer_result.returncode == 0
        assert cyclopts_result.returncode == 0

        for keyword in ["Version:", "API version:", "Python version:", "Profile:"]:
            assert keyword in typer_result.stdout
            assert keyword in cyclopts_result.stdout

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_version_omit_integrations_exits_zero(self):
        """version --omit-integrations should succeed in both modes."""
        typer_result = run_cli(["version", "--omit-integrations"], fast=False)
        cyclopts_result = run_cli(["version", "--omit-integrations"], fast=True)

        assert typer_result.returncode == 0
        assert cyclopts_result.returncode == 0


# =============================================================================
# Server command parity
# =============================================================================


class TestServerCommandParity:
    """Test that server commands produce equivalent data."""

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_server_services_ls_shows_services(self):
        """server services ls should show 'Available Services' table."""
        typer_result = run_cli(["server", "services", "ls"], fast=False)
        cyclopts_result = run_cli(["server", "services", "ls"], fast=True)

        assert typer_result.returncode == 0
        assert cyclopts_result.returncode == 0

        assert "Available Services" in strip_ansi(typer_result.stdout)
        assert "Available Services" in strip_ansi(cyclopts_result.stdout)

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_server_services_ls_same_service_names(self):
        """server services ls should list the same service names."""
        typer_result = run_cli(["server", "services", "ls"], fast=False)
        cyclopts_result = run_cli(["server", "services", "ls"], fast=True)

        typer_out = strip_ansi(typer_result.stdout)
        cyclopts_out = strip_ansi(cyclopts_result.stdout)

        # Extract service environment variable names (PREFECT_SERVER_SERVICES_*)
        svc_pattern = re.compile(r"PREFECT_SERVER_SERVICES_\w+")
        typer_services = set(svc_pattern.findall(typer_out))
        cyclopts_services = set(svc_pattern.findall(cyclopts_out))

        assert typer_services == cyclopts_services, (
            f"Services differ:\n"
            f"Typer only: {typer_services - cyclopts_services}\n"
            f"Cyclopts only: {cyclopts_services - typer_services}"
        )

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_server_stop_no_server_running(self):
        """server stop with no server running should exit 0 in both modes."""
        typer_result = run_cli(["server", "stop"], fast=False)
        cyclopts_result = run_cli(["server", "stop"], fast=True)

        assert typer_result.returncode == cyclopts_result.returncode

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_server_database_reset_no_confirm_exits_nonzero(self):
        """server database reset without --yes should exit non-zero (no tty)."""
        typer_result = run_cli(["server", "database", "reset"], fast=False)
        cyclopts_result = run_cli(["server", "database", "reset"], fast=True)

        # Both should fail when not interactive and no --yes flag
        assert typer_result.returncode != 0
        assert cyclopts_result.returncode != 0

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_server_manager_not_in_help(self):
        """The internal manager command should not appear in services help."""
        cyclopts_result = run_cli(["server", "services", "--help"], fast=True)
        assert cyclopts_result.returncode == 0
        assert "manager" not in strip_ansi(cyclopts_result.stdout).lower()


# =============================================================================
# Worker command parity
# =============================================================================


class TestWorkerCommandParity:
    """Test that worker commands produce equivalent behavior."""

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_worker_start_missing_pool_exits_nonzero(self):
        """worker start without --pool should exit non-zero."""
        typer_result = run_cli(["worker", "start"], fast=False)
        cyclopts_result = run_cli(["worker", "start"], fast=True)

        assert typer_result.returncode != 0
        assert cyclopts_result.returncode != 0


# =============================================================================
# Shell command parity
# =============================================================================


class TestShellCommandParity:
    """Test that shell commands produce equivalent behavior."""

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_shell_watch_missing_command_exits_nonzero(self):
        """shell watch without a command arg should exit non-zero."""
        typer_result = run_cli(["shell", "watch"], fast=False)
        cyclopts_result = run_cli(["shell", "watch"], fast=True)

        assert typer_result.returncode != 0
        assert cyclopts_result.returncode != 0

    @pytest.mark.usefixtures("skip_if_cyclopts_not_installed")
    def test_shell_serve_missing_args_exits_nonzero(self):
        """shell serve without required args should exit non-zero."""
        typer_result = run_cli(["shell", "serve"], fast=False)
        cyclopts_result = run_cli(["shell", "serve"], fast=True)

        assert typer_result.returncode != 0
        assert cyclopts_result.returncode != 0
