import os
import socket
from subprocess import PIPE, STDOUT, Popen
from typing import Iterable

from prefect import config, context
from prefect.agent import Agent
from prefect.engine.state import Failed
from prefect.environments.storage import Local
from prefect.serialization.storage import StorageSchema
from prefect.utilities.graphql import GraphQLResult


class LocalAgent(Agent):
    """
    Agent which deploys flow runs locally as Docker containers. Information on using the
    Docker Agent can be found at https://docs.prefect.io/cloud/agent/local.html

    Args:
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
    """

    def __init__(
        self,
        name: str = None,
        labels: Iterable[str] = None,
        import_paths: Iterable[str] = None,
    ) -> None:
        self.processes = []
        self.import_paths = import_paths or []
        super().__init__(name=name, labels=labels)
        hostname = socket.gethostname()
        if hostname not in self.labels:
            self.labels.append(hostname)

    def heartbeat(self) -> None:
        for idx, process in enumerate(self.processes):
            if process.poll() is not None:
                self.processes.pop(idx)
                if process.returncode:
                    self.logger.info(
                        "Process PID {} returned non-zero exit code".format(process.pid)
                    )
                    for raw_line in iter(process.stdout.readline, b""):
                        self.logger.info(raw_line.decode("utf-8").rstrip())
        super().heartbeat()

    def deploy_flows(self, flow_runs: list) -> None:
        """
        Deploy flow runs on your local machine as Docker containers

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects
        """
        for flow_run in flow_runs:
            self.logger.info(
                "Deploying flow run {}".format(flow_run.id)  # type: ignore
            )

            try:
                storage = StorageSchema().load(flow_run.flow.storage)
                if not isinstance(StorageSchema().load(flow_run.flow.storage), Local):
                    self.logger.error(
                        "Storage for flow run {} is not of type Local.".format(
                            flow_run.id
                        )
                    )
                    continue

                env_vars = self.populate_env_vars(flow_run=flow_run)
                current_env = os.environ.copy()
                current_env.update(env_vars)

                current_env.setdefault("PYTHONPATH", current_env["PWD"])
                if self.import_paths:
                    current_env["PYTHONPATH"] += os.pathsep.join(self.import_paths)
                p = Popen(
                    ["prefect", "execute", "cloud-flow"],
                    stdout=PIPE,
                    stderr=STDOUT,
                    env=current_env,
                )
                self.processes.append(p)
                self.logger.debug(
                    "Submitted flow run {} to process PID {}".format(flow_run.id, p.pid)
                )
            except Exception as exc:
                self.client.set_flow_run_state(
                    flow_run_id=flow_run.id,
                    version=flow_run.version + 1,
                    state=Failed(message=str(exc)),
                )

    def populate_env_vars(self, flow_run: GraphQLResult) -> dict:
        """
        Populate metadata and variables in the environment variables for a flow run

        Args:
            - flow_run (GraphQLResult): A flow run object

        Returns:
            - dict: a dictionary representing the populated environment variables
        """
        return {
            "PREFECT__CLOUD__API": config.cloud.api,
            "PREFECT__CLOUD__AUTH_TOKEN": self.client._api_token,
            "PREFECT__CLOUD__AGENT__LABELS": str(self.labels),
            "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run.id,  # type: ignore
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__LOGGING__LOG_TO_CLOUD": "true",
            "PREFECT__LOGGING__LEVEL": "DEBUG",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }

    @staticmethod
    def generate_supervisor_conf(
        token: str = None,
        api: str = None,
        labels: Iterable[str] = None,
        import_paths: Iterable[str] = None,
    ) -> str:
        """
        Generate and output an installable supervisorctl configuration file for the agent.

        Args:
            - token (str, optional): A `RUNNER` token to give the agent
            - api (str, optional): A URL pointing to the Prefect API. Defaults to
                `https://api.prefect.io`
            - labels (List[str], optional): a list of labels, which are arbitrary string
                identifiers used by Prefect Agents when polling for work

        Returns:
            - str: A string representation of the generated configuration file
        """

        # Use defaults if not provided
        token = token or ""
        api = api or "https://api.prefect.io"
        labels = labels or []
        import_paths = import_paths or []

        with open(
            os.path.join(os.path.dirname(__file__), "supervisord.conf"), "r"
        ) as conf_file:
            conf = conf_file.read()

        conf = conf.replace("{{TOKEN_CMD}}", "-t {token}".format(token=token) if token else "")
        conf = conf.replace("{{API_CMD}}", "-a {api}".format(api=api))
        label_cmd = " ".join("-l {label}".format(label=label) for label in labels) if labels else ""
#        conf.replace("{{PATH_CMD}}",
        conf = conf.replace("{{LABEL_CMD}}", label_cmd)
        return conf


if __name__ == "__main__":
    LocalAgent().start()
