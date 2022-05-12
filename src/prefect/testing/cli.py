import textwrap
from typing import Any, List

import pytest
import rich
from typer.testing import CliRunner, Result

import prefect.cli
from prefect.cli import app


def invoke_and_assert(
    command: List[str],
    expected_output: str = None,
    expected_code: int = 0,
    echo: bool = True,
    user_input=None,
) -> Result:
    """
    Test utility for the Prefect CLI application, asserts exact match with CLI output.
    """
    runner = CliRunner()
    result = runner.invoke(app, command, catch_exceptions=False, input=user_input)

    if echo:
        print(result.stdout)

    if expected_code is not None:
        assert (
            result.exit_code == expected_code
        ), f"Actual exit code: {result.exit_code!r}"

    if expected_output is not None:
        output = result.stdout.strip()
        expected_output = textwrap.dedent(expected_output).strip()

        print("------ expected ------")
        print(expected_output)
        print()

        assert output == expected_output

    return result


def invoke_and_assert_in(
    command: List[str],
    desired_contents: str = None,
    expected_code: int = 0,
    echo: bool = True,
    user_input=None,
) -> Result:
    """
    Test utility for the Prefect CLI application, asserts string in CLI output.
    """
    runner = CliRunner()
    result = runner.invoke(app, command, catch_exceptions=False, input=user_input)

    if echo:
        print("------ actual ------")
        print(result.stdout)

    if expected_code is not None:
        assert (
            result.exit_code == expected_code
        ), f"Actual exit code: {result.exit_code!r}"

    if desired_contents is not None:
        output = result.stdout.strip()
        desired_contents = textwrap.dedent(desired_contents).strip()

        print("------ expected ------")
        print(desired_contents)
        print()

        assert desired_contents in output, "Desired contents not found in CLI ouput"

    return result


def invoke_and_assert_not_in(
    command: List[str],
    undesired_contents: str = None,
    expected_code: int = 0,
    echo: bool = True,
    user_input=None,
) -> Result:
    """
    Test utility for the Prefect CLI application, asserts string not in CLI output.
    """
    runner = CliRunner()
    result = runner.invoke(app, command, catch_exceptions=False, input=user_input)

    if echo:
        print("------ actual ------")
        print(result.stdout)

    if expected_code is not None:
        assert (
            result.exit_code == expected_code
        ), f"Actual exit code: {result.exit_code!r}"

    if undesired_contents is not None:
        output = result.stdout.strip()
        undesired_contents = textwrap.dedent(undesired_contents).strip()

        print("------ expected ------")
        print(undesired_contents)
        print()

        assert undesired_contents not in output, "Undesired contents found in CLI ouput"

    return result


@pytest.fixture
def disable_terminal_wrapping(monkeypatch):
    """
    Sometimes, line wrapping makes it hard to make deterministic assertions about the
    output of a CLI command. Wrapping can be disabled by using this fixture.
    """
    monkeypatch.setattr(
        "prefect.cli.root.app.console", rich.console.Console(soft_wrap=True)
    )
