from unittest.mock import MagicMock, create_autospec
from importlib import import_module

from click.testing import CliRunner
import pytest

import prefect
from prefect.cli import cli
from prefect.cli.agent import agent

pytest.importorskip("boto3")
pytest.importorskip("botocore")
pytest.importorskip("kubernetes")


@pytest.mark.parametrize(
    "cmd",
    [
        "agent",
        "agent start",
        "agent install",
        "agent local",
        "agent local start",
        "agent local install",
        "agent docker",
        "agent docker start",
        "agent kubernetes",
        "agent kubernetes start",
        "agent kubernetes install",
        "agent fargate",
        "agent fargate start",
        "agent ecs",
        "agent ecs start",
    ],
)
def test_help(cmd):
    args = cmd.split()
    result = CliRunner().invoke(cli, args + ["-h"])
    assert result.exit_code == 0


@pytest.mark.parametrize("deprecated", [False, True])
@pytest.mark.parametrize(
    "name, import_path, extra_cmd, extra_kwargs",
    [
        (
            "local",
            "prefect.agent.local.LocalAgent",
            "-p path1 -p path2 -f --no-hostname-label",
            {
                "import_paths": ["path1", "path2"],
                "show_flow_logs": True,
                "hostname_label": False,
            },
        ),
        (
            "docker",
            "prefect.agent.docker.DockerAgent",
            (
                "--base-url testurl --no-pull --show-flow-logs --volume volume1 "
                "--volume volume2 --network testnetwork1 --network testnetwork2 "
                "--no-docker-interface --docker-client-timeout 123"
            ),
            {
                "base_url": "testurl",
                "volumes": ["volume1", "volume2"],
                "networks": ("testnetwork1", "testnetwork2"),
                "no_pull": True,
                "show_flow_logs": True,
                "docker_interface": False,
                "docker_client_timeout": 123,
            },
        ),
        (
            "kubernetes",
            "prefect.agent.kubernetes.KubernetesAgent",
            (
                "--namespace TESTNAMESPACE --job-template testtemplate.yaml",
                "--service-account-name TESTACCT --image-pull-secrets VAL1,VAL2",
                "--disable-job-deletion",
            ),
            (
                {
                    "namespace": "TESTNAMESPACE",
                    "job_template_path": "testtemplate.yaml",
                },
                {
                    "service_account_name": "TESTACCT",
                    "image_pull_secrets": ["VAL1", "VAL2"],
                },
                {"delete_finished_job": False},
            ),
        ),
        (
            "fargate",
            "prefect.agent.fargate.FargateAgent",
            "--launchType=EC2 --taskRoleArn=my-task-role",
            {"launchType": "EC2", "taskRoleArn": "my-task-role"},
        ),
        (
            "ecs",
            "prefect.agent.ecs.ECSAgent",
            (
                "--cluster TEST-CLUSTER --launch-type EC2 --task-role-arn TEST-TASK-ROLE-ARN "
                "--task-definition task-definition-path.yaml --run-task-kwargs "
                "run-task-kwargs-path.yaml"
            ),
            {
                "cluster": "TEST-CLUSTER",
                "launch_type": "EC2",
                "task_role_arn": "TEST-TASK-ROLE-ARN",
                "task_definition_path": "task-definition-path.yaml",
                "run_task_kwargs_path": "run-task-kwargs-path.yaml",
            },
        ),
        (
            "ecs",
            "prefect.agent.ecs.ECSAgent",
            (
                "--cluster TEST-CLUSTER --launch-type FARGATE --execution-role-arn TEST-EXECUTION-ROLE-ARN "
                "--task-definition task-definition-path.yaml --run-task-kwargs "
                "run-task-kwargs-path.yaml"
            ),
            {
                "cluster": "TEST-CLUSTER",
                "launch_type": "FARGATE",
                "execution_role_arn": "TEST-EXECUTION-ROLE-ARN",
                "task_definition_path": "task-definition-path.yaml",
                "run_task_kwargs_path": "run-task-kwargs-path.yaml",
            },
        ),
    ],
)
def test_agent_start(
    name, import_path, extra_cmd, extra_kwargs, deprecated, monkeypatch
):
    if name == "ecs" and deprecated:
        pytest.skip("No deprecated version for ECS agent")

    command = ["start", name] if deprecated else [name, "start"]
    command.extend(
        (
            "--token TEST-TOKEN --api TEST-API --agent-config-id TEST-AGENT-CONFIG-ID "
            "--name TEST-NAME -l label1 -l label2 -e KEY1=VALUE1 -e KEY2=VALUE2 "
            "-e KEY3=VALUE=WITH=EQUALS --max-polls 10 --agent-address 127.0.0.1:8080"
        ).split()
    )
    if deprecated:
        command.append("--verbose")
    else:
        command.extend(["--log-level", "debug"])
    if not isinstance(extra_cmd, str):
        extra_cmd = extra_cmd[0] if deprecated else " ".join(extra_cmd)
    command.extend(extra_cmd.split())

    if not isinstance(extra_kwargs, dict):
        extra_kwargs = (
            extra_kwargs[0]
            if deprecated
            else dict(**extra_kwargs[0], **extra_kwargs[1])
        )

    expected_kwargs = {
        "agent_config_id": "TEST-AGENT-CONFIG-ID",
        "name": "TEST-NAME",
        "labels": ["label1", "label2"],
        "env_vars": {"KEY1": "VALUE1", "KEY2": "VALUE2", "KEY3": "VALUE=WITH=EQUALS"},
        "max_polls": 10,
        "agent_address": "127.0.0.1:8080",
        "no_cloud_logs": False,
        **extra_kwargs,
    }

    agent_obj = MagicMock()

    def check_config(*args, **kwargs):
        assert prefect.config.cloud.agent.auth_token == "TEST-TOKEN"
        assert prefect.config.cloud.agent.level == "DEBUG"
        assert prefect.config.cloud.api == "TEST-API"
        return agent_obj

    module, cls_name = import_path.rsplit(".", 1)
    cls = getattr(import_module(module), cls_name)
    agent_cls = create_autospec(cls, side_effect=check_config)
    monkeypatch.setattr(import_path, agent_cls)

    result = CliRunner().invoke(agent, command)
    if deprecated:
        if name == "fargate":
            assert f"Warning: The Fargate agent is deprecated" in result.output
        else:
            assert (
                f"Warning: `prefect agent start {name}` is deprecated" in result.output
            )

    kwargs = agent_cls.call_args[1]
    for k, v in expected_kwargs.items():
        assert kwargs[k] == v
    assert agent_obj.start.called


