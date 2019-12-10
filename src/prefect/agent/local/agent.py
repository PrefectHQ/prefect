import os
import sys
import socket
from subprocess import PIPE, STDOUT, Popen
from typing import Iterable, List

from prefect import config, context
from prefect.agent import Agent
from prefect.engine.state import Failed
from prefect.environments.storage import Local
from prefect.environments.storage import Docker
from prefect.serialization.storage import StorageSchema
from prefect.utilities.graphql import GraphQLResult


class LocalAgent(Agent):
    """
    Agent which deploys flow runs locally as subprocesses.

    Args:
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - import_paths (List[str], optional): system paths which will be provided to each Flow's runtime environment;
            useful for Flows which import from locally hosted scripts or packages
        - show_flow_logs (bool, optional): a boolean specifying whether the agent should re-route Flow run logs
            to stdout; defaults to `False`
        - hostname_label (boolean, optional): a boolean specifying whether this agent should auto-label itself
            with the hostname of the machine it is running on.  Useful for flows which are stored on the local
            filesystem.
    """

    def __init__(
        self,
        name: str = None,
        labels: Iterable[str] = None,
        import_paths: List[str] = None,
        show_flow_logs: bool = False,
        hostname_label: bool = True,
    ) -> None:
        self.processes = []  # type: list
        self.import_paths = import_paths or []
        self.show_flow_logs = show_flow_logs
        super().__init__(name=name, labels=labels)
        hostname = socket.gethostname()
        if hostname_label and (hostname not in self.labels):
            assert isinstance(self.labels, list)
            self.labels.append(hostname)
        self.labels.extend(["s3-flow-storage", "gcs-flow-storage"])

    def heartbeat(self) -> None:
        for idx, process in enumerate(self.processes):
            if process.poll() is not None:
                self.processes.pop(idx)
                if process.returncode:
                    self.logger.info(
                        "Process PID {} returned non-zero exit code".format(process.pid)
                    )
                    if not self.show_flow_logs:
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

                python_path = []
                if current_env.get("PYTHONPATH"):
                    python_path.append(current_env.get("PYTHONPATH"))

                python_path.append(os.getcwd())

                if self.import_paths:
                    python_path += self.import_paths

                current_env["PYTHONPATH"] = ":".join(python_path)

                stdout = sys.stdout if self.show_flow_logs else PIPE

                p = Popen(
                    ["prefect", "execute", "cloud-flow"],
                    stdout=stdout,
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
                self.logger.error("Error while deploying flow: {}".format(repr(exc)))

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
        labels: Iterable[str] = None,
        import_paths: List[str] = None,
        show_flow_logs: bool = False,
    ) -> str:
        """
        Generate and output an installable supervisorctl configuration file for the agent.

        Args:
            - token (str, optional): A `RUNNER` token to give the agent
            - labels (List[str], optional): a list of labels, which are arbitrary string
                identifiers used by Prefect Agents when polling for work
            - import_paths (List[str], optional): system paths which will be provided to each Flow's runtime environment;
                useful for Flows which import from locally hosted scripts or packages
            - show_flow_logs (bool, optional): a boolean specifying whether the agent should re-route Flow run logs
                to stdout; defaults to `False`

        Returns:
            - str: A string representation of the generated configuration file
        """

        # Use defaults if not provided
        token = token or ""
        labels = labels or []
        import_paths = import_paths or []

        with open(
            os.path.join(os.path.dirname(__file__), "supervisord.conf"), "r"
        ) as conf_file:
            conf = conf_file.read()

        add_opts = ""
        add_opts += "-t {token} ".format(token=token) if token else ""
        add_opts += "-f " if show_flow_logs else ""
        add_opts += (
            " ".join("-l {label} ".format(label=label) for label in labels)
            if labels
            else ""
        )
        add_opts += (
            " ".join("-p {path}".format(path=path) for path in import_paths)
            if import_paths
            else ""
        )
        conf = conf.replace("{{OPTS}}", add_opts)
        return conf


if __name__ == "__main__":
    LocalAgent().start()
