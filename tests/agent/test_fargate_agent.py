from unittest.mock import MagicMock

import pytest

from prefect.agent.fargate import FargateAgent
from prefect.environments.storage import Docker, Local
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


def test_fargate_agent_config_options(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    botocore_config = MagicMock()
    monkeypatch.setattr("botocore.config.Config", botocore_config)

    # Client args
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "")
    monkeypatch.setenv("REGION_NAME", "")

    monkeypatch.delenv("AWS_ACCESS_KEY_ID")
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY")
    monkeypatch.delenv("AWS_SESSION_TOKEN")
    monkeypatch.delenv("REGION_NAME")

    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = FargateAgent(name="test", labels=["test"])
        assert agent
        assert agent.labels == ["test"]
        assert agent.name == "test"
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert agent.boto3_client

        assert boto3_client.call_args[0][0] == "ecs"
        assert boto3_client.call_args[1]["aws_access_key_id"] == None
        assert boto3_client.call_args[1]["aws_secret_access_key"] == None
        assert boto3_client.call_args[1]["aws_session_token"] == None
        assert boto3_client.call_args[1]["region_name"] == None

        assert botocore_config.called
        assert botocore_config.call_args == {}


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

    (
        task_definition_kwargs,
        task_run_kwargs,
        container_definitions_kwargs,
    ) = agent._parse_kwargs(kwarg_dict)

    assert task_definition_kwargs == kwarg_dict
    assert task_run_kwargs == {"placementConstraints": "test", "tags": "test"}


