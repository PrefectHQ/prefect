from unittest.mock import MagicMock


import cloudpickle
import pytest

import prefect
from prefect import Flow, config
from prefect.engine.executors import LocalDaskExecutor
from prefect.environments import FargateTaskEnvironment
from prefect.environments.storage import Docker
from prefect.utilities.configuration import set_temporary_config

from botocore.exceptions import ClientError


def test_create_fargate_task_environment():
    environment = FargateTaskEnvironment()
    assert environment.executor is not None
    assert environment.labels == set()
    assert environment.on_start is None
    assert environment.on_exit is None
    assert environment.metadata == {}
    assert environment.logger.name == "prefect.FargateTaskEnvironment"


def test_create_fargate_task_environment_with_executor():
    executor = LocalDaskExecutor()
    environment = FargateTaskEnvironment(executor=executor)
    assert environment.executor is executor


def test_create_fargate_task_environment_with_deprecated_executor_kwargs():
    with set_temporary_config(
        {"engine.executor.default_class": "prefect.engine.executors.LocalDaskExecutor"}
    ):
        with pytest.warns(UserWarning, match="executor_kwargs"):
            environment = FargateTaskEnvironment(
                executor_kwargs={"scheduler": "synchronous"}
            )
    assert isinstance(environment.executor, LocalDaskExecutor)
    assert environment.executor.scheduler == "synchronous"


def test_create_fargate_task_environment_labels():
    environment = FargateTaskEnvironment(labels=["foo"])
    assert environment.labels == set(["foo"])


def test_create_fargate_task_environment_callbacks():
    def f():
        pass

    environment = FargateTaskEnvironment(labels=["foo"], on_start=f, on_exit=f)
    assert environment.labels == set(["foo"])
    assert environment.on_start is f
    assert environment.on_exit is f


def test_fargate_task_environment_dependencies():
    environment = FargateTaskEnvironment()
    assert environment.dependencies == ["boto3", "botocore"]


def test_create_fargate_task_environment_aws_creds_provided():
    environment = FargateTaskEnvironment(
        labels=["foo"],
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="session",
        region_name="region",
    )
    assert environment.labels == set(["foo"])
    assert environment.aws_access_key_id == "id"
    assert environment.aws_secret_access_key == "secret"
    assert environment.aws_session_token == "session"
    assert environment.region_name == "region"


def test_create_fargate_task_environment_aws_creds_environment(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "session")
    monkeypatch.setenv("REGION_NAME", "region")

    environment = FargateTaskEnvironment(labels=["foo"])
    assert environment.labels == set(["foo"])
    assert environment.aws_access_key_id == "id"
    assert environment.aws_secret_access_key == "secret"
    assert environment.aws_session_token == "session"
    assert environment.region_name == "region"


def test_parse_task_definition_kwargs():
    environment = FargateTaskEnvironment()

    kwarg_dict = {
        "family": "test",
        "taskRoleArn": "test",
        "executionRoleArn": "test",
        "networkMode": "test",
        "containerDefinitions": "test",
        "volumes": "test",
        "placementConstraints": "test",
        "requiresCompatibilities": "test",
        "cpu": "test",
        "memory": "test",
        "tags": "test",
        "pidMode": "test",
        "ipcMode": "test",
        "proxyConfiguration": "test",
        "inferenceAccelerators": "test",
    }

    task_definition_kwargs, task_run_kwargs = environment._parse_kwargs(kwarg_dict)

    assert task_definition_kwargs == kwarg_dict
    assert task_run_kwargs == {"placementConstraints": "test", "tags": "test"}


