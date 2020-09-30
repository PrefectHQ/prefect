import os

import pytest
import yaml

from prefect.run_configs import KubernetesJob


def test_no_args():
    config = KubernetesJob()
    assert config.job_template_path is None
    assert config.job_template is None
    assert config.image is None
    assert config.env is None
    assert config.cpu_limit is None
    assert config.cpu_request is None
    assert config.memory_limit is None
    assert config.memory_request is None
    assert config.labels == set()


def test_labels():
    config = KubernetesJob(labels=["a", "b"])
    assert config.labels == {"a", "b"}


def test_cant_specify_both_job_template_and_job_template_path():
    with pytest.raises(ValueError, match="Cannot provide both"):
        KubernetesJob(job_template={}, job_template_path="/some/path")


def test_remote_job_template_path():
    config = KubernetesJob(job_template_path="s3://bucket/example.yaml")
    assert config.job_template_path == "s3://bucket/example.yaml"
    assert config.job_template is None


@pytest.mark.parametrize("scheme", ["local", "file", None])
def test_local_job_template_path(tmpdir, scheme):
    job_template = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"labels": {"example": "foo"}},
    }
    path = str(tmpdir.join("test.yaml"))
    if scheme is None:
        job_template_path = path
    else:
        # With a scheme, unix-style slashes are required
        job_template_path = f"{scheme}://" + os.path.splitdrive(path)[1].replace(
            "\\", "/"
        )

    with open(path, "w") as f:
        yaml.safe_dump(job_template, f)

    config = KubernetesJob(job_template_path=job_template_path)

    assert config.job_template_path is None
    assert config.job_template == job_template


@pytest.mark.parametrize("kind", [dict, str])
def test_job_template(kind):
    job_template = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"labels": {"example": "foo"}},
    }
    arg = job_template if kind is dict else yaml.safe_dump(job_template)
    config = KubernetesJob(job_template=arg)

    assert config.job_template_path is None
    assert config.job_template == job_template


def test_cpu_limit_and_request_acceptable_types():
    config = KubernetesJob()
    assert config.cpu_limit is None
    assert config.cpu_request is None

    config = KubernetesJob(cpu_limit="200m", cpu_request="100m")
    assert config.cpu_limit == "200m"
    assert config.cpu_request == "100m"

    config = KubernetesJob(cpu_limit=0.5, cpu_request=0.1)
    assert config.cpu_limit == "0.5"
    assert config.cpu_request == "0.1"
