# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import logging
from os import path
import uuid

from dask_kubernetes import KubeCluster
import docker
from kubernetes import client, config
import yaml

import prefect
from prefect.environments import DockerEnvironment

class DaskOnKubernetesEnvironment(DockerEnvironment):

    # Add dask related config options to the init
    def __init__(
        self,
        base_image: str = "python:3.6",
        registry_url: str = None,
        python_dependencies: list = None,
        image_name: str = None,
        image_tag: str = None,
        env_vars: dict = None,
        files: dict = None,
    ) -> None:
        super().__init__(
            base_image=base_image,
            registry_url=registry_url,
            python_dependencies=python_dependencies,
            image_name=image_name,
            image_tag=image_tag,
            env_vars=env_vars,
            files=files,
        )

        self.identifier_label = str(uuid.uuid4())

    def execute(self) -> None:
        """
        Create a single Kubernetes job on the default namespace that runs a flow. This also
        blocks until the job is either Failed or Completed in order to preserve the dask scheduler.
        """
        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            raise EnvironmentError("Environment not currently inside a cluster")

        batch_client = client.BatchV1Api()

        with open(path.join(path.dirname(__file__), "job.yaml")) as job_file:
            job = yaml.safe_load(job_file)
            job = self._populate_yaml(yaml_obj=job)

            # Create Job
            batch_client.create_namespaced_job(namespace="default", body=job)

    def setup(self) -> None:
        """
        ASDF
        """
        pass

    def build(
        self, flow: "prefect.Flow", push: bool = True
    ) -> "prefect.environments.DockerEnvironment":
        """
        Build the Docker container. Returns a DockerEnvironment with the appropriate
        image_name and image_tag set.

        Args:
            - flow (prefect.Flow): Flow to be placed in container
            - push (bool): Whether or not to push to registry after build

        Returns:
            - DockerEnvironment: a DockerEnvironment that represents the provided flow.
        """

        image_name, image_tag = self.build_image(flow=flow, push=push)

        return DaskOnKubernetesEnvironment(
            base_image=self.base_image,
            registry_url=self.registry_url,
            image_name=image_name,
            image_tag=image_tag,
        )