import os
import tempfile

import prefect
from prefect import environments
from prefect.serialization.environment import (
    BaseEnvironmentSchema,
    DaskKubernetesEnvironmentSchema,
    EnvironmentSchema,
    FargateTaskEnvironmentSchema,
    KubernetesJobEnvironmentSchema,
    LocalEnvironmentSchema,
    RemoteEnvironmentSchema,
    RemoteDaskEnvironmentSchema,
)


def test_serialize_base_environment():
    env = environments.Environment()

    serialized = BaseEnvironmentSchema().dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["labels"] == []


def test_serialize_base_environment_with_labels():
    env = environments.Environment(labels=["foo", "bar"])

    serialized = BaseEnvironmentSchema().dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert set(serialized["labels"]) == set(["foo", "bar"])


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
    env = environments.DaskKubernetesEnvironment(labels=["a", "b", "c"])

    schema = DaskKubernetesEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["docker_secret"] is None
    assert serialized["min_workers"] == 1
    assert serialized["max_workers"] == 2
    assert set(serialized["labels"]) == set(["a", "b", "c"])

    new = schema.load(serialized)
    assert new.private_registry is False
    assert new.docker_secret is None
    assert new.min_workers == 1
    assert new.max_workers == 2
    assert new.labels == set(["a", "b", "c"])


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
    env = environments.FargateTaskEnvironment(labels=["a", "b", "c"])

    schema = FargateTaskEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert set(serialized["labels"]) == set(["a", "b", "c"])

    new = schema.load(serialized)
    assert new.labels == set(["a", "b", "c"])


def test_serialize_k8s_job_environment():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        env = environments.KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )

        schema = KubernetesJobEnvironmentSchema()
        serialized = schema.dump(env)
        assert serialized
        assert serialized["__version__"] == prefect.__version__
        assert serialized["labels"] == []

    new = schema.load(serialized)
    assert new.labels == set()
    assert new.job_spec_file is None


def test_serialize_k8s_job_env_with_job_spec():
    with tempfile.TemporaryDirectory() as directory:
        with open(os.path.join(directory, "job.yaml"), "w+") as f:
            f.write("job")

        env = environments.KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )

        schema = KubernetesJobEnvironmentSchema()
        serialized = schema.dump(env)

        deserialized = schema.load(serialized)
        assert isinstance(deserialized, environments.KubernetesJobEnvironment)


def test_serialize_k8s_job_environment_with_labels():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        env = environments.KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml"), labels=["a", "b", "c"]
        )

        schema = KubernetesJobEnvironmentSchema()
        serialized = schema.dump(env)
        assert serialized
        assert serialized["__version__"] == prefect.__version__
        assert set(serialized["labels"]) == set(["a", "b", "c"])

    new = schema.load(serialized)
    assert new.labels == set(["a", "b", "c"])


def test_serialize_remote_environment():
    env = environments.RemoteEnvironment()

    schema = RemoteEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["executor"] == prefect.config.engine.executor.default_class
    assert serialized["executor_kwargs"] == {}
    assert serialized["labels"] == []

    new = schema.load(serialized)
    assert new.executor == prefect.config.engine.executor.default_class
    assert new.executor_kwargs == {}
    assert new.labels == set()


def test_serialize_remote_environment_with_labels():
    env = environments.RemoteEnvironment(labels=["bob", "alice"])

    schema = RemoteEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["executor"] == prefect.config.engine.executor.default_class
    assert serialized["executor_kwargs"] == {}
    assert set(serialized["labels"]) == set(["bob", "alice"])

    new = schema.load(serialized)
    assert new.executor == prefect.config.engine.executor.default_class
    assert new.executor_kwargs == {}
    assert new.labels == set(["bob", "alice"])


def test_serialize_remote_dask_environment():
    env = environments.RemoteDaskEnvironment(address="test")

    schema = RemoteDaskEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["address"] == "test"
    assert serialized["labels"] == []

    new = schema.load(serialized)
    assert new.address == "test"
    assert new.labels == set()


def test_serialize_remote_dask_environment_with_labels():
    env = environments.RemoteDaskEnvironment(
        address="test", labels=["bob", "alice"], executor_kwargs={"not": "present"}
    )

    schema = RemoteDaskEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["address"] == "test"
    assert set(serialized["labels"]) == set(["bob", "alice"])

    new = schema.load(serialized)
    assert new.address == "test"
    assert new.labels == set(["bob", "alice"])


def test_serialize_local_environment_with_labels():
    env = environments.LocalEnvironment(labels=["bob", "alice"])

    schema = RemoteEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert set(serialized["labels"]) == set(["bob", "alice"])

    new = schema.load(serialized)
    assert new.labels == set(["bob", "alice"])


def test_deserialize_old_env_payload():
    old = {
        "executor": "prefect.engine.executors.LocalExecutor",
        "executor_kwargs": {},
        "__version__": "0.6.3",
        "type": "RemoteEnvironment",
    }

    schema = EnvironmentSchema()
    obj = schema.load(old)
    assert isinstance(obj, environments.RemoteEnvironment)
    assert obj.labels == set()


def test_serialize_custom_environment():
    class MyEnv(environments.Environment):
        def __init__(self, x=5):
            self.x = 5
            super().__init__(labels=["foo", "bar"])

        def custom_method(self):
            pass

    env = MyEnv()
    schema = EnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized["type"] == "CustomEnvironment"
    assert set(serialized["labels"]) == set(["foo", "bar"])

    obj = schema.load(serialized)
    assert isinstance(obj, environments.Environment)
    assert obj.labels == set(["foo", "bar"])
