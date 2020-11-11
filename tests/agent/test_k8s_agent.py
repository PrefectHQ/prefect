import json
from unittest.mock import MagicMock

import pytest

pytest.importorskip("kubernetes")

import yaml

import prefect
from prefect.agent.kubernetes.agent import KubernetesAgent, read_bytes_from_path
from prefect.environments import LocalEnvironment
from prefect.environments.storage import Docker, Local
from prefect.run_configs import KubernetesRun
from prefect.serialization.run_config import RunConfigSchema
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult


@pytest.fixture(autouse=True)
def mocked_k8s_config(monkeypatch):
    k8s_config = MagicMock()
    monkeypatch.setattr("kubernetes.config", k8s_config)


def test_k8s_agent_init(monkeypatch, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

    agent = KubernetesAgent()
    assert agent
    assert agent.agent_config_id == None
    assert agent.labels == []
    assert agent.name == "agent"
    assert agent.batch_client


def test_k8s_agent_config_options(monkeypatch, cloud_api):
    k8s_client = MagicMock()
    monkeypatch.setattr("kubernetes.client", k8s_client)

    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

    with set_temporary_config({"cloud.agent.auth_token": "TEST_TOKEN"}):
        agent = KubernetesAgent(name="test", labels=["test"], namespace="namespace")
        assert agent
        assert agent.labels == ["test"]
        assert agent.name == "test"
        assert agent.namespace == "namespace"
        assert agent.client.get_auth_token() == "TEST_TOKEN"
        assert agent.logger
        assert agent.batch_client


@pytest.mark.parametrize(
    "core_version,command",
    [
        ("0.10.0", "prefect execute cloud-flow"),
        ("0.6.0+134", "prefect execute cloud-flow"),
        ("0.13.0", "prefect execute flow-run"),
        ("0.13.1+134", "prefect execute flow-run"),
    ],
)
def test_k8s_agent_deploy_flow(core_version, command, monkeypatch, cloud_api):
    batch_client = MagicMock()
    monkeypatch.setattr(
        "kubernetes.client.BatchV1Api", MagicMock(return_value=batch_client)
    )

    core_client = MagicMock()
    core_client.list_namespaced_pod.return_value = MagicMock(items=[])
    monkeypatch.setattr(
        "kubernetes.client.CoreV1Api", MagicMock(return_value=core_client)
    )

    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
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
                        "environment": LocalEnvironment().serialize(),
                        "id": "id",
                        "core_version": core_version,
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
    assert agent.batch_client.create_namespaced_job.call_args[1]["body"]["spec"][
        "template"
    ]["spec"]["containers"][0]["args"] == [command]


def test_k8s_agent_deploy_flow_uses_environment_metadata(monkeypatch, cloud_api):
    batch_client = MagicMock()
    monkeypatch.setattr(
        "kubernetes.client.BatchV1Api", MagicMock(return_value=batch_client)
    )

    core_client = MagicMock()
    core_client.list_namespaced_pod.return_value = MagicMock(items=[])
    monkeypatch.setattr(
        "kubernetes.client.CoreV1Api", MagicMock(return_value=core_client)
    )

    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

    agent = KubernetesAgent()
    agent.deploy_flow(
        flow_run=GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": Local().serialize(),
                        "environment": LocalEnvironment(
                            metadata={"image": "repo/name:tag"}
                        ).serialize(),
                        "id": "id",
                        "core_version": "0.13.0",
                    }
                ),
                "id": "id",
            }
        )
    )

    assert agent.batch_client.create_namespaced_job.called
    assert (
        agent.batch_client.create_namespaced_job.call_args[1]["body"]["spec"][
            "template"
        ]["spec"]["containers"][0]["image"]
        == "repo/name:tag"
    )


