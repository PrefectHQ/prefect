from unittest.mock import MagicMock

import box
import pytest
import yaml

pytest.importorskip("boto3")
pytest.importorskip("botocore")

import prefect
from prefect.agent.ecs.agent import (
    merge_run_task_kwargs,
    ECSAgent,
    DEFAULT_TASK_DEFINITION_PATH,
)
from prefect.storage import Local, Docker
from prefect.run_configs import ECSRun, LocalRun, UniversalRun
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.filesystems import read_bytes_from_path
from prefect.utilities.graphql import GraphQLResult
from prefect.utilities.aws import _CLIENT_CACHE


@pytest.fixture(autouse=True)
def clear_boto3_cache():
    _CLIENT_CACHE.clear()


@pytest.fixture
def default_task_definition():
    with open(DEFAULT_TASK_DEFINITION_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture(autouse=True)
def aws(monkeypatch):
    ec2 = MagicMock()
    ec2.describe_vpcs.return_value = {"Vpcs": [{"VpcId": "test-vpc-id"}]}
    ec2.describe_subnets.return_value = {
        "Subnets": [{"SubnetId": "test-subnet-id-1"}, {"SubnetId": "test-subnet-id-2"}]
    }

    clients = dict(ecs=MagicMock(), ec2=ec2, s3=MagicMock())

    def get_client(key, **kwargs):
        if key not in clients:
            raise ValueError("Unknown client type!")
        return clients[key]

    boto3_client = MagicMock(side_effect=get_client)
    monkeypatch.setattr("boto3.client", boto3_client)
    return box.Box(clients)


class TestMergeRunTaskKwargs:
    def test_merge_run_task_kwargs_no_op(self):
        assert merge_run_task_kwargs({}, {}) == {}

    def test_merge_run_task_kwargs_top_level(self):
        opt1 = {"cluster": "testing", "launchType": "FARGATE"}
        opt2 = {"cluster": "new", "enableECSManagedTags": False}
        assert merge_run_task_kwargs(opt1, {}) == opt1
        assert merge_run_task_kwargs({}, opt1) == opt1
        assert merge_run_task_kwargs(opt1, opt2) == {
            "cluster": "new",
            "launchType": "FARGATE",
            "enableECSManagedTags": False,
        }

    def test_merge_run_task_kwargs_overrides(self):
        opt1 = {"overrides": {"cpu": "1024", "memory": "2048"}}
        opt2 = {"overrides": {"cpu": "2048", "taskRoleArn": "testing"}}
        assert merge_run_task_kwargs(opt1, {}) == opt1
        assert merge_run_task_kwargs(opt1, {"overrides": {}}) == opt1
        assert merge_run_task_kwargs({}, opt1) == opt1
        assert merge_run_task_kwargs({"overrides": {}}, opt1) == opt1
        assert merge_run_task_kwargs(opt1, opt2) == {
            "overrides": {"cpu": "2048", "memory": "2048", "taskRoleArn": "testing"}
        }

    def test_merge_run_task_kwargs_container_overrides(self):
        opt1 = {}
        opt2 = {"overrides": {}}
        opt3 = {"overrides": {"containerOverrides": []}}
        opt4 = {
            "overrides": {
                "taskRoleArn": "my-task-role",
                "containerOverrides": [{"name": "a", "cpu": 1, "memory": 2}],
            }
        }
        opt5 = {
            "overrides": {
                "executionRoleArn": "my-ex-role",
                "containerOverrides": [{"name": "a", "cpu": 3, "memoryReservation": 4}],
            }
        }
        opt6 = {
            "overrides": {
                "executionRoleArn": "my-ex-role",
                "containerOverrides": [{"name": "b", "cpu": 5}],
            }
        }
        assert merge_run_task_kwargs(opt4, opt1) == opt4
        assert merge_run_task_kwargs(opt4, opt2) == opt4
        assert merge_run_task_kwargs(opt4, opt3) == opt4
        assert merge_run_task_kwargs(opt1, opt4) == opt4
        assert merge_run_task_kwargs(opt2, opt4) == opt4
        assert merge_run_task_kwargs(opt3, opt4) == opt4
        assert merge_run_task_kwargs(opt4, opt5) == {
            "overrides": {
                "taskRoleArn": "my-task-role",
                "executionRoleArn": "my-ex-role",
                "containerOverrides": [
                    {"name": "a", "cpu": 3, "memory": 2, "memoryReservation": 4}
                ],
            }
        }
        assert merge_run_task_kwargs(opt4, opt6) == {
            "overrides": {
                "taskRoleArn": "my-task-role",
                "executionRoleArn": "my-ex-role",
                "containerOverrides": [
                    {"name": "a", "cpu": 1, "memory": 2},
                    {"name": "b", "cpu": 5},
                ],
            }
        }


def test_boto_kwargs(monkeypatch):
    # Defaults to loaded from environment
    agent = ECSAgent()
    keys = [
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "region_name",
    ]
    for k in keys:
        assert agent.boto_kwargs[k] is None
    assert agent.boto_kwargs["config"].retries == {"mode": "standard"}

    # Explicit parametes are passed on
    kwargs = dict(zip(keys, "abcd"))
    agent = ECSAgent(
        botocore_config={"retries": {"mode": "adaptive", "max_attempts": 2}}, **kwargs
    )
    for k, v in kwargs.items():
        assert agent.boto_kwargs[k] == v
    assert agent.boto_kwargs["config"].retries == {
        "mode": "adaptive",
        "max_attempts": 2,
    }

    # Does not set 'standard' if env variable is set
    monkeypatch.setenv("AWS_RETRY_MODE", "adaptive")
    agent = ECSAgent()
    assert (agent.boto_kwargs["config"].retries or {}).get("mode") is None


def test_agent_defaults(default_task_definition):
    agent = ECSAgent()
    assert agent.agent_config_id is None
    assert set(agent.labels) == set()
    assert agent.name == "agent"
    assert agent.cluster is None
    assert agent.launch_type == "FARGATE"
    assert agent.task_role_arn is None
    assert agent.execution_role_arn is None


class TestAgentTaskDefinitionPath:
    def test_task_definition_path_default(self, default_task_definition):
        agent = ECSAgent()
        assert agent.task_definition == default_task_definition

    def test_task_definition_path_read_errors(self, tmpdir):
        with pytest.raises(Exception):
            ECSAgent(task_definition_path=str(tmpdir.join("missing.yaml")))

    def test_task_definition_path_local(self, tmpdir):
        task_definition = {"networkMode": "awsvpc", "cpu": 2048, "memory": 4096}
        path = str(tmpdir.join("task.yaml"))
        with open(path, "w") as f:
            yaml.safe_dump(task_definition, f)

        agent = ECSAgent(task_definition_path=path)
        assert agent.task_definition == task_definition

    def test_task_definition_path_remote(self, monkeypatch):
        task_definition = {"networkMode": "awsvpc", "cpu": 2048, "memory": 4096}
        data = yaml.safe_dump(task_definition)

        mock = MagicMock(wraps=read_bytes_from_path, return_value=data)
        monkeypatch.setattr("prefect.agent.ecs.agent.read_bytes_from_path", mock)

        agent = ECSAgent(task_definition_path="s3://bucket/test.yaml")
        assert agent.task_definition == task_definition
        assert mock.call_args[0] == ("s3://bucket/test.yaml",)


class TestAgentRunTaskKwargsPath:
    def test_run_task_kwargs_path_default(self):
        agent = ECSAgent(launch_type="EC2")
        assert agent.run_task_kwargs == {}

    def test_run_task_kwargs_path_read_errors(self, tmpdir):
        with pytest.raises(Exception):
            ECSAgent(run_task_kwargs_path=str(tmpdir.join("missing.yaml")))

    def test_run_task_kwargs_path_local(self, tmpdir):
        run_task_kwargs = {"overrides": {"taskRoleArn": "my-task-role"}}
        path = str(tmpdir.join("kwargs.yaml"))
        with open(path, "w") as f:
            yaml.safe_dump(run_task_kwargs, f)

        agent = ECSAgent(launch_type="EC2", run_task_kwargs_path=path)
        assert agent.run_task_kwargs == run_task_kwargs

    def test_run_task_kwargs_path_remote(self, monkeypatch):
        run_task_kwargs = {"overrides": {"taskRoleArn": "my-task-role"}}
        data = yaml.safe_dump(run_task_kwargs)
        s3_path = "s3://bucket/kwargs.yaml"

        def mock(path):
            return data if path == s3_path else read_bytes_from_path(path)

        monkeypatch.setattr("prefect.agent.ecs.agent.read_bytes_from_path", mock)
        agent = ECSAgent(launch_type="EC2", run_task_kwargs_path=s3_path)
        assert agent.run_task_kwargs == run_task_kwargs


class TestInferNetworkConfiguration:
    def test_infer_network_configuration(self):
        agent = ECSAgent()
        assert agent.run_task_kwargs == {
            "networkConfiguration": {
                "awsvpcConfiguration": {
                    "subnets": ["test-subnet-id-1", "test-subnet-id-2"],
                    "assignPublicIp": "ENABLED",
                }
            }
        }

    def test_infer_network_configuration_not_called_if_configured(self, aws, tmpdir):
        run_task_kwargs = {
            "networkConfiguration": {"awsvpcConfiguration": {"subnets": ["one", "two"]}}
        }
        path = str(tmpdir.join("kwargs.yaml"))
        with open(path, "w") as f:
            yaml.safe_dump(run_task_kwargs, f)

        agent = ECSAgent(run_task_kwargs_path=path)
        assert agent.run_task_kwargs == run_task_kwargs
        assert not aws.ec2.mock_calls

    def test_infer_network_configuration_not_called_if_using_ec2(self, aws):
        agent = ECSAgent(launch_type="EC2")
        assert agent.launch_type == "EC2"
        assert agent.run_task_kwargs == {}
        assert not aws.ec2.mock_calls

    def test_infer_network_configuration_errors(self, aws):
        aws.ec2.describe_vpcs.return_value = {"Vpcs": []}
        with pytest.raises(
            ValueError, match="Failed to infer default networkConfiguration"
        ):
            ECSAgent()


class TestGenerateTaskDefinition:
    def generate_task_definition(self, run_config, storage=None, **kwargs):
        if storage is None:
            storage = Local()
        agent = ECSAgent(**kwargs)
        flow_run = GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": storage.serialize(),
                        "id": "flow-id",
                        "version": 1,
                        "name": "Test Flow",
                        "core_version": "0.13.0",
                    }
                ),
                "run_config": run_config.serialize(),
                "id": "flow-run-id",
            }
        )
        return agent.generate_task_definition(flow_run, run_config)

    @pytest.mark.parametrize("use_path", [False, True])
    def test_generate_task_definition_uses_run_config_task_definition(
        self, use_path, monkeypatch
    ):
        task_definition = {
            "tags": [{"key": "mykey", "value": "myvalue"}],
            "cpu": "2048",
            "memory": "4096",
        }

        if use_path:
            data = yaml.safe_dump(task_definition)
            run_config = ECSRun(task_definition_path="s3://test/path.yaml")
            monkeypatch.setattr(
                "prefect.agent.ecs.agent.read_bytes_from_path",
                MagicMock(wraps=read_bytes_from_path, return_value=data),
            )
        else:
            run_config = ECSRun(task_definition=task_definition)

        res = self.generate_task_definition(run_config)
        assert any(e == {"key": "mykey", "value": "myvalue"} for e in res["tags"])
        assert res["memory"] == "4096"
        assert res["cpu"] == "2048"

    def test_generate_task_definition_family_and_tags(self):
        taskdef = self.generate_task_definition(ECSRun())
        assert taskdef["family"] == "prefect-test-flow-flow-run-id"
        assert sorted(taskdef["tags"], key=lambda x: x["key"]) == [
            {"key": "prefect:flow-id", "value": "flow-id"},
            {"key": "prefect:flow-version", "value": "1"},
        ]

    @pytest.mark.parametrize("launch_type", [None, "FARGATE", "EC2"])
    def test_generate_task_definition_requires_compatibilities(self, launch_type):
        taskdef = self.generate_task_definition(ECSRun(), launch_type=launch_type)
        assert taskdef["requiresCompatibilities"] == [launch_type or "FARGATE"]

    @pytest.mark.parametrize(
        "on_run_config, on_agent, expected",
        [
            (None, None, None),
            ("execution-role-1", None, "execution-role-1"),
            (None, "execution-role-2", "execution-role-2"),
            ("execution-role-1", "execution-role-2", "execution-role-1"),
        ],
    )
    def test_get_task_run_kwargs_execution_role_arn(
        self, on_run_config, on_agent, expected
    ):
        taskdef = self.generate_task_definition(
            ECSRun(execution_role_arn=on_run_config), execution_role_arn=on_agent
        )
        assert taskdef.get("executionRoleArn") == expected

    @pytest.mark.parametrize(
        "run_config, storage, expected",
        [
            (
                ECSRun(),
                Docker(registry_url="test", image_name="name", image_tag="tag"),
                "test/name:tag",
            ),
            (ECSRun(image="myimage"), Local(), "myimage"),
            (
                ECSRun(
                    task_definition={
                        "containerDefinitions": [
                            {"name": "flow", "image": "on-template"}
                        ]
                    }
                ),
                Local(),
                "on-template",
            ),
            (ECSRun(), Local(), "prefecthq/prefect:0.13.0"),
        ],
        ids=["on-storage", "on-run_config", "on-template", "default"],
    )
    def test_generate_task_definition_image(self, run_config, storage, expected):
        taskdef = self.generate_task_definition(run_config, storage)
        assert taskdef["containerDefinitions"][0]["image"] == expected

    def test_generate_task_definition_environment(self):
        run_config = ECSRun(
            image="test-image",
            task_definition={
                "containerDefinitions": [
                    {
                        "name": "flow",
                        "environment": [
                            {"name": "CUSTOM1", "value": "VALUE1"},
                            {"name": "CUSTOM2", "value": "VALUE2"},
                        ],
                    }
                ]
            },
            env={"CUSTOM4": "VALUE4"},
        )

        taskdef = self.generate_task_definition(
            run_config, env_vars={"CUSTOM3": "VALUE3"}
        )
        env_list = taskdef["containerDefinitions"][0]["environment"]
        env = {item["name"]: item["value"] for item in env_list}
        # Agent and run-config level envs are only set at runtime
        assert env == {
            "PREFECT__CONTEXT__IMAGE": "test-image",
            "CUSTOM1": "VALUE1",
            "CUSTOM2": "VALUE2",
        }

    def test_generate_task_definition_multiple_containers(self):
        """A container with the name "flow" is used for prefect stuff"""
        run_config = ECSRun(
            task_definition={
                "containerDefinitions": [
                    {"name": "other", "image": "other-image"},
                    {"name": "flow", "cpu": 1234},
                ]
            },
            image="flow-image",
        )
        taskdef = self.generate_task_definition(run_config)
        assert taskdef["containerDefinitions"][0]["name"] == "other"
        assert taskdef["containerDefinitions"][0]["image"] == "other-image"
        assert taskdef["containerDefinitions"][1]["name"] == "flow"
        assert taskdef["containerDefinitions"][1]["cpu"] == 1234
        assert taskdef["containerDefinitions"][1]["image"] == "flow-image"


