import os
import tempfile
from unittest.mock import MagicMock

from click.testing import CliRunner

from prefect.cli.register import register


def test_register_init():
    runner = CliRunner()
    result = runner.invoke(register)
    assert result.exit_code == 0
    assert "Register flows" in result.output


def test_register_help():
    runner = CliRunner()
    result = runner.invoke(register, ["--help"])
    assert result.exit_code == 0
    assert "Register flows" in result.output


def test_register_flow():
    runner = CliRunner()
    result = runner.invoke(register, ["flow", "--help"])
    assert result.exit_code == 0
    assert "Register a flow" in result.output


def test_register_flow_kwargs(monkeypatch, tmpdir):
    monkeypatch.setattr("prefect.Client", MagicMock())

    contents = """from prefect import Flow\nf=Flow('test-flow')"""

    full_path = os.path.join(tmpdir, "flow.py")

    with open(full_path, "w") as f:
        f.write(contents)

    runner = CliRunner()
    result = runner.invoke(
        register,
        ["flow", "--file", full_path, "--name", "test-flow", "--project", "project"],
    )
    assert result.exit_code == 0
