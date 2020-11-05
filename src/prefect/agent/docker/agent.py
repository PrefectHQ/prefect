import multiprocessing
import ntpath
import posixpath
import re
import sys
from sys import platform
from typing import TYPE_CHECKING, Dict, Iterable, List, Tuple

from prefect import config, context
from prefect.agent import Agent
from prefect.run_configs import DockerRun
from prefect.serialization.run_config import RunConfigSchema
from prefect.utilities.agent import get_flow_image, get_flow_run_command
from prefect.utilities.docker_util import get_docker_ip
from prefect.utilities.graphql import GraphQLResult

if TYPE_CHECKING:
    import docker


def _stream_container_logs(base_url: str, container_id: str) -> None:
    """
    Stream container logs back to stdout

    Args:
        - base_url (str): URL for a Docker daemon server
        - container_id (str): ID of a container to stream logs
    """
    import docker

    client = docker.APIClient(base_url=base_url, version="auto")
    for log in client.logs(container=container_id, stream=True, follow=True):
        print(str(log, "utf-8").rstrip())


class DockerAgent(Agent):
    """
    Agent which deploys flow runs locally as Docker containers. Information on using the
    Docker Agent can be found at https://docs.prefect.io/orchestration/agents/docker.html

    Environment variables may be set on the agent to be provided to each flow run's container:
    ```
    prefect agent docker start --env MY_SECRET_KEY=secret --env OTHER_VAR=$OTHER_VAR
    ```

    The default Docker daemon may be overridden by providing a different `base_url`:
    ```
    prefect agent docker start --base-url "tcp://0.0.0.0:2375"
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
        - base_url (str, optional): URL for a Docker daemon server. Defaults to
            `unix:///var/run/docker.sock` however other hosts such as
            `tcp://0.0.0.0:2375` can be provided
        - no_pull (bool, optional): Flag on whether or not to pull flow images.
            Defaults to `False` if not provided here or in context.
        - show_flow_logs (bool, optional): a boolean specifying whether the agent should
            re-route Flow run logs to stdout; defaults to `False`
        - volumes (List[str], optional): a list of Docker volume mounts to be attached to any
            and all created containers.
        - network (str, optional): Add containers to an existing docker network
        - docker_interface (bool, optional): Toggle whether or not a `docker0` interface is
            present on this machine.  Defaults to `True`. **Note**: This is mostly relevant for
            some Docker-in-Docker setups that users may be running their agent with.
        - reg_allow_list (List[str], optional): Limits Docker Agent to only pull images
            from the listed registries.
    """

    def __init__(
        self,
        agent_config_id: str = None,
        name: str = None,
        labels: Iterable[str] = None,
        env_vars: dict = None,
        max_polls: int = None,
        agent_address: str = None,
        no_cloud_logs: bool = False,
        base_url: str = None,
        no_pull: bool = None,
        volumes: List[str] = None,
        show_flow_logs: bool = False,
        network: str = None,
        docker_interface: bool = True,
        reg_allow_list: List[str] = None,
    ) -> None:
        super().__init__(
            agent_config_id=agent_config_id,
            name=name,
            labels=labels,
            env_vars=env_vars,
            max_polls=max_polls,
            agent_address=agent_address,
            no_cloud_logs=no_cloud_logs,
        )
        if platform == "win32":
            default_url = "npipe:////./pipe/docker_engine"
        else:
            default_url = "unix://var/run/docker.sock"
        self.logger.debug(
            "Platform {} and default docker daemon {}".format(platform, default_url)
        )

        # Determine Daemon URL
        self.base_url = base_url or context.get("base_url", default_url)
        self.logger.debug("Base docker daemon url {}".format(self.base_url))

        # Determine pull specification
        self.no_pull = no_pull or context.get("no_pull", False)
        self.logger.debug("no_pull set to {}".format(self.no_pull))

        # Resolve volumes from specs
        (
            self.named_volumes,
            self.container_mount_paths,
            self.host_spec,
        ) = self._parse_volume_spec(volumes or [])

        # Add containers to a docker network
        self.network = network
        self.logger.debug("Docker network set to {}".format(self.network))

        self.docker_interface = docker_interface
        self.logger.debug(
            "Docker interface toggle set to {}".format(self.docker_interface)
        )

        self.failed_connections = 0
        self.docker_client = self._get_docker_client()
        self.show_flow_logs = show_flow_logs
        self.processes = []  # type: List[multiprocessing.Process]

        self.reg_allow_list = reg_allow_list
        self.logger.debug("reg_allow_list set to {}".format(self.reg_allow_list))

        # Ping Docker daemon for connection issues
        try:
            self.logger.debug("Pinging docker daemon")
            self.docker_client.ping()
        except Exception as exc:
            self.logger.exception(
                "Issue connecting to the Docker daemon. Make sure it is running."
            )
            raise exc

        self.logger.debug(f"Base URL: {self.base_url}")
        self.logger.debug(f"No pull: {self.no_pull}")
        self.logger.debug(f"Volumes: {volumes}")
        self.logger.debug(f"Network: {self.network}")
        self.logger.debug(f"Docker interface: {self.docker_interface}")

    def _get_docker_client(self) -> "docker.APIClient":
        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        return docker.APIClient(base_url=self.base_url, version="auto")

    def heartbeat(self) -> None:
        try:
            if not self.docker_client.ping():
                raise RuntimeError("Unexpected Docker ping result")
            if self.failed_connections > 0:
                self.logger.info("Reconnected to Docker daemon")
            self.failed_connections = 0
        except Exception as exc:
            self.logger.warning("Failed heartbeat: {}".format(repr(exc)))
            self.failed_connections += 1

        if self.failed_connections >= 6:
            self.logger.error(
                "Cannot reconnect to Docker daemon. Agent is shutting down."
            )
            raise SystemExit()

    def on_shutdown(self) -> None:
        """
        Cleanup any child processes created for streaming logs. This is to prevent
        logs from displaying on the terminal after the agent exits.
        """
        for proc in self.processes:
            if proc.is_alive():
                proc.terminate()

    def _is_named_volume_unix(self, canditate_path: str) -> bool:
        if not canditate_path:
            return False

        return not canditate_path.startswith((".", "/", "~"))

    def _is_named_volume_win32(self, canditate_path: str) -> bool:
        result = self._is_named_volume_unix(canditate_path)

        return (
            result
            and not re.match(r"^[A-Za-z]\:\\.*", canditate_path)
            and not canditate_path.startswith("\\")
        )

    def _parse_volume_spec(
        self, volume_specs: List[str]
    ) -> Tuple[Iterable[str], Iterable[str], Dict[str, Dict[str, str]]]:
        if platform == "win32":
            return self._parse_volume_spec_win32(volume_specs)
        return self._parse_volume_spec_unix(volume_specs)

    def _parse_volume_spec_win32(
        self, volume_specs: List[str]
    ) -> Tuple[Iterable[str], Iterable[str], Dict[str, Dict[str, str]]]:
        named_volumes = []  # type: List[str]
        container_mount_paths = []  # type: List[str]
        host_spec = {}  # type: Dict[str, Dict[str, str]]

        for volume_spec in volume_specs:
            fields = volume_spec.split(":")

            if fields[-1] in ("ro", "rw"):
                mode = fields.pop()
            else:
                mode = "rw"

            if len(fields) == 3 and len(fields[0]) == 1:
                # C:\path1:/path2   <-- extenal and internal path
                external = ntpath.normpath(":".join(fields[0:2]))
                internal = posixpath.normpath(fields[2])
            elif len(fields) == 2:
                combined_path = ":".join(fields)
                (drive, path) = ntpath.splitdrive(combined_path)
                if drive:
                    # C:\path1          <-- assumed container path of /path1
                    external = ntpath.normpath(combined_path)

                    # C:\path1  --> /c/path1
                    path = str("/" + drive.lower().rstrip(":") + path).replace(
                        "\\", "/"
                    )
                    internal = posixpath.normpath(path)
                else:
                    # /path1:\path2     <-- extenal and internal path (relative to current drive)
                    # C:/path2          <-- valid named volume
                    external = ntpath.normpath(fields[0])
                    internal = posixpath.normpath(fields[1])
            elif len(fields) == 1:
                # \path1          <-- assumed container path of /path1 (relative to current drive)
                external = ntpath.normpath(fields[0])
                internal = external
            else:
                raise ValueError(
                    "Unable to parse volume specification '{}'".format(volume_spec)
                )

            container_mount_paths.append(internal)

            if external and self._is_named_volume_win32(external):
                named_volumes.append(external)
                if mode != "rw":
                    raise ValueError(
                        "Named volumes can only have 'rw' mode, provided '{}'".format(
                            mode
                        )
                    )
            else:
                if not external:
                    # no internal container path given, assume the host path is the same as the
                    # internal path
                    external = internal
                host_spec[external] = {
                    "bind": internal,
                    "mode": mode,
                }

        return named_volumes, container_mount_paths, host_spec

    def _parse_volume_spec_unix(
        self, volume_specs: List[str]
    ) -> Tuple[Iterable[str], Iterable[str], Dict[str, Dict[str, str]]]:
        named_volumes = []  # type: List[str]
        container_mount_paths = []  # type: List[str]
        host_spec = {}  # type: Dict[str, Dict[str, str]]

        for volume_spec in volume_specs:
            fields = volume_spec.split(":")

            if len(fields) > 3:
                raise ValueError(
                    f"Docker volume format is invalid: {volume_spec} "
                    f"(should be 'external:internal[:mode]')"
                )

            if len(fields) == 1:
                external = None
                internal = posixpath.normpath(fields[0].strip())
            else:
                external = posixpath.normpath(fields[0].strip())
                internal = posixpath.normpath(fields[1].strip())

            mode = "rw"
            if len(fields) == 3:
                mode = fields[2]

            container_mount_paths.append(internal)

            if external and self._is_named_volume_unix(external):
                named_volumes.append(external)
                if mode != "rw":
                    raise ValueError(
                        "Named volumes can only have 'rw' mode, provided '{}'".format(
                            mode
                        )
                    )
            else:
                if not external:
                    # no internal container path given, assume the host path is the same as the
                    # internal path
                    external = internal
                host_spec[external] = {
                    "bind": internal,
                    "mode": mode,
                }

        return named_volumes, container_mount_paths, host_spec

    def deploy_flow(self, flow_run: GraphQLResult) -> str:
        """
        Deploy flow runs on your local machine as Docker containers

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object

        Returns:
            - str: Information about the deployment
        """
        self.logger.info("Deploying flow run {}".format(flow_run.id))  # type: ignore

        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        if getattr(flow_run.flow, "run_config", None) is not None:
            run_config = RunConfigSchema().load(flow_run.flow.run_config)
            if not isinstance(run_config, DockerRun):
                self.logger.error(
                    "Flow run %s has a `run_config` of type `%s`, only `DockerRun` is supported",
                    flow_run.id,
                    type(run_config).__name__,
                )
                raise TypeError(
                    "Unsupported RunConfig type: %s" % type(run_config).__name__
                )
        else:
            run_config = None

        image = get_flow_image(flow_run=flow_run)
        env_vars = self.populate_env_vars(flow_run, run_config=run_config)

        if not self.no_pull and len(image.split("/")) > 1:
            self.logger.info("Pulling image {}...".format(image))
            registry = image.split("/")[0]
            if self.reg_allow_list and registry not in self.reg_allow_list:
                self.logger.error(
                    "Trying to pull image from a Docker registry '{}' which"
                    " is not in the reg_allow_list".format(registry)
                )
                raise ValueError(
                    "Trying to pull image from a Docker registry '{}' which"
                    " is not in the reg_allow_list".format(registry)
                )
            else:
                pull_output = self.docker_client.pull(image, stream=True, decode=True)
                for line in pull_output:
                    self.logger.debug(line)
                self.logger.info("Successfully pulled image {}...".format(image))

        # Create any named volumes (if they do not already exist)
        for named_volume_name in self.named_volumes:
            try:
                self.docker_client.inspect_volume(name=named_volume_name)
            except docker.errors.APIError:
                self.logger.debug("Creating named volume {}".format(named_volume_name))
                self.docker_client.create_volume(
                    name=named_volume_name,
                    driver="local",
                    labels={"prefect_created": "true"},
                )

        # Create a container
        self.logger.debug("Creating Docker container {}".format(image))

        host_config = {"auto_remove": True}  # type: dict
        container_mount_paths = self.container_mount_paths
        if container_mount_paths:
            host_config.update(binds=self.host_spec)

        if sys.platform.startswith("linux") and self.docker_interface:
            docker_internal_ip = get_docker_ip()
            host_config.update(extra_hosts={"host.docker.internal": docker_internal_ip})

        networking_config = None
        if self.network:
            networking_config = self.docker_client.create_networking_config(
                {self.network: self.docker_client.create_endpoint_config()}
            )

        container = self.docker_client.create_container(
            image,
            command=get_flow_run_command(flow_run),
            environment=env_vars,
            volumes=container_mount_paths,
            host_config=self.docker_client.create_host_config(**host_config),
            networking_config=networking_config,
        )

        # Start the container
        self.logger.debug(
            "Starting Docker container with ID {}".format(container.get("Id"))
        )
        if self.network:
            self.logger.debug(
                "Adding container to docker network: {}".format(self.network)
            )

        self.docker_client.start(container=container.get("Id"))

        if self.show_flow_logs:
            self.stream_flow_logs(container.get("Id"))

        self.logger.debug("Docker container {} started".format(container.get("Id")))

        return "Container ID: {}".format(container.get("Id"))

    def stream_flow_logs(self, container_id: str) -> None:
        """Stream container logs back to stdout.

        Args:
            - container_id (str): ID of container
        """
        # All arguments to multiprocessing.Process need to be pickleable
        proc = multiprocessing.Process(
            target=_stream_container_logs,
            kwargs={
                "base_url": self.base_url,
                "container_id": container_id,
            },
        )
        proc.start()
        self.processes.append(proc)

    def populate_env_vars(
        self, flow_run: GraphQLResult, run_config: DockerRun = None
    ) -> dict:
        """
        Populate metadata and variables in the environment variables for a flow run

        Args:
            - flow_run (GraphQLResult): A flow run object
            - run_config (DockerRun, optional): The `run_config` for the flow, if any.

        Returns:
            - dict: a dictionary representing the populated environment variables
        """
        if "localhost" in config.cloud.api:
            api = "http://host.docker.internal:{}".format(config.server.port)
        else:
            api = config.cloud.api

        env = {}
        # Populate environment variables, later sources overriding

        # 1. Logging config (optional)
        # We only set this on non-DockerRun runs for backwards compatibility.
        # In the future we don't want the agent to set logging config on a flow
        # run unless explicitly asked.  We do this early on so later config
        # sources can override
        if run_config is None:
            env.update({"PREFECT__LOGGING__LEVEL": config.logging.level})

        # 2. Values set on the agent via `--env`
        env.update(self.env_vars)

        # 3. Values set on a DockerRun RunConfig (if present
        if run_config is not None and run_config.env is not None:
            env.update(run_config.env)

        # 4. Non-overrideable required env vars
        env.update(
            {
                "PREFECT__CLOUD__API": api,
                "PREFECT__CLOUD__AUTH_TOKEN": config.cloud.agent.auth_token,
                "PREFECT__CLOUD__AGENT__LABELS": str(self.labels),
                "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run.id,  # type: ignore
                "PREFECT__CONTEXT__FLOW_ID": flow_run.flow.id,  # type: ignore
                "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
                "PREFECT__LOGGING__LOG_TO_CLOUD": str(self.log_to_cloud).lower(),
                "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
                "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
            }
        )
        return env


if __name__ == "__main__":
    DockerAgent().start()