class TestGetRunTaskKwargs:
    def get_run_task_kwargs(self, run_config, **kwargs):
        agent = ECSAgent(**kwargs)
        agent.client._get_auth_tenant = MagicMock(return_value="ID")
        flow_run = GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Local().serialize(),
                        "id": "flow-id",
                        "version": 1,
                        "name": "Test Flow",
                        "core_version": "0.13.0",
                    }
                ),
                "run_config": run_config.serialize(),
                "id": "flow-run-id",
            }
        )
        return agent.get_run_task_kwargs(flow_run, run_config)

    @pytest.mark.parametrize("launch_type", ["EC2", "FARGATE"])
    @pytest.mark.parametrize("cluster", [None, "my-cluster"])
    def test_get_run_task_kwargs_common(self, launch_type, cluster):
        kwargs = self.get_run_task_kwargs(
            ECSRun(), launch_type=launch_type, cluster=cluster
        )
        assert kwargs["launchType"] == launch_type
        assert kwargs.get("cluster") == cluster
        assert ("networkConfiguration" in kwargs) == (launch_type == "FARGATE")
        assert kwargs["overrides"]["containerOverrides"][0]["name"] == "flow"

    def test_get_run_task_kwargs_merges(self, tmpdir):
        path = str(tmpdir.join("kwargs.yaml"))
        with open(path, "w") as f:
            yaml.safe_dump({"overrides": {"cpu": "1024", "memory": "2048"}}, f)
        kwargs = self.get_run_task_kwargs(
            ECSRun(
                run_task_kwargs={"overrides": {"cpu": "2048", "taskRoleArn": "testing"}}
            ),
            launch_type="EC2",
            run_task_kwargs_path=path,
        )
        del kwargs["overrides"]["containerOverrides"]  # These are checked below
        assert kwargs == {
            "launchType": "EC2",
            "overrides": {"cpu": "2048", "memory": "2048", "taskRoleArn": "testing"},
        }

    def test_get_run_task_kwargs_command(self):
        kwargs = self.get_run_task_kwargs(ECSRun())
        assert kwargs["overrides"]["containerOverrides"][0]["command"] == [
            "/bin/sh",
            "-c",
            "prefect execute flow-run",
        ]

    def test_get_run_task_kwargs_resources(self):
        kwargs = self.get_run_task_kwargs(ECSRun(cpu="2048", memory="4096"))
        assert kwargs["overrides"]["cpu"] == "2048"
        assert kwargs["overrides"]["memory"] == "4096"

    @pytest.mark.parametrize(
        "on_run_config, on_agent, expected",
        [
            (None, None, None),
            ("task-role-1", None, "task-role-1"),
            (None, "task-role-2", "task-role-2"),
            ("task-role-1", "task-role-2", "task-role-1"),
        ],
    )
    def test_get_task_run_kwargs_task_role_arn(self, on_run_config, on_agent, expected):
        kwargs = self.get_run_task_kwargs(
            ECSRun(task_role_arn=on_run_config), task_role_arn=on_agent
        )
        assert kwargs["overrides"].get("taskRoleArn") == expected

    @pytest.mark.parametrize(
        "on_run_config, on_agent, expected",
        [
            (None, None, None),
            ("execution-role-1", None, "execution-role-1"),
            (None, "execution-role-2", "execution-role-2"),
            ("execution-role-1", "execution-role-2", "execution-role-1"),
        ],
    )
    def test_get_task_run_kwargs_execution_role_arn(
        self, on_run_config, on_agent, expected
    ):
        kwargs = self.get_run_task_kwargs(
            ECSRun(execution_role_arn=on_run_config), execution_role_arn=on_agent
        )
        assert kwargs["overrides"].get("executionRoleArn") == expected

    def test_get_run_task_kwargs_environment(self, tmpdir, backend):
        path = str(tmpdir.join("kwargs.yaml"))
        with open(path, "w") as f:
            yaml.safe_dump(
                {
                    "overrides": {
                        "containerOverrides": [
                            {
                                "name": "flow",
                                "environment": [
                                    {"name": "CUSTOM1", "value": "VALUE1"},
                                    {"name": "CUSTOM2", "value": "VALUE2"},
                                ],
                            }
                        ]
                    }
                },
                f,
            )

        kwargs = self.get_run_task_kwargs(
            ECSRun(env={"CUSTOM3": "OVERRIDE3", "CUSTOM4": "VALUE4"}),
            env_vars={"CUSTOM2": "OVERRIDE2", "CUSTOM3": "VALUE3"},
            run_task_kwargs_path=path,
        )
        env_list = kwargs["overrides"]["containerOverrides"][0]["environment"]
        env = {item["name"]: item["value"] for item in env_list}
        assert env == {
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
            "PREFECT__BACKEND": backend,
            "PREFECT__CLOUD__API": prefect.config.cloud.api,
            "PREFECT__CLOUD__AUTH_TOKEN": "",
            "PREFECT__CLOUD__API_KEY": "",
            "PREFECT__CLOUD__TENANT_ID": "",
            "PREFECT__CLOUD__AGENT__LABELS": "[]",
            "PREFECT__CONTEXT__FLOW_RUN_ID": "flow-run-id",
            "PREFECT__CONTEXT__FLOW_ID": "flow-id",
            "PREFECT__CLOUD__SEND_FLOW_RUN_LOGS": "true",
            "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
            "PREFECT__LOGGING__LEVEL": prefect.config.logging.level,
            "CUSTOM1": "VALUE1",
            "CUSTOM2": "OVERRIDE2",  # agent envs override agent run-task-kwargs
            "CUSTOM3": "OVERRIDE3",  # run-config envs override agent
            "CUSTOM4": "VALUE4",
        }

    def test_environment_has_agent_token_from_config(self):
        with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
            env_list = self.get_run_task_kwargs(ECSRun())["overrides"][
                "containerOverrides"
            ][0]["environment"]
            env = {item["name"]: item["value"] for item in env_list}

        assert env["PREFECT__CLOUD__AUTH_TOKEN"] == "TEST_TOKEN"

    @pytest.mark.parametrize("tenant_id", ["ID", None])
    def test_environment_has_api_key_from_config(self, tenant_id):
        with set_temporary_config(
            {
                "cloud.api_key": "TEST_KEY",
                "cloud.tenant_id": tenant_id,
                "cloud.agent.auth_token": None,
            }
        ):
            env_list = self.get_run_task_kwargs(ECSRun())["overrides"][
                "containerOverrides"
            ][0]["environment"]
            env = {item["name"]: item["value"] for item in env_list}

        assert env["PREFECT__CLOUD__API_KEY"] == "TEST_KEY"
        assert env["PREFECT__CLOUD__AUTH_TOKEN"] == "TEST_KEY"
        assert env["PREFECT__CLOUD__TENANT_ID"] == "ID"

    @pytest.mark.parametrize("tenant_id", ["ID", None])
    def test_environment_has_api_key_from_disk(self, monkeypatch, tenant_id):
        """Check that the API key is passed through from the on disk cache"""
        monkeypatch.setattr(
            "prefect.Client.load_auth_from_disk",
            MagicMock(return_value={"api_key": "TEST_KEY", "tenant_id": tenant_id}),
        )

        env_list = self.get_run_task_kwargs(ECSRun())["overrides"][
            "containerOverrides"
        ][0]["environment"]
        env = {item["name"]: item["value"] for item in env_list}

        assert env["PREFECT__CLOUD__API_KEY"] == "TEST_KEY"
        assert env["PREFECT__CLOUD__AUTH_TOKEN"] == "TEST_KEY"
        assert env["PREFECT__CLOUD__TENANT_ID"] == "ID"

    @pytest.mark.parametrize(
        "config, agent_env_vars, run_config_env_vars, expected_logging_level",
        [
            ({"logging.level": "DEBUG"}, {}, {}, "DEBUG"),
            (
                {"logging.level": "DEBUG"},
                {"PREFECT__LOGGING__LEVEL": "TEST2"},
                {},
                "TEST2",
            ),
            (
                {"logging.level": "DEBUG"},
                {"PREFECT__LOGGING__LEVEL": "TEST2"},
                {"PREFECT__LOGGING__LEVEL": "TEST"},
                "TEST",
            ),
        ],
    )
    def test_prefect_logging_level_override_logic(
        self, config, agent_env_vars, run_config_env_vars, expected_logging_level
    ):
        with set_temporary_config(config):
            kwargs = self.get_run_task_kwargs(
                ECSRun(env=run_config_env_vars), env_vars=agent_env_vars
            )
            env_list = kwargs["overrides"]["containerOverrides"][0]["environment"]
            env = {item["name"]: item["value"] for item in env_list}
            assert env["PREFECT__LOGGING__LEVEL"] == expected_logging_level


