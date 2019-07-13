import click
from click.testing import CliRunner

import prefect
from prefect.cli import cli, config, version


def test_init():
    runner = CliRunner()
    result = runner.invoke(cli)
    assert result.exit_code == 0
    assert (
        "The Prefect CLI for creating, managing, and inspecting your flows."
        in result.output
    )


def test_init_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert (
        "The Prefect CLI for creating, managing, and inspecting your flows."
        in result.output
    )


def test_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert result.output.rstrip() == prefect.__version__


def test_config():
    runner = CliRunner()
    result = runner.invoke(cli, ["config"])
    assert result.exit_code == 0
    assert result.output
