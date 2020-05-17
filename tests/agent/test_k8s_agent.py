from unittest.mock import MagicMock

import pytest

pytest.importorskip("kubernetes")

import yaml

import prefect
from prefect.agent.kubernetes import KubernetesAgent
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
        agent = KubernetesAgent(name="test", labels=["test"], namespace="namespace")
        assert agent
        assert agent.labels == ["test"]
        assert agent.name == "test"
        assert agent.namespace == "namespace"
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert agent.batch_client


def test_k8s_agent_deploy_flow(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    batch_client = MagicMock()
    batch_client.create_namespaced_job.return_value = {}
    monkeypatch.setattr(
        "kubernetes.client.BatchV1Api", MagicMock(retrurn_value=batch_client)
    )

    agent = KubernetesAgent()
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

    assert agent.batch_client.create_namespaced_job.called
    assert (
        agent.batch_client.create_namespaced_job.call_args[1]["namespace"] == "default"
    )
    assert (
        agent.batch_client.create_namespaced_job.call_args[1]["body"]["apiVersion"]
        == "batch/v1"
    )


def test_k8s_agent_deploy_flow_raises(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    batch_client = MagicMock()
    batch_client.create_namespaced_job.return_value = {}
    monkeypatch.setattr(
        "kubernetes.client.BatchV1Api", MagicMock(retrurn_value=batch_client)
    )

    agent = KubernetesAgent()
    with pytest.raises(ValueError):
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {
                    "flow": GraphQLResult({"storage": Local().serialize(), "id": "id"}),
                    "id": "id",
                }
            )
        )

    assert not agent.batch_client.create_namespaced_job.called


def test_k8s_agent_replace_yaml_uses_user_env_vars(
    monkeypatch, runner_token, cloud_api
):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    monkeypatch.setenv("IMAGE_PULL_SECRETS", "my-secret")
    monkeypatch.setenv("JOB_MEM_REQUEST", "mr")
    monkeypatch.setenv("JOB_MEM_LIMIT", "ml")
    monkeypatch.setenv("JOB_CPU_REQUEST", "cr")
    monkeypatch.setenv("JOB_CPU_LIMIT", "cl")

    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "id": "new_id",
                }
            ),
            "id": "id",
        }
    )

    with set_temporary_config(
        {"cloud.agent.auth_token": "token", "logging.log_to_cloud": True}
    ):
        agent = KubernetesAgent(env_vars=dict(AUTH_THING="foo", PKG_SETTING="bar"))
        job = agent.replace_job_spec_yaml(flow_run)

        assert job["metadata"]["labels"]["flow_run_id"] == "id"
        assert job["metadata"]["labels"]["flow_id"] == "new_id"
        assert job["spec"]["template"]["metadata"]["labels"]["flow_run_id"] == "id"
        assert (
            job["spec"]["template"]["spec"]["containers"][0]["image"] == "test/name:tag"
        )

        env = job["spec"]["template"]["spec"]["containers"][0]["env"]

        assert env[0]["value"] == "https://api.prefect.io"
        assert env[1]["value"] == "token"
        assert env[2]["value"] == "id"
        assert env[3]["value"] == "new_id"
        assert env[4]["value"] == "default"
        assert env[5]["value"] == "[]"
        assert env[6]["value"] == "true"

        user_vars = [
            dict(name="AUTH_THING", value="foo"),
            dict(name="PKG_SETTING", value="bar"),
        ]
        assert env[-1] in user_vars
        assert env[-2] in user_vars


def test_k8s_agent_replace_yaml(monkeypatch, runner_token, cloud_api):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    monkeypatch.setenv("IMAGE_PULL_SECRETS", "my-secret")
    monkeypatch.setenv("JOB_MEM_REQUEST", "mr")
    monkeypatch.setenv("JOB_MEM_LIMIT", "ml")
    monkeypatch.setenv("JOB_CPU_REQUEST", "cr")
    monkeypatch.setenv("JOB_CPU_LIMIT", "cl")

    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "id": "new_id",
                }
            ),
            "id": "id",
        }
    )

    with set_temporary_config(
        {"cloud.agent.auth_token": "token", "logging.log_to_cloud": True}
    ):
        agent = KubernetesAgent()
        job = agent.replace_job_spec_yaml(flow_run)

        assert job["metadata"]["labels"]["flow_run_id"] == "id"
        assert job["metadata"]["labels"]["flow_id"] == "new_id"
        assert job["spec"]["template"]["metadata"]["labels"]["flow_run_id"] == "id"
        assert (
            job["spec"]["template"]["spec"]["containers"][0]["image"] == "test/name:tag"
        )

        env = job["spec"]["template"]["spec"]["containers"][0]["env"]

        assert env[0]["value"] == "https://api.prefect.io"
        assert env[1]["value"] == "token"
        assert env[2]["value"] == "id"
        assert env[3]["value"] == "new_id"
        assert env[4]["value"] == "default"
        assert env[5]["value"] == "[]"
        assert env[6]["value"] == "true"

        assert (
            job["spec"]["template"]["spec"]["imagePullSecrets"][0]["name"]
            == "my-secret"
        )

        resources = job["spec"]["template"]["spec"]["containers"][0]["resources"]
        assert resources["requests"]["memory"] == "mr"
        assert resources["limits"]["memory"] == "ml"
        assert resources["requests"]["cpu"] == "cr"
        assert resources["limits"]["cpu"] == "cl"


