"""Tests for the root CLI app in `prefect.cli._app`."""

import sys

import pytest

from prefect.cli._app import _normalize_command_names, app
from prefect.testing.cli import invoke_and_assert


class TestUsageErrorExitCode:
    @pytest.mark.parametrize(
        "command",
        [
            ["definitely-not-a-command"],
            ["config", "view", "--definitely-not-an-option"],
            ["work-pool", "create"],
        ],
    )
    def test_usage_error_exits_with_code_1(self, command: list[str]):
        """cyclopts exits with 2 on usage errors; the Prefect CLI exits with 1."""
        invoke_and_assert(command, expected_code=1)

    def test_entrypoint_usage_error_exits_with_code_1(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(sys, "argv", ["prefect", "definitely-not-a-command"])
        with pytest.raises(SystemExit) as exc_info:
            app()
        assert exc_info.value.code == 1


class TestCommandNameMatching:
    @pytest.mark.parametrize(
        ("tokens", "expected"),
        [
            (("work_pool", "ls"), ("work-pool", "ls")),
            (("WorkPool", "LS"), ("work-pool", "ls")),
            (("flows", "ls"), ("flows", "ls")),
            (
                ("work_pool", "set_concurrency_limit", "my_pool", "5"),
                ("work-pool", "set-concurrency-limit", "my_pool", "5"),
            ),
            (("work_pool", "--help"), ("work-pool", "--help")),
            (("work-pool", "--json", "l_s"), ("work-pool", "--json", "l_s")),
            (("definitely-not-a-command",), ("definitely-not-a-command",)),
        ],
    )
    def test_normalize_command_names(
        self, tokens: tuple[str, ...], expected: tuple[str, ...]
    ):
        assert _normalize_command_names(tokens) == expected

    def test_runs_command_given_with_underscores(self):
        invoke_and_assert(
            ["work_pool", "set_concurrency_limit", "--help"],
            expected_output_contains="Usage: prefect work-pool set-concurrency-limit",
        )

    def test_unmatched_command_is_a_usage_error(self):
        invoke_and_assert(
            ["work_pol", "ls"],
            expected_code=1,
            expected_output_contains='Unknown command "work_pol"',
        )
