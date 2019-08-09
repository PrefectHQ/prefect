import logging
import os
from os import path
import uuid

from kubernetes import client, config
import yaml

from prefect.agent import Agent
from prefect.environments.storage import Docker
from prefect.serialization.storage import StorageSchema
from prefect.utilities.graphql import GraphQLResult


class KubernetesAgent(Agent):
    """
    Agent which deploys flow runs as Kubernetes jobs. Currently this is required to either
    run on a k8s cluster or on a local machine where the kube_config is pointing at the
    desired cluster.
    """

    def __init__(self) -> None:
        super().__init__()

        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException as exc:
            self.logger.warning(f"{exc} Using out of cluster configuration option.")
            config.load_kube_config()

    def deploy_flows(self, flow_runs: list) -> None:
        """
        Deploy flow runs on to a k8s cluster as jobs

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects
        """
        batch_client = client.BatchV1Api()

        for flow_run in flow_runs:

            # Require Docker storage
            if not isinstance(StorageSchema().load(flow_run.flow.storage), Docker):
                self.logger.error(
                    f"Storage for flow run {flow_run.id} is not of type Docker."
                )
                continue

            job_spec = self.replace_job_spec_yaml(flow_run)

            batch_client.create_namespaced_job(
                namespace=os.getenv("NAMESPACE", "default"), body=job_spec
            )

    def replace_job_spec_yaml(self, flow_run: GraphQLResult) -> dict:
        """
        Populate metadata and variables in the job_spec.yaml file for flow runs

        Args:
            - flow_run (GraphQLResult): A flow run objects

        Returns:
            - dict: a dictionary representing the populated yaml object
        """
        with open(path.join(path.dirname(__file__), "job_spec.yaml"), "r") as job_file:
            job = yaml.safe_load(job_file)

        identifier = str(uuid.uuid4())[:8]
        job_name = "prefect-job-{}".format(identifier)

        # Populate job metadata for identification
        job["metadata"]["name"] = job_name
        job["metadata"]["labels"]["app"] = job_name
        job["metadata"]["labels"]["identifier"] = identifier
        job["metadata"]["labels"]["flow_run_id"] = flow_run.id  # type: ignore
        job["metadata"]["labels"]["flow_id"] = flow_run.flow.id  # type: ignore
        job["spec"]["template"]["metadata"]["labels"]["app"] = job_name
        job["spec"]["template"]["metadata"]["labels"]["identifier"] = identifier

        # Use flow storage image for job
        job["spec"]["template"]["spec"]["containers"][0]["image"] = (
            StorageSchema().load(flow_run.flow.storage).name  # type: ignore
        )

        # Populate environment variables for flow run execution
        env = job["spec"]["template"]["spec"]["containers"][0]["env"]

        env[0]["value"] = os.getenv("PREFECT__CLOUD__API", "https://api.prefect.io")
        env[1]["value"] = os.environ["PREFECT__CLOUD__AGENT__AUTH_TOKEN"]
        env[2]["value"] = flow_run.id  # type: ignore
        env[3]["value"] = os.getenv("NAMESPACE", "default")

        return job


if __name__ == "__main__":
    KubernetesAgent().start()