@pytest.mark.parametrize("flag", [True, False])
def test_k8s_agent_replace_yaml_responds_to_logging_config(
    monkeypatch, runner_token, flag
):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "id": "new_id",
                }
            ),
            "id": "id",
            "name": "name",
        }
    )

    agent = KubernetesAgent(no_cloud_logs=flag)
    job = agent.replace_job_spec_yaml(flow_run)
    env = job["spec"]["template"]["spec"]["containers"][0]["env"]
    assert env[6]["value"] == str(not flag).lower()


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


def test_k8s_agent_includes_agent_labels_in_job(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "id": "new_id",
                }
            ),
            "id": "id",
        }
    )

    agent = KubernetesAgent(labels=["foo", "bar"])
    job = agent.replace_job_spec_yaml(flow_run)
    env = job["spec"]["template"]["spec"]["containers"][0]["env"]
    assert env[5]["value"] == "['foo', 'bar']"


def test_k8s_agent_generate_deployment_yaml(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml(
        token="test_token",
        api="test_api",
        namespace="test_namespace",
        resource_manager_enabled=True,
        backend="backend-test",
    )

    deployment = yaml.safe_load(deployment)

    agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]
    resource_manager_env = deployment["spec"]["template"]["spec"]["containers"][1][
        "env"
    ]

    assert agent_env[0]["value"] == "test_token"
    assert agent_env[1]["value"] == "test_api"
    assert agent_env[2]["value"] == "test_namespace"
    assert agent_env[9]["value"] == "backend-test"

    assert resource_manager_env[0]["value"] == "test_token"
    assert resource_manager_env[1]["value"] == "test_api"
    assert resource_manager_env[3]["value"] == "test_namespace"


def test_k8s_agent_generate_deployment_yaml_env_vars(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml(
        env_vars={"test1": "test2", "test3": "test4"}
    )

    deployment = yaml.safe_load(deployment)

    agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]

    assert agent_env[11]["name"] == "PREFECT__CLOUD__AGENT__ENV_VARS__test1"
    assert agent_env[11]["value"] == "test2"
    assert agent_env[12]["name"] == "PREFECT__CLOUD__AGENT__ENV_VARS__test3"
    assert agent_env[12]["value"] == "test4"


def test_k8s_agent_generate_deployment_yaml_backend_default(monkeypatch, server_api):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml()

    deployment = yaml.safe_load(deployment)

    agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]

    assert agent_env[9]["value"] == "server"


@pytest.mark.parametrize(
    "version",
    [
        ("0.6.3", "0.6.3-python3.6"),
        ("0.5.3+114.g35bc7ba4", "latest"),
        ("0.5.2+999.gr34343.dirty", "latest"),
    ],
)
def test_k8s_agent_generate_deployment_yaml_local_version(
    monkeypatch, version, runner_token
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


def test_k8s_agent_generate_deployment_yaml_latest(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml(
        token="test_token",
        api="test_api",
        namespace="test_namespace",
        resource_manager_enabled=True,
        latest=True,
    )

    deployment = yaml.safe_load(deployment)

    agent_yaml = deployment["spec"]["template"]["spec"]["containers"][0]
    resource_manager_yaml = deployment["spec"]["template"]["spec"]["containers"][1]

    assert agent_yaml["image"] == "prefecthq/prefect:latest"
    assert resource_manager_yaml["image"] == "prefecthq/prefect:latest"


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
    agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]
    assert agent_env[3]["value"] == ""


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
    agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]
    assert agent_env[3]["value"] == "secrets"


def test_k8s_agent_generate_deployment_yaml_contains_resources(
    monkeypatch, runner_token
):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml(
        token="test_token",
        api="test_api",
        namespace="test_namespace",
        mem_request="mr",
        mem_limit="ml",
        cpu_request="cr",
        cpu_limit="cl",
    )

    deployment = yaml.safe_load(deployment)

    env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]

    assert env[5]["value"] == "mr"
    assert env[6]["value"] == "ml"
    assert env[7]["value"] == "cr"
    assert env[8]["value"] == "cl"


def test_k8s_agent_generate_deployment_yaml_rbac(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml(
        token="test_token", api="test_api", namespace="test_namespace", rbac=True
    )

    deployment = yaml.safe_load_all(deployment)

    for document in deployment:
        if "rbac" in document:
            assert "rbac" in document["apiVersion"]
            assert document["metadata"]["namespace"] == "test_namespace"
            assert document["metadata"]["name"] == "prefect-agent-rbac"


def test_k8s_agent_start_max_polls(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    on_shutdown = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.on_shutdown", on_shutdown
    )

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.heartbeat", heartbeat
    )

    agent = KubernetesAgent(max_polls=1)
    agent.start()

    assert agent_process.called
    assert heartbeat.called


def test_k8s_gent_start_max_polls_count(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    on_shutdown = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.on_shutdown", on_shutdown
    )

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.heartbeat", heartbeat
    )

    agent = KubernetesAgent(max_polls=2)
    agent.start()

    assert on_shutdown.call_count == 1
    assert agent_process.call_count == 2
    assert heartbeat.call_count == 2


def test_k8s_agent_start_max_polls_zero(monkeypatch, runner_token):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)

    on_shutdown = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.on_shutdown", on_shutdown
    )

    agent_process = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_process", agent_process)

    agent_connect = MagicMock(return_value="id")
    monkeypatch.setattr("prefect.agent.agent.Agent.agent_connect", agent_connect)

    heartbeat = MagicMock()
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.heartbeat", heartbeat
    )

    agent = KubernetesAgent(max_polls=0)
    agent.start()

    assert on_shutdown.call_count == 1
    assert agent_process.call_count == 0
    assert heartbeat.call_count == 0
