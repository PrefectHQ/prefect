import pytest

from marshmallow import ValidationError

from prefect.run_configs import KubernetesJob, RunConfig
from prefect.serialization.run_config import RunConfigSchema


class Custom(RunConfig):
    pass


def test_run_config_dump_errors_unknown_kind():
    with pytest.raises(ValidationError, match="Don't know how to serialize"):
        RunConfigSchema().dump(Custom())


def test_run_config_load_errors_missing_kind():
    with pytest.raises(ValidationError, match="No `RunConfig` kind found"):
        RunConfigSchema().load({"labels": []})


def test_run_config_load_errors_unknown_kind():
    msg = {"kind": "Custom", "labels": [], "spec": {}}
    with pytest.raises(ValidationError, match="Unknown `RunConfig` kind 'Custom'"):
        RunConfigSchema().load(msg)


class TestKubernetesJob:
    def test_no_args(self):
        config = KubernetesJob()
        msg = RunConfigSchema().dump(config)
        assert msg == {
            "kind": "KubernetesJob",
            "labels": [],
            "spec": {
                "job_template": None,
                "job_template_path": None,
                "image": None,
                "env": None,
                "cpu_limit": None,
                "cpu_request": None,
                "memory_limit": None,
                "memory_request": None,
            },
        }

    def test_full_args(self):
        config = KubernetesJob(
            job_template_path="s3://bucket/test.yaml",
            image="myimage",
            env={"test": "foo"},
            cpu_limit=2,
            cpu_request="500m",
            memory_limit="4G",
            memory_request="2G",
            labels=["a", "b"],
        )
        msg = RunConfigSchema().dump(config)
        spec = {
            "job_template_path": "s3://bucket/test.yaml",
            "job_template": None,
            "image": "myimage",
            "env": {"test": "foo"},
            "cpu_limit": "2",
            "cpu_request": "500m",
            "memory_limit": "4G",
            "memory_request": "2G",
        }
        assert msg["kind"] == "KubernetesJob"
        assert sorted(msg["labels"]) == ["a", "b"]
        assert msg["spec"] == spec
        config2 = RunConfigSchema().load(msg)
        for field in spec:
            assert getattr(config, field) == getattr(config2, field)

    def test_job_template(self):
        job_template = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"labels": {"example": "foo"}},
        }
        config = KubernetesJob(job_template=job_template)
        msg = RunConfigSchema().dump(config)
        assert msg["spec"]["job_template"] == job_template
        config2 = RunConfigSchema().load(msg)
        assert config2.job_template == job_template
