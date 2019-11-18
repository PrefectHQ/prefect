from unittest.mock import MagicMock

from click.testing import CliRunner
import pytest

from prefect.cli.agent import agent

pytest.importorskip("boto3")
pytest.importorskip("botocore")
pytest.importorskip("kubernetes")


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
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start"])
    assert result.exit_code == 1


def test_agent_start_token(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "docker", "-t", "test"])
    assert result.exit_code == 0


def test_agent_start_verbose(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "docker", "-v"])
    assert result.exit_code == 0


def test_agent_start_docker(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "docker"])
    assert result.exit_code == 0


def test_agent_start_kubernetes(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.kubernetes.KubernetesAgent.start", start)

    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "kubernetes"])
    assert result.exit_code == 0


def test_agent_start_kubernetes_kwargs_ignored(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.kubernetes.KubernetesAgent.start", start)

    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "kubernetes", "test_kwarg=ignored"])
    assert result.exit_code == 0


def test_agent_start_fargate(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.fargate.FargateAgent.start", start)

    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "fargate"])
    assert result.exit_code == 0


def test_agent_start_fargate_kwargs(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.fargate.FargateAgent.start", start)

    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "fargate", "taskRoleArn=test"])
    assert result.exit_code == 0


def test_agent_start_fargate_kwargs_received(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.fargate.FargateAgent.start", start)

    fargate_agent = MagicMock()
    monkeypatch.setattr("prefect.agent.fargate.FargateAgent", fargate_agent)

    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    runner = CliRunner()
    result = runner.invoke(
        agent, ["start", "fargate", "taskRoleArn=arn", "--volumes=vol"]
    )
    assert result.exit_code == 0

    assert fargate_agent.called
    fargate_agent.assert_called_with(
        labels=[], name=None, taskRoleArn="arn", volumes="vol"
    )


def test_agent_start_name(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "docker", "--name", "test_agent"])
    assert result.exit_code == 0


def test_agent_start_local_vars(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(
        agent, ["start", "docker", "-t", "test", "--base-url", "url", "--no-pull"]
    )
    assert result.exit_code == 0


def test_agent_start_local_labels(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", docker_client)

    runner = CliRunner()
    result = runner.invoke(
        agent, ["start", "docker", "-t", "test", "--label", "label1", "-l", "label2"]
    )
    assert result.exit_code == 0


def test_agent_start_fails(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.agent.docker.APIClient", docker_client)

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
