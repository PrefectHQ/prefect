from unittest.mock import MagicMock

import click
import requests
from click.testing import CliRunner

import prefect
from prefect.cli.summarize import summarize


def test_summarize_init():
    runner = CliRunner()
    result = runner.invoke(summarize)
    assert result.exit_code == 0
    assert "Summarize Prefect Cloud metadata. *Not yet implemented*" in result.output


def test_summarize_help():
    runner = CliRunner()
    result = runner.invoke(summarize, ["--help"])
    assert result.exit_code == 0
    assert "Summarize Prefect Cloud metadata. *Not yet implemented*" in result.output


def test_summarize_flow_runs():
    runner = CliRunner()
    result = runner.invoke(summarize, ["flow-runs"])
    assert result.exit_code == 0


def test_summarize_projects():
    runner = CliRunner()
    result = runner.invoke(summarize, ["projects"])
    assert result.exit_code == 0
