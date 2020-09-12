import logging
import os
import sys
import time
from typing import TYPE_CHECKING

import pendulum

from prefect import Client
from prefect import config as prefect_config
from prefect.utilities.context import context

if TYPE_CHECKING:
    import kubernetes


class ResourceManager:
    """
    The resource manager is responsible for cleaning up old completed/failed k8s jobs
    and pods from the cluster. This is optional and does not need to me used for the agent
    to work.

    DEPRECATED: The resource manager is deprecated and it's main functionality is now present in the
    Kubernetes agent.
    """

    def __init__(self) -> None:
        self.loop_interval = prefect_config.cloud.agent.resource_manager.get(
            "loop_interval"
        )
        self.client = Client(api_token=prefect_config.cloud.agent.get("auth_token"))
        self.namespace = os.getenv("NAMESPACE", "default")

        logger = logging.getLogger("resource-manager")
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(context.config.logging.format)
        formatter.converter = time.gmtime  # type: ignore
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
        self.logger.warning("DEPRECATED: The resource manager is deprecated")
        self.logger.info("Starting {}".format(type(self).__name__))
        while True:
            try:
                self.clean_resources()
            except Exception as exc:
                self.logger.exception(exc)
            time.sleep(self.loop_interval)

    def clean_resources(self) -> None:
        """
        Find jobs that are either completed or failed to delete from the cluster
        """
        batch_client = self.k8s_client.BatchV1Api()

        more = True
        _continue = ""
        while more:
            try:
                jobs = batch_client.list_namespaced_job(
                    namespace=self.namespace,
                    label_selector="prefect.io/identifier",
                    limit=20,
                    _continue=_continue,
                )
                _continue = jobs.metadata._continue
                more = bool(_continue)
            except self.k8s_client.rest.ApiException as exc:
                if exc.status == 410:
                    self.logger.debug("List jobs continue token expired, relisting")
                    _continue = ""
                    continue
                else:
                    self.logger.exception(
                        "Error attempting to list jobs in namespace {}".format(
                            self.namespace
                        )
                    )
                    return

            for job in jobs.items:
                if job.status.succeeded or job.status.failed:

                    identifier = job.metadata.labels.get("prefect.io/identifier")
                    name = job.metadata.name

                    if job.status.failed:
                        self.logger.info(
                            "Found failed job {} in namespace {}".format(
                                name, self.namespace
                            )
                        )
                        self.report_failed_job(identifier=identifier)

                    self.delete_job(name=name)

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
                body=self.k8s_client.V1DeleteOptions(propagation_policy="Foreground"),
            )
        except self.k8s_client.rest.ApiException:
            self.logger.exception(
                "Error attempting to delete job {} in namespace {}".format(
                    name, self.namespace
                )
            )

    def report_failed_job(self, identifier: str) -> None:
        """
        Report jobs that failed for reasons outside of a flow run
        """
        core_client = self.k8s_client.CoreV1Api()
        try:
            pods = core_client.list_namespaced_pod(
                namespace=self.namespace,
                label_selector="prefect.io/identifier={}".format(identifier),
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
        # deferred import to reduce import time for prefect
        from requests.exceptions import HTTPError

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
            self.client.write_run_logs(
                [
                    dict(
                        flow_run_id=pod.metadata.labels.get("prefect.io/flow_run_id"),
                        timestamp=pendulum.now("UTC").isoformat(),
                        name="resource-manager",
                        message=logs,
                        level="ERROR",
                        info={},
                    )
                ]
            )
        except HTTPError as exc:
            self.logger.exception(exc)


if __name__ == "__main__":
    ResourceManager().start()