def test_parse_task_definition_kwargs_errors(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    agent = FargateAgent()

    kwarg_dict = {
        "placementConstraints": "taskRoleArn='arn:aws:iam::543216789012:role/Dev",
    }

    (
        task_definition_kwargs,
        task_run_kwargs,
        container_definitions_kwargs,
    ) = agent._parse_kwargs(kwarg_dict)

    assert task_definition_kwargs == kwarg_dict
    assert task_run_kwargs == {
        "placementConstraints": "taskRoleArn='arn:aws:iam::543216789012:role/Dev"
    }


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

    (
        task_definition_kwargs,
        task_run_kwargs,
        container_definitions_kwargs,
    ) = agent._parse_kwargs(kwarg_dict)

    assert task_run_kwargs == kwarg_dict
    assert task_definition_kwargs == {"placementConstraints": "test", "tags": "test"}


def test_parse_container_definition_kwargs(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    agent = FargateAgent()

    kwarg_dict = {
        "containerDefinitions": [
            {"environment": "test", "secrets": "test", "mountPoints": "test"}
        ]
    }

    (
        task_definition_kwargs,
        task_run_kwargs,
        container_definitions_kwargs,
    ) = agent._parse_kwargs(kwarg_dict)

    assert container_definitions_kwargs == {
        "environment": "test",
        "secrets": "test",
        "mountPoints": "test",
    }


def test_parse_container_definition_kwargs_errors(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    agent = FargateAgent()

    kwarg_dict = {
        "containerDefinitions": [
            {
                "secrets": [
                    {
                        "name": "TEST_SECRET1",
                        "valueFrom": "arn:aws:ssm:us-east-1:123456789101:parameter/test/test",
                    }
                ],
            }
        ]
    }

    (
        task_definition_kwargs,
        task_run_kwargs,
        container_definitions_kwargs,
    ) = agent._parse_kwargs(kwarg_dict)

    assert container_definitions_kwargs == {
        "secrets": [
            {
                "name": "TEST_SECRET1",
                "valueFrom": "arn:aws:ssm:us-east-1:123456789101:parameter/test/test",
            }
        ]
    }


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

    (
        task_definition_kwargs,
        task_run_kwargs,
        container_definitions_kwargs,
    ) = agent._parse_kwargs(kwarg_dict)

    assert task_definition_kwargs == def_kwarg_dict
    assert task_run_kwargs == run_kwarg_dict


def test_parse_task_kwargs_invalid_value_removed(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    agent = FargateAgent()

    kwarg_dict = {"test": "not_real", "containerDefinitions": [{"test": "not_real",}]}

    (
        task_definition_kwargs,
        task_run_kwargs,
        container_definitions_kwargs,
    ) = agent._parse_kwargs(kwarg_dict)

    assert task_definition_kwargs == {}
    assert task_run_kwargs == {}
    assert container_definitions_kwargs == {}


def test_fargate_agent_config_options_init(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    botocore_config = MagicMock()
    monkeypatch.setattr("botocore.config.Config", botocore_config)

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

    container_def_kwargs_dict = {
        "environment": "test",
        "secrets": "test",
        "mountPoints": "test",
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
        "containerDefinitions": [
            {"environment": "test", "secrets": "test", "mountPoints": "test"}
        ],
    }

    agent = FargateAgent(
        name="test",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="token",
        region_name="region",
        botocore_config={"test": "config"},
        **kwarg_dict
    )
    assert agent
    assert agent.name == "test"
    assert agent.task_definition_kwargs == def_kwarg_dict
    assert agent.task_run_kwargs == run_kwarg_dict
    assert agent.container_definitions_kwargs == container_def_kwargs_dict

    assert boto3_client.call_args[0][0] == "ecs"
    assert boto3_client.call_args[1]["aws_access_key_id"] == "id"
    assert boto3_client.call_args[1]["aws_secret_access_key"] == "secret"
    assert boto3_client.call_args[1]["aws_session_token"] == "token"
    assert boto3_client.call_args[1]["region_name"] == "region"

    assert botocore_config.called
    assert botocore_config.call_args[1] == {"test": "config"}


def test_fargate_agent_config_env_vars(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    botocore_config = MagicMock()
    monkeypatch.setattr("botocore.config.Config", botocore_config)

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

    container_def_kwargs_dict = {
        "environment": "test",
        "secrets": "test",
        "mountPoints": "test",
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
    monkeypatch.setenv("containerDefinitions_environment", "test")
    monkeypatch.setenv("containerDefinitions_secrets", "test")
    monkeypatch.setenv("containerDefinitions_mountPoints", "test")

    agent = FargateAgent(subnets=["subnet"])
    assert agent
    assert agent.task_definition_kwargs == def_kwarg_dict
    assert agent.task_run_kwargs == run_kwarg_dict
    assert agent.container_definitions_kwargs == container_def_kwargs_dict

    assert boto3_client.call_args[0][0] == "ecs"
    assert boto3_client.call_args[1]["aws_access_key_id"] == "id"
    assert boto3_client.call_args[1]["aws_secret_access_key"] == "secret"
    assert boto3_client.call_args[1]["aws_session_token"] == "token"
    assert boto3_client.call_args[1]["region_name"] == "region"

    assert botocore_config.called
    assert botocore_config.call_args == {}


def test_fargate_agent_config_env_vars_lists_dicts(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    botocore_config = MagicMock()
    monkeypatch.setattr("botocore.config.Config", botocore_config)

    def_kwarg_dict = {
        "placementConstraints": ["test"],
        "proxyConfiguration": {"test": "test"},
    }

    run_kwarg_dict = {
        "placementConstraints": ["test"],
        "networkConfiguration": {"test": "test"},
    }

    container_def_kwargs_dict = {
        "environment": [{"name": "test", "value": "test"}],
        "secrets": [{"name": "test", "valueFrom": "test"}],
        "mountPoints": [
            {"sourceVolume": "myEfsVolume", "containerPath": "/data", "readOnly": False}
        ],
    }

    # Client args
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "token")
    monkeypatch.setenv("REGION_NAME", "region")

    # Def / run args
    monkeypatch.setenv("placementConstraints", "['test']")
    monkeypatch.setenv("proxyConfiguration", "{'test': 'test'}")
    monkeypatch.setenv("networkConfiguration", "{'test': 'test'}")
    monkeypatch.setenv(
        "containerDefinitions_environment", '[{"name": "test", "value": "test"}]'
    )
    monkeypatch.setenv(
        "containerDefinitions_secrets", '[{"name": "test", "valueFrom": "test"}]'
    )
    monkeypatch.setenv(
        "containerDefinitions_mountPoints",
        '[{"sourceVolume": "myEfsVolume", "containerPath": "/data", "readOnly": False}]',
    )

    agent = FargateAgent(subnets=["subnet"])
    assert agent
    assert agent.task_definition_kwargs == def_kwarg_dict
    assert agent.task_run_kwargs == run_kwarg_dict
    assert agent.container_definitions_kwargs == container_def_kwargs_dict

    assert boto3_client.call_args[0][0] == "ecs"
    assert boto3_client.call_args[1]["aws_access_key_id"] == "id"
    assert boto3_client.call_args[1]["aws_secret_access_key"] == "secret"
    assert boto3_client.call_args[1]["aws_session_token"] == "token"
    assert boto3_client.call_args[1]["region_name"] == "region"

    assert botocore_config.called
    assert botocore_config.call_args == {}


def test_deploy_flow_local_storage_raises(monkeypatch, runner_token):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.return_value = {}
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent()

    with pytest.raises(ValueError):
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {
                    "flow": GraphQLResult({"storage": Local().serialize(), "id": "id"}),
                    "id": "id",
                }
            ),
        )

    assert not boto3_client.describe_task_definition.called
    assert not boto3_client.run_task.called


def test_deploy_flow_docker_storage_raises(monkeypatch, runner_token):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.return_value = {}
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
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
                "name": "name",
            }
        )
    )

    assert boto3_client.describe_task_definition.called
    assert boto3_client.run_task.called


def test_deploy_flow_all_args(monkeypatch, runner_token):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.return_value = {}
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}

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
    agent.deploy_flow(
        flow_run=GraphQLResult(
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
                    {"name": "PREFECT__CONTEXT__FLOW_ID", "value": "id"},
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


def test_deploy_flow_register_task_definition(monkeypatch, runner_token):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.side_effect = ClientError({}, None)
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}
    boto3_client.register_task_definition.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
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
    )

    assert boto3_client.describe_task_definition.called
    assert boto3_client.register_task_definition.called
    assert (
        boto3_client.register_task_definition.call_args[1]["family"]
        == "prefect-task-id"
    )


def test_deploy_flow_register_task_definition_uses_user_env_vars(
    monkeypatch, runner_token
):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.side_effect = ClientError({}, None)
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}
    boto3_client.register_task_definition.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent(env_vars=dict(AUTH_THING="foo", PKG_SETTING="bar"))
    agent.deploy_flow(
        flow_run=GraphQLResult(
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
    )

    assert boto3_client.describe_task_definition.called
    assert boto3_client.register_task_definition.called
    assert (
        boto3_client.register_task_definition.call_args[1]["family"]
        == "prefect-task-id"
    )

    container_defs = boto3_client.register_task_definition.call_args[1][
        "containerDefinitions"
    ]

    user_vars = [
        dict(name="AUTH_THING", value="foo"),
        dict(name="PKG_SETTING", value="bar"),
    ]
    assert container_defs[0]["environment"][-1] in user_vars
    assert container_defs[0]["environment"][-2] in user_vars


def test_deploy_flow_register_task_definition_all_args(
    monkeypatch, runner_token, cloud_api
):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.side_effect = ClientError({}, None)
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}
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
        "containerDefinitions": [
            {
                "environment": [{"name": "TEST_ENV", "value": "Success!"}],
                "secrets": [
                    {
                        "name": "TEST_SECRET1",
                        "valueFrom": "arn:aws:ssm:us-east-1:123456789101:parameter/test/test",
                    },
                    {
                        "name": "TEST_SECRET",
                        "valueFrom": "arn:aws:ssm:us-east-1:123456789101:parameter/test/test",
                    },
                ],
                "mountPoints": [
                    {
                        "sourceVolume": "myEfsVolume",
                        "containerPath": "/data",
                        "readOnly": False,
                    }
                ],
            }
        ],
    }

    with set_temporary_config({"logging.log_to_cloud": True}):
        agent = FargateAgent(
            aws_access_key_id="id",
            aws_secret_access_key="secret",
            aws_session_token="token",
            region_name="region",
            **kwarg_dict
        )
    agent.deploy_flow(
        flow_run=GraphQLResult(
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
                {"name": "PREFECT__CLOUD__AGENT__LABELS", "value": "[]"},
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
                {"name": "TEST_ENV", "value": "Success!"},
            ],
            "essential": True,
            "secrets": [
                {
                    "name": "TEST_SECRET1",
                    "valueFrom": "arn:aws:ssm:us-east-1:123456789101:parameter/test/test",
                },
                {
                    "name": "TEST_SECRET",
                    "valueFrom": "arn:aws:ssm:us-east-1:123456789101:parameter/test/test",
                },
            ],
            "mountPoints": [
                {
                    "sourceVolume": "myEfsVolume",
                    "containerPath": "/data",
                    "readOnly": False,
                }
            ],
        }
    ]
    assert boto3_client.register_task_definition.call_args[1][
        "requiresCompatibilities"
    ] == ["FARGATE"]
    assert boto3_client.register_task_definition.call_args[1]["networkMode"] == "awsvpc"
    assert boto3_client.register_task_definition.call_args[1]["cpu"] == "1"
    assert boto3_client.register_task_definition.call_args[1]["memory"] == "2"


