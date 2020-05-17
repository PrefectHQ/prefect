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


def test_agent_start_fails_no_token(monkeypatch, cloud_api):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    runner = CliRunner()
    result = runner.invoke(agent, ["start"])
    assert result.exit_code == 1


def test_docker_agent_start_token(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=docker_client),
    )

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "docker", "-t", "test"])
    assert result.exit_code == 0


def test_docker_agent_start_verbose(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=docker_client),
    )

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "docker", "-v"])
    assert result.exit_code == 0


def test_agent_start_local(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "local"])
    assert result.exit_code == 0


def test_agent_start_local_import_paths(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "local", "-p", "test"])
    assert result.exit_code == 0


def test_agent_start_docker(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=docker_client),
    )

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "docker"])
    assert result.exit_code == 0


def test_agent_start_kubernetes(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.kubernetes.KubernetesAgent.start", start)

    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "kubernetes"])
    assert result.exit_code == 0


def test_agent_start_kubernetes_namespace(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.kubernetes.KubernetesAgent.start", start)

    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "kubernetes", "--namespace", "test"])
    assert result.exit_code == 0


def test_agent_start_kubernetes_kwargs_ignored(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.kubernetes.KubernetesAgent.start", start)

    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "kubernetes", "test_kwarg=ignored"])
    assert result.exit_code == 0


def test_agent_start_fargate(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.fargate.FargateAgent.start", start)

    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "fargate"])
    assert result.exit_code == 0


def test_agent_start_fargate_kwargs(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.fargate.FargateAgent.start", start)

    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "fargate", "taskRoleArn=test"])
    assert result.exit_code == 0


def test_agent_start_fargate_kwargs_received(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.fargate.FargateAgent.start", start)

    fargate_agent = MagicMock()
    monkeypatch.setattr("prefect.agent.fargate.FargateAgent", fargate_agent)

    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    runner = CliRunner()
    result = runner.invoke(
        agent,
        [
            "start",
            "fargate",
            "taskRoleArn=arn",
            "--volumes=vol",
            "--agent-address=http://localhost:8000",
        ],
    )
    assert result.exit_code == 0

    assert fargate_agent.called
    fargate_agent.assert_called_with(
        agent_address="http://localhost:8000",
        labels=[],
        env_vars=dict(),
        max_polls=None,
        name=None,
        taskRoleArn="arn",
        volumes="vol",
    )


def test_agent_start_with_env_vars(monkeypatch, runner_token):
    docker_agent = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent", docker_agent)

    runner = CliRunner()
    result = runner.invoke(
        agent, ["start", "docker", "-e", "KEY=VAL", "-e", "SETTING=false"]
    )
    assert result.exit_code == 0

    docker_agent.assert_called_with(
        agent_address="",
        base_url=None,
        env_vars={"KEY": "VAL", "SETTING": "false"},
        max_polls=None,
        labels=[],
        name=None,
        no_pull=False,
        show_flow_logs=False,
        volumes=[],
        network=None,
        docker_interface=True,
    )


def test_agent_start_with_max_polls(monkeypatch, runner_token):
    docker_agent = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent", docker_agent)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "docker", "--max-polls", "5"])
    assert result.exit_code == 0

    docker_agent.assert_called_with(
        agent_address="",
        base_url=None,
        env_vars={},
        max_polls=5,
        labels=[],
        name=None,
        no_pull=False,
        show_flow_logs=False,
        volumes=[],
        network=None,
        docker_interface=True,
    )


def test_agent_start_name(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=docker_client),
    )

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "docker", "--name", "test_agent"])
    assert result.exit_code == 0


def test_agent_start_max_polls(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=docker_client),
    )

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "docker", "--max-polls", "1"])
    assert result.exit_code == 0


def test_agent_start_docker_vars(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=docker_client),
    )

    runner = CliRunner()
    result = runner.invoke(
        agent, ["start", "docker", "-t", "test", "--base-url", "url", "--no-pull"]
    )
    assert result.exit_code == 0


def test_agent_start_docker_labels(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.docker.DockerAgent.start", start)

    docker_client = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.docker.agent.DockerAgent._get_docker_client",
        MagicMock(return_value=docker_client),
    )

    runner = CliRunner()
    result = runner.invoke(
        agent, ["start", "docker", "-t", "test", "--label", "label1", "-l", "label2"]
    )
    assert result.exit_code == 0


def test_agent_start_fails(monkeypatch, runner_token):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "TEST"])
    assert result.exit_code == 0
    assert "TEST is not a valid agent" in result.output


def test_agent_install_local():
    runner = CliRunner()
    result = runner.invoke(agent, ["install", "local"])
    assert result.exit_code == 0
    assert "supervisord" in result.output


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


def test_agent_install_k8s_asses_args():
    runner = CliRunner()
    result = runner.invoke(
        agent,
        [
            "install",
            "kubernetes",
            "--token",
            "TEST_TOKEN",
            "--api",
            "TEST_API",
            "--namespace",
            "TEST_NAMESPACE",
            "--resource-manager",
            "--rbac",
            "--latest",
            "--image-pull-secrets",
            "secret-test",
            "--mem-request",
            "mem_req",
            "--mem-limit",
            "mem_lim",
            "--cpu-request",
            "cpu_req",
            "--cpu-limit",
            "cpu_limt",
            "--label",
            "test_label1",
            "-l",
            "test_label2",
            "-b",
            "backend-test",
            "-e",
            "ENVTEST=TESTENV",
            "-e",
            "ENVTEST2=TESTENV2",
        ],
    )
    assert result.exit_code == 0
    assert "TEST_TOKEN" in result.output
    assert "TEST_API" in result.output
    assert "TEST_NAMESPACE" in result.output
    assert "resource-manager" in result.output
    assert "rbac" in result.output
    assert "latest" in result.output
    assert "mem_req" in result.output
    assert "mem_lim" in result.output
    assert "cpu_req" in result.output
    assert "cpu_lim" in result.output
    assert "secret-test" in result.output
    assert "test_label1" in result.output
    assert "test_label2" in result.output
    assert "backend-test" in result.output

    # Environment Variables
    assert "ENVTEST" in result.output
    assert "TESTENV" in result.output
    assert "ENVTEST2" in result.output
    assert "TESTENV2" in result.output


def test_agent_install_k8s_no_resource_manager():
    runner = CliRunner()
    result = runner.invoke(
        agent,
        [
            "install",
            "kubernetes",
            "--token",
            "TEST_TOKEN",
            "--api",
            "TEST_API",
            "--namespace",
            "TEST_NAMESPACE",
            "--image-pull-secrets",
            "secret-test",
            "--rbac",
        ],
    )
    assert result.exit_code == 0
    assert "TEST_TOKEN" in result.output
    assert "TEST_API" in result.output
    assert "TEST_NAMESPACE" in result.output
    assert not "resource-manager" in result.output
    assert "rbac" in result.output
    assert "secret-test" in result.output


def test_agent_install_local_asses_args():
    runner = CliRunner()
    result = runner.invoke(
        agent,
        [
            "install",
            "local",
            "--token",
            "TEST_TOKEN",
            "--label",
            "test_label1",
            "-l",
            "test_label2",
            "--import-path",
            "my_path",
        ],
    )
    assert result.exit_code == 0
    assert "TEST_TOKEN" in result.output
    assert "test_label1" in result.output
    assert "test_label2" in result.output
    assert "my_path" in result.output
