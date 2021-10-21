import sys
import pytest
import yaml

from prefect.run_configs import ECSRun


def test_no_args():
    config = ECSRun()
    assert config.task_definition is None
    assert config.task_definition_path is None
    assert config.task_definition_arn is None
    assert config.image is None
    assert config.env is None
    assert config.cpu is None
    assert config.memory is None
    assert config.task_role_arn is None
    assert config.execution_role_arn is None
    assert config.run_task_kwargs is None
    assert config.labels == set()


def test_all_args():
    config = ECSRun(
        task_definition_path="s3://path/to/task.yaml",
        image="myimage",
        env={"HELLO": "WORLD"},
        cpu=1024,
        memory=2048,
        task_role_arn="my-task-role",
        execution_role_arn="execution-role",
        run_task_kwargs={"overrides": {"taskRoleArn": "example"}},
        labels=["a", "b"],
    )
    assert config.task_definition_path == "s3://path/to/task.yaml"
    assert config.image == "myimage"
    assert config.env == {"HELLO": "WORLD"}
    assert config.cpu == "1024"
    assert config.memory == "2048"
    assert config.task_role_arn == "my-task-role"
    assert config.execution_role_arn == "execution-role"
    assert config.run_task_kwargs == {"overrides": {"taskRoleArn": "example"}}
    assert config.labels == {"a", "b"}


def test_labels():
    config = ECSRun(labels=["a", "b"])
    assert config.labels == {"a", "b"}


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(task_definition={}, task_definition_path="/some/path"),
        dict(task_definition={}, task_definition_arn="some_arn"),
        dict(task_definition_path="/some/path", task_definition_arn="some_arn"),
        dict(
            task_definition={},
            task_definition_path="/some/path",
            task_definition_arn="some_arn",
        ),
    ],
)
def test_can_only_specify_task_definition_one_way(kwargs):
    with pytest.raises(ValueError, match="Can only provide one of"):
        ECSRun(**kwargs)


def test_remote_task_definition_path():
    config = ECSRun(task_definition_path="s3://bucket/example.yaml")
    assert config.task_definition_path == "s3://bucket/example.yaml"
    assert config.task_definition is None
    assert config.task_definition_arn is None


@pytest.mark.parametrize("scheme", ["local", "file", None])
def test_local_task_definition_path(tmpdir, scheme):
    task_definition = {
        "containerDefinitions": [
            {"name": "flow", "environment": [{"name": "TEST", "value": "VALUE"}]}
        ]
    }
    path = str(tmpdir.join("test.yaml"))
    if scheme is None:
        task_definition_path = path
    else:
        if sys.platform == "win32":
            pytest.skip("Schemes are not supported on win32")
        task_definition_path = f"{scheme}://" + path

    with open(path, "w") as f:
        yaml.safe_dump(task_definition, f)

    config = ECSRun(task_definition_path=task_definition_path)

    assert config.task_definition_path is None
    assert config.task_definition_arn is None
    assert config.task_definition == task_definition


def test_task_definition_arn():
    config = ECSRun(task_definition_arn="my-task-definition")
    assert config.task_definition_arn == "my-task-definition"
    assert config.task_definition is None
    assert config.task_definition_path is None

    # Can't mix `image` and `task_definition_arn`
    with pytest.raises(ValueError, match="task_definition_arn"):
        ECSRun(task_definition_arn="my-task-definition", image="my-image")


def test_task_definition():
    task_definition = {
        "containerDefinitions": [
            {"name": "flow", "environment": [{"name": "TEST", "value": "VALUE"}]}
        ]
    }
    config = ECSRun(task_definition=task_definition)

    assert config.task_definition_path is None
    assert config.task_definition_arn is None
    assert config.task_definition == task_definition


def test_cpu_and_memory_acceptable_types():
    config = ECSRun()
    assert config.cpu is None
    assert config.memory is None

    config = ECSRun(cpu="1 vcpu", memory="1 GB")
    assert config.cpu == "1 vcpu"
    assert config.memory == "1 GB"

    config = ECSRun(cpu=1024, memory=2048)
    assert config.cpu == "1024"
    assert config.memory == "2048"
