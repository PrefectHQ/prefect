import os
import tempfile
from os import path
from unittest.mock import MagicMock

import cloudpickle
import pytest
import yaml

import prefect
from prefect.environments import DaskKubernetesEnvironment
from prefect.storage import Docker, Local
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult

base_flow = prefect.Flow("test", storage=Docker())


def test_create_dask_environment():
    environment = DaskKubernetesEnvironment()
    assert environment
    assert environment.min_workers == 1
    assert environment.max_workers == 2
    assert environment.work_stealing is True
    assert environment.scheduler_logs is False
    assert environment.private_registry is False
    assert environment.docker_secret is None
    assert environment.labels == set()
    assert environment.on_start is None
    assert environment.on_exit is None
    assert environment.metadata == {}
    assert environment.logger.name == "prefect.DaskKubernetesEnvironment"
    assert environment.image_pull_secret is None


def test_create_dask_environment_args():
    environment = DaskKubernetesEnvironment(
        min_workers=5,
        max_workers=6,
        work_stealing=False,
        scheduler_logs=True,
        private_registry=True,
        docker_secret="docker",
        metadata={"test": "here"},
        image_pull_secret="secret",
    )
    assert environment
    assert environment.min_workers == 5
    assert environment.max_workers == 6
    assert environment.work_stealing is False
    assert environment.scheduler_logs is True
    assert environment.private_registry is True
    assert environment.docker_secret == "docker"
    assert environment.metadata == {"test": "here"}
    assert environment.image_pull_secret == "secret"


def test_create_dask_environment_multiple_image_secrets_in_args():
    environment = DaskKubernetesEnvironment(
        min_workers=5,
        max_workers=6,
        work_stealing=False,
        scheduler_logs=True,
        private_registry=True,
        docker_secret="docker",
        metadata={"test": "here"},
        image_pull_secret="some-cred,different-cred",
    )
    assert environment.image_pull_secret == "some-cred,different-cred"


def test_create_dask_environment_labels():
    environment = DaskKubernetesEnvironment(labels=["foo"])
    assert environment.labels == set(["foo"])


def test_create_dask_environment_callbacks():
    def f():
        pass

    environment = DaskKubernetesEnvironment(labels=["foo"], on_start=f, on_exit=f)
    assert environment.labels == set(["foo"])
    assert environment.on_start is f
    assert environment.on_exit is f


def test_dask_environment_dependencies():
    environment = DaskKubernetesEnvironment()
    assert environment.dependencies == ["kubernetes"]


def test_create_dask_environment_identifier_label():
    environment = DaskKubernetesEnvironment()
    assert environment.identifier_label


def test_create_dask_environment_identifier_label_none():
    environment = DaskKubernetesEnvironment()
    environment._identifier_label = None
    assert environment.identifier_label


def test_setup_dask_environment_passes():
    environment = DaskKubernetesEnvironment()
    environment.setup(flow=base_flow)
    assert environment


def test_setup_doesnt_pass_if_private_registry(monkeypatch):
    environment = DaskKubernetesEnvironment(private_registry=True)
    assert environment.docker_secret == "DOCKER_REGISTRY_CREDENTIALS"

    config = MagicMock()
    monkeypatch.setattr("kubernetes.config", config)

    v1 = MagicMock()
    v1.list_namespaced_secret.return_value = MagicMock(items=[])
    monkeypatch.setattr(
        "kubernetes.client", MagicMock(CoreV1Api=MagicMock(return_value=v1))
    )

    create_secret = MagicMock()
    monkeypatch.setattr(
        "prefect.environments.DaskKubernetesEnvironment._create_namespaced_secret",
        create_secret,
    )
    with set_temporary_config({"cloud.auth_token": "test"}):
        environment.setup(flow=base_flow)

    assert create_secret.called


def test_create_secret_isnt_called_if_exists(monkeypatch):
    environment = DaskKubernetesEnvironment(private_registry=True)

    config = MagicMock()
    monkeypatch.setattr("kubernetes.config", config)

    secret = MagicMock()
    secret.metadata.name = "foo-docker"
    v1 = MagicMock()
    v1.list_namespaced_secret.return_value = MagicMock(items=[secret])
    monkeypatch.setattr(
        "kubernetes.client", MagicMock(CoreV1Api=MagicMock(return_value=v1))
    )

    create_secret = MagicMock()
    monkeypatch.setattr(
        "prefect.environments.DaskKubernetesEnvironment._create_namespaced_secret",
        create_secret,
    )
    with set_temporary_config({"cloud.auth_token": "test"}):
        with prefect.context(namespace="foo"):
            environment.setup(flow=base_flow)

    assert not create_secret.called


