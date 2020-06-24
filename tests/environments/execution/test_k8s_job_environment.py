import copy
import os
from unittest.mock import MagicMock

import cloudpickle
import pytest
import yaml

import prefect
from prefect import Flow
from prefect.engine.executors import LocalDaskExecutor
from prefect.environments import KubernetesJobEnvironment
from prefect.environments.storage import Docker, Local
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.graphql import GraphQLResult


@pytest.fixture
def job_spec_file(tmpdir):
    job_spec_file = str(tmpdir.join("job.yaml"))
    with open(job_spec_file, "w") as f:
        f.write("job")
    return job_spec_file


@pytest.fixture
def job():
    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

    with open(os.path.join(file_path, "job.yaml")) as job_file:
        return yaml.safe_load(job_file)


def test_create_k8s_job_environment(job_spec_file):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)
    assert environment.job_spec_file == job_spec_file
    assert environment.unique_job_name is False
    assert environment.executor is not None
    assert environment.labels == set()
    assert environment.on_start is None
    assert environment.on_exit is None
    assert environment.metadata == {}
    assert environment.logger.name == "prefect.KubernetesJobEnvironment"


def test_create_k8s_job_environment_with_deprecated_executor_kwargs(job_spec_file):
    with set_temporary_config(
        {"engine.executor.default_class": "prefect.engine.executors.LocalDaskExecutor"}
    ):
        with pytest.warns(UserWarning, match="executor_kwargs"):
            environment = KubernetesJobEnvironment(
                job_spec_file=job_spec_file,
                executor_kwargs={"scheduler": "synchronous"},
            )
        assert isinstance(environment.executor, LocalDaskExecutor)
        assert environment.executor.scheduler == "synchronous"


def test_create_k8s_job_environment_labels(job_spec_file):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file, labels=["foo"])
    assert environment.labels == set(["foo"])


def test_create_k8s_job_callbacks(job_spec_file):
    def f():
        pass

    environment = KubernetesJobEnvironment(
        job_spec_file=job_spec_file, labels=["foo"], on_start=f, on_exit=f,
    )
    assert environment.labels == set(["foo"])
    assert environment.on_start is f
    assert environment.on_exit is f


def test_k8s_job_environment_dependencies():
    environment = KubernetesJobEnvironment()
    assert environment.dependencies == ["kubernetes"]


def test_create_k8s_job_environment_identifier_label(job_spec_file):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)
    assert environment.identifier_label


def test_create_k8s_job_environment_identifier_label_none(job_spec_file):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)
    environment._identifier_label = None
    assert environment.identifier_label


def test_setup_k8s_job_environment_passes(job_spec_file):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)
    environment.setup(Flow("test", storage=Docker()))


def test_execute_storage_missing_fields(job_spec_file):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)
    with pytest.raises(ValueError):
        environment.execute(Flow("test", storage=Docker()))


def test_execute(monkeypatch):
    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)
    environment = KubernetesJobEnvironment(os.path.join(file_path, "job.yaml"))

    config = MagicMock()
    monkeypatch.setattr("kubernetes.config", config)

    batchv1 = MagicMock()
    monkeypatch.setattr(
        "kubernetes.client", MagicMock(BatchV1Api=MagicMock(return_value=batchv1))
    )

    storage = Docker(registry_url="test1", image_name="test2", image_tag="test3")

    with set_temporary_config({"cloud.auth_token": "test"}):
        environment.execute(Flow("test", storage=storage))

    assert (
        batchv1.create_namespaced_job.call_args[1]["body"]["apiVersion"] == "batch/v1"
    )


def test_create_namespaced_job_fails_outside_cluster(job_spec_file):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)
    storage = Docker(registry_url="test1", image_name="test2", image_tag="test3")

    with pytest.raises(EnvironmentError):
        with set_temporary_config({"cloud.auth_token": "test"}):
            environment.execute(Flow("test", storage=storage))


