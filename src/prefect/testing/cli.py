import contextlib
import textwrap
from typing import Iterable, List, Union

from typer.testing import CliRunner, Result

from prefect.cli import app
from prefect.utilities.asyncutils import in_async_main_thread


def check_contains(cli_result: Result, content: str, should_contain: bool):
    """
    Utility function to see if content is or is not in a CLI result.

    Args:
        should_contain: if True, checks that content is in cli_result,
            if False, checks that content is not in cli_result
    """
    output = cli_result.stdout.strip()
    content = textwrap.dedent(content).strip()

    if should_contain:
        section_heading = "------ desired content ------"
    else:
        section_heading = "------ undesired content ------"

    print(section_heading)
    print(content)
    print()

    if len(content) > 20:
        display_content = content[:20] + "..."
    else:
        display_content = content

    if should_contain:
        assert (
            content in output
        ), f"Desired contents {display_content!r} not found in CLI ouput"
    else:
        assert (
            content not in output
        ), f"Undesired contents {display_content!r} found in CLI ouput"


def invoke_and_assert(
    command: List[str],
    user_input: str = None,
    expected_output: str = None,
    expected_output_contains: Union[str, Iterable[str]] = None,
    expected_output_does_not_contain: Union[str, Iterable[str]] = None,
    expected_line_count: int = None,
    expected_code: int = 0,
    echo: bool = True,
    temp_dir: str = None,
) -> Result:
    """
    Test utility for the Prefect CLI application, asserts exact match with CLI output.

    Args:
        command: Command passed to the Typer CliRunner
        user_input: User input passed to the Typer CliRunner when running interactive
            commands.
        expected_output: Used when you expect the CLI output to be an exact match with
            the provided text.
        expected_output_contains: Used when you expect the CLI output to contain the
            string or strings.
        expected_output_does_not_contain: Used when you expect the CLI output to not
            contain the string or strings.
        expected_code: 0 if we expect the app to exit cleanly, else 1 if we expect
            the app to exit with an error.
        temp_dir: if provided, the CLI command will be run with this as its present
            working directory.
    """
    if in_async_main_thread():
        raise RuntimeError(
            textwrap.dedent(
                """
                You cannot run `invoke_and_assert` directly from an async 
                function. If you need to run `invoke_and_assert` in an async 
                function, run it with `run_sync_in_worker_thread`. 

                Example: 
                    run_sync_in_worker_thread(
                        invoke_and_assert, 
                        command=['my', 'command'],
                        expected_code=0,
                    )
                """
            )
        )
    runner = CliRunner()
    if temp_dir:
        ctx = runner.isolated_filesystem(temp_dir=temp_dir)
    else:
        ctx = contextlib.nullcontext()

    with ctx:
        result = runner.invoke(app, command, catch_exceptions=False, input=user_input)

    if echo:
        print("------ CLI output ------")
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

    if expected_output_contains is not None:
        if isinstance(expected_output_contains, str):
            check_contains(result, expected_output_contains, should_contain=True)
        else:
            for contents in expected_output_contains:
                check_contains(result, contents, should_contain=True)

    if expected_output_does_not_contain is not None:
        if isinstance(expected_output_does_not_contain, str):
            check_contains(
                result, expected_output_does_not_contain, should_contain=False
            )
        else:
            for contents in expected_output_does_not_contain:
                check_contains(result, contents, should_contain=False)

    if expected_line_count is not None:
        line_count = len(result.stdout.splitlines())
        assert (
            expected_line_count == line_count
        ), f"Expected {expected_line_count} lines of CLI output, only {line_count} lines present"

    return result


@contextlib.contextmanager
def temporary_console_width(console, width):
    original = console.width

    try:
        console._width = width
        yield
    finally:
        console._width = original
