import contextlib
import re
import textwrap
from typing import Iterable, List, Tuple, Union

import readchar
from typer.testing import CliRunner, Result  # type: ignore

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
        ), f"Desired contents {display_content!r} not found in CLI output"
    else:
        assert (
            content not in output
        ), f"Undesired contents {display_content!r} found in CLI output"


def invoke_and_assert(
    command: Union[str, List[str]],
    user_input: Union[str, None] = None,
    prompts_and_responses: List[Union[Tuple[str, str], Tuple[str, str, str]]] = [],
    expected_output: Union[str, None] = None,
    expected_output_contains: Union[str, Iterable[str], None] = None,
    expected_output_does_not_contain: Union[str, Iterable[str], None] = None,
    expected_line_count: Union[int, None] = None,
    expected_code: int = 0,
    echo: bool = True,
    temp_dir: Union[str, None] = None,
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

    if user_input and prompts_and_responses:
        raise ValueError("Cannot provide both user_input and prompts_and_responses")

    if prompts_and_responses:
        user_input = (
            ("\n".join(response for (_, response, *_) in prompts_and_responses) + "\n")
            .replace("↓", readchar.key.DOWN)
            .replace("↑", readchar.key.UP)
        )

    with ctx:
        result = runner.invoke(app, command, catch_exceptions=False, input=user_input)

    if echo:
        print("\n------ CLI output ------")
        print(result.stdout)

    if expected_code is not None:
        assertion_error_message = (
            f"Expected code {expected_code} but got {result.exit_code}\n"
            "Output from CLI command:\n"
            "-----------------------\n"
            f"{result.stdout}"
        )
        assert result.exit_code == expected_code, assertion_error_message

    if expected_output is not None:
        output = result.stdout.strip()
        expected_output = textwrap.dedent(expected_output).strip()

        compare_string = (
            "------ expected ------\n"
            f"{expected_output}\n"
            "------ actual ------\n"
            f"{output}\n"
            "------ end ------\n"
        )
        assert output == expected_output, compare_string

    if prompts_and_responses:
        output = result.stdout.strip()
        cursor = 0

        for item in prompts_and_responses:
            prompt = item[0]
            selected_option = item[2] if len(item) == 3 else None

            prompt_re = rf"{re.escape(prompt)}.*?"
            if not selected_option:
                # If we're not prompting for a table, then expect that the
                # prompt ends with a colon.
                prompt_re += ":"

            match = re.search(prompt_re, output[cursor:])
            if not match:
                raise AssertionError(f"Prompt '{prompt}' not found in CLI output")
            cursor = cursor + match.end()

            if selected_option:
                option_re = re.escape(f"│ >  │ {selected_option}")
                match = re.search(option_re, output[cursor:])
                if not match:
                    raise AssertionError(
                        f"Option '{selected_option}' not found after prompt '{prompt}'"
                    )
                cursor = cursor + match.end()

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
        assert expected_line_count == line_count, (
            f"Expected {expected_line_count} lines of CLI output, only"
            f" {line_count} lines present"
        )

    return result


@contextlib.contextmanager
def temporary_console_width(console, width):
    original = console.width

    try:
        console._width = width
        yield
    finally:
        console._width = original