def test_k8s_agent_deploy_flow_raises(monkeypatch, cloud_api):
    batch_client = MagicMock()
    monkeypatch.setattr(
        "kubernetes.client.BatchV1Api", MagicMock(return_value=batch_client)
    )

    core_client = MagicMock()
    core_client.list_namespaced_pod.return_value = MagicMock(items=[])
    monkeypatch.setattr(
        "kubernetes.client.CoreV1Api", MagicMock(return_value=core_client)
    )

    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

    agent = KubernetesAgent()
    with pytest.raises(ValueError):
        agent.deploy_flow(
            flow_run=GraphQLResult(
                {
                    "flow": GraphQLResult(
                        {
                            "storage": Local().serialize(),
                            "id": "id",
                            "environment": LocalEnvironment().serialize(),
                            "core_version": "0.13.0",
                        }
                    ),
                    "id": "id",
                }
            )
        )

    assert not agent.batch_client.create_namespaced_job.called


def test_k8s_agent_replace_yaml_uses_user_env_vars(monkeypatch, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

    monkeypatch.setenv("IMAGE_PULL_SECRETS", "my-secret")
    monkeypatch.setenv("JOB_MEM_REQUEST", "mr")
    monkeypatch.setenv("JOB_MEM_LIMIT", "ml")
    monkeypatch.setenv("JOB_CPU_REQUEST", "cr")
    monkeypatch.setenv("JOB_CPU_LIMIT", "cl")
    monkeypatch.setenv("IMAGE_PULL_POLICY", "custom_policy")
    monkeypatch.setenv("SERVICE_ACCOUNT_NAME", "svc_name")

    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "environment": LocalEnvironment().serialize(),
                    "id": "new_id",
                    "core_version": "0.13.0",
                }
            ),
            "id": "id",
        }
    )

    with set_temporary_config(
        {"cloud.agent.auth_token": "token", "logging.log_to_cloud": True}
    ):
        agent = KubernetesAgent(env_vars=dict(AUTH_THING="foo", PKG_SETTING="bar"))
        job = agent.generate_job_spec_from_environment(flow_run, image="test/name:tag")

        assert job["metadata"]["labels"]["prefect.io/flow_run_id"] == "id"
        assert job["metadata"]["labels"]["prefect.io/flow_id"] == "new_id"
        assert (
            job["spec"]["template"]["metadata"]["labels"]["prefect.io/flow_run_id"]
            == "id"
        )
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

        assert (
            job["spec"]["template"]["spec"]["containers"][0]["imagePullPolicy"]
            == "custom_policy"
        )
        assert job["spec"]["template"]["spec"]["serviceAccountName"] == "svc_name"

        assert job["spec"]["template"]["spec"]["imagePullSecrets"] == [
            {"name": "my-secret"}
        ]


def test_k8s_agent_replace_yaml_respects_multiple_image_secrets(monkeypatch, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

    monkeypatch.setenv("IMAGE_PULL_SECRETS", "some-secret,other-secret")
    monkeypatch.setenv("IMAGE_PULL_POLICY", "custom_policy")

    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "environment": LocalEnvironment().serialize(),
                    "id": "new_id",
                    "core_version": "0.13.0",
                }
            ),
            "id": "id",
        }
    )

    with set_temporary_config(
        {"cloud.agent.auth_token": "token", "logging.log_to_cloud": True}
    ):
        agent = KubernetesAgent(env_vars=dict(AUTH_THING="foo", PKG_SETTING="bar"))
        job = agent.generate_job_spec_from_environment(flow_run, image="test/name:tag")
        expected_secrets = [{"name": "some-secret"}, {"name": "other-secret"}]
        assert job["spec"]["template"]["spec"]["imagePullSecrets"] == expected_secrets


def test_k8s_agent_replace_yaml(monkeypatch, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

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
                    "environment": LocalEnvironment().serialize(),
                    "id": "new_id",
                    "core_version": "0.13.0",
                }
            ),
            "id": "id",
        }
    )

    with set_temporary_config(
        {"cloud.agent.auth_token": "token", "logging.log_to_cloud": True}
    ):
        volume_mounts = [{"name": "my-vol", "mountPath": "/mnt/my-mount"}]
        volumes = [{"name": "my-vol", "hostPath": "/host/folder"}]
        agent = KubernetesAgent(volume_mounts=volume_mounts, volumes=volumes)
        job = agent.generate_job_spec_from_environment(flow_run, image="test/name:tag")

        assert job["metadata"]["labels"]["prefect.io/flow_run_id"] == "id"
        assert job["metadata"]["labels"]["prefect.io/flow_id"] == "new_id"
        assert (
            job["spec"]["template"]["metadata"]["labels"]["prefect.io/flow_run_id"]
            == "id"
        )
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

        volumeMounts = job["spec"]["template"]["spec"]["containers"][0]["volumeMounts"]
        assert volumeMounts[0]["name"] == "my-vol"
        assert volumeMounts[0]["mountPath"] == "/mnt/my-mount"

        assert (
            job["spec"]["template"]["spec"]["containers"][0]["imagePullPolicy"]
            == "IfNotPresent"
        )

        volumes = job["spec"]["template"]["spec"]["volumes"]
        assert volumes[0]["name"] == "my-vol"
        assert volumes[0]["hostPath"] == "/host/folder"

        assert job["spec"]["template"]["spec"].get("serviceAccountName", None) is None


