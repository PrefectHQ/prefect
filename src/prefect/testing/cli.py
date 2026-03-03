from __future__ import annotations

import contextlib
import getpass
import io
import os
import re
import sys
import textwrap
import warnings
from typing import Iterable

import readchar
from rich.console import Console

# Regex pattern to match ANSI escape codes
_ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape codes from text.

    This is necessary because Typer/Rich may output ANSI codes in CI environments
    (e.g., GitHub Actions) even when Click's CliRunner has color=False, due to
    Typer's terminal detection logic.
    """
    return _ANSI_ESCAPE_PATTERN.sub("", text)


class _TTYStringIO(io.StringIO):
    """A StringIO that reports isatty()=True.

    Rich's Console.is_interactive checks file.isatty() to decide whether to
    show prompts.  By emulating a TTY, any Console created while sys.stdout
    points to this buffer will behave interactively — matching real terminal
    behavior and allowing Confirm.ask / Prompt.ask to work correctly.
    """

    def isatty(self) -> bool:
        return True


class CycloptsResult:
    """Result of a cyclopts CLI invocation.

    Compatible with typer's Result so existing invoke_and_assert callers
    can work with either runner without changes.
    """

    def __init__(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        exception: BaseException | None,
    ):
        self.stdout = stdout
        self.stderr = stderr
        # Click's CliRunner merges stdout and stderr into one stream.
        # Match that behavior so ``result.output`` always contains both.
        self.output: str = stdout + stderr
        self.exit_code = exit_code
        self.exception = exception


class CycloptsCliRunner:
    """In-process test runner for the cyclopts CLI.

    Analogous to Click's CliRunner: captures stdout/stderr, simulates stdin,
    emulates a TTY for Rich Console interactive mode, and isolates global
    state between invocations.

    Design principles:
    - Use a TTY-emulating StringIO as sys.stdout so that Rich Console
      instances (which resolve sys.stdout dynamically via their ``file``
      property) write to our capture buffer AND report is_interactive=True.
    - Redirect sys.stdin to a StringIO for prompt input.
    - Save and restore all mutated global state (sys.stdout/stderr/stdin,
      os.environ["COLUMNS"], the cyclopts app's global console) in a
      try/finally block.
    - Catch SystemExit to extract exit codes without terminating the process.

    Not thread-safe (mutates interpreter globals), but safe with pytest-xdist
    which forks separate worker processes.
    """

    def invoke(
        self,
        args: str | list[str],
        input: str | None = None,
    ) -> CycloptsResult:
        """Invoke the cyclopts CLI with the given arguments.

        Args:
            args: Command-line arguments (e.g. ["config", "view"]).
            input: Simulated stdin content for interactive prompts.

        Returns:
            CycloptsResult with captured stdout, stderr, exit_code, and
            any exception that occurred.
        """
        import prefect.cli._app as _cli
        from prefect.cli._app import _app, _normalize_top_level_flags

        if isinstance(args, str):
            import shlex

            args = shlex.split(args)
        else:
            # Ensure all args are strings (tests may pass integers).
            # Drop None values and their preceding --flag, matching
            # Click's CliRunner which passes None through to the parser
            # as "no value" (the option keeps its default).
            cleaned: list[str] = []
            for a in args:
                if a is None:
                    # Drop the preceding --flag too, if present
                    if cleaned and cleaned[-1].startswith("--"):
                        cleaned.pop()
                else:
                    cleaned.append(str(a))
            args = cleaned

        # Emulate a TTY only when input is provided (interactive tests).
        # Without input, use plain StringIO (isatty()=False) so that
        # Rich Console.is_interactive is False — matching Click's CliRunner
        # behavior and suppressing interactive prompts in non-interactive tests.
        if input is not None:
            stdout_buf = _TTYStringIO()
            stderr_buf = _TTYStringIO()
        else:
            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()
        exit_code = 0
        exception: BaseException | None = None

        # Save all global state we're about to mutate.
        saved_stdout = sys.stdout
        saved_stderr = sys.stderr
        saved_stdin = sys.stdin
        saved_columns = os.environ.get("COLUMNS")
        saved_console = _cli.console

        try:
            sys.stdout = stdout_buf  # type: ignore[assignment]
            sys.stderr = stderr_buf  # type: ignore[assignment]
            if input is not None:
                sys.stdin = io.StringIO(input)  # type: ignore[assignment]
            else:
                sys.stdin = io.StringIO()  # type: ignore[assignment]
            # Wide terminal prevents Rich from wrapping long lines, which
            # would cause brittle assertions on output content.
            os.environ["COLUMNS"] = "500"

            # Suppress getpass warnings — like Click's CliRunner, our
            # StringIO stdin doesn't support terminal echo control.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", getpass.GetPassWarning)
                _app.meta(_normalize_top_level_flags(args))

        except SystemExit as exc:
            exit_code = (
                exc.code if isinstance(exc.code, int) else (1 if exc.code else 0)
            )
        finally:
            sys.stdout = saved_stdout
            sys.stderr = saved_stderr
            sys.stdin = saved_stdin
            _cli.console = saved_console
            if saved_columns is None:
                os.environ.pop("COLUMNS", None)
            else:
                os.environ["COLUMNS"] = saved_columns

        return CycloptsResult(
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
            exit_code=exit_code,
            exception=exception,
        )


def check_contains(
    cli_result: CycloptsResult, content: str, should_contain: bool
) -> None:
    """
    Utility function to see if content is or is not in a CLI result.

    Args:
        should_contain: if True, checks that content is in cli_result,
            if False, checks that content is not in cli_result
    """
    stdout_output = _strip_ansi_codes(cli_result.stdout.strip())

    # Try to get stderr, but handle the case where it's not captured separately
    stderr_output = ""
    try:
        stderr_output = _strip_ansi_codes(getattr(cli_result, "stderr", "").strip())
    except ValueError:
        # In some Click/Typer versions, stderr is not separately captured
        pass

    # Combine both stdout and stderr for checking
    output = stdout_output + stderr_output

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
        assert content in output, (
            f"Desired contents {display_content!r} not found in CLI output"
        )
    else:
        assert content not in output, (
            f"Undesired contents {display_content!r} found in CLI output"
        )


def invoke_and_assert(
    command: str | list[str],
    user_input: str | None = None,
    prompts_and_responses: list[tuple[str, str] | tuple[str, str, str]] | None = None,
    expected_output: str | None = None,
    expected_output_contains: str | Iterable[str] | None = None,
    expected_output_does_not_contain: str | Iterable[str] | None = None,
    expected_line_count: int | None = None,
    expected_code: int | None = 0,
    echo: bool = True,
    temp_dir: str | None = None,
) -> CycloptsResult:
    """
    Test utility for the Prefect CLI application.

    Uses CycloptsCliRunner for in-process invocation with proper I/O
    isolation.

    Args:
        command: Command-line arguments (string or list of strings).
        user_input: Simulated stdin for interactive commands.
        prompts_and_responses: List of (prompt, response[, selected_option])
            tuples for interactive commands.
        expected_output: Assert exact match with CLI output.
        expected_output_contains: Assert CLI output contains this string or
            each string in the iterable.
        expected_output_does_not_contain: Assert CLI output does not contain
            this string or any string in the iterable.
        expected_line_count: Assert the number of output lines.
        expected_code: Expected exit code (default 0).
        echo: Print CLI output for debugging (default True).
        temp_dir: Run the command in this directory.
    """
    if user_input and prompts_and_responses:
        raise ValueError("Cannot provide both user_input and prompts_and_responses")

    cyclopts_input = user_input
    if not cyclopts_input and prompts_and_responses:
        cyclopts_input = (
            "\n".join(response for (_, response, *_) in prompts_and_responses) + "\n"
        )
        cyclopts_input = cyclopts_input.replace("↓", readchar.key.DOWN).replace(
            "↑", readchar.key.UP
        )

    saved_cwd = os.getcwd()
    if temp_dir:
        os.chdir(temp_dir)

    runner = CycloptsCliRunner()
    try:
        result = runner.invoke(command, input=cyclopts_input)
    finally:
        if temp_dir:
            os.chdir(saved_cwd)

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
def temporary_console_width(console: Console, width: int):
    original = console.width

    try:
        console._width = width  # type: ignore
        yield
    finally:
        console._width = original  # type: ignore