def test_execute(monkeypatch):
    environment = DaskKubernetesEnvironment()

    config = MagicMock()
    monkeypatch.setattr("kubernetes.config", config)

    batchv1 = MagicMock()
    monkeypatch.setattr(
        "kubernetes.client", MagicMock(BatchV1Api=MagicMock(return_value=batchv1))
    )

    environment = DaskKubernetesEnvironment()
    storage = Docker(registry_url="test1", image_name="test2", image_tag="test3")

    flow = base_flow
    flow.storage = storage
    with set_temporary_config({"cloud.auth_token": "test"}):
        environment.execute(flow=flow)

    assert (
        batchv1.create_namespaced_job.call_args[1]["body"]["apiVersion"] == "batch/v1"
    )


def test_create_namespaced_job_fails_outside_cluster():
    environment = DaskKubernetesEnvironment()
    storage = Docker(registry_url="test1", image_name="test2", image_tag="test3")

    with pytest.raises(EnvironmentError):
        with set_temporary_config({"cloud.auth_token": "test"}):
            flow = base_flow
            flow.storage = storage
            with set_temporary_config({"cloud.auth_token": "test"}):
                environment.execute(flow=flow)


def test_environment_run(monkeypatch):
    from prefect.executors import DaskExecutor

    start_func = MagicMock()
    exit_func = MagicMock()

    flow = prefect.Flow("my-flow")
    flow.environment = DaskKubernetesEnvironment(
        on_start=start_func,
        on_exit=exit_func,
        min_workers=3,
        max_workers=5,
    )

    flow_runner = MagicMock()
    flow_runner_class = MagicMock(return_value=flow_runner)
    monkeypatch.setattr(
        "prefect.engine.get_default_flow_runner_class",
        MagicMock(return_value=flow_runner_class),
    )

    kube_cluster = MagicMock()
    kube_cluster.scheduler_address = "tcp://fake-address:8786"
    kube_cluster_class = MagicMock()
    kube_cluster_class.from_dict.return_value = kube_cluster
    monkeypatch.setattr("dask_kubernetes.KubeCluster", kube_cluster_class)

    with set_temporary_config({"cloud.auth_token": "test"}), prefect.context(
        {"flow_run_id": "id", "namespace": "mynamespace"}
    ):
        flow.environment.run(flow)

    # Flow runner creation
    assert flow_runner_class.call_args[1]["flow"] is flow

    # Kube cluster is created with proper config
    assert kube_cluster_class.from_dict.called
    assert kube_cluster_class.from_dict.call_args[1]["namespace"] == "mynamespace"

    # Kube  cluster adapt is called with config
    assert kube_cluster.adapt.called
    assert kube_cluster.adapt.call_args[1]["minimum"] == 3
    assert kube_cluster.adapt.call_args[1]["maximum"] == 5

    # Flow runner run is called with proper executor
    assert flow_runner.run.called
    executor = flow_runner.run.call_args[1]["executor"]
    assert isinstance(executor, DaskExecutor)
    assert executor.address == kube_cluster.scheduler_address

    # start/exit callbacks are called
    assert start_func.called
    assert exit_func.called