@pytest.mark.parametrize("flag", [True, False])
def test_k8s_agent_replace_yaml_responds_to_logging_config(
    monkeypatch, cloud_api, flag
):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "environment": LocalEnvironment().serialize(),
                    "id": "new_id",
                    "core_version": "0.13.0",
                }
            ),
            "id": "id",
            "name": "name",
        }
    )

    agent = KubernetesAgent(no_cloud_logs=flag)
    job = agent.generate_job_spec_from_environment(flow_run, image="test/name:tag")
    env = job["spec"]["template"]["spec"]["containers"][0]["env"]
    assert env[6]["value"] == str(not flag).lower()


def test_k8s_agent_replace_yaml_no_pull_secrets(monkeypatch, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "environment": LocalEnvironment().serialize(),
                    "id": "id",
                    "core_version": "0.13.0",
                }
            ),
            "id": "id",
        }
    )

    agent = KubernetesAgent()
    job = agent.generate_job_spec_from_environment(flow_run, image="test/name:tag")

    assert not job["spec"]["template"]["spec"].get("imagePullSecrets", None)


def test_k8s_agent_removes_yaml_no_volume(monkeypatch, cloud_api):
    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "environment": LocalEnvironment().serialize(),
                    "id": "id",
                    "core_version": "0.13.0",
                }
            ),
            "id": "id",
        }
    )

    agent = KubernetesAgent()
    job = agent.generate_job_spec_from_environment(flow_run, image="test/name:tag")

    assert not job["spec"]["template"]["spec"].get("volumes", None)
    assert not job["spec"]["template"]["spec"]["containers"][0].get(
        "volumeMounts", None
    )