class TestDeployFlow:
    def deploy_flow(self, run_config, storage=None, **kwargs):
        agent = ECSAgent(**kwargs)
        flow_run = GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": (storage or Local()).serialize(),
                        "id": "flow-id",
                        "version": 1,
                        "name": "Test Flow",
                        "core_version": "0.13.0",
                    }
                ),
                "run_config": run_config.serialize() if run_config else None,
                "id": "flow-run-id",
            }
        )
        return agent.deploy_flow(flow_run)

    def test_deploy_flow_errors_if_not_ecs_run_config(self):
        with pytest.raises(
            TypeError,
            match="`run_config` of type `LocalRun`, only `ECSRun` is supported",
        ):
            self.deploy_flow(LocalRun())

    def test_deploy_flow_errors_if_mix_task_definition_arn_and_docker_storage(self):
        with pytest.raises(
            ValueError,
            match="Cannot provide `task_definition_arn` when using `Docker` storage",
        ):
            self.deploy_flow(
                ECSRun(task_definition_arn="my-taskdef-arn"),
                storage=Docker(registry_url="test", image_name="name", image_tag="tag"),
            )

    @pytest.mark.parametrize("run_config", [ECSRun(), UniversalRun(), None])
    def test_deploy_flow_registers_new_task_definition(self, run_config, aws):
        aws.ecs.register_task_definition.return_value = {
            "taskDefinition": {"taskDefinitionArn": "my-taskdef-arn"}
        }
        aws.ecs.run_task.return_value = {"tasks": [{"taskArn": "my-task-arn"}]}

        res = self.deploy_flow(run_config)
        assert aws.ecs.register_task_definition.called
        assert (
            aws.ecs.register_task_definition.call_args[1]["family"]
            == "prefect-test-flow"
        )
        assert aws.ecs.run_task.called
        assert aws.ecs.run_task.call_args[1]["taskDefinition"] == "my-taskdef-arn"
        assert "my-task-arn" in res
        assert aws.ecs.deregister_task_definition.called
        assert (
            aws.ecs.deregister_task_definition.call_args[1]["taskDefinition"]
            == "my-taskdef-arn"
        )

    def test_deploy_flow_uses_provided_task_definition_arn(self, aws):
        aws.ecs.run_task.return_value = {"tasks": [{"taskArn": "my-task-arn"}]}

        res = self.deploy_flow(ECSRun(task_definition_arn="my-taskdef-arn"))
        assert not aws.ecs.register_task_definition.called
        assert aws.ecs.run_task.called
        assert aws.ecs.run_task.call_args[1]["taskDefinition"] == "my-taskdef-arn"
        assert not aws.ecs.deregister_task_definition.called
        assert "my-task-arn" in res

    def test_deploy_flow_run_task_fails(self, aws):
        aws.ecs.run_task.return_value = {
            "tasks": [],
            "failures": [{"reason": "my-reason"}],
        }
        with pytest.raises(ValueError) as exc:
            self.deploy_flow(ECSRun())
        assert aws.ecs.run_task.called
        assert aws.ecs.deregister_task_definition.called
        assert "my-reason" in str(exc.value)

    def test_deploy_flow_forwards_run_task_kwargs(self, aws):
        aws.ecs.register_task_definition.return_value = {
            "taskDefinition": {"taskDefinitionArn": "my-taskdef-arn"}
        }
        aws.ecs.run_task.return_value = {"tasks": [{"taskArn": "my-task-arn"}]}

        res = self.deploy_flow(ECSRun(run_task_kwargs={"enableECSManagedTags": True}))
        assert aws.ecs.run_task.called
        assert aws.ecs.run_task.call_args[1]["taskDefinition"] == "my-taskdef-arn"
        assert aws.ecs.run_task.call_args[1]["enableECSManagedTags"] is True
        assert "my-task-arn" in res

    def test_deploy_flow_forwards_run_config_settings(self, aws):
        aws.ecs.register_task_definition.return_value = {
            "taskDefinition": {"taskDefinitionArn": "my-taskdef-arn"}
        }
        aws.ecs.run_task.return_value = {"tasks": [{"taskArn": "my-task-arn"}]}

        self.deploy_flow(ECSRun(cpu=8, memory=1024))

        aws.ecs.run_task.assert_called_once()
        assert aws.ecs.run_task.call_args[1]["overrides"]["cpu"] == "8"
        assert aws.ecs.run_task.call_args[1]["overrides"]["memory"] == "1024"
