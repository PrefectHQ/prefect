import copy
import os
import tempfile
from os import path
from unittest.mock import MagicMock

import cloudpickle
import pytest
import yaml

import prefect
from prefect.environments import KubernetesJobEnvironment
from prefect.environments.storage import Docker, Local
from prefect.utilities.configuration import set_temporary_config


def test_create_k8s_job_environment():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )
        assert environment
        assert environment.job_spec_file == os.path.join(directory, "job.yaml")
        assert environment.unique_job_name == False
        assert environment.executor_kwargs == {}
        assert environment.labels == set()
        assert environment.on_start is None
        assert environment.on_exit is None
        assert environment.logger.name == "prefect.KubernetesJobEnvironment"


def test_create_k8s_job_environment_with_executor_kwargs():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml"),
            executor_kwargs={"test": "here"},
        )
        assert environment
        assert environment.executor_kwargs == {"test": "here"}


def test_create_k8s_job_environment_labels():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml"), labels=["foo"]
        )
        assert environment.labels == set(["foo"])


def test_create_k8s_job_callbacks():
    def f():
        pass

    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml"),
            labels=["foo"],
            on_start=f,
            on_exit=f,
        )
        assert environment.labels == set(["foo"])
        assert environment.on_start is f
        assert environment.on_exit is f


def test_k8s_job_environment_dependencies():
    environment = KubernetesJobEnvironment()
    assert environment.dependencies == ["kubernetes"]


def test_create_k8s_job_environment_identifier_label():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )
        assert environment.identifier_label


def test_create_k8s_job_environment_identifier_label_none():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )
        environment._identifier_label = None
        assert environment.identifier_label


def test_setup_k8s_job_environment_passes():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )
        environment.setup(storage=Docker())
        assert environment


def test_execute_improper_storage():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )
        with pytest.raises(TypeError):
            environment.execute(storage=Local(), flow_location="")


def test_execute_storage_missing_fields():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )
        with pytest.raises(ValueError):
            environment.execute(storage=Docker(), flow_location="")


def test_execute(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )
        storage = Docker(registry_url="test1", image_name="test2", image_tag="test3")

        create_flow_run = MagicMock()
        monkeypatch.setattr(
            "prefect.environments.KubernetesJobEnvironment.create_flow_run_job",
            create_flow_run,
        )

        environment.execute(storage=storage, flow_location="")

        assert create_flow_run.call_args[1]["docker_name"] == "test1/test2:test3"


def test_create_flow_run_job(monkeypatch):
    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)
    environment = KubernetesJobEnvironment(path.join(file_path, "job.yaml"))

    config = MagicMock()
    monkeypatch.setattr("kubernetes.config", config)

    batchv1 = MagicMock()
    monkeypatch.setattr(
        "kubernetes.client", MagicMock(BatchV1Api=MagicMock(return_value=batchv1))
    )

    with set_temporary_config({"cloud.auth_token": "test"}):
        environment.create_flow_run_job(
            docker_name="test1/test2:test3", flow_file_path="test4"
        )

    assert (
        batchv1.create_namespaced_job.call_args[1]["body"]["apiVersion"] == "batch/v1"
    )


def test_create_flow_run_job_fails_outside_cluster():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )

        with pytest.raises(EnvironmentError):
            with set_temporary_config({"cloud.auth_token": "test"}):
                environment.create_flow_run_job(
                    docker_name="test1/test2:test3", flow_file_path="test4"
                )


def test_run_flow(monkeypatch):
    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)
    environment = KubernetesJobEnvironment(
        path.join(file_path, "job.yaml"), executor_kwargs={"test": "here"}
    )

    flow_runner = MagicMock()
    monkeypatch.setattr(
        "prefect.engine.get_default_flow_runner_class",
        MagicMock(return_value=flow_runner),
    )

    executor = MagicMock()
    monkeypatch.setattr(
        "prefect.engine.get_default_executor_class", MagicMock(return_value=executor),
    )

    with tempfile.TemporaryDirectory() as directory:
        with open(os.path.join(directory, "flow_env.prefect"), "w+") as env:
            storage = Local(directory)
            flow = prefect.Flow("test", storage=storage)
            flow_path = os.path.join(directory, "flow_env.prefect")
            with open(flow_path, "wb") as f:
                cloudpickle.dump(flow, f)

        with set_temporary_config({"cloud.auth_token": "test"}):
            with prefect.context(
                flow_file_path=os.path.join(directory, "flow_env.prefect")
            ):
                environment.run_flow()

        assert flow_runner.call_args[1]["flow"].name == "test"
        assert executor.call_args[1] == {"test": "here"}