@pytest.mark.parametrize("flag", [True, False])
def test_deploy_flows_includes_agent_labels_in_environment(
    monkeypatch, runner_token, flag, cloud_api
):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.side_effect = ClientError({}, None)
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}
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
        labels=["aws", "staging"],
        no_cloud_logs=flag,
        **kwarg_dict
    )
    agent.deploy_flow(
        flow_run=GraphQLResult(
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
                {
                    "name": "PREFECT__CLOUD__AGENT__LABELS",
                    "value": "['aws', 'staging']",
                },
                {"name": "PREFECT__CLOUD__USE_LOCAL_SECRETS", "value": "false"},
                {
                    "name": "PREFECT__LOGGING__LOG_TO_CLOUD",
                    "value": str(not flag).lower(),
                },
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
            "secrets": [],
            "mountPoints": [],
        }
    ]
    assert boto3_client.register_task_definition.call_args[1][
        "requiresCompatibilities"
    ] == ["FARGATE"]
    assert boto3_client.register_task_definition.call_args[1]["networkMode"] == "awsvpc"
    assert boto3_client.register_task_definition.call_args[1]["cpu"] == "1"
    assert boto3_client.register_task_definition.call_args[1]["memory"] == "2"


def test_deploy_flow_register_task_definition_no_repo_credentials(
    monkeypatch, runner_token, cloud_api
):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.side_effect = ClientError({}, None)
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}
    boto3_client.register_task_definition.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    with set_temporary_config({"logging.log_to_cloud": True}):
        agent = FargateAgent()

    agent.deploy_flow(
        flow_run=GraphQLResult(
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
                {"name": "PREFECT__CLOUD__AGENT__LABELS", "value": "[]"},
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
            "secrets": [],
            "mountPoints": [],
        }
    ]


