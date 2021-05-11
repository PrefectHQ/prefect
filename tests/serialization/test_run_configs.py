import pytest

from prefect.run_configs import KubernetesRun, LocalRun, DockerRun, ECSRun, UniversalRun
from prefect.serialization.run_config import RunConfigSchema, RunConfigSchemaBase


def test_serialized_run_config_sorts_labels():
    assert RunConfigSchemaBase().dump({"labels": ["b", "c", "a"]})["labels"] == [
        "a",
        "b",
        "c",
    ]


@pytest.mark.parametrize(
    "config", [UniversalRun(), UniversalRun(env={"FOO": "BAR"}, labels=["a", "b"])]
)
def test_serialize_universal_run(config):
    msg = RunConfigSchema().dump(config)
    config2 = RunConfigSchema().load(msg)
    assert (config.env) == config2.env
    assert sorted(config.labels) == sorted(config2.labels)


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
            service_account_name="my-account",
            image_pull_secrets=["secret-1", "secret-2"],
            labels=["a", "b"],
            image_pull_policy="Always",
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
        "service_account_name",
        "image_pull_secrets",
        "image_pull_policy",
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


@pytest.mark.parametrize(
    "config",
    [
        ECSRun(),
        ECSRun(
            task_definition_path="s3://bucket/test.yaml",
            image="myimage",
            env={"test": "foo"},
            cpu="1 vcpu",
            memory="1 GB",
            task_role_arn="my-task-role",
            execution_role_arn="execution-role",
            run_task_kwargs={"overrides": {"taskRoleArn": "example"}},
            labels=["a", "b"],
        ),
        ECSRun(
            task_definition={
                "containerDefinitions": [
                    {
                        "name": "flow",
                        "environment": [{"name": "TEST", "value": "VALUE"}],
                    }
                ]
            }
        ),
        ECSRun(task_definition_arn="my-task-definition"),
    ],
)
def test_serialize_ecs_run(config):
    msg = RunConfigSchema().dump(config)
    config2 = RunConfigSchema().load(msg)
    assert sorted(config.labels) == sorted(config2.labels)
    fields = [
        "task_definition",
        "task_definition_path",
        "task_definition_arn",
        "image",
        "env",
        "cpu",
        "memory",
        "task_role_arn",
        "execution_role_arn",
        "run_task_kwargs",
    ]
    for field in fields:
        assert getattr(config, field) == getattr(config2, field)
