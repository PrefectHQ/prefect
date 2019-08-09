from unittest.mock import MagicMock

from click.testing import CliRunner

from prefect.cli.agent import agent


def test_agent_init():
    runner = CliRunner()
    result = runner.invoke(agent)
    assert result.exit_code == 0
    assert "Manage Prefect agents." in result.output


def test_agent_help():
    runner = CliRunner()
    result = runner.invoke(agent, ["--help"])
    assert result.exit_code == 0
    assert "Manage Prefect agents." in result.output


def test_agent_start(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    runner = CliRunner()
    result = runner.invoke(agent, ["start"])
    assert result.exit_code == 0


def test_agent_start_token(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "-t", "test"])
    assert result.exit_code == 0


def test_agent_start_fails(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "TEST"])
    assert result.exit_code == 0
    assert "TEST is not a valid agent" in result.output