def test_deploy_flows_require_docker_storage(monkeypatch, runner_token):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.return_value = {"tags": []}
    boto3_client.run_task.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))
    with pytest.raises(Exception) as excinfo:
        agent = FargateAgent()
        agent.deploy_flow(
            GraphQLResult(
                {
                    "flow": GraphQLResult(
                        {
                            "storage": Local().serialize(),
                            "id": "id",
                            "version": 2,
                            "name": "name",
                        }
                    ),
                    "id": "id",
                    "name": "name",
                }
            )
        )
    assert boto3_client.describe_task_definition.not_called
    assert boto3_client.run_task.not_called


# test to support task revisions and external kwargs


def test_deploy_flows_enable_task_revisions_no_tags(
    monkeypatch, runner_token, cloud_api
):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.return_value = {"tags": []}
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}
    boto3_client.register_task_definition.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent(enable_task_revisions=True)
    agent.deploy_flow(
        GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "id": "id",
                        "version": 2,
                        "name": "name",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )
    assert boto3_client.describe_task_definition.called
    assert boto3_client.register_task_definition.called
    boto3_client.register_task_definition.assert_called_with(
        containerDefinitions=[
            {
                "name": "flow",
                "image": "test/name:tag",
                "command": ["/bin/sh", "-c", "prefect execute cloud-flow"],
                "environment": [
                    {"name": "PREFECT__CLOUD__API", "value": "https://api.prefect.io"},
                    {"name": "PREFECT__CLOUD__AGENT__LABELS", "value": "[]"},
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
                "secrets": [],
                "mountPoints": [],
            }
        ],
        family="name",
        networkMode="awsvpc",
        requiresCompatibilities=["FARGATE"],
        tags=[
            {"key": "PrefectFlowId", "value": "id"},
            {"key": "PrefectFlowVersion", "value": "2"},
        ],
    )
    assert boto3_client.run_task.called
    assert boto3_client.run_task.called_with(taskDefinition="name")


def test_deploy_flows_enable_task_revisions_tags_current(monkeypatch, runner_token):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.return_value = {
        "tags": [
            {"key": "PrefectFlowId", "value": "id"},
            {"key": "PrefectFlowVersion", "value": "5"},
        ]
    }
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}
    boto3_client.register_task_definition.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent(enable_task_revisions=True)
    agent.deploy_flow(
        GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "id": "id",
                        "version": 5,
                        "name": "name #1",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )
    assert boto3_client.describe_task_definition.called
    assert boto3_client.register_task_definition.not_called
    assert boto3_client.run_task.called_with(taskDefinition="name-1")


