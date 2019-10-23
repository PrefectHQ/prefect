import json
import os
import uuid
from os import path
from typing import Iterable

import requests

from prefect import config
from prefect.agent import Agent
from prefect.environments.storage import Docker
from prefect.serialization.storage import StorageSchema
from prefect.utilities.graphql import GraphQLResult


class NomadAgent(Agent):
    """
    Agent which deploys flow runs as Nomad jobs to a Nomad cluster based on the
    `NOMAD_HOST` environment variable.

    Args:
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
    """

    def __init__(self, name: str = None, labels: Iterable[str] = None) -> None:
        super().__init__(name=name, labels=labels)

    def deploy_flows(self, flow_runs: list) -> None:
        """
        Deploy flow runs on to a Nomad cluster as jobs

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects
        """
        for flow_run in flow_runs:

            if not isinstance(StorageSchema().load(flow_run.flow.storage), Docker):
                self.logger.error(
                    "Storage for flow run {} is not of type Docker.".format(flow_run.id)
                )
                continue

            job_spec = self.replace_job_spec_json(flow_run)
            nomad_host = os.getenv("NOMAD_HOST", "http://127.0.0.1:4646")
            requests.post(path.join(nomad_host, "v1/jobs"), json=job_spec)

    def replace_job_spec_json(self, flow_run: GraphQLResult) -> dict:
        """
        Populate metadata and variables in the job_spec.nomad file for flow runs

        Args:
            - flow_run (GraphQLResult): A flow run objects

        Returns:
            - dict: a dictionary representing the populated json object
        """
        with open(path.join(path.dirname(__file__), "job_spec.nomad"), "r") as job_file:
            job = json.load(job_file)

        job["Job"]["ID"] = flow_run.id  # type: ignore
        job["Job"]["Name"] = "prefect-job-{}".format(str(uuid.uuid4())[:8])

        job["Job"]["TaskGroups"][0]["Name"] = "prefect-job-{}".format(
            flow_run.id  # type: ignore
        )
        job["Job"]["TaskGroups"][0]["Tasks"][0]["Name"] = flow_run.id  # type: ignore

        job["Job"]["TaskGroups"][0]["Tasks"][0]["Config"]["image"] = (
            StorageSchema().load(flow_run.flow.storage).name  # type: ignore
        )

        env = job["Job"]["TaskGroups"][0]["Tasks"][0]["Env"]
        env["PREFECT__CLOUD__API"] = config.cloud.api or "https://api.prefect.io"
        env["PREFECT__CLOUD__AGENT__AUTH_TOKEN"] = config.cloud.agent.auth_token
        env["PREFECT__CONTEXT__FLOW_RUN_ID"] = flow_run.id  # type: ignore
        env["PREFECT__CONTEXT__NAMESPACE"] = os.getenv("NAMESPACE", "default")

        return job


if __name__ == "__main__":
    NomadAgent().start()
