from unittest.mock import MagicMock

import pytest

from prefect.agent.fargate import FargateAgent
from prefect.environments.storage import Docker
from prefect.utilities.graphql import GraphQLResult

pytest.importorskip("boto3")
pytest.importorskip("botocore")

from botocore.exceptions import ClientError


def test_ecs_agent_init(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    agent = FargateAgent()
    assert agent
    assert agent.boto3_client


def test_ecs_agent_config_options_default(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    agent = FargateAgent()
    assert agent
    assert agent.labels is None
    assert agent.cluster == "default"
    assert not agent.subnets
    assert not agent.security_groups
    assert not agent.repository_credentials
    assert agent.assign_public_ip == "ENABLED"
    assert agent.task_cpu == "256"
    assert agent.task_memory == "512"
    assert agent.boto3_client


def test_ecs_agent_config_options_init(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    agent = FargateAgent(
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        region_name="region",
        cluster="cluster",
        subnets=["subnet"],
        security_groups=["security_group"],
        repository_credentials="repo",
        assign_public_ip="DISABLED",
        task_cpu="1",
        task_memory="2",
        labels=["test"],
    )
    assert agent
    assert agent.labels == ["test"]
    assert agent.cluster == "cluster"
    assert agent.subnets == ["subnet"]
    assert agent.security_groups == ["security_group"]
    assert agent.repository_credentials == "repo"
    assert agent.assign_public_ip == "DISABLED"
    assert agent.task_cpu == "1"
    assert agent.task_memory == "2"

    boto3_client.assert_called_with(
        "ecs",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        region_name="region",
    )


def test_ecs_agent_config_env_vars(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("REGION_NAME", "region")
    monkeypatch.setenv("CLUSTER", "cluster")
    monkeypatch.setenv("REPOSITORY_CREDENTIALS", "repo")
    monkeypatch.setenv("ASSIGN_PUBLIC_IP", "DISABLED")
    monkeypatch.setenv("TASK_CPU", "1")
    monkeypatch.setenv("TASK_MEMORY", "2")

    agent = FargateAgent(subnets=["subnet"])
    assert agent
    assert agent.cluster == "cluster"
    assert agent.repository_credentials == "repo"
    assert agent.assign_public_ip == "DISABLED"
    assert agent.task_cpu == "1"
    assert agent.task_memory == "2"

    boto3_client.assert_called_with(
        "ecs",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        region_name="region",
    )


def test_default_subnets(monkeypatch, runner_token):
    boto3_client = MagicMock()
    boto3_client.describe_subnets.return_value = {
        "Subnets": [
            {"MapPublicIpOnLaunch": False, "SubnetId": "id"},
            {"MapPublicIpOnLaunch": True, "SubnetId": "id2"},
        ]
    }
    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent()
    assert agent.subnets == ["id"]


def test_deploy_flows(monkeypatch, runner_token):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.return_value = {}
    boto3_client.run_task.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent()
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

    assert boto3_client.describe_task_definition.called
    assert boto3_client.run_task.called
    assert boto3_client.run_task.call_args[1]["cluster"] == "default"


def test_deploy_flows_all_args(monkeypatch, runner_token):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.return_value = {}
    boto3_client.run_task.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent(
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        region_name="region",
        cluster="cluster",
        subnets=["subnet"],
        security_groups=["security_group"],
        repository_credentials="repo",
        assign_public_ip="DISABLED",
        task_cpu="1",
        task_memory="2",
    )
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

    assert boto3_client.describe_task_definition.called
    assert boto3_client.run_task.called
    assert boto3_client.run_task.call_args[1]["cluster"] == "cluster"
    assert boto3_client.run_task.call_args[1]["taskDefinition"] == "prefect-task-id"
    assert boto3_client.run_task.call_args[1]["launchType"] == "FARGATE"
    assert boto3_client.run_task.call_args[1]["overrides"] == {
        "containerOverrides": [
            {
                "name": "flow",
                "environment": [
                    {"name": "PREFECT__CLOUD__AUTH_TOKEN", "value": ""},
                    {"name": "PREFECT__CONTEXT__FLOW_RUN_ID", "value": "id"},
                ],
            }
        ]
    }
    assert boto3_client.run_task.call_args[1]["networkConfiguration"] == {
        "awsvpcConfiguration": {
            "subnets": ["subnet"],
            "assignPublicIp": "DISABLED",
            "securityGroups": ["security_group"],
        }
    }


def test_deploy_flows_no_security_group(monkeypatch, runner_token):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.return_value = {}
    boto3_client.run_task.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent()
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

    assert boto3_client.describe_task_definition.called
    assert boto3_client.run_task.called
    assert boto3_client.run_task.call_args[1]["cluster"] == "default"
    assert boto3_client.run_task.call_args[1]["networkConfiguration"] == {
        "awsvpcConfiguration": {"subnets": [], "assignPublicIp": "ENABLED"}
    }


def test_deploy_flows_register_task_definition(monkeypatch, runner_token):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.side_effect = ClientError({}, None)
    boto3_client.run_task.return_value = {}
    boto3_client.register_task_definition.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent()
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

    assert boto3_client.describe_task_definition.called
    assert boto3_client.register_task_definition.called
    assert (
        boto3_client.register_task_definition.call_args[1]["family"]
        == "prefect-task-id"
    )


def test_deploy_flows_register_task_definition_all_args(monkeypatch, runner_token):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.side_effect = ClientError({}, None)
    boto3_client.run_task.return_value = {}
    boto3_client.register_task_definition.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent(
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        region_name="region",
        cluster="cluster",
        subnets=["subnet"],
        security_groups=["security_group"],
        repository_credentials="repo",
        assign_public_ip="DISABLED",
        task_cpu="1",
        task_memory="2",
    )
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

    assert boto3_client.describe_task_definition.called
    assert boto3_client.register_task_definition.called
    assert (
        boto3_client.register_task_definition.call_args[1]["family"]
        == "prefect-task-id"
    )
    assert boto3_client.register_task_definition.call_args[1][
        "containerDefinitions"
    ] == [
        {
            "name": "flow",
            "image": "test/name:tag",
            "command": ["/bin/sh", "-c", "prefect execute cloud-flow"],
            "environment": [
                {"name": "PREFECT__CLOUD__API", "value": "https://api.prefect.io"},
                {"name": "PREFECT__CLOUD__USE_LOCAL_SECRETS", "value": "false"},
                {"name": "PREFECT__LOGGING__LOG_TO_CLOUD", "value": "true"},
                {"name": "PREFECT__LOGGING__LEVEL", "value": "DEBUG"},
                {
                    "name": "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS",
                    "value": "prefect.engine.cloud.CloudFlowRunner",
                },
                {
                    "name": "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS",
                    "value": "prefect.engine.cloud.CloudTaskRunner",
                },
            ],
            "essential": True,
            "repositoryCredentials": {"credentialsParameter": "repo"},
        }
    ]
    assert boto3_client.register_task_definition.call_args[1][
        "requiresCompatibilities"
    ] == ["FARGATE"]
    assert boto3_client.register_task_definition.call_args[1]["networkMode"] == "awsvpc"
    assert boto3_client.register_task_definition.call_args[1]["cpu"] == "1"
    assert boto3_client.register_task_definition.call_args[1]["memory"] == "2"


def test_deploy_flows_register_task_definition_no_repo_credentials(
    monkeypatch, runner_token
):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.side_effect = ClientError({}, None)
    boto3_client.run_task.return_value = {}
    boto3_client.register_task_definition.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent()
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

    assert boto3_client.describe_task_definition.called
    assert boto3_client.register_task_definition.called
    assert boto3_client.register_task_definition.call_args[1][
        "containerDefinitions"
    ] == [
        {
            "name": "flow",
            "image": "test/name:tag",
            "command": ["/bin/sh", "-c", "prefect execute cloud-flow"],
            "environment": [
                {"name": "PREFECT__CLOUD__API", "value": "https://api.prefect.io"},
                {"name": "PREFECT__CLOUD__USE_LOCAL_SECRETS", "value": "false"},
                {"name": "PREFECT__LOGGING__LOG_TO_CLOUD", "value": "true"},
                {"name": "PREFECT__LOGGING__LEVEL", "value": "DEBUG"},
                {
                    "name": "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS",
                    "value": "prefect.engine.cloud.CloudFlowRunner",
                },
                {
                    "name": "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS",
                    "value": "prefect.engine.cloud.CloudTaskRunner",
                },
            ],
            "essential": True,
        }
    ]