def test_deploy_flows_enable_task_revisions_old_version_exists(
    monkeypatch, runner_token
):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.return_value = {
        "tags": [
            {"key": "PrefectFlowId", "value": "current_id"},
            {"key": "PrefectFlowVersion", "value": "5"},
        ]
    }
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}
    boto3_client.get_resources.return_value = {
        "ResourceTagMappingList": [
            {"ResourceARN": "arn:aws:ecs:us-east-1:12345:task-definition/flow:22"}
        ]
    }

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent(enable_task_revisions=True)
    agent.deploy_flow(
        GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "id": "id",
                        "version": 3,
                        "name": "name",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )
    assert boto3_client.describe_task_definition.called
    assert boto3_client.get_resources.called
    assert boto3_client.register_task_definition.not_called
    assert boto3_client.run_task.called_with(
        taskDefinition="arn:aws:ecs:us-east-1:12345:task-definition/flow:22"
    )


def test_override_kwargs(monkeypatch, runner_token):

    boto3_resource = MagicMock()
    streaming_body = MagicMock()
    streaming_body.read.return_value.decode.return_value = """{
              "cpu": "256",
              "networkConfiguration": "test",
              "containerDefinitions": [{
                "environment": [{
                  "name": "TEST_ENV",
                  "value": "Success!"
                }],
                "secrets": [{
                    "name": "TEST_SECRET1",
                    "valueFrom": "arn:aws:ssm:us-east-1:123456789101:parameter/test/test"
                  },
                  {
                    "name": "TEST_SECRET",
                    "valueFrom": "arn:aws:ssm:us-east-1:123456789101:parameter/test/test"
                  }
                ],
                "mountPoints": [{
                  "sourceVolume": "myEfsVolume",
                  "containerPath": "/data",
                  "readOnly": false
                }]
              }]
            }"""
    boto3_resource.return_value.Object.return_value.get.return_value = {
        "Body": streaming_body
    }
    monkeypatch.setattr("boto3.resource", boto3_resource)

    agent = FargateAgent(
        use_external_kwargs=True,
        external_kwargs_s3_bucket="test-bucket",
        external_kwargs_s3_key="prefect-artifacts/kwargs",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="token",
        region_name="region",
        labels=["aws", "staging"],
    )
    definition_kwargs = {}
    run_kwargs = {}
    container_definitions_kwargs = {}
    agent._override_kwargs(
        GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "id": "id",
                        "version": 2,
                        "name": "name",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        ),
        definition_kwargs,
        run_kwargs,
        container_definitions_kwargs,
    )
    print(container_definitions_kwargs)
    assert boto3_resource.called
    assert streaming_body.read().decode.called
    assert definition_kwargs == {"cpu": "256"}
    assert run_kwargs == {"networkConfiguration": "test"}
    assert container_definitions_kwargs == {
        "environment": [{"name": "TEST_ENV", "value": "Success!"}],
        "secrets": [
            {
                "name": "TEST_SECRET1",
                "valueFrom": "arn:aws:ssm:us-east-1:123456789101:parameter/test/test",
            },
            {
                "name": "TEST_SECRET",
                "valueFrom": "arn:aws:ssm:us-east-1:123456789101:parameter/test/test",
            },
        ],
        "mountPoints": [
            {"sourceVolume": "myEfsVolume", "containerPath": "/data", "readOnly": False}
        ],
    }


