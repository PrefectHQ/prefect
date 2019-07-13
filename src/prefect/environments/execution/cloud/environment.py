import base64
import json
import sys
import time
import uuid
from os import path
from typing import Any, List

import cloudpickle
import docker
import yaml
from slugify import slugify

import prefect
from prefect.client import Secret
from prefect.environments.execution import Environment
from prefect.environments.storage import Docker
from prefect.utilities import logging


class CloudEnvironment(Environment):
    """
    CloudEnvironment is an environment which deploys your flow (stored in a Docker image)
    on Kubernetes and it uses the Prefect dask executor by dynamically spawning workers as pods.

    *Note*: This environment is not currently customizable. This may be subject to change.

    If pulling from a private docker registry, `setup` will ensure the appropriate
    kubernetes secret exists; `execute` creates a single job that has the role
    of spinning up a dask executor and running the flow. The job created in the execute
    function does have the requirement in that it needs to have an `identifier_label`
    set with a UUID so resources can be cleaned up independently of other deployments.

    Args:
        - private_registry (bool, optional): a boolean specifying whether your Flow's Docker container will be in a private
            Docker registry; if so, requires a Prefect Secret containing your docker credentials to be set.
            Defaults to `False`.
        - docker_secret (str, optional): the name of the Prefect Secret containing your Docker credentials; defaults to
            `"DOCKER_REGISTRY_CREDENTIALS"`.  This Secret should be a dictionary containing the following keys: `"docker-server"`,
            `"docker-username"`, `"docker-password"`, and `"docker-email"`.
    """

    def __init__(
        self, private_registry: bool = False, docker_secret: str = None
    ) -> None:
        self.identifier_label = str(uuid.uuid4())
        self.private_registry = private_registry
        if self.private_registry:
            self.docker_secret = docker_secret or "DOCKER_REGISTRY_CREDENTIALS"
        else:
            self.docker_secret = None  # type: ignore
        self.logger = logging.get_logger("CloudEnvironment")

    def setup(self, storage: "Docker") -> None:  # type: ignore
        if self.private_registry:
            from kubernetes import client, config

            # Verify environment is running in cluster
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                self.logger.error("Environment not currently running inside a cluster")
                raise EnvironmentError("Environment not currently inside a cluster")

            v1 = client.CoreV1Api()
            namespace = prefect.context.get("namespace", "")
            secret_name = namespace + "-docker"
            secrets = v1.list_namespaced_secret(namespace=namespace, watch=False)
            if not [
                secret
                for secret in secrets.items
                if secret.metadata.name == secret_name
            ]:
                self.logger.debug(
                    "Docker registry secret {} does not exist for this tenant.".format(
                        secret_name
                    )
                )
                self._create_namespaced_secret()
            else:
                self.logger.debug(
                    "Docker registry secret {} found.".format(secret_name)
                )

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

    def _create_namespaced_secret(self) -> None:
        self.logger.debug(
            'Creating Docker registry kubernetes secret from "{}" Prefect Secret.'.format(
                self.docker_secret
            )
        )
        try:
            from kubernetes import client

            docker_creds = Secret(self.docker_secret).get()
            assert isinstance(docker_creds, dict)

            v1 = client.CoreV1Api()
            cred_payload = {
                "auths": {
                    docker_creds["docker-server"]: {
                        "Username": docker_creds["docker-username"],
                        "Password": docker_creds["docker-password"],
                        "Email": docker_creds["docker-email"],
                    }
                }
            }
            data = {
                ".dockerconfigjson": base64.b64encode(
                    json.dumps(cred_payload).encode()
                ).decode()
            }
            namespace = prefect.context.get("namespace", "unknown")
            name = namespace + "-docker"
            secret = client.V1Secret(
                api_version="v1",
                data=data,
                kind="Secret",
                metadata=dict(name=name, namespace=namespace),
                type="kubernetes.io/dockerconfigjson",
            )
            v1.create_namespaced_secret(namespace, body=secret)
            self.logger.debug("Created Docker registry secret {}.".format(name))
        except Exception as exc:
            self.logger.error(
                "Failed to create Kubernetes secret for private Docker registry: {}".format(
                    exc
                )
            )
            raise exc

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
            self.logger.error("Environment not currently running inside a cluster")
            raise EnvironmentError("Environment not currently inside a cluster")

        batch_client = client.BatchV1Api()

        with open(path.join(path.dirname(__file__), "job.yaml")) as job_file:
            job = yaml.safe_load(job_file)
            job = self._populate_job_yaml(
                yaml_obj=job, docker_name=docker_name, flow_file_path=flow_file_path
            )

            # Create Job
            try:
                batch_client.create_namespaced_job(
                    namespace=prefect.context.get("namespace"), body=job
                )
            except Exception as exc:
                self.logger.critical("Failed to create Kubernetes job: {}".format(exc))
                raise exc

    def run_flow(self) -> None:
        """
        Run the flow from specified flow_file_path location using a Dask executor
        """
        try:
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
                    sys.exit(0)  # attempt to force resource cleanup
        except Exception as exc:
            self.logger.error("Unexpected error raised during flow run: {}".format(exc))
            raise exc

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
        flow_run_id = prefect.context.get("flow_run_id", "unknown")
        namespace = prefect.context.get("namespace", "unknown")

        # set identifier labels
        yaml_obj["metadata"]["name"] = "prefect-dask-job-{}".format(
            self.identifier_label
        )
        yaml_obj["metadata"]["labels"]["identifier"] = self.identifier_label
        yaml_obj["metadata"]["labels"]["flow_run_id"] = flow_run_id
        yaml_obj["spec"]["template"]["metadata"]["labels"][
            "identifier"
        ] = self.identifier_label

        # set environment variables
        env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]
        if self.private_registry:
            pod_spec = yaml_obj["spec"]["template"]["spec"]
            pod_spec["imagePullSecrets"] = []
            pod_spec["imagePullSecrets"].append({"name": namespace + "-docker"})

        env[0]["value"] = prefect.config.cloud.graphql
        env[1]["value"] = prefect.config.cloud.auth_token
        env[2]["value"] = flow_run_id
        env[3]["value"] = prefect.context.get("namespace", "")
        env[4]["value"] = docker_name
        env[5]["value"] = flow_file_path

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
        yaml_obj["metadata"]["labels"]["flow_run_id"] = prefect.context.get(
            "flow_run_id", "unknown"
        )

        # set environment variables
        env = yaml_obj["spec"]["containers"][0]["env"]

        env[0]["value"] = prefect.config.cloud.graphql
        env[1]["value"] = prefect.config.cloud.auth_token
        env[2]["value"] = prefect.context.get("flow_run_id", "")

        if self.private_registry:
            namespace = prefect.context.get("namespace", "")
            pod_spec = yaml_obj["spec"]
            pod_spec["imagePullSecrets"] = []
            pod_spec["imagePullSecrets"].append({"name": namespace + "-docker"})

        # set image
        yaml_obj["spec"]["containers"][0]["image"] = prefect.context.get(
            "image", "daskdev/dask:latest"
        )

        return yaml_obj
