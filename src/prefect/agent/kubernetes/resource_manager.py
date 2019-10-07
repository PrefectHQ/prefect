import logging
import os
import time
from typing import TYPE_CHECKING

import pendulum
from requests.exceptions import HTTPError

from prefect import Client
from prefect import config as prefect_config

if TYPE_CHECKING:
    import kubernetes


class ResourceManager:
    """
    The resource manager is responsible for cleaning up old completed/failed k8s jobs
    and pods from the cluster. This is optional and does not need to me used for the agent
    to work.
    """

    def __init__(self) -> None:
        self.loop_interval = prefect_config.cloud.agent.resource_manager.get(
            "loop_interval"
        )
        self.client = Client(api_token=prefect_config.cloud.agent.get("auth_token"))
        self.namespace = os.getenv("NAMESPACE", "default")

        logger = logging.getLogger("resource-manager")
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        self.logger = logger

        from kubernetes import client, config

        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException as exc:
            self.logger.warning(
                "{} Using out of cluster configuration option.".format(exc)
            )
            config.load_kube_config()

        self.k8s_client = client

    def start(self) -> None:
        """
        Main loop which waits on a `LOOP_INTERVAL` and looks for finished jobs to clean
        """
        self.logger.info("Starting {}".format(type(self).__name__))
        while True:
            try:
                self.clean_resources()
            except Exception as exc:
                self.logger.exception(exc)
            time.sleep(self.loop_interval)

    # IDENTIFICATION

    def clean_resources(self) -> None:
        """
        Find jobs that are either completed or failed to delete from the cluster
        """
        batch_client = self.k8s_client.BatchV1Api()

        try:
            jobs = batch_client.list_namespaced_job(namespace=self.namespace)
        except self.k8s_client.rest.ApiException:
            self.logger.exception(
                "Error attempting to list jobs in namespace {}".format(self.namespace)
            )
            return

        for job in jobs.items:
            if job.status.succeeded or job.status.failed:

                identifier = job.metadata.labels.get("identifier")
                name = job.metadata.name

                if job.status.failed:
                    self.logger.info(
                        "Found failed job {} in namespace {}".format(
                            name, self.namespace
                        )
                    )
                    self.report_failed_job(identifier=identifier)

                self.delete_job(name=name)
                self.delete_pods(job_name=name, identifier=identifier)

        if not jobs.items:
            self.clean_extra_pods()

    def clean_extra_pods(self) -> None:
        """
        Any runaway pods which failed due to unexpected reasons will be cleaned up here.
        ImagePullBackoffs, Evictions, etc...
        """
        core_client = self.k8s_client.CoreV1Api()

        try:
            pods = core_client.list_namespaced_pod(namespace=self.namespace)
        except self.k8s_client.rest.ApiException:
            self.logger.exception(
                "Error attempting to list pods in namespace {}".format(self.namespace)
            )
            return

        for pod in pods.items:
            phase = pod.status.phase
            if phase != "Running":

                name = pod.metadata.name

                if phase == "Failed":
                    self.report_failed_pod(pod=pod)

                if phase == "Unknown":
                    self.report_unknown_pod(pod=pod)

                if phase == "Pending":
                    if pod.status.container_statuses:
                        self.report_pod_image_pull_error(pod=pod)

                self.delete_extra_pod(name=name)

    # DELETION

    def delete_job(self, name: str) -> None:
        """
        Delete a job based on the name
        """
        batch_client = self.k8s_client.BatchV1Api()
        self.logger.info("Deleting job {} in namespace {}".format(name, self.namespace))

        try:
            batch_client.delete_namespaced_job(
                name=name,
                namespace=self.namespace,
                body=self.k8s_client.V1DeleteOptions(),
            )
        except self.k8s_client.rest.ApiException:
            self.logger.exception(
                "Error attempting to delete job {} in namespace {}".format(
                    name, self.namespace
                )
            )

    def delete_pods(self, job_name: str, identifier: str) -> None:
        """
        Delete a pod based on the job name and identifier
        """
        core_client = self.k8s_client.CoreV1Api()
        try:
            pods = core_client.list_namespaced_pod(
                namespace=self.namespace,
                label_selector="identifier={}".format(identifier),
            )
        except self.k8s_client.rest.ApiException:
            self.logger.exception(
                "Error attempting to list pods in namespace {}".format(self.namespace)
            )
            return

        if pods:
            self.logger.info(
                "Deleting {} pods for job {} in namespace {}".format(
                    len(pods.items), job_name, self.namespace
                )
            )
        for pod in pods.items:
            name = pod.metadata.name

            try:
                core_client.delete_namespaced_pod(
                    name=name,
                    namespace=self.namespace,
                    body=self.k8s_client.V1DeleteOptions(),
                )
            except self.k8s_client.rest.ApiException:
                self.logger.exception(
                    "Error attempting to delete pod {} in namespace {}".format(
                        name, self.namespace
                    )
                )

    def delete_extra_pod(self, name: str) -> None:
        """
        Delete a pod based on the name
        """
        core_client = self.k8s_client.CoreV1Api()
        self.logger.info(
            "Deleting extra pod {} in namespace {}".format(name, self.namespace)
        )

        try:
            core_client.delete_namespaced_pod(
                name=name,
                namespace=self.namespace,
                body=self.k8s_client.V1DeleteOptions(),
            )
        except self.k8s_client.rest.ApiException:
            self.logger.exception(
                "Error attempting to delete pod {} in namespace {}".format(
                    name, self.namespace
                )
            )

    # REPORTING

    def report_failed_job(self, identifier: str) -> None:
        """
        Report jobs that failed for reasons outside of a flow run
        """
        core_client = self.k8s_client.CoreV1Api()
        try:
            pods = core_client.list_namespaced_pod(
                namespace=self.namespace,
                label_selector="identifier={}".format(identifier),
            )
        except self.k8s_client.rest.ApiException:
            self.logger.exception(
                "Error attempting to list pods in namespace {}".format(self.namespace)
            )
            return

        for pod in pods.items:
            phase = pod.status.phase
            if phase == "Failed":
                self.report_failed_pod(pod)

    def report_failed_pod(self, pod: "kubernetes.client.V1Pod") -> None:
        """
        Report pods that failed for reasons outside of a flow run. Write cloud log
        """
        core_client = self.k8s_client.CoreV1Api()
        name = pod.metadata.name

        if pod.status.reason == "Evicted":
            logs = "Pod was evicted due to cluster resource constraints / auto scaling."
        else:
            try:
                logs = core_client.read_namespaced_pod_log(
                    namespace=self.namespace, name=name
                )
            except self.k8s_client.rest.ApiException:
                self.logger.exception(
                    "Error attempting to read pod logs for {} in namespace {}".format(
                        name, self.namespace
                    )
                )
                return

        self.logger.info(
            "Reporting failed pod {} in namespace {}".format(name, self.namespace)
        )

        try:
            self.client.write_run_log(
                flow_run_id=pod.metadata.labels.get("flow_run_id"),
                timestamp=pendulum.now(),
                name="resource-manager",
                message=logs,
                level="ERROR",
                info={},
            )
        except HTTPError as exc:
            self.logger.exception(exc)

    def report_unknown_pod(self, pod: "kubernetes.client.V1Pod") -> None:
        """
        Write cloud log of pods that entered unknonw states
        """
        name = pod.metadata.name
        self.logger.info(
            "Reporting unknown pod {} in namespace {}".format(name, self.namespace)
        )

        try:
            self.client.write_run_log(
                flow_run_id=pod.metadata.labels.get("flow_run_id"),
                timestamp=pendulum.now(),
                name="resource-manager",
                message="Flow run pod {} entered an unknown state in namespace {}".format(
                    name, self.namespace
                ),
                level="ERROR",
                info={},
            )
        except HTTPError as exc:
            self.logger.exception(exc)

    def report_pod_image_pull_error(self, pod: "kubernetes.client.V1Pod") -> None:
        """
        Write cloud log of pods that ahd image pull errors
        """
        for status in pod.status.container_statuses:
            waiting = status.state.waiting

            if waiting and waiting.reason == "ImagePullBackoff":
                self.logger.info(
                    "Reporting image pull error for pod {} in namespace {}".format(
                        pod.metadata.name, self.namespace
                    )
                )

                try:
                    self.client.write_run_log(
                        flow_run_id=pod.metadata.labels.get("flow_run_id"),
                        timestamp=pendulum.now(),
                        name="resource-manager",
                        message="Flow run image pull error for pod {} in namespace {}".format(
                            pod.metadata.name, self.namespace
                        ),
                        level="ERROR",
                        info={},
                    )
                except HTTPError as exc:
                    self.logger.exception(exc)


if __name__ == "__main__":
    ResourceManager().start()
