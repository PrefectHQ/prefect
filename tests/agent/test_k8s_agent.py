from unittest.mock import MagicMock

import pytest

pytest.importorskip("kubernetes")

import yaml

from prefect.agent.kubernetes import KubernetesAgent
from prefect.environments.storage import Docker, Local
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult


def test_k8s_agent_init(monkeypatch):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    assert agent
    assert agent.batch_client


def test_k8s_agent_config_options(monkeypatch):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    with set_temporary_config({"cloud.agent.api_token": "TEST_TOKEN"}):
        agent = KubernetesAgent()
        assert agent
        assert agent.client.token == "TEST_TOKEN"
        assert agent.logger
        assert agent.batch_client


def test_k8s_agent_deploy_flows(monkeypatch):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    batch_client = MagicMock()
    batch_client.create_namespaced_job.return_value = {}
    monkeypatch.setattr(
        "kubernetes.client.BatchV1Api", MagicMock(retrurn_value=batch_client)
    )

    with set_temporary_config({"cloud.agent.api_token": "token"}):
        agent = KubernetesAgent()
        agent.deploy_flows(
            flow_runs=[
                GraphQLResult(
                    {
                        "flow": GraphQLResult(
                            {
                                "storage": Docker(
                                    registry_url="test",
                                    image_name="name",
                                    image_tag="tag",
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


def test_k8s_agent_deploy_flows_continues(monkeypatch):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    batch_client = MagicMock()
    batch_client.create_namespaced_job.return_value = {}
    monkeypatch.setattr(
        "kubernetes.client.BatchV1Api", MagicMock(retrurn_value=batch_client)
    )

    with set_temporary_config({"cloud.agent.api_token": "token"}):
        agent = KubernetesAgent()
        agent.deploy_flows(
            flow_runs=[
                GraphQLResult(
                    {
                        "flow": GraphQLResult(
                            {"storage": Local().serialize(), "id": "id"}
                        ),
                        "id": "id",
                    }
                )
            ]
        )

    assert not agent.batch_client.create_namespaced_job.called


def test_k8s_agent_replace_yaml(monkeypatch):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    monkeypatch.setenv("IMAGE_PULL_SECRETS", "my-secret")

    with set_temporary_config({"cloud.agent.api_token": "token"}):
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


def test_k8s_agent_replace_yaml_no_pull_secrets(monkeypatch):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    with set_temporary_config({"cloud.agent.auth_token": "token"}):
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


def test_k8s_agent_generate_deployment_yaml(monkeypatch):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    with set_temporary_config({"cloud.agent.api_token": "token"}):
        agent = KubernetesAgent()
        deployment = agent.generate_deployment_yaml(
            token="test_token", api="test_api", namespace="test_namespace"
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