def test_override_kwargs_exception(monkeypatch, runner_token):

    boto3_resource = MagicMock()
    streaming_body = MagicMock()
    streaming_body.read.return_value.decode.side_effect = ClientError({}, None)
    boto3_resource.return_value.Object.return_value.get.return_value = {
        "Body": streaming_body
    }
    monkeypatch.setattr("boto3.resource", boto3_resource)

    agent = FargateAgent(
        use_external_kwargs=True,
        external_kwargs_s3_bucket="test-bucket",
        external_kwargs_s3_key="prefect-artifacts/kwargs",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="token",
        region_name="region",
        labels=["aws", "staging"],
    )
    definition_kwargs = {}
    run_kwargs = {}
    container_definitions_kwargs = {}
    agent._override_kwargs(
        GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "id": "id",
                        "version": 2,
                        "name": "name",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        ),
        definition_kwargs,
        run_kwargs,
        container_definitions_kwargs,
    )

    assert boto3_resource.called
    assert streaming_body.read().decode.called
    assert definition_kwargs == {}
    assert run_kwargs == {}
    assert container_definitions_kwargs == {}


def test_deploy_flows_enable_task_revisions_tags_passed_in(monkeypatch, runner_token):
    boto3_client = MagicMock()

    boto3_client.describe_task_definition.return_value = {
        "tags": [{"key": "PrefectFlowId", "value": "id"}]
    }
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}
    boto3_client.register_task_definition.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    agent = FargateAgent(
        enable_task_revisions=True,
        tags=[
            {"key": "PrefectFlowId", "value": "id"},
            {"key": "PrefectFlowVersion", "value": "2"},
        ],
    )
    agent.deploy_flow(
        GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "id": "id",
                        "version": 2,
                        "name": "name",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )
    assert agent.task_definition_kwargs == {
        "tags": [
            {"key": "PrefectFlowId", "value": "id"},
            {"key": "PrefectFlowVersion", "value": "2"},
        ]
    }
    assert boto3_client.describe_task_definition.called
    assert boto3_client.register_task_definition.not_called
    assert boto3_client.run_task.called
    assert boto3_client.run_task.called_with(taskDefinition="name")


