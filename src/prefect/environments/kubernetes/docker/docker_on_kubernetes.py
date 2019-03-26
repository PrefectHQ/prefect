import logging
import uuid
from os import path
from typing import List

import docker
import yaml

import prefect
from prefect.environments import DockerEnvironment


class DockerOnKubernetesEnvironment(DockerEnvironment):
    """
    DockerOnKubernetes is an environment which deploys your image of choice on Kubernetes.
    *Note*: Make sure the base image is able to pip install Prefect. The default image for this
    environment is Python 3.6.

    (A future environment will allow for a minimal set up which does not require pip)

    There are no set up requirements, and execute creates a single job that has the role
    of running the flow. The job created in the execute function does have the requirement in that
    it needs to have an `identifier_label` set with a UUID so resources can be cleaned up
    independently of other deployments.

    Args:
        - base_image (string, optional): the base image for this environment (e.g. `python:3.6`), defaults to `python:3.6`
        - registry_url (string, optional): URL of a registry to push the image to; image will not be pushed if not provided
        - python_dependencies (List[str], optional): list of pip installable dependencies for the image
        - image_name (string, optional): name of the image to use when building, defaults to a UUID
        - image_tag (string, optional): tag of the image to use when building, defaults to a UUID
        - env_vars (dict, optional): a dictionary of environment variables to use when building
        - files (dict, optional): a dictionary of files to copy into the image when building
    """

    def __init__(
        self,
        base_image: str = "python:3.6",
        registry_url: str = None,
        python_dependencies: List[str] = None,
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
        env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]

        env[0]["value"] = prefect.config.cloud.graphql
        env[1]["value"] = prefect.config.cloud.log
        env[2]["value"] = prefect.config.cloud.result_handler
        env[3]["value"] = prefect.config.cloud.auth_token
        env[4]["value"] = prefect.context.get("flow_run_id", "")

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
        from kubernetes import client, config

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
        Build the Docker container. Returns a DockerEnvironment with the appropriate
        image_name and image_tag set.

        Args:
            - flow (prefect.Flow): Flow to be placed in container
            - push (bool): Whether or not to push to registry after build

        Returns:
            - DockerEnvironment: a DockerEnvironment that represents the provided flow.
        """

        image_name, image_tag = self.build_image(flow=flow, push=push)

        return DockerOnKubernetesEnvironment(
            base_image=self.base_image,
            registry_url=self.registry_url,
            image_name=image_name,
            image_tag=image_tag,
        )
