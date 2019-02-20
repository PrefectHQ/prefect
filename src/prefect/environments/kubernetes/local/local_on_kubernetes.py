# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import logging
from os import path
import uuid

import docker
from kubernetes import client, config
import yaml

import prefect
from prefect.environments import DockerEnvironment


class LocalOnKubernetesEnvironment(DockerEnvironment):
    """
    LocalOnKubernetes is an environment which deploys a python:3.6 container on Kubernetes
    with Prefect installed. This is the simplest method of execution on Kubernetes. There
    is no set up requirements and execute creates a single job which has the role of running
    the flow.

    This environment is meant to be used as a simple and non-configurable environment for quickly
    testing a flow on Kubernetes. No dependencies or custom images are intended to be set with this
    environment and if desired then a DockerOnKubernetes environment should be used instead.

    This is called a LocalOnKubernetes job because the Docker portion is meant to be ignored
    however the image containing the flow is required at a minimum to currently run a flow on
    Kubernetes. Again, refer to the DockerOnKubernetes environment for a more customizeable
    experience.
    """

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

    def _populate_yaml(self, yaml_obj: dict) -> dict:
        """
        Populate a yaml object used in this environment with the proper values

        Args:
            - yaml_obj (dict): A dictionary representing the parsed yaml

        Returns:
            - dict: a dictionary with the yaml values replaced
        """
        # set identifier labels
        yaml_obj["metadata"]["name"] = "prefect-local-job-{}".format(
            self.identifier_label
        )
        yaml_obj["metadata"]["labels"]["identifier"] = self.identifier_label
        yaml_obj["spec"]["template"]["metadata"]["labels"][
            "identifier"
        ] = self.identifier_label

        # set environment variables
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"][0][
            "value"
        ] = prefect.config.cloud.graphql
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"][1][
            "value"
        ] = prefect.config.cloud.log
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"][2][
            "value"
        ] = prefect.config.cloud.result_handler
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"][3][
            "value"
        ] = prefect.config.cloud.auth_token
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"][4][
            "value"
        ] = prefect.context.get("flow_run_id", "")

        # set image
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"] = "{}:{}".format(
            path.join(self.registry_url, self.image_name),  # type: ignore
            self.image_tag,
        )

        return yaml_obj

    def execute(self) -> None:
        """
        Create a single Kubernetes job on the default namespace that runs a flow
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
        No setup is required for this environment
        """
        pass

    def build(
        self, flow: "prefect.Flow", push: bool = True
    ) -> "prefect.environments.DockerEnvironment":
        """
        Build the Docker container. Returns a Container Environment with the appropriate
        image_name and image_tag set.

        Args:
            - flow (prefect.Flow): Flow to be placed in container
            - push (bool): Whether or not to push to registry after build

        Returns:
            - DockerEnvironment: a DockerEnvironment that represents the provided flow.
        """

        image_name, image_tag = self.build_image(flow=flow, push=push)

        return LocalOnKubernetesEnvironment(
            base_image=self.base_image,
            registry_url=self.registry_url,
            image_name=image_name,
            image_tag=image_tag,
        )
