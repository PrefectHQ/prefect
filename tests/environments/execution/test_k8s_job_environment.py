import copy
import os
from typing import List
from unittest.mock import MagicMock

import cloudpickle
import pytest
import yaml

import prefect
from prefect import Flow
from prefect.executors import LocalDaskExecutor
from prefect.environments import KubernetesJobEnvironment
from prefect.storage import Docker
from prefect.utilities.configuration import set_temporary_config


pytestmark = pytest.mark.filterwarnings("ignore:`Environment` based flow configuration")


@pytest.fixture
def default_command_args() -> List[str]:
    return [
        'python -c "import prefect; prefect.environments.execution.load_and_run_flow()"'
    ]


@pytest.fixture
def initial_job_spec(default_command_args):
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"labels": {}},
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {"command": ["/bin/sh", "-c"], "args": default_command_args}
                    ]
                },
                "metadata": {"labels": {}},
            }
        },
    }


@pytest.fixture
def job_spec_file(tmpdir):
    job_spec_file = str(tmpdir.join("job.yaml"))
    with open(job_spec_file, "w") as f:
        f.write("apiVersion: batch/v1\nkind: Job\n")
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


def test_create_k8s_job_environment_labels(job_spec_file):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file, labels=["foo"])
    assert environment.labels == set(["foo"])


def test_create_k8s_job_callbacks(job_spec_file):
    def f():
        pass

    environment = KubernetesJobEnvironment(
        job_spec_file=job_spec_file, labels=["foo"], on_start=f, on_exit=f
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


def test_environment_run():
    class MyExecutor(LocalDaskExecutor):
        submit_called = False

        def submit(self, *args, **kwargs):
            self.submit_called = True
            return super().submit(*args, **kwargs)

    global_dict = {}

    @prefect.task
    def add_to_dict():
        global_dict["run"] = True

    executor = MyExecutor()
    environment = KubernetesJobEnvironment(executor=executor)
    flow = prefect.Flow("test", tasks=[add_to_dict], environment=environment)

    environment.run(flow=flow)

    assert global_dict.get("run") is True
    assert executor.submit_called


def test_create_namespaced_job_fails_outside_cluster(job_spec_file):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)
    storage = Docker(registry_url="test1", image_name="test2", image_tag="test3")

    with pytest.raises(EnvironmentError):
        with set_temporary_config({"cloud.auth_token": "test"}):
            environment.execute(Flow("test", storage=storage))


def test_populate_job_yaml(job_spec_file, job, default_command_args):
    environment = KubernetesJobEnvironment(
        job_spec_file=job_spec_file, unique_job_name=True
    )

    job["spec"]["template"]["spec"]["containers"][0]["env"] = []
    environment._job_spec = job

    with set_temporary_config(
        {
            "cloud.graphql": "gql_test",
            "cloud.auth_token": "auth_test",
            "logging.extra_loggers": "['test_logger']",
        }
    ):
        with prefect.context(flow_run_id="id_test", namespace="namespace_test"):
            yaml_obj = environment._populate_run_time_job_spec_details(
                docker_name="test1/test2:test3"
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
    assert (
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["args"]
        == default_command_args
    )


def test_populate_job_yaml_no_defaults(job_spec_file, job):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)

    # only command and args are set on the container when the instance
    # is initialized
    job["spec"]["template"]["spec"]["containers"][0] = {
        "command": ["/bin/sh", "-c"],
        "args": default_command_args,
    }
    del job["metadata"]
    del job["spec"]["template"]["metadata"]
    environment._job_spec = job

    with set_temporary_config(
        {"cloud.graphql": "gql_test", "cloud.auth_token": "auth_test"}
    ):
        with prefect.context(flow_run_id="id_test", namespace="namespace_test"):
            yaml_obj = environment._populate_run_time_job_spec_details(
                docker_name="test1/test2:test3"
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


def test_populate_job_yaml_command_and_args_not_overridden_at_run_time(job_spec_file):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)

    test_command = ["/bin/bash", "-acdefg"]
    test_args = "echo 'hello'; python -c 'import prefect; prefect.environments.execution.load_and_run_flow()'"
    environment._job_spec["spec"]["template"]["spec"]["containers"][0][
        "command"
    ] = test_command
    environment._job_spec["spec"]["template"]["spec"]["containers"][0][
        "args"
    ] = test_args

    with set_temporary_config(
        {"cloud.graphql": "gql_test", "cloud.auth_token": "auth_test"}
    ):
        with prefect.context(flow_run_id="id_test", namespace="namespace_test"):
            yaml_obj = environment._populate_run_time_job_spec_details(
                docker_name="test1/test2:test3"
            )

    assert (
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["command"] == test_command
    )
    assert yaml_obj["spec"]["template"]["spec"]["containers"][0]["args"] == test_args


def test_populate_job_yaml_multiple_containers(
    job_spec_file, job, default_command_args
):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)

    # Generate yaml object with multiple containers
    job["spec"]["template"]["spec"]["containers"][0]["env"] = []
    job["spec"]["template"]["spec"]["containers"].append(
        copy.deepcopy(job["spec"]["template"]["spec"]["containers"][0])
    )
    job["spec"]["template"]["spec"]["containers"][1]["env"] = []
    job["spec"]["template"]["spec"]["containers"][1]["args"] = "echo 'other command'"
    environment._job_spec = job

    with set_temporary_config(
        {
            "cloud.graphql": "gql_test",
            "cloud.auth_token": "auth_test",
            "logging.extra_loggers": "['test_logger']",
        }
    ):
        with prefect.context(flow_run_id="id_test", namespace="namespace_test"):
            yaml_obj = environment._populate_run_time_job_spec_details(
                docker_name="test1/test2:test3"
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
    assert (
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["args"]
        == default_command_args
    )

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

    assert (
        yaml_obj["spec"]["template"]["spec"]["containers"][1]["args"]
        != default_command_args
    )


def test_initialize_environment_with_spec_populates(
    monkeypatch, job_spec_file, initial_job_spec, default_command_args
):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)
    assert environment._job_spec == initial_job_spec
    assert environment._job_spec["spec"]["template"]["spec"]["containers"][0][
        "command"
    ] == ["/bin/sh", "-c"]
    assert (
        environment._job_spec["spec"]["template"]["spec"]["containers"][0]["args"]
        == default_command_args
    )


def test_roundtrip_cloudpickle(job_spec_file, initial_job_spec):
    environment = KubernetesJobEnvironment(job_spec_file=job_spec_file)

    assert environment._job_spec == initial_job_spec

    new = cloudpickle.loads(cloudpickle.dumps(environment))
    assert isinstance(new, KubernetesJobEnvironment)
    assert new._job_spec == initial_job_spec

    # Identifer labels do not persist
    assert environment.identifier_label
    assert new.identifier_label

    assert environment.identifier_label != new.identifier_label
