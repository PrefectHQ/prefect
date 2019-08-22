import json
import os
import tempfile
from os import path
from unittest.mock import MagicMock

import cloudpickle
import pytest
import yaml

import prefect
from prefect.environments import DaskKubernetesEnvironment
from prefect.environments.storage import Docker, Memory
from prefect.utilities.configuration import set_temporary_config


def test_create_dask_environment():
    environment = DaskKubernetesEnvironment()
    assert environment
    assert environment.private_registry is False
    assert environment.docker_secret is None


def test_create_dask_environment_identifier_label():
    environment = DaskKubernetesEnvironment()
    assert environment.identifier_label


def test_setup_dask_environment_passes():
    environment = DaskKubernetesEnvironment()
    environment.setup(storage=Docker())
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
    with set_temporary_config({"cloud.api_token": "test"}):
        environment.setup(storage=Docker())

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
    with set_temporary_config({"cloud.api_token": "test"}):
        with prefect.context(namespace="foo"):
            environment.setup(storage=Docker())

    assert not create_secret.called


def test_execute_improper_storage():
    environment = DaskKubernetesEnvironment()
    with pytest.raises(TypeError):
        environment.execute(storage=Memory(), flow_location="")


def test_execute_storage_missing_fields():
    environment = DaskKubernetesEnvironment()
    with pytest.raises(ValueError):
        environment.execute(storage=Docker(), flow_location="")


def test_execute(monkeypatch):
    environment = DaskKubernetesEnvironment()
    storage = Docker(registry_url="test1", image_name="test2", image_tag="test3")

    create_flow_run = MagicMock()
    monkeypatch.setattr(
        "prefect.environments.DaskKubernetesEnvironment.create_flow_run_job",
        create_flow_run,
    )

    environment.execute(storage=storage, flow_location="")

    assert create_flow_run.call_args[1]["docker_name"] == "test1/test2:test3"


def test_create_flow_run_job(monkeypatch):
    environment = DaskKubernetesEnvironment()

    config = MagicMock()
    monkeypatch.setattr("kubernetes.config", config)

    batchv1 = MagicMock()
    monkeypatch.setattr(
        "kubernetes.client", MagicMock(BatchV1Api=MagicMock(return_value=batchv1))
    )

    with set_temporary_config({"cloud.api_token": "test"}):
        environment.create_flow_run_job(
            docker_name="test1/test2:test3", flow_file_path="test4"
        )

    assert (
        batchv1.create_namespaced_job.call_args[1]["body"]["apiVersion"] == "batch/v1"
    )


def test_create_flow_run_job_fails_outside_cluster():
    environment = DaskKubernetesEnvironment()

    with pytest.raises(EnvironmentError):
        with set_temporary_config({"cloud.api_token": "test"}):
            environment.create_flow_run_job(
                docker_name="test1/test2:test3", flow_file_path="test4"
            )


def test_run_flow(monkeypatch):
    environment = DaskKubernetesEnvironment()

    flow_runner = MagicMock()
    monkeypatch.setattr(
        "prefect.engine.get_default_flow_runner_class",
        MagicMock(return_value=flow_runner),
    )

    kube_cluster = MagicMock()
    monkeypatch.setattr("dask_kubernetes.KubeCluster", kube_cluster)

    with tempfile.TemporaryDirectory() as directory:
        with open(os.path.join(directory, "flow_env.prefect"), "w+") as env:
            flow = prefect.Flow("test")
            flow_path = os.path.join(directory, "flow_env.prefect")
            with open(flow_path, "wb") as f:
                cloudpickle.dump(flow, f)

        with set_temporary_config({"cloud.api_token": "test"}):
            with prefect.context(
                flow_file_path=os.path.join(directory, "flow_env.prefect")
            ):
                environment.run_flow()

        assert flow_runner.call_args[1]["flow"].name == "test"


def test_populate_job_yaml():
    environment = DaskKubernetesEnvironment()

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

    with open(path.join(file_path, "job.yaml")) as job_file:
        job = yaml.safe_load(job_file)

    with set_temporary_config(
        {"cloud.graphql": "gql_test", "cloud.api_token": "auth_test"}
    ):
        with prefect.context(flow_run_id="id_test", namespace="namespace_test"):
            yaml_obj = environment._populate_job_yaml(
                yaml_obj=job, docker_name="test1/test2:test3", flow_file_path="test4"
            )

    assert yaml_obj["metadata"]["name"] == "prefect-dask-job-{}".format(
        environment.identifier_label
    )
    assert yaml_obj["metadata"]["labels"]["identifier"] == environment.identifier_label
    assert yaml_obj["metadata"]["labels"]["flow_run_id"] == "id_test"
    assert (
        yaml_obj["spec"]["template"]["metadata"]["labels"]["identifier"]
        == environment.identifier_label
    )

    env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]

    assert env[0]["value"] == "gql_test"
    assert env[1]["value"] == "auth_test"
    assert env[2]["value"] == "id_test"
    assert env[3]["value"] == "namespace_test"
    assert env[4]["value"] == "test1/test2:test3"
    assert env[5]["value"] == "test4"

    assert (
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"]
        == "test1/test2:test3"
    )


def test_populate_worker_pod_yaml():
    environment = DaskKubernetesEnvironment()

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

    with open(path.join(file_path, "worker_pod.yaml")) as pod_file:
        pod = yaml.safe_load(pod_file)

    with set_temporary_config(
        {"cloud.graphql": "gql_test", "cloud.api_token": "auth_test"}
    ):
        with prefect.context(flow_run_id="id_test", image="my_image"):
            yaml_obj = environment._populate_worker_pod_yaml(yaml_obj=pod)

    assert yaml_obj["metadata"]["labels"]["identifier"] == environment.identifier_label
    assert yaml_obj["metadata"]["labels"]["flow_run_id"] == "id_test"

    env = yaml_obj["spec"]["containers"][0]["env"]

    assert env[0]["value"] == "gql_test"
    assert env[1]["value"] == "auth_test"
    assert env[2]["value"] == "id_test"

    assert yaml_obj["spec"]["containers"][0]["image"] == "my_image"


def test_populate_worker_pod_yaml_with_private_registry():
    environment = DaskKubernetesEnvironment(private_registry=True)

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

    with open(path.join(file_path, "worker_pod.yaml")) as pod_file:
        pod = yaml.safe_load(pod_file)

    with set_temporary_config(
        {"cloud.graphql": "gql_test", "cloud.api_token": "auth_test"}
    ):
        with prefect.context(
            flow_run_id="id_test", image="my_image", namespace="foo-man"
        ):
            yaml_obj = environment._populate_worker_pod_yaml(yaml_obj=pod)

    yaml_obj["spec"]["imagePullSecrets"][0] == dict(name="foo-man-docker")
