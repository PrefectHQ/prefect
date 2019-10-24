from os import path
import tempfile
from unittest.mock import MagicMock

import pytest

pytest.importorskip("kubernetes")

import yaml

import prefect
from prefect.agent.kubernetes import KubernetesAgent
from prefect.agent.kubernetes.agent import check_heartbeat
from prefect.environments.storage import Docker, Local
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult


def test_k8s_agent_init(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    assert agent
    assert agent.labels == []
    assert agent.name == "agent"
    assert agent.batch_client


def test_k8s_agent_config_options(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = KubernetesAgent(name="test", labels=["test"])
        assert agent
        assert agent.labels == ["test"]
        assert agent.name == "test"
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert agent.batch_client


def test_k8s_agent_deploy_flows(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    batch_client = MagicMock()
    batch_client.create_namespaced_job.return_value = {}
    monkeypatch.setattr(
        "kubernetes.client.BatchV1Api", MagicMock(retrurn_value=batch_client)
    )

    agent = KubernetesAgent()
    agent.deploy_flows(
        flow_runs=[
            GraphQLResult(
                {
                    "flow": GraphQLResult(
                        {
                            "storage": Docker(
                                registry_url="test", image_name="name", image_tag="tag"
                            ).serialize(),
                            "id": "id",
                        }
                    ),
                    "id": "id",
                }
            )
        ]
    )

    assert agent.batch_client.create_namespaced_job.called
    assert (
        agent.batch_client.create_namespaced_job.call_args[1]["namespace"] == "default"
    )
    assert (
        agent.batch_client.create_namespaced_job.call_args[1]["body"]["apiVersion"]
        == "batch/v1"
    )


def test_k8s_agent_deploy_flows_continues(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    batch_client = MagicMock()
    batch_client.create_namespaced_job.return_value = {}
    monkeypatch.setattr(
        "kubernetes.client.BatchV1Api", MagicMock(retrurn_value=batch_client)
    )

    agent = KubernetesAgent()
    agent.deploy_flows(
        flow_runs=[
            GraphQLResult(
                {
                    "flow": GraphQLResult({"storage": Local().serialize(), "id": "id"}),
                    "id": "id",
                }
            )
        ]
    )

    assert not agent.batch_client.create_namespaced_job.called


def test_k8s_agent_replace_yaml(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    monkeypatch.setenv("IMAGE_PULL_SECRETS", "my-secret")

    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "id": "id",
                }
            ),
            "id": "id",
        }
    )

    with set_temporary_config({"cloud.agent.auth_token": "token"}):
        agent = KubernetesAgent()
        job = agent.replace_job_spec_yaml(flow_run)

        assert job["metadata"]["labels"]["flow_run_id"] == "id"
        assert job["metadata"]["labels"]["flow_id"] == "id"
        assert job["spec"]["template"]["metadata"]["labels"]["flow_run_id"] == "id"
        assert (
            job["spec"]["template"]["spec"]["containers"][0]["image"] == "test/name:tag"
        )

        env = job["spec"]["template"]["spec"]["containers"][0]["env"]

        assert env[0]["value"] == "https://api.prefect.io"
        assert env[1]["value"] == "token"
        assert env[2]["value"] == "id"
        assert env[3]["value"] == "default"

        assert (
            job["spec"]["template"]["spec"]["imagePullSecrets"][0]["name"]
            == "my-secret"
        )


def test_k8s_agent_replace_yaml_no_pull_secrets(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "id": "id",
                }
            ),
            "id": "id",
        }
    )

    agent = KubernetesAgent()
    job = agent.replace_job_spec_yaml(flow_run)

    assert not job["spec"]["template"]["spec"]["imagePullSecrets"][0]["name"]


def test_k8s_agent_generate_deployment_yaml(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml(
        token="test_token",
        api="test_api",
        namespace="test_namespace",
        resource_manager_enabled=True,
    )

    deployment = yaml.safe_load(deployment)

    agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]
    resource_manager_env = deployment["spec"]["template"]["spec"]["containers"][1][
        "env"
    ]

    assert agent_env[0]["value"] == "test_token"
    assert agent_env[1]["value"] == "test_api"
    assert agent_env[2]["value"] == "test_namespace"

    assert resource_manager_env[0]["value"] == "test_token"
    assert resource_manager_env[1]["value"] == "test_api"
    assert resource_manager_env[3]["value"] == "test_namespace"