def test_deploy_flows_enable_task_revisions_with_external_kwargs(
    monkeypatch, runner_token, cloud_api
):
    boto3_client = MagicMock()
    boto3_resource = MagicMock()
    streaming_body = MagicMock()

    streaming_body.read.return_value.decode.return_value = '{"cpu": "256", "networkConfiguration": "test", "tags": [{"key": "test", "value": "test"}]}'
    boto3_resource.return_value.Object.return_value.get.return_value = {
        "Body": streaming_body
    }

    boto3_client.describe_task_definition.return_value = {
        "tags": [
            {"key": "PrefectFlowId", "value": "id"},
            {"key": "PrefectFlowVersion", "value": "5"},
        ]
    }
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}
    boto3_client.register_task_definition.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))
    monkeypatch.setattr("boto3.resource", boto3_resource)

    agent = FargateAgent(
        enable_task_revisions=True,
        use_external_kwargs=True,
        external_kwargs_s3_bucket="test-bucket",
        external_kwargs_s3_key="prefect-artifacts/kwargs",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="token",
        region_name="region",
        cluster="test",
        tags=[{"key": "team", "value": "data"}],
        labels=["aws", "staging"],
        no_cloud_logs=True,
    )
    agent.deploy_flow(
        GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "id": "new_id",
                        "version": 6,
                        "name": "name",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )
    assert boto3_client.describe_task_definition.called
    boto3_client.register_task_definition.assert_called_with(
        containerDefinitions=[
            {
                "name": "flow",
                "image": "test/name:tag",
                "command": ["/bin/sh", "-c", "prefect execute cloud-flow"],
                "environment": [
                    {"name": "PREFECT__CLOUD__API", "value": "https://api.prefect.io"},
                    {
                        "name": "PREFECT__CLOUD__AGENT__LABELS",
                        "value": "['aws', 'staging']",
                    },
                    {"name": "PREFECT__CLOUD__USE_LOCAL_SECRETS", "value": "false"},
                    {"name": "PREFECT__LOGGING__LOG_TO_CLOUD", "value": "false"},
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
                "secrets": [],
                "mountPoints": [],
            }
        ],
        cpu="256",
        family="name",
        networkMode="awsvpc",
        requiresCompatibilities=["FARGATE"],
        tags=[
            {"key": "test", "value": "test"},
            {"key": "PrefectFlowId", "value": "new_id"},
            {"key": "PrefectFlowVersion", "value": "6"},
        ],
    )
    boto3_client.run_task.assert_called_with(
        launchType="FARGATE",
        networkConfiguration="test",
        cluster="test",
        overrides={
            "containerOverrides": [
                {
                    "name": "flow",
                    "environment": [
                        {"name": "PREFECT__CLOUD__AUTH_TOKEN", "value": ""},
                        {"name": "PREFECT__CONTEXT__FLOW_RUN_ID", "value": "id"},
                        {"name": "PREFECT__CONTEXT__FLOW_ID", "value": "new_id"},
                    ],
                }
            ]
        },
        taskDefinition="name",
        tags=[{"key": "test", "value": "test"}],
    )
    assert boto3_client.run_task.called_with(taskDefinition="name")


def test_deploy_flows_disable_task_revisions_with_external_kwargs(
    monkeypatch, runner_token
):
    boto3_client = MagicMock()
    boto3_resource = MagicMock()
    streaming_body = MagicMock()

    streaming_body.read.return_value.decode.return_value = '{"cpu": "256", "networkConfiguration": "test", "tags": [{"key": "test", "value": "test"}]}'
    boto3_resource.return_value.Object.return_value.get.return_value = {
        "Body": streaming_body
    }

    boto3_client.describe_task_definition.return_value = {}
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}
    boto3_client.register_task_definition.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))
    monkeypatch.setattr("boto3.resource", boto3_resource)

    agent = FargateAgent(
        enable_task_revisions=False,
        use_external_kwargs=True,
        external_kwargs_s3_bucket="test-bucket",
        external_kwargs_s3_key="prefect-artifacts/kwargs",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="token",
        region_name="region",
        cluster="test",
        labels=["aws", "staging"],
    )
    agent.deploy_flow(
        GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "id": "new_id",
                        "version": 6,
                        "name": "name",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )
    assert agent.task_definition_kwargs == {}
    assert boto3_client.describe_task_definition.called
    assert boto3_client.register_task_definition.not_called
    boto3_client.run_task.assert_called_with(
        launchType="FARGATE",
        networkConfiguration="test",
        cluster="test",
        overrides={
            "containerOverrides": [
                {
                    "name": "flow",
                    "environment": [
                        {"name": "PREFECT__CLOUD__AUTH_TOKEN", "value": ""},
                        {"name": "PREFECT__CONTEXT__FLOW_RUN_ID", "value": "id"},
                        {"name": "PREFECT__CONTEXT__FLOW_ID", "value": "new_id"},
                    ],
                }
            ]
        },
        taskDefinition="prefect-task-new_id",
        tags=[{"key": "test", "value": "test"}],
    )
    assert boto3_client.run_task.called_with(taskDefinition="prefect-task-new_id")


def test_deploy_flows_launch_type_ec2(monkeypatch, runner_token):
    boto3_client = MagicMock()
    boto3_resource = MagicMock()
    streaming_body = MagicMock()

    streaming_body.read.return_value.decode.return_value = '{"cpu": "256", "networkConfiguration": "test", "tags": [{"key": "test", "value": "test"}]}'
    boto3_resource.return_value.Object.return_value.get.return_value = {
        "Body": streaming_body
    }

    boto3_client.describe_task_definition.return_value = {}
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}
    boto3_client.register_task_definition.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))
    monkeypatch.setattr("boto3.resource", boto3_resource)

    agent = FargateAgent(
        launch_type="EC2",
        enable_task_revisions=False,
        use_external_kwargs=True,
        external_kwargs_s3_bucket="test-bucket",
        external_kwargs_s3_key="prefect-artifacts/kwargs",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="token",
        region_name="region",
        cluster="test",
        labels=["aws", "staging"],
    )
    agent.deploy_flow(
        GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "id": "new_id",
                        "version": 6,
                        "name": "name",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )
    assert agent.task_definition_kwargs == {}
    assert boto3_client.describe_task_definition.called
    assert boto3_client.register_task_definition.not_called
    boto3_client.run_task.assert_called_with(
        launchType="EC2",
        networkConfiguration="test",
        cluster="test",
        overrides={
            "containerOverrides": [
                {
                    "name": "flow",
                    "environment": [
                        {"name": "PREFECT__CLOUD__AUTH_TOKEN", "value": ""},
                        {"name": "PREFECT__CONTEXT__FLOW_RUN_ID", "value": "id"},
                        {"name": "PREFECT__CONTEXT__FLOW_ID", "value": "new_id"},
                    ],
                }
            ]
        },
        taskDefinition="prefect-task-new_id",
        tags=[{"key": "test", "value": "test"}],
    )
    assert boto3_client.run_task.called_with(taskDefinition="prefect-task-new_id")


