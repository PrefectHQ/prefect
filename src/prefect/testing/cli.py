import textwrap
from typing import Iterable, List, Union

import pytest
import rich
from typer.testing import CliRunner, Result

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
    desired_contents: Union[str, Iterable[str]] = None,
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

        def check_contents(content):
            output = result.stdout.strip()
            content = textwrap.dedent(content).strip()

            print("------ expected ------")
            print(content)
            print()

            if len(content) > 15:
                display_content = content[:15] + "..."
            else:
                display_content = content
            assert (
                content in output
            ), f"Desired contents '{display_content} not found in CLI ouput"

        if isinstance(desired_contents, str):
            check_contents(desired_contents)
        else:
            for contents in desired_contents:
                check_contents(contents)

    return result


def invoke_and_assert_not_in(
    command: List[str],
    undesired_contents: Union[str, Iterable[str]] = None,
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

        def check_contents(content):
            output = result.stdout.strip()
            content = textwrap.dedent(content).strip()

            print("------ expected ------")
            print(content)
            print()

            if len(content) > 15:
                display_content = content[:15] + "..."
            else:
                display_content = content
            assert (
                content not in output
            ), f"Undesired contents '{display_content} found in CLI ouput"

        if isinstance(undesired_contents, str):
            check_contents(undesired_contents)
        else:
            for contents in undesired_contents:
                check_contents(contents)

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
