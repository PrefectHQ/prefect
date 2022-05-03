import multiprocessing
import ntpath
import posixpath
import re
import warnings
from sys import platform
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Tuple

from packaging.version import parse as parse_version
from slugify import slugify

from prefect import config, context
from prefect.agent import Agent
from prefect.run_configs import DockerRun
from prefect.utilities.agent import get_flow_image, get_flow_run_command
from prefect.utilities.graphql import GraphQLResult

if TYPE_CHECKING:
    import docker


def _stream_container_logs(base_url: str, timeout: int, container_id: str) -> None:
    """
    Stream container logs back to stdout

    Args:
        - base_url (str): URL for a Docker daemon server
        - timeout (int): timeout for docker api requests
        - container_id (str): ID of a container to stream logs
    """
    import docker

    client = docker.APIClient(base_url=base_url, timeout=timeout, version="auto")
    for log in client.logs(container=container_id, stream=True, follow=True):
        print(str(log, "utf-8").rstrip())


class DockerAgent(Agent):
    """
    Agent which deploys flow runs locally as Docker containers. Information on using the
    Docker Agent can be found at https://docs.prefect.io/orchestration/agents/docker.html

    This agent requires Docker v20.10.0+

    Environment variables may be set on the agent to be provided to each flow run's container:
    ```
    prefect agent docker start --env MY_SECRET_KEY=secret --env OTHER_VAR=$OTHER_VAR
    ```

    The default Docker daemon may be overridden by providing a different `base_url`:
    ```
    prefect agent docker start --base-url "tcp://0.0.0.0:2375"
    ```

    If connecting to a local instance of Prefect Server that does not have the
    `--expose` flag set, you must provide a network:
    ```
    prefect agent docker start --network prefect-server
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
        - networks (List[str], optional): Add containers to existing Docker networks.
        - reg_allow_list (List[str], optional): Limits Docker Agent to only pull images
            from the listed registries.
        - docker_client_timeout (int, optional): The timeout to use for docker
            API calls, defaults to 60 seconds.
    """

    def __init__(
        self,
        agent_config_id: str = None,
        name: str = None,
        labels: Iterable[str] = None,
        env_vars: dict = None,
        max_polls: int = None,
        agent_address: str = None,
        no_cloud_logs: bool = None,
        base_url: str = None,
        no_pull: bool = None,
        volumes: List[str] = None,
        show_flow_logs: bool = False,
        networks: List[str] = None,
        reg_allow_list: List[str] = None,
        docker_client_timeout: int = None,
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

        # Add containers to the given Docker networks
        self.networks = networks

        self.docker_client_timeout = docker_client_timeout or 60

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
        self.logger.debug(f"Networks: {self.networks}")

    def _get_docker_client(self) -> "docker.APIClient":
        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        return docker.APIClient(
            base_url=self.base_url,
            version="auto",
            timeout=self.docker_client_timeout,
        )

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
                if fields[0] == "//var/run/docker.sock":
                    # Special handling for docker-in-docker
                    external = "//var/run/docker.sock"
                    internal = "/var/run/docker.sock"
                else:
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
        # 'import docker' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import docker

        run_config = self._get_run_config(flow_run, DockerRun)
        assert run_config is None or isinstance(run_config, DockerRun)  # mypy

        image = get_flow_image(flow_run=flow_run)
        env_vars = self.populate_env_vars(flow_run, image, run_config=run_config)

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
                self.logger.info("Successfully pulled image {}".format(image))

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

        # By default, auto-remove containers
        host_config: Dict[str, Any] = {"auto_remove": True}
        # By default, no ports
        ports = None

        # Set up a host gateway for local communication; check the docker version since
        # this is not supported by older versions
        docker_engine_version = parse_version(self.docker_client.version()["Version"])
        host_gateway_version = parse_version("20.10.0")

        if docker_engine_version < host_gateway_version:
            warnings.warn(
                "`host.docker.internal` could not be automatically resolved to your "
                "local host. This feature is not supported on Docker Engine "
                f"v{docker_engine_version}, upgrade to v{host_gateway_version}+ if you "
                "encounter issues."
            )
        else:
            # Compatibility for linux -- https://github.com/docker/cli/issues/2290
            # Only supported by Docker v20.10.0+ which is our minimum recommend version
            host_config["extra_hosts"] = {"host.docker.internal": "host-gateway"}

        container_mount_paths = self.container_mount_paths
        if container_mount_paths:
            host_config.update(binds=self.host_spec)
        if run_config is not None and run_config.host_config:
            # The host_config passed from the run_config will overwrite defaults
            host_config.update(run_config.host_config)
        if run_config is not None and run_config.ports:
            ports = run_config.ports

        networking_config = None
        # At the time of creation, you can only connect a container to a single network,
        # however you can create more connections after creation.
        # Connect first network in the creation step. If no network is connected here the container
        # is connected to the default `bridge` network.
        # The rest of the networks are connected after creation.
        if self.networks:
            network = self.networks[0]
            networking_config = self.docker_client.create_networking_config(
                {network: self.docker_client.create_endpoint_config()}
            )

            # Ensure that we change the network mode from bridge to host/none if using
            # the special predefined network names
            if network in ("host", "none"):
                host_config.setdefault("network_mode", network)

        labels = {
            "io.prefect.flow-name": flow_run.flow.name,
            "io.prefect.flow-id": flow_run.flow.id,
            "io.prefect.flow-run-id": flow_run.id,
        }

        # Generate a container name to match the flow run name, ensuring it is docker
        # compatible and unique. Must match `[a-zA-Z0-9][a-zA-Z0-9_.-]+` in the end
        container_name = slugified_name = (
            slugify(
                flow_run.name,
                lowercase=False,
                # Docker does not limit length but URL limits apply eventually so
                # limit the length for safety
                max_length=250,
                # Docker allows these characters for container names
                regex_pattern=r"[^a-zA-Z0-9_.-]+",
            ).lstrip(
                # Docker does not allow leading underscore, dash, or period
                "_-."
            )
            # Docker does not allow 0 character names so use the flow run id if name
            # would be empty after cleaning
            or flow_run.id
        )

        # Create the container with retries on name conflicts
        index = 0  # will be bumped on name colissions
        while True:
            try:
                container = self.docker_client.create_container(
                    image,
                    command=get_flow_run_command(flow_run),
                    environment=env_vars,
                    name=container_name,
                    volumes=container_mount_paths,
                    host_config=self.docker_client.create_host_config(**host_config),
                    networking_config=networking_config,
                    labels=labels,
                    ports=ports,
                )
            except docker.errors.APIError as exc:
                if "Conflict" in str(exc) and "container name" in str(exc):
                    index += 1
                    container_name = f"{slugified_name}-{index}"
                else:
                    raise
            else:
                break

        # Connect the rest of the networks
        if self.networks:
            for network in self.networks[1:]:
                self.docker_client.connect_container_to_network(
                    container=container, net_id=network
                )
        # Start the container
        self.logger.debug(
            f"Starting Docker container with ID {container.get('Id')} and "
            f"name {container_name!r}"
        )
        if self.networks:
            self.logger.debug(
                "Adding container with ID {} to docker networks: {}.".format(
                    container.get("Id"), self.networks
                )
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
                "timeout": self.docker_client_timeout,
                "container_id": container_id,
            },
        )
        proc.start()
        self.processes.append(proc)

    def populate_env_vars(
        self, flow_run: GraphQLResult, image: str, run_config: DockerRun = None
    ) -> dict:
        """
        Populate metadata and variables in the environment variables for a flow run

        Args:
            - flow_run (GraphQLResult): A flow run object
            - image (str): The image for this flow
            - run_config (DockerRun, optional): The `run_config` for the flow, if any.

        Returns:
            - dict: a dictionary representing the populated environment variables
        """
        if "localhost" in config.cloud.api:
            if self.networks and "prefect-server" in self.networks:
                api = "http://apollo:{}".format(config.server.port)
            else:
                api = "http://host.docker.internal:{}".format(config.server.port)
        else:
            api = config.cloud.api

        # Populate environment variables, later sources overriding
        # Set the API to be the same as the agent connects to, but since the flow run
        # will be in a container and our inferences above are not perfect, allow the
        # user to override the value
        env = {"PREFECT__CLOUD__API": api}

        # 1. Logging level from config
        # Default to the config logging level, allowing it to be overriden
        # by later config soruces
        env.update({"PREFECT__LOGGING__LEVEL": config.logging.level})

        # 2. Values set on the agent via `--env`
        env.update(self.env_vars)

        # 3. Values set on a DockerRun RunConfig (if present)
        if run_config is not None and run_config.env is not None:
            env.update(run_config.env)

        # 4. Non-overrideable required env vars
        env.update(
            {
                "PREFECT__BACKEND": config.backend,
                "PREFECT__CLOUD__API_KEY": self.flow_run_api_key or "",
                "PREFECT__CLOUD__TENANT_ID": (
                    # A tenant id is only required when authenticating
                    self.client.tenant_id
                    if self.flow_run_api_key
                    else ""
                ),
                "PREFECT__CLOUD__AGENT__LABELS": str(self.labels),
                "PREFECT__CLOUD__SEND_FLOW_RUN_LOGS": str(self.log_to_cloud).lower(),
                "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run.id,  # type: ignore
                "PREFECT__CONTEXT__FLOW_ID": flow_run.flow.id,  # type: ignore
                "PREFECT__CONTEXT__IMAGE": image,
                "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
                "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
                "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
                # Backwards compatibility variable for containers on Prefect <0.15.0
                "PREFECT__LOGGING__LOG_TO_CLOUD": str(self.log_to_cloud).lower(),
                # Backwards compatibility variable for containers on Prefect <1.0.0
                "PREFECT__CLOUD__AUTH_TOKEN": self.flow_run_api_key or "",
            }
        )
        return env


if __name__ == "__main__":
    DockerAgent().start()
