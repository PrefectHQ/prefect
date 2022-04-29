import re
import textwrap

import pytest
from typer.testing import CliRunner

import prefect.context
import prefect.settings
from prefect.cli import app
from prefect.settings import (
    PREFECT_LOGGING_ORION_MAX_LOG_SIZE,
    PREFECT_ORION_DATABASE_TIMEOUT,
    PREFECT_PROFILES_PATH,
    temporary_settings,
    use_profile,
)
from prefect.testing.cli import disable_terminal_wrapping, invoke_and_assert

"""
Testing Typer tutorial here: https://typer.tiangolo.com/tutorial/testing/
"""

DEFAULT_STRING = "(from defaults)"
ENV_STRING = "(from env)"
PROFILE_STRING = "(from profile)"

runner = CliRunner()


@pytest.fixture(autouse=True)
def temporary_profiles_path(tmp_path):
    path = tmp_path / "profiles.toml"
    with temporary_settings({PREFECT_PROFILES_PATH: path}):
        yield path


def test_set_while_using_default_profile():
    invoke_and_assert(
        ["config", "set", "PREFECT_LOGGING_LEVEL='DEBUG'"],
        expected_output=(
            """
            Set 'PREFECT_LOGGING_LEVEL' to "'DEBUG'".
            Updated profile 'test-session'.
            """
        ),
    )


def test_view_excludes_unset_settings_by_default():
    """Default values should be hidden by default"""
    res = invoke_and_assert(["config", "view", "--show-sources"])

    config_items = res.stdout.split("\n")
    for item in config_items:
        assert DEFAULT_STRING not in item

    assert res.exit_code == 0


def test_view_with_show_defaults_includes_unset_settings():
    settings = prefect.settings.get_settings_from_env().dict()

    # Force show-sources, because we are relying on it to identify defaults
    res = invoke_and_assert(["config", "view", "--show-defaults", "--show-sources"])

    # Assumes that we will have at least one default setting
    assert DEFAULT_STRING in res.stdout

    # Each setting is on its own line, so if all settings, including defaults
    # are being shown, this should be at least as long as settings
    printed_output = re.split(r"\nP", res.stdout.strip())
    assert len(printed_output) >= len(settings)

    assert res.exit_code == 0


@pytest.mark.usefixtures("disable_terminal_wrapping")
def test_view_shows_setting_sources_by_default(monkeypatch):

    monkeypatch.setenv("PREFECT_ORION_DATABASE_CONNECTION_TIMEOUT", "2.5")

    with prefect.settings.use_profile(
        prefect.settings.Profile(
            name="foo",
            settings={
                PREFECT_ORION_DATABASE_TIMEOUT: 2.0,
                PREFECT_LOGGING_ORION_MAX_LOG_SIZE: 1000001,
            },
        ),
        include_current_context=False,
    ):
        res = invoke_and_assert(["config", "view"])

    lines = res.stdout.splitlines()

    # The first line should not include a source
    assert lines[0] == "PREFECT_PROFILE='foo'"

    for line in lines[1:]:
        # Assert that each line ends with a source
        assert any(
            line.endswith(s) for s in [DEFAULT_STRING, PROFILE_STRING, ENV_STRING]
        ), f"Source missing from line: {line}"

    # Assert that sources are correct
    assert f"PREFECT_ORION_DATABASE_TIMEOUT='2.0' {PROFILE_STRING}" in lines
    assert f"PREFECT_LOGGING_ORION_MAX_LOG_SIZE='1000001' {PROFILE_STRING}" in lines
    assert f"PREFECT_ORION_DATABASE_CONNECTION_TIMEOUT='2.5' {ENV_STRING}" in lines


@pytest.mark.usefixtures("disable_terminal_wrapping")
def test_view_with_hide_sources_excludes_sources():
    with prefect.settings.use_profile(
        prefect.settings.Profile(
            name="foo",
            settings={
                PREFECT_ORION_DATABASE_TIMEOUT: 2.0,
                PREFECT_LOGGING_ORION_MAX_LOG_SIZE: 1000001,
            },
        ),
    ):
        res = invoke_and_assert(["config", "view", "--hide-sources"])

    lines = res.stdout.splitlines()

    for line in lines:
        # Assert that each line does not end with a source
        assert not any(
            line.endswith(s) for s in [DEFAULT_STRING, PROFILE_STRING, ENV_STRING]
        ), f"Source included in line: {line}"