def test_populate_job_yaml():
    environment = DaskKubernetesEnvironment(
        work_stealing=True, scheduler_logs=True, log_k8s_errors=True
    )

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

    with open(path.join(file_path, "job.yaml")) as job_file:
        job = yaml.safe_load(job_file)

    with set_temporary_config(
        {
            "cloud.graphql": "gql_test",
            "cloud.auth_token": "auth_test",
            "logging.extra_loggers": ["test_logger"],
        }
    ):
        with prefect.context(flow_run_id="id_test", namespace="namespace_test"):
            yaml_obj = environment._populate_job_yaml(
                yaml_obj=job, docker_name="test1/test2:test3"
            )

    assert yaml_obj["metadata"]["name"] == "prefect-dask-job-{}".format(
        environment.identifier_label
    )
    assert (
        yaml_obj["metadata"]["labels"]["prefect.io/identifier"]
        == environment.identifier_label
    )
    assert yaml_obj["metadata"]["labels"]["prefect.io/flow_run_id"] == "id_test"
    assert (
        yaml_obj["spec"]["template"]["metadata"]["labels"]["prefect.io/identifier"]
        == environment.identifier_label
    )

    env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]

    assert env[0]["value"] == "gql_test"
    assert env[1]["value"] == "auth_test"
    assert env[2]["value"] == "id_test"
    assert env[3]["value"] == "namespace_test"
    assert env[4]["value"] == "test1/test2:test3"
    assert env[12]["value"] == "True"
    assert (
        env[13]["value"]
        == "['test_logger', 'dask_kubernetes.core', 'distributed.deploy.adaptive', 'kubernetes', 'distributed.scheduler']"
    )

    assert (
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"]
        == "test1/test2:test3"
    )


def test_populate_job_yaml_multiple_image_secrets():
    environment = DaskKubernetesEnvironment(
        image_pull_secret="good-secret,dangerous-secret"
    )

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

    with open(path.join(file_path, "job.yaml")) as job_file:
        job = yaml.safe_load(job_file)

    with set_temporary_config(
        {
            "cloud.graphql": "gql_test",
            "cloud.auth_token": "auth_test",
            "logging.extra_loggers": ["test_logger"],
        }
    ):
        with prefect.context(flow_run_id="id_test", namespace="namespace_test"):
            yaml_obj = environment._populate_job_yaml(
                yaml_obj=job, docker_name="test1/test2:test3"
            )

    expected_secrets = [dict(name="good-secret"), dict(name="dangerous-secret")]
    assert yaml_obj["spec"]["template"]["spec"]["imagePullSecrets"] == expected_secrets


def test_populate_worker_pod_yaml():
    environment = DaskKubernetesEnvironment()

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

    with open(path.join(file_path, "worker_pod.yaml")) as pod_file:
        pod = yaml.safe_load(pod_file)

    with set_temporary_config(
        {
            "cloud.graphql": "gql_test",
            "cloud.auth_token": "auth_test",
            "logging.extra_loggers": ["test_logger"],
        }
    ):
        with prefect.context(flow_run_id="id_test", image="my_image"):
            yaml_obj = environment._populate_worker_pod_yaml(yaml_obj=pod)

    assert (
        yaml_obj["metadata"]["labels"]["prefect.io/identifier"]
        == environment.identifier_label
    )
    assert yaml_obj["metadata"]["labels"]["prefect.io/flow_run_id"] == "id_test"

    env = yaml_obj["spec"]["containers"][0]["env"]

    assert env[0]["value"] == "gql_test"
    assert env[1]["value"] == "auth_test"
    assert env[2]["value"] == "id_test"
    assert (
        env[10]["value"]
        == "['test_logger', 'dask_kubernetes.core', 'distributed.deploy.adaptive']"
    )

    assert yaml_obj["spec"]["containers"][0]["image"] == "my_image"


def test_populate_worker_pod_yaml_with_private_registry():
    environment = DaskKubernetesEnvironment(private_registry=True)

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

    with open(path.join(file_path, "worker_pod.yaml")) as pod_file:
        pod = yaml.safe_load(pod_file)

    with set_temporary_config(
        {"cloud.graphql": "gql_test", "cloud.auth_token": "auth_test"}
    ):
        with prefect.context(
            flow_run_id="id_test", image="my_image", namespace="foo-man"
        ):
            yaml_obj = environment._populate_worker_pod_yaml(yaml_obj=pod)

    assert yaml_obj["spec"]["imagePullSecrets"][0] == dict(name="foo-man-docker")


def test_populate_worker_pod_yaml_with_image_pull_secret():
    environment = DaskKubernetesEnvironment(image_pull_secret="mysecret")

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

    with open(path.join(file_path, "worker_pod.yaml")) as pod_file:
        pod = yaml.safe_load(pod_file)

    with set_temporary_config(
        {"cloud.graphql": "gql_test", "cloud.auth_token": "auth_test"}
    ):
        with prefect.context(
            flow_run_id="id_test", image="my_image", namespace="foo-man"
        ):
            yaml_obj = environment._populate_worker_pod_yaml(yaml_obj=pod)

    assert yaml_obj["spec"]["imagePullSecrets"][0] == dict(name="mysecret")