def test_k8s_agent_includes_agent_labels_in_job(monkeypatch, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

    flow_run = GraphQLResult(
        {
            "flow": GraphQLResult(
                {
                    "storage": Docker(
                        registry_url="test", image_name="name", image_tag="tag"
                    ).serialize(),
                    "environment": LocalEnvironment().serialize(),
                    "id": "new_id",
                    "core_version": "0.13.0",
                }
            ),
            "id": "id",
        }
    )

    agent = KubernetesAgent(labels=["foo", "bar"])
    job = agent.generate_job_spec_from_environment(flow_run, image="test/name:tag")
    env = job["spec"]["template"]["spec"]["containers"][0]["env"]
    assert env[5]["value"] == "['foo', 'bar']"


def test_k8s_agent_generate_deployment_yaml(monkeypatch, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

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
    assert agent_env[11]["value"] == "backend-test"

    assert resource_manager_env[0]["value"] == "test_token"
    assert resource_manager_env[1]["value"] == "test_api"
    assert resource_manager_env[3]["value"] == "test_namespace"


def test_k8s_agent_generate_deployment_yaml_env_vars(monkeypatch, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

    agent = KubernetesAgent()
    env_vars = {"test1": "test2", "test3": "test4"}
    deployment = agent.generate_deployment_yaml(env_vars=env_vars)

    deployment = yaml.safe_load(deployment)

    agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]

    assert agent_env[13]["name"] == "PREFECT__CLOUD__AGENT__ENV_VARS"
    assert agent_env[13]["value"] == json.dumps(env_vars)


def test_k8s_agent_generate_deployment_yaml_backend_default(monkeypatch, server_api):
    c = MagicMock()
    monkeypatch.setattr("prefect.agent.agent.Client", c)

    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml()

    deployment = yaml.safe_load(deployment)

    agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]

    assert agent_env[11]["value"] == "server"


@pytest.mark.parametrize(
    "version",
    [
        ("0.6.3", "0.6.3-python3.6"),
        ("0.5.3+114.g35bc7ba4", "latest"),
        ("0.5.2+999.gr34343.dirty", "latest"),
    ],
)
def test_k8s_agent_generate_deployment_yaml_local_version(
    monkeypatch, version, cloud_api
):
    monkeypatch.setattr(prefect, "__version__", version[0])

    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

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


def test_k8s_agent_generate_deployment_yaml_latest(monkeypatch, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

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


def test_k8s_agent_generate_deployment_yaml_no_resource_manager(monkeypatch, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

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


def test_k8s_agent_generate_deployment_yaml_labels(monkeypatch, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

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
    monkeypatch, cloud_api
):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml(
        token="test_token", api="test_api", namespace="test_namespace"
    )

    deployment = yaml.safe_load(deployment)

    assert deployment["spec"]["template"]["spec"].get("imagePullSecrets") is None
    agent_env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]
    assert agent_env[3]["value"] == ""


def test_k8s_agent_generate_deployment_yaml_contains_image_pull_secrets(
    monkeypatch, cloud_api
):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

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


def test_k8s_agent_generate_deployment_yaml_contains_resources(monkeypatch, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

    agent = KubernetesAgent()
    deployment = agent.generate_deployment_yaml(
        token="test_token",
        api="test_api",
        namespace="test_namespace",
        mem_request="mr",
        mem_limit="ml",
        cpu_request="cr",
        cpu_limit="cl",
        image_pull_policy="custom_policy",
        service_account_name="svc",
    )

    deployment = yaml.safe_load(deployment)

    env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]

    assert env[5]["value"] == "mr"
    assert env[6]["value"] == "ml"
    assert env[7]["value"] == "cr"
    assert env[8]["value"] == "cl"
    assert env[9]["value"] == "custom_policy"
    assert env[10]["value"] == "svc"


def test_k8s_agent_generate_deployment_yaml_rbac(monkeypatch, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

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


def test_k8s_agent_start_max_polls(monkeypatch, runner_token, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

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


def test_k8s_gent_start_max_polls_count(monkeypatch, runner_token, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

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
    assert heartbeat.call_count == 1


def test_k8s_agent_start_max_polls_zero(monkeypatch, runner_token, cloud_api):
    get_jobs = MagicMock(return_value=[])
    monkeypatch.setattr(
        "prefect.agent.kubernetes.agent.KubernetesAgent.manage_jobs",
        get_jobs,
    )

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
    assert heartbeat.call_count == 1


def test_k8s_agent_manage_jobs_pass(monkeypatch, cloud_api):
    job_mock = MagicMock()
    job_mock.metadata.labels = {
        "prefect.io/identifier": "id",
        "prefect.io/flow_run_id": "fr",
    }
    job_mock.metadata.name = "my_job"
    batch_client = MagicMock()
    list_job = MagicMock()
    list_job.metadata._continue = 0
    list_job.items = [job_mock]
    batch_client.list_namespaced_job.return_value = list_job
    monkeypatch.setattr(
        "kubernetes.client.BatchV1Api", MagicMock(return_value=batch_client)
    )

    pod = MagicMock()
    pod.metadata.name = "pod_name"
    core_client = MagicMock()
    list_pods = MagicMock()
    list_pods.items = [pod]
    core_client.list_namespaced_pod.return_value = list_pods
    monkeypatch.setattr(
        "kubernetes.client.CoreV1Api", MagicMock(return_value=core_client)
    )

    agent = KubernetesAgent()
    agent.heartbeat()


def test_k8s_agent_manage_jobs_client_call(monkeypatch, cloud_api):
    gql_return = MagicMock(
        return_value=MagicMock(data=MagicMock(set_flow_run_state=None))
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.agent.agent.Client", client)

    job_mock = MagicMock()
    job_mock.metadata.labels = {
        "prefect.io/identifier": "id",
        "prefect.io/flow_run_id": "fr",
    }
    job_mock.metadata.name = "my_job"
    job_mock.status.failed = False
    job_mock.status.succeeded = False
    batch_client = MagicMock()
    list_job = MagicMock()
    list_job.metadata._continue = 0
    list_job.items = [job_mock]
    batch_client.list_namespaced_job.return_value = list_job
    monkeypatch.setattr(
        "kubernetes.client.BatchV1Api", MagicMock(return_value=batch_client)
    )

    pod = MagicMock()
    pod.metadata.name = "pod_name"
    c_status = MagicMock()
    c_status.state.waiting.reason = "ErrImagePull"
    pod.status.container_statuses = [c_status]
    core_client = MagicMock()
    list_pods = MagicMock()
    list_pods.items = [pod]
    core_client.list_namespaced_pod.return_value = list_pods
    monkeypatch.setattr(
        "kubernetes.client.CoreV1Api", MagicMock(return_value=core_client)
    )

    agent = KubernetesAgent()
    agent.manage_jobs()


def test_k8s_agent_manage_jobs_delete_jobs(monkeypatch, cloud_api):
    job_mock = MagicMock()
    job_mock.metadata.labels = {
        "prefect.io/identifier": "id",
        "prefect.io/flow_run_id": "fr",
    }
    job_mock.metadata.name = "my_job"
    job_mock.status.failed = True
    job_mock.status.succeeded = True
    batch_client = MagicMock()
    list_job = MagicMock()
    list_job.metadata._continue = 0
    list_job.items = [job_mock]
    batch_client.list_namespaced_job.return_value = list_job
    batch_client.delete_namespaced_job.return_value = None
    monkeypatch.setattr(
        "kubernetes.client.BatchV1Api", MagicMock(return_value=batch_client)
    )

    agent = KubernetesAgent()
    agent.manage_jobs()

    assert batch_client.delete_namespaced_job.called


class TestK8sAgentRunConfig:
    def setup(self):
        self.agent = KubernetesAgent(
            namespace="testing",
        )

    def read_default_template(self):
        from prefect.agent.kubernetes.agent import DEFAULT_JOB_TEMPLATE_PATH

        with open(DEFAULT_JOB_TEMPLATE_PATH) as f:
            return yaml.safe_load(f)

    def build_flow_run(self, config, storage=None):
        if storage is None:
            storage = Local()
        return GraphQLResult(
            {
                "flow": GraphQLResult(
                    {
                        "storage": storage.serialize(),
                        "run_config": RunConfigSchema().dump(config),
                        "id": "new_id",
                        "core_version": "0.13.0",
                    }
                ),
                "id": "id",
            }
        )

    def test_generate_job_spec_uses_job_template_provided_in_run_config(self):
        template = self.read_default_template()
        labels = template.setdefault("metadata", {}).setdefault("labels", {})
        labels["TEST"] = "VALUE"
        flow_run = self.build_flow_run(KubernetesRun(job_template=template))
        job = self.agent.generate_job_spec(flow_run)
        assert job["metadata"]["labels"]["TEST"] == "VALUE"

    def test_generate_job_spec_uses_job_template_path_provided_in_run_config(
        self, tmpdir, monkeypatch
    ):
        path = str(tmpdir.join("job.yaml"))
        template = self.read_default_template()
        labels = template.setdefault("metadata", {}).setdefault("labels", {})
        labels["TEST"] = "VALUE"
        with open(path, "w") as f:
            yaml.safe_dump(template, f)
        template_path = f"agent://{path}"

        flow_run = self.build_flow_run(KubernetesRun(job_template_path=template_path))

        mocked_read_bytes = MagicMock(wraps=read_bytes_from_path)
        monkeypatch.setattr(
            "prefect.agent.kubernetes.agent.read_bytes_from_path", mocked_read_bytes
        )
        job = self.agent.generate_job_spec(flow_run)
        assert job["metadata"]["labels"]["TEST"] == "VALUE"
        assert mocked_read_bytes.call_args[0] == (template_path,)

    def test_generate_job_spec_metadata(self, tmpdir):
        template_path = str(tmpdir.join("job.yaml"))
        template = self.read_default_template()
        job_labels = template.setdefault("metadata", {}).setdefault("labels", {})
        pod_labels = (
            template["spec"]["template"]
            .setdefault("metadata", {})
            .setdefault("labels", {})
        )
        job_labels.update({"JOB_LABEL": "VALUE1"})
        pod_labels.update({"POD_LABEL": "VALUE2"})
        with open(template_path, "w") as f:
            yaml.safe_dump(template, f)
        self.agent.job_template_path = template_path

        flow_run = self.build_flow_run(KubernetesRun())
        job = self.agent.generate_job_spec(flow_run)

        identifier = job["metadata"]["labels"]["prefect.io/identifier"]
        labels = {
            "prefect.io/identifier": identifier,
            "prefect.io/flow_run_id": flow_run.id,
            "prefect.io/flow_id": flow_run.flow.id,
        }

        assert job["metadata"]["name"]
        assert job["metadata"]["labels"] == dict(JOB_LABEL="VALUE1", **labels)
        assert job["spec"]["template"]["metadata"]["labels"] == dict(
            POD_LABEL="VALUE2", **labels
        )

    @pytest.mark.parametrize(
        "run_config, storage, expected",
        [
            (
                KubernetesRun(),
                Docker(registry_url="test", image_name="name", image_tag="tag"),
                "test/name:tag",
            ),
            (KubernetesRun(image="myimage"), Local(), "myimage"),
            (KubernetesRun(), Local(), "prefecthq/prefect:all_extras-0.13.0"),
        ],
        ids=["on-storage", "on-run_config", "default"],
    )
    def test_generate_job_spec_image(self, run_config, storage, expected):
        flow_run = self.build_flow_run(run_config, storage)
        job = self.agent.generate_job_spec(flow_run)
        image = job["spec"]["template"]["spec"]["containers"][0]["image"]
        assert image == expected

    def test_generate_job_spec_environment_variables(self, tmpdir):
        """Check that environment variables are set in precedence order

        - CUSTOM1 & CUSTOM2 are set on the template
        - CUSTOM2 & CUSTOM3 are set on the agent
        - CUSTOM3 & CUSTOM4 are set on the RunConfig
        """
        template_path = str(tmpdir.join("job.yaml"))
        template = self.read_default_template()
        template_env = template["spec"]["template"]["spec"]["containers"][0].setdefault(
            "env", []
        )
        template_env.extend(
            [
                {"name": "CUSTOM1", "value": "VALUE1"},
                {"name": "CUSTOM2", "value": "VALUE2"},
            ]
        )
        with open(template_path, "w") as f:
            yaml.safe_dump(template, f)
        self.agent.job_template_path = template_path

        self.agent.env_vars = {"CUSTOM2": "OVERRIDE2", "CUSTOM3": "VALUE3"}
        run_config = KubernetesRun(env={"CUSTOM3": "OVERRIDE3", "CUSTOM4": "VALUE4"})

        flow_run = self.build_flow_run(run_config)
        job = self.agent.generate_job_spec(flow_run)
        env_list = job["spec"]["template"]["spec"]["containers"][0]["env"]
        env = {item["name"]: item["value"] for item in env_list}
        assert env == {
            "PREFECT__CLOUD__API": prefect.config.cloud.api,
            "PREFECT__CLOUD__AUTH_TOKEN": prefect.config.cloud.agent.auth_token,
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run.id,
            "PREFECT__CONTEXT__FLOW_ID": flow_run.flow.id,
            "PREFECT__LOGGING__LOG_TO_CLOUD": str(self.agent.log_to_cloud).lower(),
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
            "CUSTOM1": "VALUE1",
            "CUSTOM2": "OVERRIDE2",  # Agent env-vars override those in template
            "CUSTOM3": "OVERRIDE3",  # RunConfig env-vars override those on agent and template
            "CUSTOM4": "VALUE4",
        }

    def test_generate_job_spec_resources(self):
        flow_run = self.build_flow_run(
            KubernetesRun(
                cpu_request=1, cpu_limit=2, memory_request="4G", memory_limit="8G"
            )
        )
        job = self.agent.generate_job_spec(flow_run)
        resources = job["spec"]["template"]["spec"]["containers"][0]["resources"]
        assert resources == {
            "limits": {"cpu": "2", "memory": "8G"},
            "requests": {"cpu": "1", "memory": "4G"},
        }