def test_deploy_flows_launch_type_none(monkeypatch, runner_token):
    boto3_client = MagicMock()
    boto3_resource = MagicMock()
    streaming_body = MagicMock()

    streaming_body.read.return_value.decode.return_value = '{"cpu": "256", "networkConfiguration": "test", "tags": [{"key": "test", "value": "test"}]}'
    boto3_resource.return_value.Object.return_value.get.return_value = {
        "Body": streaming_body
    }

    boto3_client.describe_task_definition.return_value = {}
    boto3_client.run_task.return_value = {"tasks": [{"taskArn": "test"}]}
    boto3_client.register_task_definition.return_value = {}

    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))
    monkeypatch.setattr("boto3.resource", boto3_resource)

    agent = FargateAgent(
        launch_type=None,
        enable_task_revisions=False,
        use_external_kwargs=True,
        external_kwargs_s3_bucket="test-bucket",
        external_kwargs_s3_key="prefect-artifacts/kwargs",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="token",
        region_name="region",
        cluster="test",
        labels=["aws", "staging"],
    )
    agent.deploy_flow(
        GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Docker(
                            registry_url="test", image_name="name", image_tag="tag"
                        ).serialize(),
                        "id": "new_id",
                        "version": 6,
                        "name": "name",
                    }
                ),
                "id": "id",
                "name": "name",
            }
        )
    )
    assert agent.task_definition_kwargs == {}
    assert boto3_client.describe_task_definition.called
    assert boto3_client.register_task_definition.not_called
    boto3_client.run_task.assert_called_with(
        networkConfiguration="test",
        cluster="test",
        overrides={
            "containerOverrides": [
                {
                    "name": "flow",
                    "environment": [
                        {"name": "PREFECT__CLOUD__AUTH_TOKEN", "value": ""},
                        {"name": "PREFECT__CONTEXT__FLOW_RUN_ID", "value": "id"},
                        {"name": "PREFECT__CONTEXT__FLOW_ID", "value": "new_id"},
                    ],
                }
            ]
        },
        taskDefinition="prefect-task-new_id",
        tags=[{"key": "test", "value": "test"}],
    )
    assert boto3_client.run_task.called_with(taskDefinition="prefect-task-new_id")


def test_fargate_agent_start_max_polls(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    on_shutdown = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.fargate.agent.FargateAgent.on_shutdown", on_shutdown
    )

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.fargate.agent.FargateAgent.heartbeat", heartbeat)

    agent = FargateAgent(max_polls=1)
    agent.start()

    assert agent_process.called
    assert heartbeat.called


def test_fargate_agent_start_max_polls_count(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    on_shutdown = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.fargate.agent.FargateAgent.on_shutdown", on_shutdown
    )

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.fargate.agent.FargateAgent.heartbeat", heartbeat)

    agent = FargateAgent(max_polls=2)
    agent.start()

    assert on_shutdown.call_count == 1
    assert agent_process.call_count == 2
    assert heartbeat.call_count == 2


def test_fargate_agent_start_max_polls_zero(monkeypatch, runner_token):
    boto3_client = MagicMock()
    monkeypatch.setattr("boto3.client", boto3_client)

    on_shutdown = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.fargate.agent.FargateAgent.on_shutdown", on_shutdown
    )

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr("prefect.agent.fargate.agent.FargateAgent.heartbeat", heartbeat)

    agent = FargateAgent(max_polls=0)
    agent.start()

    assert on_shutdown.call_count == 1
    assert agent_process.call_count == 0
    assert heartbeat.call_count == 0
