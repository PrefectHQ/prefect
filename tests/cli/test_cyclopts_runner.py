"""Tests for the CycloptsCliRunner.

These tests validate that the runner correctly captures output, handles
interactive prompts, isolates global state, and returns proper exit codes.
"""

import os
import sys

import pytest


@pytest.fixture
def runner():
    from prefect.testing.cli import CycloptsCliRunner

    return CycloptsCliRunner()


class TestOutputCapture:
    def test_captures_stdout(self, runner):
        result = runner.invoke(["config", "view"])
        assert result.exit_code == 0
        assert "PREFECT_PROFILE" in result.stdout

    def test_captures_stderr_separately(self, runner):
        result = runner.invoke(["config", "view"])
        assert isinstance(result.stderr, str)

    def test_exit_code_zero_on_success(self, runner):
        result = runner.invoke(["version"])
        assert result.exit_code == 0
        assert result.exception is None


class TestInteractiveMode:
    """Verify that prompts work correctly when input is provided."""

    def test_confirm_prompt_with_yes(self, runner):
        """Confirm.ask should render the prompt text and accept 'y' input."""
        result = runner.invoke(
            ["profile", "create", "test-runner-profile"],
            input="y\n",
        )
        # The prompt should appear in stdout since is_interactive is True
        assert result.exit_code == 0

    def test_noninteractive_without_input(self, runner):
        """Without input, is_interactive should be False (no TTY stdin)."""
        result = runner.invoke(["config", "view"])
        # Should succeed without prompting
        assert result.exit_code == 0


class TestGlobalStateIsolation:
    """Verify that the runner does not leak state between invocations."""

    def test_stdout_restored(self, runner):
        original_stdout = sys.stdout
        runner.invoke(["config", "view"])
        assert sys.stdout is original_stdout

    def test_stderr_restored(self, runner):
        original_stderr = sys.stderr
        runner.invoke(["config", "view"])
        assert sys.stderr is original_stderr

    def test_stdin_restored(self, runner):
        original_stdin = sys.stdin
        runner.invoke(["config", "view"], input="y\n")
        assert sys.stdin is original_stdin

    def test_columns_env_restored(self, runner):
        original = os.environ.get("COLUMNS")
        runner.invoke(["config", "view"])
        assert os.environ.get("COLUMNS") == original

    def test_console_restored(self, runner):
        import prefect.cli._app as _cli

        original_console = _cli.console
        runner.invoke(["config", "view"])
        assert _cli.console is original_console

    def test_multiple_invocations_isolated(self, runner):
        """Two sequential invocations should not affect each other."""
        result1 = runner.invoke(["config", "view"])
        result2 = runner.invoke(["config", "view"])
        assert result1.exit_code == 0
        assert result2.exit_code == 0
        # Both should produce output (not empty from leaked state)
        assert "PREFECT_PROFILE" in result1.stdout
        assert "PREFECT_PROFILE" in result2.stdout


class TestExitCodes:
    def test_successful_command(self, runner):
        result = runner.invoke(["config", "view"])
        assert result.exit_code == 0

    def test_exception_returns_exit_code_1(self, runner):
        """An unhandled exception should result in exit_code=1."""
        result = runner.invoke(["config", "set", "NONEXISTENT_SETTING=value"])
        assert result.exit_code == 1


class TestResultInterface:
    """Verify the CycloptsResult is compatible with typer's Result."""

    def test_has_stdout(self, runner):
        result = runner.invoke(["version"])
        assert hasattr(result, "stdout")
        assert isinstance(result.stdout, str)

    def test_has_stderr(self, runner):
        result = runner.invoke(["version"])
        assert hasattr(result, "stderr")
        assert isinstance(result.stderr, str)

    def test_has_output(self, runner):
        result = runner.invoke(["version"])
        assert hasattr(result, "output")
        assert result.output == result.stdout

    def test_has_exit_code(self, runner):
        result = runner.invoke(["version"])
        assert hasattr(result, "exit_code")
        assert isinstance(result.exit_code, int)

    def test_has_exception(self, runner):
        result = runner.invoke(["version"])
        assert hasattr(result, "exception")
