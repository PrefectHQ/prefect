import pytest

import prefect
from prefect.environments import kubernetes

#################################
##### DaskOnKubernetes Tests
#################################


class TestDaskOnKubernetesEnvironment:
    def test_create_dask_on_kubernetes_environment(self):
        env = kubernetes.DaskOnKubernetesEnvironment(base_image="a")
        assert env

    def test_dask_on_kubernetes_environment_has_default_image(self):
        env = kubernetes.DaskOnKubernetesEnvironment()
        assert env.base_image == "python:3.6"

    def test_dask_on_kubernetes_environment_variables(self):
        env = kubernetes.DaskOnKubernetesEnvironment(
            base_image="a",
            registry_url="b",
            python_dependencies=["c"],
            image_name="d",
            image_tag="e",
            env_vars={"f": "g"},
            files={"/": "/"},
            max_workers=5
        )
        assert env.base_image == "a"
        assert env.registry_url == "b"
        assert env.python_dependencies == ["c"]
        assert env.image_name == "d"
        assert env.image_tag == "e"
        assert env.env_vars == {"f": "g"}
        assert env.files == {"/": "/"}
        assert env.max_workers == 5

    def test_dask_on_kubernetes_environment_default_workers(self):
        env = kubernetes.DaskOnKubernetesEnvironment(base_image="a")
        assert env.max_workers == 1

    def test_dask_on_kubernetes_environment_default_scheduler_address_is_none(self):
        env = kubernetes.DaskOnKubernetesEnvironment(base_image="a")
        assert env.scheduler_address == None

    def test_dask_on_kubernetes_environment_identifier_label(self):
        env = kubernetes.DaskOnKubernetesEnvironment(base_image="a")
        assert env.identifier_label

    def test_dask_on_kubernetes_environment_setup_does_nothing(self):
        env = kubernetes.DaskOnKubernetesEnvironment(base_image="a")
        env.setup()
        assert env

    def test_dask_on_kubernetes_environment_execution_raises_error_out_of_cluster(
        self
    ):
        env = kubernetes.DaskOnKubernetesEnvironment(base_image="a")
        with pytest.raises(EnvironmentError) as exc:
            env.execute()
        assert "Environment not currently inside a cluster" in str(exc.value)
