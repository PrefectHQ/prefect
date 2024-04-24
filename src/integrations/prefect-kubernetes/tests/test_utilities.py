from unittest.mock import MagicMock

import pytest
from kubernetes.client import models as k8s_models
from kubernetes.config import ConfigException
from prefect_kubernetes.utilities import (
    convert_manifest_to_model,
    enable_socket_keep_alive,
)

from prefect.infrastructure.kubernetes import KubernetesJob

FAKE_CLUSTER = "fake-cluster"

base_path = "tests/sample_k8s_resources"

sample_deployment_manifest = KubernetesJob.job_from_file(
    f"{base_path}/sample_deployment.yaml"
)
sample_job_manifest = KubernetesJob.job_from_file(f"{base_path}/sample_job.yaml")
sample_pod_manifest = KubernetesJob.job_from_file(f"{base_path}/sample_pod.yaml")
sample_service_manifest = KubernetesJob.job_from_file(
    f"{base_path}/sample_service.yaml"
)

expected_deployment_model = k8s_models.V1Deployment(
    **dict(
        api_version="apps/v1",
        kind="Deployment",
        metadata=k8s_models.V1ObjectMeta(
            **dict(
                name="nginx-deployment",
                labels={"app": "nginx"},
            )
        ),
        spec=k8s_models.V1DeploymentSpec(
            **dict(
                replicas=3,
                selector=k8s_models.V1LabelSelector(
                    **dict(
                        match_labels={"app": "nginx"},
                    )
                ),
                template=k8s_models.V1PodTemplateSpec(
                    **dict(
                        metadata=k8s_models.V1ObjectMeta(
                            **dict(
                                labels={"app": "nginx"},
                            )
                        ),
                        spec=k8s_models.V1PodSpec(
                            **dict(
                                containers=[
                                    k8s_models.V1Container(
                                        **dict(
                                            name="nginx",
                                            image="nginx:1.14.2",
                                            ports=[
                                                k8s_models.V1ContainerPort(
                                                    **dict(container_port=80)
                                                )
                                            ],
                                        )
                                    )
                                ]
                            )
                        ),
                    )
                ),
            )
        ),
    )
)

expected_pod_model = k8s_models.V1Pod(
    **dict(
        api_version="v1",
        kind="Pod",
        metadata=k8s_models.V1ObjectMeta(**dict(name="nginx")),
        spec=k8s_models.V1PodSpec(
            **dict(
                containers=[
                    k8s_models.V1Container(
                        **dict(
                            name="nginx",
                            image="nginx:1.14.2",
                            ports=[
                                k8s_models.V1ContainerPort(**dict(container_port=80))
                            ],
                        )
                    )
                ]
            )
        ),
    )
)

expected_job_model = k8s_models.V1Job(
    **dict(
        api_version="batch/v1",
        kind="Job",
        metadata=k8s_models.V1ObjectMeta(
            **dict(
                name="pi",
            )
        ),
        spec=k8s_models.V1JobSpec(
            **dict(
                template=k8s_models.V1PodTemplateSpec(
                    **dict(
                        spec=k8s_models.V1PodSpec(
                            **dict(
                                containers=[
                                    k8s_models.V1Container(
                                        **dict(
                                            name="pi",
                                            image="perl:5.34.0",
                                            command=[
                                                "perl",
                                                "-Mbignum=bpi",
                                                "-wle",
                                                "print bpi(2000)",
                                            ],
                                        )
                                    )
                                ],
                                restart_policy="Never",
                            )
                        ),
                    )
                ),
                backoff_limit=4,
            )
        ),
    )
)

expected_service_model = k8s_models.V1Service(
    **dict(
        api_version="v1",
        kind="Service",
        metadata=k8s_models.V1ObjectMeta(
            **dict(
                name="nginx-service",
            )
        ),
        spec=k8s_models.V1ServiceSpec(
            **dict(
                selector={"app.kubernetes.io/name": "proxy"},
                ports=[
                    k8s_models.V1ServicePort(
                        **dict(
                            name="name-of-service-port",
                            protocol="TCP",
                            port=80,
                            target_port="http-web-svc",
                        )
                    )
                ],
            )
        ),
    )
)


@pytest.fixture
def mock_cluster_config(monkeypatch):
    mock = MagicMock()
    # We cannot mock this or the `except` clause will complain
    mock.config.ConfigException = ConfigException
    mock.list_kube_config_contexts.return_value = (
        [],
        {"context": {"cluster": FAKE_CLUSTER}},
    )
    monkeypatch.setattr("kubernetes.config", mock)
    monkeypatch.setattr("kubernetes.config.ConfigException", ConfigException)
    return mock


@pytest.fixture
def mock_api_client(mock_cluster_config):
    return MagicMock()


@pytest.mark.parametrize(
    "manifest,model_name,expected_model",
    [
        (
            f"{base_path}/sample_deployment.yaml",
            "V1Deployment",
            expected_deployment_model,
        ),
        (sample_deployment_manifest, "V1Deployment", expected_deployment_model),
        (f"{base_path}/sample_pod.yaml", "V1Pod", expected_pod_model),
        (sample_pod_manifest, "V1Pod", expected_pod_model),
        (f"{base_path}/sample_job.yaml", "V1Job", expected_job_model),
        (sample_job_manifest, "V1Job", expected_job_model),
        (f"{base_path}/sample_service.yaml", "V1Service", expected_service_model),
        (sample_service_manifest, "V1Service", expected_service_model),
    ],
)
def test_convert_manifest_to_model(manifest, model_name, expected_model):
    v1_model = convert_manifest_to_model(manifest, model_name)

    assert isinstance(v1_model, getattr(k8s_models, model_name))

    assert v1_model == expected_model


def test_bad_manifest_filename_raises():
    with pytest.raises(
        ValueError, match="Manifest must be a valid dict or path to a .yaml file."
    ):
        convert_manifest_to_model("isaid86753OHnahhhEEEIIIEEEYEN", "V1Deployment")


@pytest.mark.parametrize(
    "v1_model_name",
    [
        "V1Schledloyment",
        ["V1Deployment"],
    ],
)
def test_bad_model_type_raises(v1_model_name):
    with pytest.raises(
        ValueError,
        match="`v1_model` must be the name of a valid Kubernetes client model.",
    ):
        convert_manifest_to_model(sample_deployment_manifest, v1_model_name)


def test_keep_alive_updates_socket_options(mock_api_client):
    enable_socket_keep_alive(mock_api_client)

    assert (
        mock_api_client.rest_client.pool_manager.connection_pool_kw[
            "socket_options"
        ]._mock_set_call
        is not None
    )
