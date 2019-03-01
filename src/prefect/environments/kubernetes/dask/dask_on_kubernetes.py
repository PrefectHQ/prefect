# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import logging
from os import path
import time
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
        self.scheduler_address = None

    def _populate_worker_pod_yaml(self, yaml_obj: dict) -> dict:
        """"""
        # set identifier labels
        yaml_obj["metadata"]["labels"]["identifier"] = self.identifier_label

        yaml_obj["spec"]["containers"][0]["env"][0][
            "value"
        ] = prefect.config.cloud.graphql
        yaml_obj["spec"]["containers"][0]["env"][1]["value"] = prefect.config.cloud.log
        yaml_obj["spec"]["containers"][0]["env"][2][
            "value"
        ] = prefect.config.cloud.result_handler
        yaml_obj["spec"]["containers"][0]["env"][3][
            "value"
        ] = prefect.config.cloud.auth_token
        yaml_obj["spec"]["containers"][0]["env"][4]["value"] = prefect.context.get(
            "flow_run_id", ""
        )

        # set image
        yaml_obj["spec"]["containers"][0]["image"] = prefect.context.get(
            "image", "daskdev/dask:latest"
        )

        return yaml_obj

    def _populate_scheduler_service_yaml(self, yaml_obj: dict) -> dict:
        """"""
        # set identifier labels
        yaml_obj["metadata"]["labels"]["identifier"] = self.identifier_label

        job_identifier = prefect.context.get("job_identifier", "")

        yaml_obj["metadata"]["name"] = "prefect-job-{}".format(job_identifier)
        yaml_obj["metadata"]["labels"]["app"] = "prefect-job-{}".format(job_identifier)
        yaml_obj["spec"]["selector"]["app"] = "prefect-job-{}".format(job_identifier)

        return yaml_obj

    def _populate_job_yaml(self, yaml_obj: dict) -> dict:
        """"""
        # set identifier labels
        yaml_obj["metadata"]["name"] = "prefect-dask-job-{}".format(
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
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"][5][
            "value"
        ] = "{}:{}".format(
            path.join(self.registry_url, self.image_name),  # type: ignore
            self.image_tag,
        )
        # yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"][5][
        #     "value"
        # ] = "{}:8786".format(self.scheduler_address)

        # set image
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"] = "{}:{}".format(
            path.join(self.registry_url, self.image_name),  # type: ignore
            self.image_tag,
        )

        return yaml_obj

    def _wait_for_dask_job(self) -> None:
        """"""
        batch_client = client.BatchV1Api()

        while True:
            time.sleep(5)

            job = batch_client.read_namespaced_job_status(
                name="prefect-dask-job-{}".format(self.identifier_label),
                namespace="default",
            )

            if not job or job.status.failed or job.status.succeeded:
                print("Dask job is", job.status)
                return

    def create_dask_cluster(self) -> None:
        with open(path.join(path.dirname(__file__), "worker_pod.yaml")) as pod_file:
            worker_pod = yaml.safe_load(pod_file)
            worker_pod = self._populate_worker_pod_yaml(yaml_obj=worker_pod)

            cluster = KubeCluster.from_dict(worker_pod)
            cluster.scale_up(1)

    def execute(self) -> None:
        """
        Create a single Kubernetes job on the default namespace that runs a flow. This also
        blocks until the job is either Failed or Completed in order to preserve the dask scheduler.
        """
        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            raise EnvironmentError("Environment not currently inside a cluster")

        # job_identifier = prefect.context.get("job_identifier", "")
        # service_name = "prefect-job-{}".format(job_identifier)

        # core_client = client.CoreV1Api()
        # service = core_client.read_namespaced_service(
        #     namespace="default", name=service_name
        # )

        # self.scheduler_address = service.spec.cluster_ip
        # print("Scheduler address {}".format(self.scheduler_address))

        batch_client = client.BatchV1Api()

        with open(path.join(path.dirname(__file__), "job.yaml")) as job_file:
            job = yaml.safe_load(job_file)
            job = self._populate_job_yaml(yaml_obj=job)

            # Create Job
            batch_client.create_namespaced_job(namespace="default", body=job)

        # self._wait_for_dask_job()

    def setup(self) -> None:
        """"""
        pass
        # try:
        #     config.load_incluster_config()
        # except config.config_exception.ConfigException:
        #     raise EnvironmentError("Environment not currently inside a cluster")

        # # Make service
        # with open(
        #     path.join(path.dirname(__file__), "scheduler_service.yaml")
        # ) as svc_file:

        #     core_client = client.CoreV1Api()

        #     # Populate
        #     scheduler_service = yaml.safe_load(svc_file)
        #     scheduler_service = self._populate_scheduler_service_yaml(
        #         yaml_obj=scheduler_service
        #     )

        #     print(scheduler_service)

        #     # Create
        #     core_client.create_namespaced_service(
        #         namespace="default", body=scheduler_service
        #     )

        #     time.sleep(10)

        #     job_identifier = prefect.context.get("job_identifier", "")
        #     service_name = "prefect-job-{}".format(job_identifier)

        #     core_client = client.CoreV1Api()
        #     service = core_client.read_namespaced_service(
        #         namespace="default", name=service_name
        #     )

        #     self.scheduler_address = service.spec.cluster_ip

        #     print("Address: {}".format(self.scheduler_address))

        # Make workers
        with open(path.join(path.dirname(__file__), "worker_pod.yaml")) as pod_file:
            worker_pod = yaml.safe_load(pod_file)
            worker_pod = self._populate_worker_pod_yaml(yaml_obj=worker_pod)

            print(worker_pod)

            cluster = KubeCluster.from_dict(worker_pod, port="8786")
            cluster.scale_up(1)

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