def test_agent_start_fails(monkeypatch, cloud_api):
    start = MagicMock()
    monkeypatch.setattr("prefect.agent.local.LocalAgent.start", start)

    runner = CliRunner()
    result = runner.invoke(agent, ["start", "TEST"])
    assert result.exit_code == 0
    assert "TEST is not a valid agent" in result.output


@pytest.mark.parametrize("deprecated", [False, True])
def test_agent_local_install(monkeypatch, deprecated):
    from prefect.agent.local import LocalAgent

    command = ["install", "local"] if deprecated else ["local", "install"]
    command.extend(
        (
            "--token TEST-TOKEN -l label1 -l label2 -e KEY1=VALUE1 -e KEY2=VALUE2 "
            "-p path1 -p path2 --show-flow-logs"
        ).split()
    )

    expected_kwargs = {
        "token": "TEST-TOKEN",
        "labels": ["label1", "label2"],
        "env_vars": {"KEY1": "VALUE1", "KEY2": "VALUE2"},
        "import_paths": ["path1", "path2"],
        "show_flow_logs": True,
    }

    generate = MagicMock(wraps=LocalAgent.generate_supervisor_conf)
    monkeypatch.setattr(
        "prefect.agent.local.LocalAgent.generate_supervisor_conf", generate
    )

    result = CliRunner().invoke(agent, command)

    if deprecated:
        assert f"Warning: `prefect agent install local` is deprecated" in result.output

    kwargs = generate.call_args[1]
    assert kwargs == expected_kwargs
    assert "supervisord" in result.output


@pytest.mark.parametrize("deprecated", [False, True])
def test_agent_kubernetes_install(monkeypatch, deprecated):
    from prefect.agent.kubernetes import KubernetesAgent

    command = ["install", "kubernetes"] if deprecated else ["kubernetes", "install"]
    command.extend(
        (
            "--token TEST-TOKEN -l label1 -l label2 -e KEY1=VALUE1 -e KEY2=VALUE2 "
            "--api TEST_API --namespace TEST_NAMESPACE --rbac "
            "--latest --image-pull-secrets secret-test --mem-request mem_req "
            "--mem-limit mem_lim --cpu-request cpu_req --cpu-limit cpu_lim "
            "--image-pull-policy custom_policy --service-account-name svc_name "
            "-b backend-test"
        ).split()
    )

    expected_kwargs = {
        "token": "TEST-TOKEN",
        "labels": ["label1", "label2"],
        "env_vars": {"KEY1": "VALUE1", "KEY2": "VALUE2"},
        "api": "TEST_API",
        "namespace": "TEST_NAMESPACE",
        "rbac": True,
        "latest": True,
        "image_pull_secrets": "secret-test",
        "mem_request": "mem_req",
        "mem_limit": "mem_lim",
        "cpu_request": "cpu_req",
        "cpu_limit": "cpu_lim",
        "image_pull_policy": "custom_policy",
        "service_account_name": "svc_name",
        "backend": "backend-test",
    }

    generate = MagicMock(wraps=KubernetesAgent.generate_deployment_yaml)
    monkeypatch.setattr(
        "prefect.agent.kubernetes.KubernetesAgent.generate_deployment_yaml", generate
    )

    result = CliRunner().invoke(agent, command)

    if deprecated:
        assert (
            f"Warning: `prefect agent install kubernetes` is deprecated"
            in result.output
        )

    kwargs = generate.call_args[1]
    assert kwargs == expected_kwargs
    assert "apiVersion" in result.output


def test_agent_install_fails_non_valid_agent(cloud_api):
    runner = CliRunner()
    result = runner.invoke(agent, ["install", "fake_agent"])
    assert result.exit_code == 0
    assert "fake_agent is not a supported agent for `install`" in result.output
