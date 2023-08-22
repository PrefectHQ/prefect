import pytest
import rich
import typer
from typer.testing import CliRunner

from prefect.cli.root import app as APP
from prefect.cli.root import is_interactive
from prefect.settings import (
    PREFECT_CLI_PROMPT,
    temporary_settings,
)


@pytest.fixture
def test_app():
    # Ideally we would isolate the test application without mutating the real one
    # but it's not trivial to copy
    app = APP

    @app.command("check-interactive")
    def check_interactive():
        if is_interactive():
            # Use abnormal exit codes so they are not confused with actual errors
            raise typer.Exit(100)
        else:
            raise typer.Exit(200)

    yield app

    # Remove the command
    for command in tuple(app.registered_commands):
        if command.name == "check-interactive":
            app.registered_commands.remove(command)
            break


def get_result(app, options):
    result = CliRunner().invoke(app, options)

    if result.exit_code not in (0, 100, 200):
        print(result.output)
        raise RuntimeError(
            f"Unexpected return code {result.exit_code}"
        ) from result.exception

    return result


def assert_interactive(app, *options):
    assert get_result(app, list(options) + ["check-interactive"]).exit_code == 100


def assert_not_interactive(app, *options):
    assert get_result(app, list(options) + ["check-interactive"]).exit_code == 200


def test_prompt_default_infers_using_rich(test_app):
    if rich.console.Console().is_interactive:
        assert_interactive(test_app)
    else:
        assert_not_interactive(test_app)


def test_prompt_force_true(test_app):
    assert_interactive(test_app, "--prompt")


def test_prompt_force_false(test_app):
    assert_not_interactive(test_app, "--no-prompt")


def test_prompt_force_true_with_setting(test_app):
    with temporary_settings({PREFECT_CLI_PROMPT: True}):
        assert_interactive(test_app)


def test_prompt_force_false_with_setting(test_app):
    with temporary_settings({PREFECT_CLI_PROMPT: False}):
        assert_not_interactive(test_app)


def test_prompt_cli_takes_precendence_over_setting_false(test_app):
    with temporary_settings({PREFECT_CLI_PROMPT: True}):
        assert_not_interactive(test_app, "--no-prompt")


def test_prompt_cli_takes_precendence_over_setting_true(test_app):
    with temporary_settings({PREFECT_CLI_PROMPT: False}):
        assert_interactive(test_app, "--prompt")