def test_populate_worker_pod_yaml_with_multiple_image_pull_secrets():
    environment = DaskKubernetesEnvironment(image_pull_secret="some-secret,another-one")

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

    with open(path.join(file_path, "worker_pod.yaml")) as pod_file:
        pod = yaml.safe_load(pod_file)

    with set_temporary_config(
        {"cloud.graphql": "gql_test", "cloud.auth_token": "auth_test"}
    ):
        with prefect.context(
            flow_run_id="id_test", image="my_image", namespace="foo-man"
        ):
            yaml_obj = environment._populate_worker_pod_yaml(yaml_obj=pod)

    assert yaml_obj["spec"]["imagePullSecrets"] == [
        dict(name="some-secret"),
        dict(name="another-one"),
    ]


def test_initialize_environment_with_spec_populates(monkeypatch):

    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "scheduler.yaml"), "w+") as file:
            file.write("scheduler")
        with open(os.path.join(directory, "worker.yaml"), "w+") as file:
            file.write("worker")

        environment = DaskKubernetesEnvironment(
            scheduler_spec_file=os.path.join(directory, "scheduler.yaml"),
            worker_spec_file=os.path.join(directory, "worker.yaml"),
        )

        assert environment._scheduler_spec == "scheduler"
        assert environment._worker_spec == "worker"


@pytest.mark.parametrize("log_flag", [True, False])
def test_populate_custom_worker_spec_yaml(log_flag):
    environment = DaskKubernetesEnvironment()

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

    with open(path.join(file_path, "worker_pod.yaml")) as pod_file:
        pod = yaml.safe_load(pod_file)
        pod["spec"]["containers"][0]["env"] = []

    with set_temporary_config(
        {
            "cloud.graphql": "gql_test",
            "cloud.auth_token": "auth_test",
            "cloud.send_flow_run_logs": log_flag,
            "logging.extra_loggers": ["test_logger"],
        }
    ):
        with prefect.context(flow_run_id="id_test", image="my_image"):
            yaml_obj = environment._populate_worker_spec_yaml(yaml_obj=pod)

    assert (
        yaml_obj["metadata"]["labels"]["prefect.io/identifier"]
        == environment.identifier_label
    )
    assert yaml_obj["metadata"]["labels"]["prefect.io/flow_run_id"] == "id_test"

    env = yaml_obj["spec"]["containers"][0]["env"]

    assert env[0]["value"] == "gql_test"
    assert env[1]["value"] == "auth_test"
    assert env[2]["value"] == "id_test"
    assert env[3]["value"] == "false"
    assert env[4]["value"] == "prefect.engine.cloud.CloudFlowRunner"
    assert env[5]["value"] == "prefect.engine.cloud.CloudTaskRunner"
    assert env[6]["value"] == "prefect.executors.DaskExecutor"
    assert env[7]["value"] == str(log_flag).lower()
    assert env[8]["value"] == "INFO"
    assert (
        env[9]["value"]
        == "['test_logger', 'dask_kubernetes.core', 'distributed.deploy.adaptive']"
    )

    assert yaml_obj["spec"]["containers"][0]["image"] == "my_image"


@pytest.mark.parametrize("log_flag", [True, False])
def test_populate_custom_scheduler_spec_yaml(log_flag):
    environment = DaskKubernetesEnvironment()

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

    with open(path.join(file_path, "job.yaml")) as job_file:
        job = yaml.safe_load(job_file)
        job["spec"]["template"]["spec"]["containers"][0]["env"] = []

    with set_temporary_config(
        {
            "cloud.graphql": "gql_test",
            "cloud.auth_token": "auth_test",
            "cloud.send_flow_run_logs": log_flag,
            "logging.extra_loggers": ["test_logger"],
        }
    ):
        with prefect.context(flow_run_id="id_test", namespace="namespace_test"):
            yaml_obj = environment._populate_scheduler_spec_yaml(
                yaml_obj=job, docker_name="test1/test2:test3"
            )

    assert yaml_obj["metadata"]["name"] == "prefect-dask-job-{}".format(
        environment.identifier_label
    )

    env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]

    assert env[0]["value"] == "gql_test"
    assert env[1]["value"] == "auth_test"
    assert env[2]["value"] == "id_test"
    assert env[3]["value"] == "namespace_test"
    assert env[4]["value"] == "test1/test2:test3"
    assert env[5]["value"] == "false"
    assert env[6]["value"] == "prefect.engine.cloud.CloudFlowRunner"
    assert env[7]["value"] == "prefect.engine.cloud.CloudTaskRunner"
    assert env[8]["value"] == "prefect.executors.DaskExecutor"
    assert env[9]["value"] == str(log_flag).lower()
    assert env[10]["value"] == "INFO"
    assert (
        env[11]["value"]
        == "['test_logger', 'dask_kubernetes.core', 'distributed.deploy.adaptive']"
    )

    assert (
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"]
        == "test1/test2:test3"
    )