def test_run_flow_calls_callbacks(monkeypatch):
    start_func = MagicMock()
    exit_func = MagicMock()

    file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)
    environment = KubernetesJobEnvironment(
        path.join(file_path, "job.yaml"), on_start=start_func, on_exit=exit_func
    )

    flow_runner = MagicMock()
    monkeypatch.setattr(
        "prefect.engine.get_default_flow_runner_class",
        MagicMock(return_value=flow_runner),
    )

    with tempfile.TemporaryDirectory() as directory:
        with open(os.path.join(directory, "flow_env.prefect"), "w+") as env:
            storage = Local(directory)
            flow = prefect.Flow("test", storage=storage)
            flow_path = os.path.join(directory, "flow_env.prefect")
            with open(flow_path, "wb") as f:
                cloudpickle.dump(flow, f)

        with set_temporary_config({"cloud.auth_token": "test"}):
            with prefect.context(
                flow_file_path=os.path.join(directory, "flow_env.prefect")
            ):
                environment.run_flow()

        assert flow_runner.call_args[1]["flow"].name == "test"

    assert start_func.called
    assert exit_func.called


def test_populate_job_yaml():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml"), unique_job_name=True
        )

        file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

        with open(path.join(file_path, "job.yaml")) as job_file:
            job = yaml.safe_load(job_file)
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
                    yaml_obj=job,
                    docker_name="test1/test2:test3",
                    flow_file_path="test4",
                )

        assert "prefect-dask-job-" in yaml_obj["metadata"]["name"]
        assert len(yaml_obj["metadata"]["name"]) == 25

        assert (
            yaml_obj["metadata"]["labels"]["identifier"] == environment.identifier_label
        )
        assert yaml_obj["metadata"]["labels"]["flow_run_id"] == "id_test"
        assert (
            yaml_obj["spec"]["template"]["metadata"]["labels"]["identifier"]
            == environment.identifier_label
        )

        env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]

        assert env[0]["value"] == "gql_test"
        assert env[1]["value"] == "auth_test"
        assert env[2]["value"] == "id_test"
        assert env[3]["value"] == "namespace_test"
        assert env[4]["value"] == "test1/test2:test3"
        assert env[5]["value"] == "test4"
        assert env[10]["value"] == "['test_logger']"

        assert (
            yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"]
            == "test1/test2:test3"
        )

        assert yaml_obj["spec"]["template"]["spec"]["containers"][0]["command"] == [
            "/bin/sh",
            "-c",
        ]
        assert yaml_obj["spec"]["template"]["spec"]["containers"][0]["args"] == [
            "python -c 'import prefect; prefect.Flow.load(prefect.context.flow_file_path).environment.run_flow()'"
        ]


