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


def test_agent_start_fails_no_token(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start"])
    assert result.exit_code == 1


def test_agent_start_token(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "-t", "test"])
    assert result.exit_code == 0


def test_agent_start_verbose(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "-v"])
    assert result.exit_code == 0


def test_agent_start_name(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "--name", "test_agent"])
    assert result.exit_code == 0


def test_agent_start_local_context_vars(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(
        agent, ["start", "-t", "test", "--base-url", "url", "--no-pull"]
    )
    assert result.exit_code == 0


def test_agent_start_local_labels(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(
        agent, ["start", "-t", "test", "--label", "label1", "-l", "label2"]
    )
    assert result.exit_code == 0


def test_agent_start_fails(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.local.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "TEST"])
    assert result.exit_code == 0
    assert "TEST is not a valid agent" in result.output


def test_agent_install():
    runner = CliRunner()
    result = runner.invoke(agent, ["install"])
    assert result.exit_code == 0
    assert "apiVersion" in result.output


def test_agent_install_kubernetes():
    runner = CliRunner()
    result = runner.invoke(agent, ["install", "kubernetes"])
    assert result.exit_code == 0
    assert "apiVersion" in result.output


def test_agent_install_fails_non_valid_agent():
    runner = CliRunner()
    result = runner.invoke(agent, ["install", "fake_agent"])
    assert result.exit_code == 0
    assert "fake_agent is not a supported agent for `install`" in result.output


def test_agent_install_passes_args():
    runner = CliRunner()
    result = runner.invoke(
        agent,
        [
            "install",
            "--token",
            "TEST_TOKEN",
            "--api",
            "TEST_API",
            "--namespace",
            "TEST_NAMESPACE",
            "--resource-manager",
            "--image-pull-secrets",
            "secret-test",
            "--label",
            "test_label1",
            "-l",
            "test_label2",
        ],
    )
    assert result.exit_code == 0
    assert "TEST_TOKEN" in result.output
    assert "TEST_API" in result.output
    assert "TEST_NAMESPACE" in result.output
    assert "resource-manager" in result.output
    assert "secret-test" in result.output
    assert "test_label1" in result.output
    assert "test_label2" in result.output


def test_agent_install_no_resource_manager():
    runner = CliRunner()
    result = runner.invoke(
        agent,
        [
            "install",
            "--token",
            "TEST_TOKEN",
            "--api",
            "TEST_API",
            "--namespace",
            "TEST_NAMESPACE",
            "--image-pull-secrets",
            "secret-test",
        ],
    )
    assert result.exit_code == 0
    assert "TEST_TOKEN" in result.output
    assert "TEST_API" in result.output
    assert "TEST_NAMESPACE" in result.output
    assert not "resource-manager" in result.output
    assert "secret-test" in result.output
