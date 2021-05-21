import sys
import pytest
import yaml

from prefect.run_configs import KubernetesRun


def test_no_args():
    config = KubernetesRun()
    assert config.job_template_path is None
    assert config.job_template is None
    assert config.image is None
    assert config.env is None
    assert config.cpu_limit is None
    assert config.cpu_request is None
    assert config.memory_limit is None
    assert config.memory_request is None
    assert config.service_account_name is None
    assert config.image_pull_secrets is None
    assert config.labels == set()
    assert config.image_pull_policy is None


def test_labels():
    config = KubernetesRun(labels=["a", "b"])
    assert config.labels == {"a", "b"}


def test_cant_specify_both_job_template_and_job_template_path():
    with pytest.raises(ValueError, match="Cannot provide both"):
        KubernetesRun(job_template={}, job_template_path="/some/path")


def test_remote_job_template_path():
    config = KubernetesRun(job_template_path="s3://bucket/example.yaml")
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
        if sys.platform == "win32":
            pytest.skip("Schemes are not supported on win32")
        job_template_path = f"{scheme}://" + path

    with open(path, "w") as f:
        yaml.safe_dump(job_template, f)

    config = KubernetesRun(job_template_path=job_template_path)

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
    config = KubernetesRun(job_template=arg)

    assert config.job_template_path is None
    assert config.job_template == job_template


def test_cpu_limit_and_request_acceptable_types():
    config = KubernetesRun()
    assert config.cpu_limit is None
    assert config.cpu_request is None

    config = KubernetesRun(cpu_limit="200m", cpu_request="100m")
    assert config.cpu_limit == "200m"
    assert config.cpu_request == "100m"

    config = KubernetesRun(cpu_limit=0.5, cpu_request=0.1)
    assert config.cpu_limit == "0.5"
    assert config.cpu_request == "0.1"


def test_service_account_name_and_image_pull_secrets():
    config = KubernetesRun(
        service_account_name="my-account", image_pull_secrets=("a", "b", "c")
    )
    assert config.service_account_name == "my-account"
    assert config.image_pull_secrets == ["a", "b", "c"]

    # Ensure falsey-lists aren't converted to `None`.
    config = KubernetesRun(image_pull_secrets=[])
    assert config.image_pull_secrets == []


@pytest.mark.parametrize("image_pull_policy", ["Always", "IfNotPresent", "Never"])
def test_image_pull_policy_valid_value(image_pull_policy):
    config = KubernetesRun(image_pull_policy=image_pull_policy)
    assert config.image_pull_policy == image_pull_policy


def test_image_pull_policy_invalid_value():
    with pytest.raises(ValueError):
        KubernetesRun(image_pull_policy="WrongPolicy")