@pytest.mark.parametrize(
    "version",
    [
        ("0.6.3", "0.6.3"),
        ("0.5.3+114.g35bc7ba4", "latest"),
        ("0.5.2+999.gr34343.dirty", "latest"),
    ],
)
def test_k8s_agent_generate_deployment_yaml_local_version(
    monkeypatch, runner_token, version
):
    monkeypatch.setattr(prefect, "__version__", version[0])

    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml(
        token="test_token",
        api="test_api",
        namespace="test_namespace",
        resource_manager_enabled=True,
    )

    deployment = yaml.safe_load(deployment)

    agent_yaml = deployment["spec"]["template"]["spec"]["containers"][0]
    resource_manager_yaml = deployment["spec"]["template"]["spec"]["containers"][1]

    assert agent_yaml["image"] == "prefecthq/prefect:{}".format(version[1])
    assert resource_manager_yaml["image"] == "prefecthq/prefect:{}".format(version[1])


def test_k8s_agent_generate_deployment_yaml_no_resource_manager(
    monkeypatch, runner_token
):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml(
        token="test_token", api="test_api", namespace="test_namespace"
    )

    deployment = yaml.safe_load(deployment)

    agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]

    assert agent_env[0]["value"] == "test_token"
    assert agent_env[1]["value"] == "test_api"
    assert agent_env[2]["value"] == "test_namespace"

    assert len(deployment["spec"]["template"]["spec"]["containers"]) == 1


def test_k8s_agent_generate_deployment_yaml_labels(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml(
        token="test_token",
        api="test_api",
        namespace="test_namespace",
        labels=["test_label1", "test_label2"],
    )

    deployment = yaml.safe_load(deployment)

    agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]

    assert agent_env[0]["value"] == "test_token"
    assert agent_env[1]["value"] == "test_api"
    assert agent_env[2]["value"] == "test_namespace"
    assert agent_env[4]["value"] == "['test_label1', 'test_label2']"

    assert len(deployment["spec"]["template"]["spec"]["containers"]) == 1


def test_k8s_agent_generate_deployment_yaml_no_image_pull_secrets(
    monkeypatch, runner_token
):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml(
        token="test_token", api="test_api", namespace="test_namespace"
    )

    deployment = yaml.safe_load(deployment)

    assert deployment["spec"]["template"]["spec"].get("imagePullSecrets") is None


def test_k8s_agent_generate_deployment_yaml_contains_image_pull_secrets(
    monkeypatch, runner_token
):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml(
        token="test_token",
        api="test_api",
        namespace="test_namespace",
        image_pull_secrets="secrets",
    )

    deployment = yaml.safe_load(deployment)

    assert (
        deployment["spec"]["template"]["spec"]["imagePullSecrets"][0]["name"]
        == "secrets"
    )


def test_k8s_agent_heartbeat_creates_file(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    with tempfile.TemporaryDirectory() as tempdir:

        monkeypatch.setattr(
            "prefect.agent.kubernetes.agent.AGENT_DIRECTORY",
            "{}/.prefect/agent".format(tempdir),
        )

        agent = KubernetesAgent()
        agent.heartbeat()

        assert path.exists("{}/.prefect/agent/heartbeat".format(tempdir))


def test_k8s_agent_heartbeat_modifies(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    with tempfile.TemporaryDirectory() as tempdir:

        monkeypatch.setattr(
            "prefect.agent.kubernetes.agent.AGENT_DIRECTORY",
            "{}/.prefect/agent".format(tempdir),
        )

        agent = KubernetesAgent()
        agent.heartbeat()

        assert path.exists("{}/.prefect/agent/heartbeat".format(tempdir))

        first = path.getmtime("{}/.prefect/agent/heartbeat".format(tempdir))

        # Wait one second until next heartbeat
        import time

        time.sleep(1)

        agent.heartbeat()
        second = path.getmtime("{}/.prefect/agent/heartbeat".format(tempdir))

        assert second > first


def test_k8s_agent_heartbeat_check(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    with tempfile.TemporaryDirectory() as tempdir:

        monkeypatch.setattr(
            "prefect.agent.kubernetes.agent.AGENT_DIRECTORY",
            "{}/.prefect/agent".format(tempdir),
        )

        agent = KubernetesAgent()

        # Verify no exit codes of status `1` were raised
        agent.heartbeat()
        assert not check_heartbeat()

        agent.heartbeat()
        assert not check_heartbeat()