def test_parse_task_run_kwargs():
    environment = FargateTaskEnvironment()

    kwarg_dict = {
        "cluster": "test",
        "taskDefinition": "test",
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

    task_definition_kwargs, task_run_kwargs = environment._parse_kwargs(kwarg_dict)

    assert task_run_kwargs == kwarg_dict
    assert task_definition_kwargs == {"placementConstraints": "test", "tags": "test"}


def test_parse_task_definition_and_run_kwargs():
    environment = FargateTaskEnvironment()

    def_kwarg_dict = {
        "family": "test",
        "taskRoleArn": "test",
        "executionRoleArn": "test",
        "networkMode": "test",
        "containerDefinitions": "test",
        "volumes": "test",
        "placementConstraints": "test",
        "requiresCompatibilities": "test",
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
        "taskDefinition": "test",
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
        "family": "test",
        "taskRoleArn": "test",
        "executionRoleArn": "test",
        "networkMode": "test",
        "containerDefinitions": "test",
        "volumes": "test",
        "placementConstraints": "test",
        "requiresCompatibilities": "test",
        "cpu": "test",
        "memory": "test",
        "tags": "test",
        "pidMode": "test",
        "ipcMode": "test",
        "proxyConfiguration": "test",
        "inferenceAccelerators": "test",
        "cluster": "test",
        "taskDefinition": "test",
        "count": "test",
        "startedBy": "test",
        "group": "test",
        "placementStrategy": "test",
        "platformVersion": "test",
        "networkConfiguration": "test",
        "enableECSManagedTags": "test",
        "propagateTags": "test",
    }

    task_definition_kwargs, task_run_kwargs = environment._parse_kwargs(kwarg_dict)

    assert task_definition_kwargs == def_kwarg_dict
    assert task_run_kwargs == run_kwarg_dict


def test_parse_task_kwargs_invalid_value_removed():
    environment = FargateTaskEnvironment()

    kwarg_dict = {"test": "not_real"}

    task_definition_kwargs, task_run_kwargs = environment._parse_kwargs(kwarg_dict)

    assert task_definition_kwargs == {}
    assert task_run_kwargs == {}


def test_setup_definition_exists(monkeypatch):
    existing_task_definition = {
        "containerDefinitions": [
            {
                "environment": [
                    {"name": "PREFECT__CLOUD__GRAPHQL", "value": config.cloud.graphql},
                    {"name": "PREFECT__CLOUD__USE_LOCAL_SECRETS", "value": "false"},
                    {
                        "name": "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS",
                        "value": "prefect.engine.cloud.CloudFlowRunner",
                    },
                    {
                        "name": "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS",
                        "value": "prefect.engine.cloud.CloudTaskRunner",
                    },
                    {"name": "PREFECT__LOGGING__LOG_TO_CLOUD", "value": "true"},
                    {
                        "name": "PREFECT__LOGGING__EXTRA_LOGGERS",
                        "value": str(config.logging.extra_loggers),
                    },
                ],
                "name": "flow-container",
                "image": "test/image:tag",
                "command": [
                    "/bin/sh",
                    "-c",
                    "python -c 'import prefect; prefect.environments.execution.load_and_run_flow()'",
                ],
            }
        ],
    }

    boto3_client = MagicMock()
    boto3_client.describe_task_definition.return_value = {
        "taskDefinition": existing_task_definition
    }
    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    environment = FargateTaskEnvironment()

    environment.setup(
        Flow(
            "test",
            storage=Docker(registry_url="test", image_name="image", image_tag="tag"),
        )
    )

    assert boto3_client.describe_task_definition.called
    assert not boto3_client.register_task_definition.called


def test_setup_definition_changed(monkeypatch):
    existing_task_definition = {
        "containerDefinitions": [
            {
                "environment": [
                    {"name": "PREFECT__CLOUD__GRAPHQL", "value": config.cloud.graphql},
                    {"name": "PREFECT__CLOUD__USE_LOCAL_SECRETS", "value": "false"},
                    {
                        "name": "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS",
                        "value": "prefect.engine.cloud.CloudFlowRunner",
                    },
                    {
                        "name": "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS",
                        "value": "prefect.engine.cloud.CloudTaskRunner",
                    },
                    {"name": "PREFECT__LOGGING__LOG_TO_CLOUD", "value": "true"},
                    {
                        "name": "PREFECT__LOGGING__EXTRA_LOGGERS",
                        "value": str(config.logging.extra_loggers),
                    },
                ],
                "name": "flow-container",
                "image": "test/image:tag",
                "command": [
                    "/bin/sh",
                    "-c",
                    "python -c 'import prefect; prefect.environments.execution.load_and_run_flow()'",
                ],
            }
        ],
        "memory": 256,
        "cpu": 512,
    }

    boto3_client = MagicMock()
    boto3_client.describe_task_definition.return_value = {
        "taskDefinition": existing_task_definition
    }
    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    environment = FargateTaskEnvironment(memory=256, cpu=1024)

    with pytest.raises(ValueError):
        environment.setup(
            Flow(
                "test",
                storage=Docker(
                    registry_url="test", image_name="image", image_tag="newtag"
                ),
            )
        )

    assert boto3_client.describe_task_definition.called
    assert not boto3_client.register_task_definition.called


def test_setup_definition_register(monkeypatch):
    boto3_client = MagicMock()
    boto3_client.describe_task_definition.side_effect = ClientError({}, None)
    boto3_client.register_task_definition.return_value = {}
    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    environment = FargateTaskEnvironment(
        family="test",
        containerDefinitions=[
            {
                "name": "flow-container",
                "image": "image",
                "command": [],
                "environment": [],
                "essential": True,
            }
        ],
    )

    environment.setup(
        Flow(
            "test",
            storage=Docker(registry_url="test", image_name="image", image_tag="tag"),
        )
    )

    assert boto3_client.describe_task_definition.called
    assert boto3_client.register_task_definition.called
    assert boto3_client.register_task_definition.call_args[1]["family"] == "test"
    assert boto3_client.register_task_definition.call_args[1][
        "containerDefinitions"
    ] == [
        {
            "name": "flow-container",
            "image": "test/image:tag",
            "command": [
                "/bin/sh",
                "-c",
                "python -c 'import prefect; prefect.environments.execution.load_and_run_flow()'",
            ],
            "environment": [
                {
                    "name": "PREFECT__CLOUD__GRAPHQL",
                    "value": prefect.config.cloud.graphql,
                },
                {"name": "PREFECT__CLOUD__USE_LOCAL_SECRETS", "value": "false"},
                {
                    "name": "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS",
                    "value": "prefect.engine.cloud.CloudFlowRunner",
                },
                {
                    "name": "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS",
                    "value": "prefect.engine.cloud.CloudTaskRunner",
                },
                {"name": "PREFECT__LOGGING__LOG_TO_CLOUD", "value": "true"},
                {"name": "PREFECT__LOGGING__EXTRA_LOGGERS", "value": "[]",},
            ],
            "essential": True,
        }
    ]


def test_setup_definition_register_no_defintions(monkeypatch):
    boto3_client = MagicMock()
    boto3_client.describe_task_definition.side_effect = ClientError({}, None)
    boto3_client.register_task_definition.return_value = {}
    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    environment = FargateTaskEnvironment(family="test")

    environment.setup(
        Flow(
            "test",
            storage=Docker(registry_url="test", image_name="image", image_tag="tag"),
        )
    )

    assert boto3_client.describe_task_definition.called
    assert boto3_client.register_task_definition.called
    assert boto3_client.register_task_definition.call_args[1]["family"] == "test"
    assert boto3_client.register_task_definition.call_args[1][
        "containerDefinitions"
    ] == [
        {
            "environment": [
                {
                    "name": "PREFECT__CLOUD__GRAPHQL",
                    "value": prefect.config.cloud.graphql,
                },
                {"name": "PREFECT__CLOUD__USE_LOCAL_SECRETS", "value": "false"},
                {
                    "name": "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS",
                    "value": "prefect.engine.cloud.CloudFlowRunner",
                },
                {
                    "name": "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS",
                    "value": "prefect.engine.cloud.CloudTaskRunner",
                },
                {"name": "PREFECT__LOGGING__LOG_TO_CLOUD", "value": "true"},
                {"name": "PREFECT__LOGGING__EXTRA_LOGGERS", "value": "[]",},
            ],
            "name": "flow-container",
            "image": "test/image:tag",
            "command": [
                "/bin/sh",
                "-c",
                "python -c 'import prefect; prefect.environments.execution.load_and_run_flow()'",
            ],
        }
    ]


def test_execute_run_task(monkeypatch):
    boto3_client = MagicMock()
    boto3_client.run_task.return_value = {}
    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    with set_temporary_config({"cloud.auth_token": "test"}):
        environment = FargateTaskEnvironment(
            cluster="test", family="test", taskDefinition="test"
        )

        environment.execute(
            Flow(
                "test",
                storage=Docker(
                    registry_url="test", image_name="image", image_tag="tag"
                ),
            ),
        )

        assert boto3_client.run_task.called
        assert boto3_client.run_task.call_args[1]["taskDefinition"] == "test"
        assert boto3_client.run_task.call_args[1]["overrides"] == {
            "containerOverrides": [
                {
                    "name": "flow-container",
                    "environment": [
                        {
                            "name": "PREFECT__CLOUD__AUTH_TOKEN",
                            "value": prefect.config.cloud.get("auth_token"),
                        },
                        {"name": "PREFECT__CONTEXT__FLOW_RUN_ID", "value": "unknown"},
                        {"name": "PREFECT__CONTEXT__IMAGE", "value": "test/image:tag"},
                    ],
                }
            ]
        }
        assert boto3_client.run_task.call_args[1]["launchType"] == "FARGATE"
        assert boto3_client.run_task.call_args[1]["cluster"] == "test"


def test_execute_run_task_agent_token(monkeypatch):
    boto3_client = MagicMock()
    boto3_client.run_task.return_value = {}
    monkeypatch.setattr("boto3.client", MagicMock(return_value=boto3_client))

    with set_temporary_config({"cloud.agent.auth_token": "test"}):
        environment = FargateTaskEnvironment(
            cluster="test", family="test", taskDefinition="test"
        )

        environment.execute(
            Flow(
                "test",
                storage=Docker(
                    registry_url="test", image_name="image", image_tag="tag"
                ),
            ),
        )

        assert boto3_client.run_task.called
        assert boto3_client.run_task.call_args[1]["taskDefinition"] == "test"
        assert boto3_client.run_task.call_args[1]["overrides"] == {
            "containerOverrides": [
                {
                    "name": "flow-container",
                    "environment": [
                        {
                            "name": "PREFECT__CLOUD__AUTH_TOKEN",
                            "value": prefect.config.cloud.agent.get("auth_token"),
                        },
                        {"name": "PREFECT__CONTEXT__FLOW_RUN_ID", "value": "unknown"},
                        {"name": "PREFECT__CONTEXT__IMAGE", "value": "test/image:tag"},
                    ],
                }
            ]
        }
        assert boto3_client.run_task.call_args[1]["launchType"] == "FARGATE"
        assert boto3_client.run_task.call_args[1]["cluster"] == "test"


def test_environment_run():
    class MyExecutor(LocalDaskExecutor):
        submit_called = False

        def submit(self, *args, **kwargs):
            self.submit_called = True
            return super().submit(*args, **kwargs)

    global_dict = {}

    @prefect.task
    def add_to_dict():
        global_dict["run"] = True

    executor = MyExecutor()
    environment = FargateTaskEnvironment(executor=executor)
    flow = prefect.Flow("test", tasks=[add_to_dict], environment=environment)

    environment.run(flow=flow)

    assert global_dict.get("run") is True
    assert executor.submit_called


def test_roundtrip_cloudpickle():
    environment = FargateTaskEnvironment(cluster="test")

    assert environment.task_run_kwargs == {"cluster": "test"}

    new = cloudpickle.loads(cloudpickle.dumps(environment))
    assert isinstance(new, FargateTaskEnvironment)
    assert new.task_run_kwargs == {"cluster": "test"}
