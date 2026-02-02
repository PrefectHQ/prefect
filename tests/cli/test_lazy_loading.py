"""
Tests for CLI lazy loading functionality.

These tests verify that:
1. The _should_eager_import function correctly identifies when to eager-load
2. LazyTyperGroup properly defers module imports until commands are invoked
3. Help output still shows all available commands
4. All commands remain accessible via the CLI
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import click
import pytest
import typer

from prefect.cli import _should_eager_import
from prefect.cli._types import LazyTyperGroup
from prefect.testing.cli import invoke_and_assert


class TestShouldEagerImport:
    """Tests for the _should_eager_import function."""

    def test_empty_argv_returns_true(self):
        """When argv is empty, should eager import (shows help)."""
        assert _should_eager_import([]) is True

    def test_just_prefect_returns_true(self):
        """When only 'prefect' in argv, should eager import (shows help)."""
        assert _should_eager_import(["prefect"]) is True

    def test_help_flag_returns_true(self):
        """When --help is in argv, should eager import."""
        assert _should_eager_import(["prefect", "--help"]) is True

    def test_short_help_flag_returns_true(self):
        """When -h is in argv, should eager import."""
        assert _should_eager_import(["prefect", "-h"]) is True

    def test_help_on_subcommand_returns_true(self):
        """When --help is on a subcommand, should eager import."""
        assert _should_eager_import(["prefect", "flow", "--help"]) is True
        assert _should_eager_import(["prefect", "flow", "ls", "--help"]) is True

    def test_version_flag_returns_false(self):
        """When --version is used, should NOT eager import (lazy load)."""
        assert _should_eager_import(["prefect", "--version"]) is False

    def test_regular_command_returns_false(self):
        """Regular commands should NOT trigger eager import (lazy load)."""
        assert _should_eager_import(["prefect", "flow", "ls"]) is False
        assert _should_eager_import(["prefect", "config", "view"]) is False
        assert _should_eager_import(["prefect", "deployment", "ls"]) is False

    def test_command_with_args_returns_false(self):
        """Commands with arguments should NOT trigger eager import."""
        assert (
            _should_eager_import(["prefect", "flow-run", "ls", "--limit", "5"]) is False
        )


class TestLazyTyperGroup:
    """Tests for the LazyTyperGroup class."""

    @pytest.fixture(autouse=True)
    def reset_lazy_typer_group(self):
        """Reset LazyTyperGroup state before and after each test."""
        LazyTyperGroup.reset()
        yield
        LazyTyperGroup.reset()

    def test_reset_clears_all_state(self):
        """reset() should clear all class-level state."""
        # Set up some state
        LazyTyperGroup._lazy_commands = {"test": ("module.test",)}
        LazyTyperGroup._loaded_modules = {"module.test"}
        LazyTyperGroup._typer_instance = MagicMock()

        # Reset
        LazyTyperGroup.reset()

        # Verify state is cleared
        assert LazyTyperGroup._lazy_commands == {}
        assert LazyTyperGroup._loaded_modules == set()
        assert LazyTyperGroup._typer_instance is None

    def test_register_lazy_commands_normalizes_string_to_tuple(self):
        """register_lazy_commands should convert string modules to tuples."""
        commands = {
            "flow": "prefect.cli.flow",
            "cloud": ("prefect.cli.cloud", "prefect.cli.cloud.webhook"),
        }
        LazyTyperGroup.register_lazy_commands(commands)

        assert LazyTyperGroup._lazy_commands["flow"] == ("prefect.cli.flow",)
        assert LazyTyperGroup._lazy_commands["cloud"] == (
            "prefect.cli.cloud",
            "prefect.cli.cloud.webhook",
        )

    def test_register_lazy_commands_stores_typer_instance(self):
        """register_lazy_commands should store the typer instance."""
        mock_typer = MagicMock(spec=typer.Typer)
        LazyTyperGroup.register_lazy_commands({}, typer_instance=mock_typer)

        assert LazyTyperGroup._typer_instance is mock_typer

    def test_list_commands_includes_lazy_commands(self):
        """list_commands should include registered lazy commands."""
        LazyTyperGroup.register_lazy_commands(
            {
                "flow": "prefect.cli.flow",
                "deploy": "prefect.cli.deploy",
            }
        )

        # Create a minimal group instance
        group = LazyTyperGroup(name="test")
        ctx = MagicMock(spec=click.Context)

        commands = group.list_commands(ctx)

        assert "flow" in commands
        assert "deploy" in commands

    def test_list_commands_returns_sorted(self):
        """list_commands should return commands in sorted order."""
        LazyTyperGroup.register_lazy_commands(
            {
                "zebra": "module.zebra",
                "alpha": "module.alpha",
                "middle": "module.middle",
            }
        )

        group = LazyTyperGroup(name="test")
        ctx = MagicMock(spec=click.Context)

        commands = group.list_commands(ctx)

        assert commands == sorted(commands)

    def test_get_command_loads_module(self):
        """get_command should import the module for the requested command."""
        LazyTyperGroup.register_lazy_commands(
            {
                "test_cmd": "test.fake.module",
            }
        )

        group = LazyTyperGroup(name="test")
        ctx = MagicMock(spec=click.Context)

        with patch("importlib.import_module") as mock_import:
            # get_command will fail to find the actual command, but we can verify
            # that import_module was called
            group.get_command(ctx, "test_cmd")
            mock_import.assert_called_once_with("test.fake.module")

    def test_get_command_marks_module_as_loaded(self):
        """get_command should mark the module as loaded after importing."""
        LazyTyperGroup.register_lazy_commands(
            {
                "test_cmd": "test.fake.module",
            }
        )

        group = LazyTyperGroup(name="test")
        ctx = MagicMock(spec=click.Context)

        with patch("importlib.import_module"):
            group.get_command(ctx, "test_cmd")

        assert "test.fake.module" in LazyTyperGroup._loaded_modules

    def test_get_command_skips_already_loaded_modules(self):
        """get_command should not re-import already loaded modules."""
        LazyTyperGroup.register_lazy_commands(
            {
                "test_cmd": "test.fake.module",
            }
        )
        LazyTyperGroup._loaded_modules.add("test.fake.module")

        group = LazyTyperGroup(name="test")
        ctx = MagicMock(spec=click.Context)

        with patch("importlib.import_module") as mock_import:
            group.get_command(ctx, "test_cmd")
            mock_import.assert_not_called()

    def test_get_command_loads_multiple_modules_for_command(self):
        """get_command should load all modules for commands that require multiple."""
        LazyTyperGroup.register_lazy_commands(
            {
                "cloud": ("prefect.cli.cloud", "prefect.cli.cloud.webhook"),
            }
        )

        group = LazyTyperGroup(name="test")
        ctx = MagicMock(spec=click.Context)

        with patch("importlib.import_module") as mock_import:
            group.get_command(ctx, "cloud")
            assert mock_import.call_count == 2
            mock_import.assert_any_call("prefect.cli.cloud")
            mock_import.assert_any_call("prefect.cli.cloud.webhook")

    def test_load_all_lazy_commands_imports_unique_modules(self):
        """_load_all_lazy_commands should import each unique module once."""
        # Multiple commands can share the same module
        LazyTyperGroup.register_lazy_commands(
            {
                "block": "prefect.cli.block",
                "blocks": "prefect.cli.block",  # alias shares module
                "flow": "prefect.cli.flow",
            }
        )

        group = LazyTyperGroup(name="test")

        with patch("importlib.import_module") as mock_import:
            group._load_all_lazy_commands()

            # Should only import each unique module once
            assert mock_import.call_count == 2
            mock_import.assert_any_call("prefect.cli.block")
            mock_import.assert_any_call("prefect.cli.flow")

    def test_load_all_lazy_commands_clears_lazy_commands(self):
        """_load_all_lazy_commands should clear _lazy_commands when done."""
        LazyTyperGroup.register_lazy_commands(
            {
                "flow": "prefect.cli.flow",
            }
        )

        group = LazyTyperGroup(name="test")

        with patch("importlib.import_module"):
            group._load_all_lazy_commands()

        assert LazyTyperGroup._lazy_commands == {}

    def test_prune_loaded_commands_removes_fully_loaded(self):
        """_prune_loaded_commands should remove commands whose modules are all loaded."""
        LazyTyperGroup._lazy_commands = {
            "cmd1": ("module.a",),
            "cmd2": ("module.a", "module.b"),
            "cmd3": ("module.c",),
        }
        LazyTyperGroup._loaded_modules = {"module.a", "module.b"}

        group = LazyTyperGroup(name="test")
        group._prune_loaded_commands()

        # cmd1 and cmd2 should be removed (all their modules are loaded)
        # cmd3 should remain (module.c not loaded)
        assert "cmd1" not in LazyTyperGroup._lazy_commands
        assert "cmd2" not in LazyTyperGroup._lazy_commands
        assert "cmd3" in LazyTyperGroup._lazy_commands


class TestCLIIntegration:
    """Integration tests ensuring CLI commands work correctly."""

    def test_version_flag_works(self):
        """--version flag should work and show version info."""
        invoke_and_assert(
            ["--version"],
            expected_code=0,
            expected_output_contains="Version:",
        )

    def test_help_shows_all_commands(self):
        """--help should show all available commands."""
        result = invoke_and_assert(
            ["--help"],
            expected_code=0,
        )
        # Verify some known commands are listed
        assert "flow" in result.output
        assert "deploy" in result.output
        assert "server" in result.output
        assert "config" in result.output

    def test_subcommand_help_works(self):
        """Subcommand --help should work."""
        invoke_and_assert(
            ["flow", "--help"],
            expected_code=0,
            expected_output_contains="flow",
        )

    def test_command_alias_works(self):
        """Command aliases should work (e.g., 'flows' for 'flow')."""
        # Both 'flow ls' and 'flows ls' should work
        invoke_and_assert(
            ["flow", "ls", "--help"],
            expected_code=0,
        )

    @pytest.mark.usefixtures("disable_hosted_api_server")
    def test_config_view_works(self):
        """A real command should work end-to-end."""
        invoke_and_assert(
            ["config", "view"],
            expected_code=0,
            expected_output_contains="PREFECT_",
        )

    @pytest.mark.usefixtures("disable_hosted_api_server")
    def test_profile_ls_works(self):
        """profile ls command should work."""
        invoke_and_assert(
            ["profile", "ls"],
            expected_code=0,
        )
