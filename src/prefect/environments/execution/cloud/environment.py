import json
import logging
import time
import uuid
from os import path
from typing import Any, List

import cloudpickle
import docker
import yaml

import prefect
from prefect.environments.execution import Environment
from prefect.environments.storage import Docker


class CloudEnvironment(Environment):
    """
    CloudEnvironment is an environment which deploys your flow (stored in a Docker image)
    on Kubernetes and it uses the Prefect dask executor by dynamically spawning workers as pods.

    *Note*: This environment is not currently customizable. This may be subject to change.

    There are no set up requirements, and `execute` creates a single job that has the role
    of spinning up a dask executor and running the flow. The job created in the execute
    function does have the requirement in that it needs to have an `identifier_label`
    set with a UUID so resources can be cleaned up independently of other deployments.
    """

    def __init__(self) -> None:
        self.identifier_label = str(uuid.uuid4())

    def execute(  # type: ignore
        self, storage: "Docker", flow_location: str, **kwargs: Any
    ) -> None:
        """
        Create a single Kubernetes job that spins up a dask scheduler, dynamically
        creates worker pods, and runs the flow.

        Args:
            - storage (Docker): the Docker storage object that contains information relating
                to the image which houses the flow
            - flow_location (str): the location of the Flow to execute
            - **kwargs (Any): additional keyword arguments to pass to the runner

        Raises:
            - TypeError: if the storage is not `Docker`
        """
        if not isinstance(storage, Docker):
            raise TypeError("CloudEnvironment requires a Docker storage option")

        self.create_flow_run_job(docker_name=storage.name, flow_file_path=flow_location)

    def create_flow_run_job(self, docker_name: str, flow_file_path: str) -> None:
        """
        Creates a Kubernetes job to run the flow using the information stored on the
        Docker storage object.

        Args:
            - docker_name (str): the full name of the docker image (registry/name:tag)
            - flow_file_path (str): location of the flow file in the image
        """
        from kubernetes import client, config

        # Verify environment is running in cluster
        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            raise EnvironmentError("Environment not currently inside a cluster")

        batch_client = client.BatchV1Api()

        with open(path.join(path.dirname(__file__), "job.yaml")) as job_file:
            job = yaml.safe_load(job_file)
            job = self._populate_job_yaml(
                yaml_obj=job, docker_name=docker_name, flow_file_path=flow_file_path
            )

            # Create Job
            batch_client.create_namespaced_job(
                namespace=prefect.context.get("namespace"), body=job
            )

    def run_flow(self) -> None:
        """
        Run the flow from specified flow_file_path location using a Dask executor
        """
        from prefect.engine import get_default_flow_runner_class
        from prefect.engine.executors import DaskExecutor
        from dask_kubernetes import KubeCluster

        with open(path.join(path.dirname(__file__), "worker_pod.yaml")) as pod_file:
            worker_pod = yaml.safe_load(pod_file)
            worker_pod = self._populate_worker_pod_yaml(yaml_obj=worker_pod)

            cluster = KubeCluster.from_dict(
                worker_pod, namespace=prefect.context.get("namespace")
            )
            cluster.adapt(minimum=1, maximum=1)

            # Load serialized flow from file and run it with a DaskExecutor
            with open(
                prefect.context.get(
                    "flow_file_path", "/root/.prefect/flow_env.prefect"
                ),
                "rb",
            ) as f:
                flow = cloudpickle.load(f)

                executor = DaskExecutor(address=cluster.scheduler_address)
                runner_cls = get_default_flow_runner_class()
                runner_cls(flow=flow).run(executor=executor)

    ########################
    # YAML Spec Manipulation
    ########################

    def _populate_job_yaml(
        self, yaml_obj: dict, docker_name: str, flow_file_path: str
    ) -> dict:
        """
        Populate the execution job yaml object used in this environment with the proper values

        Args:
            - yaml_obj (dict): A dictionary representing the parsed yaml
            - docker_name (str): the full path to the docker image
            - flow_file_path (str): the location of the flow within the docker container

        Returns:
            - dict: a dictionary with the yaml values replaced
        """
        # set identifier labels
        yaml_obj["metadata"]["name"] = "prefect-dask-job-{}".format(
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
        env[5]["value"] = prefect.context.get("namespace", "")
        env[6]["value"] = docker_name
        env[7]["value"] = flow_file_path

        # set image
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"] = docker_name

        return yaml_obj

    def _populate_worker_pod_yaml(self, yaml_obj: dict) -> dict:
        """
        Populate the worker pod yaml object used in this environment with the proper values.

        Args:
            - yaml_obj (dict): A dictionary representing the parsed yaml

        Returns:
            - dict: a dictionary with the yaml values replaced
        """
        # set identifier labels
        yaml_obj["metadata"]["labels"]["identifier"] = self.identifier_label

        # set environment variables
        env = yaml_obj["spec"]["containers"][0]["env"]

        env[0]["value"] = prefect.config.cloud.graphql
        env[1]["value"] = prefect.config.cloud.log
        env[2]["value"] = prefect.config.cloud.result_handler
        env[3]["value"] = prefect.config.cloud.auth_token
        env[4]["value"] = prefect.context.get("flow_run_id", "")

        # set image
        yaml_obj["spec"]["containers"][0]["image"] = prefect.context.get(
            "image", "daskdev/dask:latest"
        )

        return yaml_obj
