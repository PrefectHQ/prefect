
import pytest

import prefect
from prefect.environments import (
    kubernetes,
)

#################################
##### DockerOnKubernetes Tests
#################################


class TestDockerOnKubernetesEnvironment:
    def test_create_docker_on_kubernetes_environment(self):
        env = kubernetes.DockerOnKubernetesEnvironment(base_image="a")
        assert env

    def test_docker_on_kubernetes_environment_has_default_image(self):
        env = kubernetes.DockerOnKubernetesEnvironment()
        assert env.base_image == "python:3.6"

    def test_docker_on_kubernetes_environment_variables(self):
        env = kubernetes.DockerOnKubernetesEnvironment(
            base_image="a",
            registry_url="b",
            python_dependencies=["c"],
            image_name="d",
            image_tag="e",
            env_vars={"f": "g"},
            files={"/": "/"},
        )
        assert env.base_image == "a"
        assert env.registry_url == "b"
        assert env.python_dependencies == ["c"]
        assert env.image_name == "d"
        assert env.image_tag == "e"
        assert env.env_vars == {"f": "g"}
        assert env.files == {"/": "/"}

    def test_docker_on_kubernetes_environment_identifier_label(self):
        env = kubernetes.DockerOnKubernetesEnvironment(base_image="a")
        assert env.identifier_label

    def test_docker_on_kubernetes_environment_setup_does_nothing(self):
        env = kubernetes.DockerOnKubernetesEnvironment(base_image="a")
        env.setup()
        assert env

    def test_docker_on_kubernetes_environment_execution_raises_error_out_of_cluster(
        self
    ):
        env = kubernetes.DockerOnKubernetesEnvironment(base_image="a")
        with pytest.raises(EnvironmentError) as exc:
            env.execute()
        assert "Environment not currently inside a cluster" in str(exc.value)
