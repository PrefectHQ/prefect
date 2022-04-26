import re
import textwrap

import pytest
from typer.testing import CliRunner

import prefect.settings
from prefect.cli import app
from prefect.context import profile
from prefect.utilities.testing import temporary_settings

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
    with temporary_settings(PREFECT_PROFILES_PATH=path):
        yield path


def test_defaults_hidden_by_default():
    """Default values should be hidden by default"""
    res = runner.invoke(app, ["config", "view", "--show-sources"])

    config_items = res.stdout.split("\n")
    for item in config_items:
        assert DEFAULT_STRING not in item

    assert res.exit_code == 0


def test_defaults_shown_with_flag():
    settings = prefect.settings.get_settings_from_env().dict()

    # Force show-sources, because we are relying on it to identify defaults
    res = runner.invoke(app, ["config", "view", "--show-defaults", "--show-sources"])

    # Assumes that we will have at least one default setting
    assert DEFAULT_STRING in res.stdout

    # Each setting is on its own line, so if all settings, including defaults
    # are being shown, this should be at least as long as settings
    printed_output = re.split(r"\nP", res.stdout.strip())
    assert len(printed_output) >= len(settings)

    assert res.exit_code == 0


def test_sources_shown_by_default(temporary_profiles_path):
    sources = [DEFAULT_STRING, PROFILE_STRING, ENV_STRING]

    temporary_profiles_path.write_text(
        textwrap.dedent(
            """
            [profiles.foo]
            PREFECT_ORION_DATABASE_TIMEOUT='2.0'
            PREFECT_LOGGING_ORION_MAX_LOG_SIZE='1000001'
            """
        )
    )
    with profile("foo", initialize=False) as ctx:
        ctx.initialize(create_home=False)
        res = runner.invoke(app, ["config", "view"])

    printed_values = re.split(r"\nP", res.stdout.strip())
    printed_values = printed_values[1:]  # First printed element is the prefect profile
    for val in printed_values:
        assert any(s in val for s in sources)

    assert res.exit_code == 0