def test_run_flow(monkeypatch, tmpdir, job_spec_file):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)

    flow_runner = MagicMock()
    flow_runner_class = MagicMock(return_value=flow_runner)

    monkeypatch.setattr(
        "prefect.engine.get_default_flow_runner_class",
        MagicMock(return_value=flow_runner_class),
    )

    d = Local(str(tmpdir))
    d.add_flow(prefect.Flow("name"))

    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(
                flow_run=[
                    GraphQLResult(
                        {
                            "flow": GraphQLResult(
                                {"name": "name", "storage": d.serialize(),}
                            )
                        }
                    )
                ],
            )
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.environments.execution.base.Client", client)

    with set_temporary_config({"cloud.auth_token": "test"}), prefect.context(
        {"flow_run_id": "id"}
    ):
        environment.run_flow()

    assert flow_runner_class.call_args[1]["flow"].name == "name"
    assert flow_runner.run.call_args[1]["executor"] is environment.executor


def test_run_flow_calls_callbacks(monkeypatch, tmpdir):
    start_func = MagicMock()
    exit_func = MagicMock()

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)
    environment = KubernetesJobEnvironment(
        os.path.join(file_path, "job.yaml"), on_start=start_func, on_exit=exit_func
    )

    flow_runner = MagicMock()
    monkeypatch.setattr(
        "prefect.engine.get_default_flow_runner_class",
        MagicMock(return_value=flow_runner),
    )

    d = Local(str(tmpdir))
    d.add_flow(prefect.Flow("name"))

    gql_return = MagicMock(
        return_value=MagicMock(
            data=MagicMock(
                flow_run=[
                    GraphQLResult(
                        {
                            "flow": GraphQLResult(
                                {"name": "name", "storage": d.serialize()}
                            )
                        }
                    )
                ],
            )
        )
    )
    client = MagicMock()
    client.return_value.graphql = gql_return
    monkeypatch.setattr("prefect.environments.execution.base.Client", client)

    with set_temporary_config({"cloud.auth_token": "test"}), prefect.context(
        {"flow_run_id": "id"}
    ):
        environment.run_flow()

    assert flow_runner.call_args[1]["flow"].name == "name"

    assert start_func.called
    assert exit_func.called


def test_populate_job_yaml(job_spec_file, job):
    environment = KubernetesJobEnvironment(
        job_spec_file=job_spec_file, unique_job_name=True
    )

    job["spec"]["template"]["spec"]["containers"][0]["env"] = []

    with set_temporary_config(
        {
            "cloud.graphql": "gql_test",
            "cloud.auth_token": "auth_test",
            "logging.extra_loggers": "['test_logger']",
        }
    ):
        with prefect.context(flow_run_id="id_test", namespace="namespace_test"):
            yaml_obj = environment._populate_job_spec_yaml(
                yaml_obj=job, docker_name="test1/test2:test3",
            )

    assert "prefect-dask-job-" in yaml_obj["metadata"]["name"]
    assert len(yaml_obj["metadata"]["name"]) == 25

    assert (
        yaml_obj["metadata"]["labels"]["prefect.io/identifier"]
        == environment.identifier_label
    )
    assert yaml_obj["metadata"]["labels"]["prefect.io/flow_run_id"] == "id_test"
    assert (
        yaml_obj["spec"]["template"]["metadata"]["labels"]["prefect.io/identifier"]
        == environment.identifier_label
    )

    env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]

    assert env[0]["value"] == "gql_test"
    assert env[1]["value"] == "auth_test"
    assert env[2]["value"] == "id_test"
    assert env[3]["value"] == "namespace_test"
    assert env[4]["value"] == "test1/test2:test3"
    assert env[9]["value"] == "['test_logger']"

    assert (
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"]
        == "test1/test2:test3"
    )

    assert yaml_obj["spec"]["template"]["spec"]["containers"][0]["command"] == [
        "/bin/sh",
        "-c",
    ]
    assert yaml_obj["spec"]["template"]["spec"]["containers"][0]["args"] == [
        "python -c 'import prefect; prefect.environments.KubernetesJobEnvironment().run_flow()'"
    ]


