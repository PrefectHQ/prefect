import os
import tempfile

import pytest

import prefect
from prefect import environments
from prefect.serialization.environment import (
    BaseEnvironmentSchema,
    DaskKubernetesEnvironmentSchema,
    EnvironmentSchema,
    FargateTaskEnvironmentSchema,
    KubernetesJobEnvironmentSchema,
    LocalEnvironmentSchema,
)


@pytest.fixture
def k8s_job_spec_content() -> str:
    return "apiVersion: batch/v1\nkind: Job\n"


def test_serialize_base_environment():
    env = environments.Environment()

    serialized = BaseEnvironmentSchema().dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["labels"] == []
    assert serialized["metadata"] == {}


def test_serialize_base_environment_with_labels():
    env = environments.Environment(labels=["b", "c", "a"])

    serialized = BaseEnvironmentSchema().dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["labels"] == ["a", "b", "c"]


def test_serialize_dask_environment():
    env = environments.DaskKubernetesEnvironment()

    schema = DaskKubernetesEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["docker_secret"] is None
    assert serialized["min_workers"] == 1
    assert serialized["max_workers"] == 2
    assert serialized["labels"] == []
    assert serialized["metadata"] == {}

    new = schema.load(serialized)
    assert new.private_registry is False
    assert new.docker_secret is None
    assert new.min_workers == 1
    assert new.max_workers == 2
    assert new.labels == set()
    assert new.scheduler_spec_file is None
    assert new.worker_spec_file is None


def test_serialize_dask_env_with_custom_specs():
    with tempfile.TemporaryDirectory() as directory:
        with open(os.path.join(directory, "scheduler.yaml"), "w+") as f:
            f.write("scheduler")
        with open(os.path.join(directory, "worker.yaml"), "w+") as f:
            f.write("worker")

        env = environments.DaskKubernetesEnvironment(
            scheduler_spec_file=os.path.join(directory, "scheduler.yaml"),
            worker_spec_file=os.path.join(directory, "worker.yaml"),
        )

        schema = DaskKubernetesEnvironmentSchema()
        serialized = schema.dump(env)

    deserialized = schema.load(serialized)
    assert isinstance(deserialized, environments.DaskKubernetesEnvironment)


def test_serialize_dask_environment_with_labels():
    env = environments.DaskKubernetesEnvironment(labels=["b", "c", "a"])

    schema = DaskKubernetesEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["docker_secret"] is None
    assert serialized["min_workers"] == 1
    assert serialized["max_workers"] == 2
    # labels should be sorted in the serialized obj
    assert serialized["labels"] == ["a", "b", "c"]

    new = schema.load(serialized)
    assert new.private_registry is False
    assert new.docker_secret is None
    assert new.min_workers == 1
    assert new.max_workers == 2
    assert new.labels == {"a", "b", "c"}


def test_serialize_dask_environment_with_customized_workers():
    env = environments.DaskKubernetesEnvironment(min_workers=10, max_workers=60)

    schema = DaskKubernetesEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["min_workers"] == 10
    assert serialized["max_workers"] == 60

    new = schema.load(serialized)
    assert new.min_workers == 10
    assert new.max_workers == 60


def test_serialize_dask_environment_with_private_registry():
    env = environments.DaskKubernetesEnvironment(
        private_registry=True, docker_secret="FOO"
    )

    schema = DaskKubernetesEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["private_registry"] is True
    assert serialized["docker_secret"] == "FOO"

    new = schema.load(serialized)
    assert new.private_registry is True
    assert new.docker_secret == "FOO"


def test_serialize_fargate_task_environment():
    env = environments.FargateTaskEnvironment()

    schema = FargateTaskEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["labels"] == []
    assert serialized["metadata"] == {}

    new = schema.load(serialized)
    assert new.labels == set()


def test_serialize_fargate_task_env_with_kwargs():
    env = environments.FargateTaskEnvironment(cluster="test")

    schema = FargateTaskEnvironmentSchema()
    serialized = schema.dump(env)

    deserialized = schema.load(serialized)
    assert isinstance(deserialized, environments.FargateTaskEnvironment)
    assert deserialized.task_run_kwargs == {}


def test_serialize_fargate_task_environment_with_labels():
    env = environments.FargateTaskEnvironment(labels=["b", "c", "a"])

    schema = FargateTaskEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    # labels should be sorted in the serialized obj
    assert serialized["labels"] == ["a", "b", "c"]

    new = schema.load(serialized)
    assert new.labels == {"a", "b", "c"}


def test_serialize_k8s_job_environment(k8s_job_spec_content):
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write(k8s_job_spec_content)

        env = environments.KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )

        schema = KubernetesJobEnvironmentSchema()
        serialized = schema.dump(env)
        assert serialized
        assert serialized["__version__"] == prefect.__version__
        assert serialized["labels"] == []
        assert serialized["metadata"] == {}

    new = schema.load(serialized)
    assert new.labels == set()
    assert new.job_spec_file is None


def test_serialize_k8s_job_env_with_job_spec(k8s_job_spec_content):
    with tempfile.TemporaryDirectory() as directory:
        with open(os.path.join(directory, "job.yaml"), "w+") as f:
            f.write(k8s_job_spec_content)

        env = environments.KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )

        schema = KubernetesJobEnvironmentSchema()
        serialized = schema.dump(env)

        deserialized = schema.load(serialized)
        assert isinstance(deserialized, environments.KubernetesJobEnvironment)


def test_serialize_k8s_job_environment_with_labels(k8s_job_spec_content):
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write(k8s_job_spec_content)

        env = environments.KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml"), labels=["b", "c", "a"]
        )

        schema = KubernetesJobEnvironmentSchema()
        serialized = schema.dump(env)
        assert serialized
        assert serialized["__version__"] == prefect.__version__
        # labels should be sorted in the serialized obj
        assert serialized["labels"] == ["a", "b", "c"]

    new = schema.load(serialized)
    assert new.labels == {"a", "b", "c"}


def test_serialize_local_environment_with_labels():
    env = environments.LocalEnvironment(labels=["b", "c", "a"])

    schema = LocalEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    # labels should be sorted in the serialized obj
    assert serialized["labels"] == ["a", "b", "c"]

    new = schema.load(serialized)
    assert new.labels == {"b", "c", "a"}


def test_serialize_custom_environment():
    class MyEnv(environments.Environment):
        def __init__(self, x=5):
            self.x = 5
            super().__init__(labels=["b", "c", "a"], metadata={"test": "here"})

        def custom_method(self):
            pass

    env = MyEnv()
    schema = EnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized["type"] == "CustomEnvironment"
    assert serialized["labels"] == ["a", "b", "c"]
    assert serialized["metadata"] == {"test": "here"}

    obj = schema.load(serialized)
    assert isinstance(obj, environments.Environment)
    assert obj.labels == {"a", "b", "c"}
    assert obj.metadata == {"test": "here"}


@pytest.mark.parametrize("cls_name", ["RemoteEnvironment", "RemoteDaskEnvironment"])
def test_deserialize_old_environments_still_work(cls_name):
    """Check that old removed environments can still be deserialzed in the agent"""
    env = {
        "type": cls_name,
        "labels": ["prod"],
        "executor": "prefect.engine.executors.LocalExecutor",
        "__version__": "0.9.0",
        "executor_kwargs": {},
    }
    schema = EnvironmentSchema()
    obj = schema.load(env)

    assert isinstance(obj, environments.Environment)
    assert obj.labels == {"prod"}
    assert obj.metadata == {}
