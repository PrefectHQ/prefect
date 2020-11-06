import os
import socket
import sys
from subprocess import STDOUT, Popen, DEVNULL
from typing import Iterable, List

from prefect import config
from prefect.agent import Agent
from prefect.environments.storage import Docker
from prefect.run_configs import LocalRun
from prefect.serialization.storage import StorageSchema
from prefect.serialization.run_config import RunConfigSchema
from prefect.utilities.agent import get_flow_run_command
from prefect.utilities.graphql import GraphQLResult


class LocalAgent(Agent):
    """
    Agent which deploys flow runs locally as subprocesses. There are a range of kwarg
    options to control information which may be provided to these subprocesses.

    Optional import paths may be specified to append dependency modules to the PATH:
    ```
    prefect agent local start --import-path "/usr/local/my_module" --import-path "~/other_module"

    # Now the local scripts/packages my_module and other_module will be importable in
    # the flow's subprocess
    ```

    Environment variables may be set on the agent to be provided to each flow run's subprocess:
    ```
    prefect agent local start --env MY_SECRET_KEY=secret --env OTHER_VAR=$OTHER_VAR
    ```

    Args:
        - agent_config_id (str, optional): An optional agent configuration ID that can be used to set
            configuration based on an agent from a backend API. If set all configuration values will be
            pulled from backend agent configuration.
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string
            identifiers used by Prefect Agents when polling for work
        - env_vars (dict, optional): a dictionary of environment variables and values that will
            be set on each flow run that this agent submits for execution
        - max_polls (int, optional): maximum number of times the agent will poll Prefect Cloud
            for flow runs; defaults to infinite
        - agent_address (str, optional):  Address to serve internal api at. Currently this is
            just health checks for use by an orchestration layer. Leave blank for no api server
            (default).
        - no_cloud_logs (bool, optional): Disable logging to a Prefect backend for this agent
            and all deployed flow runs
        - import_paths (List[str], optional): system paths which will be provided to each
            Flow's runtime environment; useful for Flows which import from locally hosted
            scripts or packages
        - show_flow_logs (bool, optional): a boolean specifying whether the agent should
            re-route Flow run logs to stdout; defaults to `False`
        - hostname_label (boolean, optional): a boolean specifying whether this agent should
            auto-label itself with the hostname of the machine it is running on.  Useful for
            flows which are stored on the local filesystem.
        - storage_labels (boolean, optional): a boolean specifying whether this agent should
            auto-label itself with all of the storage options labels.
    """

    def __init__(
        self,
        agent_config_id: str = None,
        name: str = None,
        labels: Iterable[str] = None,
        env_vars: dict = None,
        import_paths: List[str] = None,
        show_flow_logs: bool = False,
        hostname_label: bool = True,
        max_polls: int = None,
        agent_address: str = None,
        no_cloud_logs: bool = False,
        storage_labels: bool = True,
    ) -> None:
        self.processes = set()
        self.import_paths = import_paths or []
        self.show_flow_logs = show_flow_logs
        super().__init__(
            agent_config_id=agent_config_id,
            name=name,
            labels=labels,
            env_vars=env_vars,
            max_polls=max_polls,
            agent_address=agent_address,
            no_cloud_logs=no_cloud_logs,
        )
        hostname = socket.gethostname()

        # Resolve common Docker hostname by using IP
        if hostname == "docker-desktop":
            hostname = socket.gethostbyname(hostname)

        if hostname_label and (hostname not in self.labels):
            assert isinstance(self.labels, list)
            self.labels.append(hostname)

        if storage_labels:
            all_storage_labels = [
                "azure-flow-storage",
                "gcs-flow-storage",
                "s3-flow-storage",
                "github-flow-storage",
                "webhook-flow-storage",
                "gitlab-flow-storage",
            ]
            for label in all_storage_labels:
                if label not in self.labels:
                    self.labels.append(label)

        self.logger.debug(f"Import paths: {self.import_paths}")
        self.logger.debug(f"Show flow logs: {self.show_flow_logs}")

    def heartbeat(self) -> None:
        for process in list(self.processes):
            if process.poll() is not None:
                self.processes.remove(process)
                if process.returncode:
                    self.logger.info(
                        "Process PID {} returned non-zero exit code".format(process.pid)
                    )
        super().heartbeat()

    def deploy_flow(self, flow_run: GraphQLResult) -> str:
        """
        Deploy flow runs on your local machine as Docker containers

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object

        Returns:
            - str: Information about the deployment

        Raises:
            - ValueError: if deployment attempted on unsupported Storage type
        """
        self.logger.info("Deploying flow run {}".format(flow_run.id))  # type: ignore

        storage = StorageSchema().load(flow_run.flow.storage)
        if isinstance(storage, Docker):
            self.logger.error(
                "Flow run %s has an unsupported storage type: `%s`",
                flow_run.id,
                type(storage).__name__,
            )
            raise TypeError("Unsupported Storage type: %s" % type(storage).__name__)

        # If the flow is using a run_config, load it
        if getattr(flow_run.flow, "run_config", None) is not None:
            run_config = RunConfigSchema().load(flow_run.flow.run_config)
            if not isinstance(run_config, LocalRun):
                self.logger.error(
                    "Flow run %s has a `run_config` of type `%s`, only `LocalRun` is supported",
                    flow_run.id,
                    type(run_config).__name__,
                )
                raise TypeError(
                    "Unsupported RunConfig type: %s" % type(run_config).__name__
                )
        else:
            run_config = None

        env = self.populate_env_vars(flow_run, run_config=run_config)

        working_dir = None if run_config is None else run_config.working_dir
        if working_dir and not os.path.exists(working_dir):
            msg = f"Flow run {flow_run.id} has a nonexistent `working_dir` configured: {working_dir}"
            self.logger.error(msg)
            raise ValueError(msg)

        stdout = sys.stdout if self.show_flow_logs else DEVNULL

        # note: we will allow these processes to be orphaned if the agent were to exit
        # before the flow runs have completed. The lifecycle of the agent should not
        # dictate the lifecycle of the flow run. However, if the user has elected to
        # show flow logs, these log entries will continue to stream to the users terminal
        # until these child processes exit, even if the agent has already exited.
        p = Popen(
            get_flow_run_command(flow_run).split(" "),
            stdout=stdout,
            stderr=STDOUT,
            env=env,
            cwd=working_dir,
        )

        self.processes.add(p)
        self.logger.debug(
            "Submitted flow run {} to process PID {}".format(flow_run.id, p.pid)
        )

        return "PID: {}".format(p.pid)

    def populate_env_vars(
        self, flow_run: GraphQLResult, run_config: LocalRun = None
    ) -> dict:
        """
        Populate metadata and variables in the environment variables for a flow run

        Args:
            - flow_run (GraphQLResult): A flow run object
            - run_config (LocalRun, optional): The `run_config` for the flow, if any.

        Returns:
            - dict: a dictionary representing the populated environment variables
        """
        # Environment variables come from (later options override):

        # 1. Local environment
        env = os.environ.copy()

        # 2. Logging config
        env.update({"PREFECT__LOGGING__LEVEL": config.logging.level})

        # 3. PYTHONPATH
        # XXX: I'm 99% sure this isn't needed, a new Python process should
        # always add the CWD as the first entry in sys.path
        python_path = [
            run_config.working_dir
            if run_config is not None and run_config.working_dir
            else os.getcwd()
        ]
        if os.environ.get("PYTHONPATH"):
            python_path.append(os.environ["PYTHONPATH"])
        if self.import_paths:
            python_path.extend(self.import_paths)
        env["PYTHONPATH"] = os.pathsep.join(python_path)

        # 4. Values set on the agent via `--env`
        env.update(self.env_vars)

        # 5. Values set on a LocalRun RunConfig (if present
        if run_config is not None and run_config.env is not None:
            env.update(run_config.env)

        # 6. Non-overrideable required env vars
        env.update(
            {
                "PREFECT__CLOUD__API": config.cloud.api,
                "PREFECT__CLOUD__AUTH_TOKEN": self.client._api_token,
                "PREFECT__CLOUD__AGENT__LABELS": str(self.labels),
                "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run.id,  # type: ignore
                "PREFECT__CONTEXT__FLOW_ID": flow_run.flow.id,  # type: ignore
                "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
                "PREFECT__LOGGING__LOG_TO_CLOUD": str(self.log_to_cloud).lower(),
                "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
                "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
            }
        )

        # Filter out None values
        return {k: v for k, v in env.items() if v is not None}

    @staticmethod
    def generate_supervisor_conf(
        token: str = None,
        labels: Iterable[str] = None,
        env_vars: dict = None,
        import_paths: List[str] = None,
        show_flow_logs: bool = False,
    ) -> str:
        """
        Generate and output an installable supervisorctl configuration file for the agent.

        Args:
            - token (str, optional): A `RUNNER` token to give the agent
            - labels (List[str], optional): a list of labels, which are arbitrary string
                identifiers used by Prefect Agents when polling for work
            - env_vars (dict, optional): a dictionary of environment variables and values that
                will be set on each flow run that this agent submits for execution
            - import_paths (List[str], optional): system paths which will be provided to each
                Flow's runtime environment; useful for Flows which import from locally hosted
                scripts or packages
            - show_flow_logs (bool, optional): a boolean specifying whether the agent should
                re-route Flow run logs to stdout; defaults to `False`

        Returns:
            - str: A string representation of the generated configuration file
        """

        # Use defaults if not provided
        token = token or ""
        labels = labels or []
        env_vars = env_vars or {}
        import_paths = import_paths or []

        with open(
            os.path.join(os.path.dirname(__file__), "supervisord.conf"), "r"
        ) as conf_file:
            conf = conf_file.read()

        add_opts = ""
        add_opts += "-t {token} ".format(token=token) if token else ""
        add_opts += "-f " if show_flow_logs else ""
        add_opts += " ".join("-l {label} ".format(label=label) for label in labels)
        add_opts += " ".join(
            "-e {k}={v} ".format(k=k, v=v) for k, v in env_vars.items()
        )
        add_opts += " ".join("-p {path}".format(path=path) for path in import_paths)
        conf = conf.replace("{{OPTS}}", add_opts)
        return conf


if __name__ == "__main__":
    LocalAgent().start()
