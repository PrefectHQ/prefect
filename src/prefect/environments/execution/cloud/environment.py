import json
import logging
import time
import uuid
from os import path
from typing import List

import docker
import yaml

import prefect
from prefect.environments.storage import Docker
from prefect.environments.execution import Environment


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

    def execute(self, storage: "Docker" = Docker()) -> None:
        """
        Create a single Kubernetes job that spins up a dask scheduler, dynamically
        creates worker pods, and runs the flow.

        Args:
            - storage (Docker): the Docker storage object that contains information relating
                to the image which houses the flow
        """
        if not isinstance(storage, Docker):
            raise TypeError("CloudEnvironment requires a Docker storage option")

        if not storage.image_name or not storage.image_tag or not storage.registry_url:
            raise ValueError("Docker storage is missing required fields")

        self.create_flow_run_job(
            registry_url=storage.registry_url,
            image_name=storage.image_name,
            image_tag=storage.image_tag,
            flow_file_path=storage.flow_file_path,
        )

    def create_flow_run_job(
        self, registry_url: str, image_name: str, image_tag: str, flow_file_path: str
    ) -> None:
        """
        Creates a Kubernetes job to run the flow using the information stored on the
        Docker storage object.

        Args:
            - registry_url (str): URL of a registry the image was stored in
            - image_name (str): name of the image
            - image_tag (str): tag of the image
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
                yaml_obj=job,
                registry_url=registry_url,
                image_name=image_name,
                image_tag=image_tag,
                flow_file_path=flow_file_path,
            )

            # Create Job
            batch_client.create_namespaced_job(namespace="default", body=job)

    def run_flow(self) -> None:
        """
        Run the flow from specified flow_file_path location using a Dask executor
        """
        from prefect.engine import FlowRunner
        from prefect.engine.executors import DaskExecutor
        from dask_kubernetes import KubeCluster

        with open(path.join(path.dirname(__file__), "worker_pod.yaml")) as pod_file:
            worker_pod = yaml.safe_load(pod_file)
            worker_pod = self._populate_worker_pod_yaml(yaml_obj=worker_pod)

            cluster = KubeCluster.from_dict(worker_pod)
            cluster.adapt(minimum=1, maximum=1)

            # Load serialized flow from file and run it with a DaskExecutor
            schema = prefect.serialization.flow.FlowSchema()
            with open(
                prefect.context.get(
                    "flow_file_path", "/root/.prefect/flow_env.prefect"
                ),
                "r",
            ) as f:
                flow = schema.load(json.load(f))

                executor = DaskExecutor(address=cluster.scheduler_address)
                FlowRunner(flow=flow).run(executor=executor)

    ########################
    # YAML Spec Manipulation
    ########################

    def _populate_job_yaml(
        self,
        yaml_obj: dict,
        registry_url: str,
        image_name: str,
        image_tag: str,
        flow_file_path: str,
    ) -> dict:
        """
        Populate the execution job yaml object used in this environment with the proper values

        Args:
            - yaml_obj (dict): A dictionary representing the parsed yaml

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
        env[5]["value"] = "{}:{}".format(
            path.join(registry_url, image_name), image_tag  # type: ignore
        )
        env[6]["value"] = flow_file_path

        # set image
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"] = "{}:{}".format(
            path.join(registry_url, image_name), image_tag  # type: ignore
        )

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
