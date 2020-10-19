import pytest

from prefect.run_configs import KubernetesRun, LocalRun, DockerRun
from prefect.serialization.run_config import RunConfigSchema


@pytest.mark.parametrize(
    "config",
    [
        KubernetesRun(),
        KubernetesRun(
            job_template_path="s3://bucket/test.yaml",
            image="myimage",
            env={"test": "foo"},
            cpu_limit=2,
            cpu_request="500m",
            memory_limit="4G",
            memory_request="2G",
            labels=["a", "b"],
        ),
        KubernetesRun(
            job_template={
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {"labels": {"example": "foo"}},
            }
        ),
    ],
)
def test_serialize_kubernetes_run(config):
    msg = RunConfigSchema().dump(config)
    config2 = RunConfigSchema().load(msg)
    assert sorted(config.labels) == sorted(config2.labels)
    fields = [
        "job_template",
        "job_template_path",
        "image",
        "env",
        "cpu_limit",
        "cpu_request",
        "memory_limit",
        "memory_request",
    ]
    for field in fields:
        assert getattr(config, field) == getattr(config2, field)


@pytest.mark.parametrize(
    "config",
    [
        LocalRun(),
        LocalRun(
            env={"test": "foo"},
            working_dir="/path/to/dir",
            labels=["a", "b"],
        ),
    ],
)
def test_serialize_local_run(config):
    msg = RunConfigSchema().dump(config)
    config2 = RunConfigSchema().load(msg)
    assert sorted(config.labels) == sorted(config2.labels)
    fields = ["env", "working_dir"]
    for field in fields:
        assert getattr(config, field) == getattr(config2, field)


@pytest.mark.parametrize(
    "config",
    [
        DockerRun(),
        DockerRun(
            env={"test": "foo"},
            image="testing",
            labels=["a", "b"],
        ),
    ],
)
def test_serialize_docker_run(config):
    msg = RunConfigSchema().dump(config)
    config2 = RunConfigSchema().load(msg)
    assert sorted(config.labels) == sorted(config2.labels)
    fields = ["env", "image"]
    for field in fields:
        assert getattr(config, field) == getattr(config2, field)