def test_populate_job_yaml_no_defaults(job_spec_file, job):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)

    job["spec"]["template"]["spec"]["containers"][0] = {}
    del job["metadata"]
    del job["spec"]["template"]["metadata"]

    with set_temporary_config(
        {"cloud.graphql": "gql_test", "cloud.auth_token": "auth_test"}
    ):
        with prefect.context(flow_run_id="id_test", namespace="namespace_test"):
            yaml_obj = environment._populate_job_spec_yaml(
                yaml_obj=job, docker_name="test1/test2:test3",
            )

    assert (
        yaml_obj["metadata"]["labels"]["prefect.io/identifier"]
        == environment.identifier_label
    )
    assert yaml_obj["metadata"]["labels"]["prefect.io/flow_run_id"] == "id_test"
    assert (
        yaml_obj["spec"]["template"]["metadata"]["labels"]["prefect.io/identifier"]
        == environment.identifier_label
    )

    env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]

    assert env[0]["value"] == "gql_test"
    assert env[1]["value"] == "auth_test"
    assert env[2]["value"] == "id_test"
    assert env[3]["value"] == "namespace_test"
    assert env[4]["value"] == "test1/test2:test3"
    assert env[9]["value"] == "[]"

    assert (
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"]
        == "test1/test2:test3"
    )

    assert yaml_obj["spec"]["template"]["spec"]["containers"][0]["command"] == [
        "/bin/sh",
        "-c",
    ]
    assert yaml_obj["spec"]["template"]["spec"]["containers"][0]["args"] == [
        "python -c 'import prefect; prefect.environments.KubernetesJobEnvironment().run_flow()'"
    ]


def test_populate_job_yaml_multiple_containers(job_spec_file, job):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)

    # Generate yaml object with multiple containers
    job["spec"]["template"]["spec"]["containers"][0]["env"] = []
    job["spec"]["template"]["spec"]["containers"].append(
        copy.deepcopy(job["spec"]["template"]["spec"]["containers"][0])
    )
    job["spec"]["template"]["spec"]["containers"][1]["env"] = []

    with set_temporary_config(
        {
            "cloud.graphql": "gql_test",
            "cloud.auth_token": "auth_test",
            "logging.extra_loggers": "['test_logger']",
        }
    ):
        with prefect.context(flow_run_id="id_test", namespace="namespace_test"):
            yaml_obj = environment._populate_job_spec_yaml(
                yaml_obj=job, docker_name="test1/test2:test3",
            )

    assert (
        yaml_obj["metadata"]["labels"]["prefect.io/identifier"]
        == environment.identifier_label
    )
    assert yaml_obj["metadata"]["labels"]["prefect.io/flow_run_id"] == "id_test"
    assert (
        yaml_obj["spec"]["template"]["metadata"]["labels"]["prefect.io/identifier"]
        == environment.identifier_label
    )

    # Assert First Container
    env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]

    assert env[0]["value"] == "gql_test"
    assert env[1]["value"] == "auth_test"
    assert env[2]["value"] == "id_test"
    assert env[3]["value"] == "namespace_test"
    assert env[4]["value"] == "test1/test2:test3"
    assert env[9]["value"] == "['test_logger']"

    assert (
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"]
        == "test1/test2:test3"
    )

    assert yaml_obj["spec"]["template"]["spec"]["containers"][0]["command"] == [
        "/bin/sh",
        "-c",
    ]
    assert yaml_obj["spec"]["template"]["spec"]["containers"][0]["args"] == [
        "python -c 'import prefect; prefect.environments.KubernetesJobEnvironment().run_flow()'"
    ]

    # Assert Second Container
    env = yaml_obj["spec"]["template"]["spec"]["containers"][1]["env"]

    assert env[0]["value"] == "gql_test"
    assert env[1]["value"] == "auth_test"
    assert env[2]["value"] == "id_test"
    assert env[3]["value"] == "namespace_test"
    assert env[4]["value"] == "test1/test2:test3"
    assert env[9]["value"] == "['test_logger']"

    assert (
        yaml_obj["spec"]["template"]["spec"]["containers"][1]["image"]
        != "test1/test2:test3"
    )

    assert yaml_obj["spec"]["template"]["spec"]["containers"][1]["args"] != [
        "python -c 'import prefect; prefect.environments.KubernetesJobEnvironment().run_flow()'"
    ]


def test_initialize_environment_with_spec_populates(monkeypatch, job_spec_file):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)
    assert environment._job_spec == "job"


def test_roundtrip_cloudpickle(job_spec_file):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)

    assert environment._job_spec == "job"

    new = cloudpickle.loads(cloudpickle.dumps(environment))
    assert isinstance(new, KubernetesJobEnvironment)
    assert new._job_spec == "job"

    # Identifer labels do not persist
    assert environment.identifier_label
    assert new.identifier_label

    assert environment.identifier_label != new.identifier_label