@pytest.mark.parametrize("log_flag", [True, False])
def test_populate_custom_yaml_specs_with_logging_vars(log_flag):
    environment = DaskKubernetesEnvironment()

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

    log_vars = [
        {
            "name": "PREFECT__CLOUD__SEND_FLOW_RUN_LOGS",
            "value": "YES",
        },
        {
            "name": "PREFECT__LOGGING__LEVEL",
            "value": "NO",
        },
        {
            "name": "PREFECT__LOGGING__EXTRA_LOGGERS",
            "value": "MAYBE",
        },
    ]

    with open(path.join(file_path, "job.yaml")) as job_file:
        job = yaml.safe_load(job_file)
        job["spec"]["template"]["spec"]["containers"][0]["env"] = []
        job["spec"]["template"]["spec"]["containers"][0]["env"].extend(log_vars)

    with set_temporary_config(
        {
            "cloud.graphql": "gql_test",
            "cloud.auth_token": "auth_test",
            "cloud.send_flow_run_logs": log_flag,
            "logging.extra_loggers": ["test_logger"],
        }
    ):
        with prefect.context(flow_run_id="id_test", namespace="namespace_test"):
            yaml_obj = environment._populate_scheduler_spec_yaml(
                yaml_obj=job, docker_name="test1/test2:test3"
            )

    assert yaml_obj["metadata"]["name"] == "prefect-dask-job-{}".format(
        environment.identifier_label
    )

    env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]

    assert env[0]["value"] == "YES"
    assert env[1]["value"] == "NO"
    assert env[2]["value"] == "MAYBE"
    assert len(env) == 12

    # worker
    with open(path.join(file_path, "worker_pod.yaml")) as pod_file:
        pod = yaml.safe_load(pod_file)
        pod["spec"]["containers"][0]["env"] = []
        pod["spec"]["containers"][0]["env"].extend(log_vars)

    with set_temporary_config(
        {
            "cloud.graphql": "gql_test",
            "cloud.auth_token": "auth_test",
            "cloud.send_flow_run_logs": log_flag,
            "logging.extra_loggers": ["test_logger"],
        }
    ):
        with prefect.context(flow_run_id="id_test", image="my_image"):
            yaml_obj = environment._populate_worker_spec_yaml(yaml_obj=pod)

    assert (
        yaml_obj["metadata"]["labels"]["prefect.io/identifier"]
        == environment.identifier_label
    )
    assert yaml_obj["metadata"]["labels"]["prefect.io/flow_run_id"] == "id_test"

    env = yaml_obj["spec"]["containers"][0]["env"]

    assert env[0]["value"] == "YES"
    assert env[1]["value"] == "NO"
    assert env[2]["value"] == "MAYBE"
    assert len(env) == 10


def test_roundtrip_cloudpickle():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "scheduler.yaml"), "w+") as file:
            file.write("scheduler")
        with open(os.path.join(directory, "worker.yaml"), "w+") as file:
            file.write("worker")

        environment = DaskKubernetesEnvironment(
            scheduler_spec_file=os.path.join(directory, "scheduler.yaml"),
            worker_spec_file=os.path.join(directory, "worker.yaml"),
        )

        assert environment._scheduler_spec == "scheduler"
        assert environment._worker_spec == "worker"

        new = cloudpickle.loads(cloudpickle.dumps(environment))
        assert isinstance(new, DaskKubernetesEnvironment)
        assert new._scheduler_spec == "scheduler"
        assert new._worker_spec == "worker"

        # Identifer labels do not persist
        assert environment.identifier_label
        assert new.identifier_label

        assert environment.identifier_label != new.identifier_label