def test_populate_job_yaml_no_defaults():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )

        file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

        with open(path.join(file_path, "job.yaml")) as job_file:
            job = yaml.safe_load(job_file)
            job["spec"]["template"]["spec"]["containers"][0] = {}
            del job["metadata"]
            del job["spec"]["template"]["metadata"]

        with set_temporary_config(
            {"cloud.graphql": "gql_test", "cloud.auth_token": "auth_test"}
        ):
            with prefect.context(flow_run_id="id_test", namespace="namespace_test"):
                yaml_obj = environment._populate_job_spec_yaml(
                    yaml_obj=job,
                    docker_name="test1/test2:test3",
                    flow_file_path="test4",
                )

        assert (
            yaml_obj["metadata"]["labels"]["identifier"] == environment.identifier_label
        )
        assert yaml_obj["metadata"]["labels"]["flow_run_id"] == "id_test"
        assert (
            yaml_obj["spec"]["template"]["metadata"]["labels"]["identifier"]
            == environment.identifier_label
        )

        env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]

        assert env[0]["value"] == "gql_test"
        assert env[1]["value"] == "auth_test"
        assert env[2]["value"] == "id_test"
        assert env[3]["value"] == "namespace_test"
        assert env[4]["value"] == "test1/test2:test3"
        assert env[5]["value"] == "test4"
        assert env[10]["value"] == "[]"

        assert (
            yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"]
            == "test1/test2:test3"
        )

        assert yaml_obj["spec"]["template"]["spec"]["containers"][0]["command"] == [
            "/bin/sh",
            "-c",
        ]
        assert yaml_obj["spec"]["template"]["spec"]["containers"][0]["args"] == [
            "python -c 'import prefect; prefect.Flow.load(prefect.context.flow_file_path).environment.run_flow()'"
        ]


def test_populate_job_yaml_multiple_containers():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )

        file_path = os.path.dirname(prefect.environments.execution.dask.k8s.__file__)

        with open(path.join(file_path, "job.yaml")) as job_file:
            job = yaml.safe_load(job_file)
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
                    yaml_obj=job,
                    docker_name="test1/test2:test3",
                    flow_file_path="test4",
                )

        assert (
            yaml_obj["metadata"]["labels"]["identifier"] == environment.identifier_label
        )
        assert yaml_obj["metadata"]["labels"]["flow_run_id"] == "id_test"
        assert (
            yaml_obj["spec"]["template"]["metadata"]["labels"]["identifier"]
            == environment.identifier_label
        )

        # Assert First Container
        env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]

        assert env[0]["value"] == "gql_test"
        assert env[1]["value"] == "auth_test"
        assert env[2]["value"] == "id_test"
        assert env[3]["value"] == "namespace_test"
        assert env[4]["value"] == "test1/test2:test3"
        assert env[5]["value"] == "test4"
        assert env[10]["value"] == "['test_logger']"

        assert (
            yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"]
            == "test1/test2:test3"
        )

        assert yaml_obj["spec"]["template"]["spec"]["containers"][0]["command"] == [
            "/bin/sh",
            "-c",
        ]
        assert yaml_obj["spec"]["template"]["spec"]["containers"][0]["args"] == [
            "python -c 'import prefect; prefect.Flow.load(prefect.context.flow_file_path).environment.run_flow()'"
        ]

        # Assert Second Container
        env = yaml_obj["spec"]["template"]["spec"]["containers"][1]["env"]

        assert env[0]["value"] == "gql_test"
        assert env[1]["value"] == "auth_test"
        assert env[2]["value"] == "id_test"
        assert env[3]["value"] == "namespace_test"
        assert env[4]["value"] == "test1/test2:test3"
        assert env[5]["value"] == "test4"
        assert env[10]["value"] == "['test_logger']"

        assert (
            yaml_obj["spec"]["template"]["spec"]["containers"][1]["image"]
            != "test1/test2:test3"
        )

        assert yaml_obj["spec"]["template"]["spec"]["containers"][1]["args"] != [
            "python -c 'import prefect; prefect.Flow.load(prefect.context.flow_file_path).environment.run_flow()'"
        ]


def test_initialize_environment_with_spec_populates(monkeypatch):

    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )

        assert environment._job_spec == "job"


def test_roundtrip_cloudpickle():
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "job.yaml"), "w+") as file:
            file.write("job")

        environment = KubernetesJobEnvironment(
            job_spec_file=os.path.join(directory, "job.yaml")
        )

        assert environment._job_spec == "job"

        new = cloudpickle.loads(cloudpickle.dumps(environment))
        assert isinstance(new, KubernetesJobEnvironment)
        assert new._job_spec == "job"

        # Identifer labels do not persist
        assert environment.identifier_label
        assert new.identifier_label

        assert environment.identifier_label != new.identifier_label
