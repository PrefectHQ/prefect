from unittest.mock import MagicMock

import pytest

from prefect.agent.fargate import FargateAgent
from prefect.environments.storage import Docker
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult

pytest.importorskip("boto3")
pytest.importorskip("botocore")

from botocore.exceptions import ClientError


def test_fargate_agent_init(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    agent = FargateAgent()
    assert agent
    assert agent.boto3_client


def test_fargate_agent_config_options_default(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    agent = FargateAgent()
    assert agent
    assert agent.labels == []
    assert agent.name == "agent"
    assert agent.task_definition_kwargs == {}
    assert agent.task_run_kwargs == {}
    assert agent.boto3_client


def test_k8s_agent_config_options(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = FargateAgent(name="test", labels=["test"])
        assert agent
        assert agent.labels == ["test"]
        assert agent.name == "test"
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert agent.boto3_client


def test_parse_task_definition_kwargs(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    agent = FargateAgent()

    kwarg_dict = {
        "taskRoleArn": "test",
        "executionRoleArn": "test",
        "volumes": "test",
        "placementConstraints": "test",
        "cpu": "test",
        "memory": "test",
        "tags": "test",
        "pidMode": "test",
        "ipcMode": "test",
        "proxyConfiguration": "test",
        "inferenceAccelerators": "test",
    }

    task_definition_kwargs, task_run_kwargs = agent._parse_kwargs(kwarg_dict)

    assert task_definition_kwargs == kwarg_dict
    assert task_run_kwargs == {"placementConstraints": "test", "tags": "test"}


def test_parse_task_run_kwargs(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    agent = FargateAgent()

    kwarg_dict = {
        "cluster": "test",
        "count": "test",
        "startedBy": "test",
        "group": "test",
        "placementConstraints": "test",
        "placementStrategy": "test",
        "platformVersion": "test",
        "networkConfiguration": "test",
        "tags": "test",
        "enableECSManagedTags": "test",
        "propagateTags": "test",
    }

    task_definition_kwargs, task_run_kwargs = agent._parse_kwargs(kwarg_dict)

    assert task_run_kwargs == kwarg_dict
    assert task_definition_kwargs == {"placementConstraints": "test", "tags": "test"}


def test_parse_task_definition_and_run_kwargs(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    agent = FargateAgent()

    def_kwarg_dict = {
        "taskRoleArn": "test",
        "executionRoleArn": "test",
        "volumes": "test",
        "placementConstraints": "test",
        "cpu": "test",
        "memory": "test",
        "tags": "test",
        "pidMode": "test",
        "ipcMode": "test",
        "proxyConfiguration": "test",
        "inferenceAccelerators": "test",
    }

    run_kwarg_dict = {
        "cluster": "test",
        "count": "test",
        "startedBy": "test",
        "group": "test",
        "placementConstraints": "test",
        "placementStrategy": "test",
        "platformVersion": "test",
        "networkConfiguration": "test",
        "tags": "test",
        "enableECSManagedTags": "test",
        "propagateTags": "test",
    }

    kwarg_dict = {
        "taskRoleArn": "test",
        "executionRoleArn": "test",
        "volumes": "test",
        "placementConstraints": "test",
        "cpu": "test",
        "memory": "test",
        "tags": "test",
        "pidMode": "test",
        "ipcMode": "test",
        "proxyConfiguration": "test",
        "inferenceAccelerators": "test",
        "cluster": "test",
        "count": "test",
        "startedBy": "test",
        "group": "test",
        "placementStrategy": "test",
        "platformVersion": "test",
        "networkConfiguration": "test",
        "enableECSManagedTags": "test",
        "propagateTags": "test",
    }

    task_definition_kwargs, task_run_kwargs = agent._parse_kwargs(kwarg_dict)

    assert task_definition_kwargs == def_kwarg_dict
    assert task_run_kwargs == run_kwarg_dict


def test_parse_task_kwargs_invalid_value_removed(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    agent = FargateAgent()

    kwarg_dict = {"test": "not_real"}

    task_definition_kwargs, task_run_kwargs = agent._parse_kwargs(kwarg_dict)

    assert task_definition_kwargs == {}
    assert task_run_kwargs == {}


def test_fargate_agent_config_options_init(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    def_kwarg_dict = {
        "taskRoleArn": "test",
        "executionRoleArn": "test",
        "volumes": "test",
        "placementConstraints": "test",
        "cpu": "test",
        "memory": "test",
        "tags": "test",
        "pidMode": "test",
        "ipcMode": "test",
        "proxyConfiguration": "test",
        "inferenceAccelerators": "test",
    }

    run_kwarg_dict = {
        "cluster": "test",
        "count": "test",
        "startedBy": "test",
        "group": "test",
        "placementConstraints": "test",
        "placementStrategy": "test",
        "platformVersion": "test",
        "networkConfiguration": "test",
        "tags": "test",
        "enableECSManagedTags": "test",
        "propagateTags": "test",
    }

    kwarg_dict = {
        "taskRoleArn": "test",
        "executionRoleArn": "test",
        "volumes": "test",
        "placementConstraints": "test",
        "cpu": "test",
        "memory": "test",
        "tags": "test",
        "pidMode": "test",
        "ipcMode": "test",
        "proxyConfiguration": "test",
        "inferenceAccelerators": "test",
        "cluster": "test",
        "count": "test",
        "startedBy": "test",
        "group": "test",
        "placementStrategy": "test",
        "platformVersion": "test",
        "networkConfiguration": "test",
        "enableECSManagedTags": "test",
        "propagateTags": "test",
    }

    agent = FargateAgent(
        name="test",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="token",
        region_name="region",
        **kwarg_dict
    )
    assert agent
    assert agent.name == "test"
    assert agent.task_definition_kwargs == def_kwarg_dict
    assert agent.task_run_kwargs == run_kwarg_dict

    boto3_client.assert_called_with(
        "ecs",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="token",
        region_name="region",
    )


def test_fargate_agent_config_env_vars(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    def_kwarg_dict = {
        "taskRoleArn": "test",
        "executionRoleArn": "test",
        "volumes": "test",
        "placementConstraints": "test",
        "cpu": "test",
        "memory": "test",
        "tags": "test",
        "pidMode": "test",
        "ipcMode": "test",
        "proxyConfiguration": "test",
        "inferenceAccelerators": "test",
    }

    run_kwarg_dict = {
        "cluster": "test",
        "count": "test",
        "startedBy": "test",
        "group": "test",
        "placementConstraints": "test",
        "placementStrategy": "test",
        "platformVersion": "test",
        "networkConfiguration": "test",
        "tags": "test",
        "enableECSManagedTags": "test",
        "propagateTags": "test",
    }

    # Client args
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "token")
    monkeypatch.setenv("REGION_NAME", "region")

    # Def / run args
    monkeypatch.setenv("taskRoleArn", "test")
    monkeypatch.setenv("executionRoleArn", "test")
    monkeypatch.setenv("volumes", "test")
    monkeypatch.setenv("placementConstraints", "test")
    monkeypatch.setenv("cpu", "test")
    monkeypatch.setenv("memory", "test")
    monkeypatch.setenv("tags", "test")
    monkeypatch.setenv("pidMode", "test")
    monkeypatch.setenv("ipcMode", "test")
    monkeypatch.setenv("proxyConfiguration", "test")
    monkeypatch.setenv("inferenceAccelerators", "test")
    monkeypatch.setenv("cluster", "test")
    monkeypatch.setenv("count", "test")
    monkeypatch.setenv("startedBy", "test")
    monkeypatch.setenv("group", "test")
    monkeypatch.setenv("placementStrategy", "test")
    monkeypatch.setenv("platformVersion", "test")
    monkeypatch.setenv("networkConfiguration", "test")
    monkeypatch.setenv("enableECSManagedTags", "test")
    monkeypatch.setenv("propagateTags", "test")

    agent = FargateAgent(subnets=["subnet"])
    assert agent
    assert agent.task_definition_kwargs == def_kwarg_dict
    assert agent.task_run_kwargs == run_kwarg_dict

    boto3_client.assert_called_with(
        "ecs",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="token",
        region_name="region",
    )


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


def test_deploy_flows_all_args(monkeypatch, runner_token):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.return_value = {}
    boto3_client.run_task.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    kwarg_dict = {
        "taskRoleArn": "test",
        "executionRoleArn": "test",
        "volumes": "test",
        "placementConstraints": "test",
        "cpu": "test",
        "memory": "test",
        "tags": "test",
        "pidMode": "test",
        "ipcMode": "test",
        "proxyConfiguration": "test",
        "inferenceAccelerators": "test",
        "cluster": "cluster",
        "count": "test",
        "startedBy": "test",
        "group": "test",
        "placementStrategy": "test",
        "platformVersion": "test",
        "networkConfiguration": {
            "awsvpcConfiguration": {
                "subnets": ["subnet"],
                "assignPublicIp": "DISABLED",
                "securityGroups": ["security_group"],
            }
        },
        "enableECSManagedTags": "test",
        "propagateTags": "test",
    }

    agent = FargateAgent(
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="token",
        region_name="region",
        **kwarg_dict
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

    kwarg_dict = {
        "taskRoleArn": "test",
        "executionRoleArn": "test",
        "volumes": "test",
        "placementConstraints": "test",
        "cpu": "1",
        "memory": "2",
        "tags": "test",
        "pidMode": "test",
        "ipcMode": "test",
        "proxyConfiguration": "test",
        "inferenceAccelerators": "test",
        "cluster": "cluster",
        "count": "test",
        "startedBy": "test",
        "group": "test",
        "placementStrategy": "test",
        "platformVersion": "test",
        "networkConfiguration": {
            "awsvpcConfiguration": {
                "subnets": ["subnet"],
                "assignPublicIp": "DISABLED",
                "securityGroups": ["security_group"],
            }
        },
        "enableECSManagedTags": "test",
        "propagateTags": "test",
    }

    agent = FargateAgent(
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="token",
        region_name="region",
        **kwarg_dict
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
