import click

from prefect import config
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.serialization import from_qualified_name

_agents = {
    "fargate": "prefect.agent.fargate.FargateAgent",
    "docker": "prefect.agent.docker.DockerAgent",
    "kubernetes": "prefect.agent.kubernetes.KubernetesAgent",
    "local": "prefect.agent.local.LocalAgent",
}


@click.group(hidden=True)
def agent():
    """
    Manage Prefect agents.

    \b
    Usage:
        $ prefect agent [COMMAND]

    \b
    Arguments:
        start       Start a Prefect agent
        install     Output platform-specific agent installation configs

    \b
    Examples:
        $ prefect agent start
        ...agent begins running in process...

    \b
        $ prefect agent start kubernetes --token MY_TOKEN
        ...agent begins running in process...

    \b
        $ prefect agent install kubernetes --token MY_TOKEN --namespace metrics
        ...k8s yaml output...
    """


@agent.command(
    hidden=True,
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True),
)
@click.argument("agent-option", default="local")
@click.option(
    "--token", "-t", required=False, help="A Prefect Cloud API token.", hidden=True
)
@click.option("--api", "-a", required=False, help="A Prefect API URL.", hidden=True)
@click.option(
    "--name",
    "-n",
    required=False,
    help="A name to use for the agent",
    hidden=True,
    default=None,
)
@click.option(
    "--verbose", "-v", is_flag=True, help="Enable verbose agent logs.", hidden=True
)
@click.option(
    "--label",
    "-l",
    multiple=True,
    help="Labels the agent will use to query for flow runs.",
    hidden=True,
)
@click.option(
    "--env",
    "-e",
    multiple=True,
    help="Environment variables to set on each submitted flow run.",
    hidden=True,
)
@click.option(
    "--max-polls",
    required=False,
    help="Maximum number of polls for the agent",
    hidden=True,
    type=int,
)
@click.option(
    "--agent-address",
    required=False,
    help="Address to serve internal api server at. Defaults to no server.",
    hidden=True,
    type=str,
    default="",
)
@click.option(
    "--namespace",
    required=False,
    help="Kubernetes namespace to create jobs.",
    hidden=True,
)
@click.option(
    "--import-path",
    "-p",
    multiple=True,
    help="Import paths the local agent will add to all flow runs.",
    hidden=True,
)
@click.option(
    "--show-flow-logs",
    "-f",
    help="Display logging output from flows run by the agent.",
    hidden=True,
    is_flag=True,
)
@click.option("--no-pull", is_flag=True, help="Pull images flag.", hidden=True)
@click.option(
    "--no-cloud-logs",
    is_flag=True,
    help="Turn off logging for all flows run through this agent.",
    hidden=True,
)
@click.option("--base-url", "-b", help="Docker daemon base URL.", hidden=True)
@click.option(
    "--volume",
    multiple=True,
    help="Host paths for Docker bind mount volumes attached to each Flow runtime container.",
    hidden=True,
)
@click.option(
    "--network", help="Add containers to an existing docker network", hidden=True,
)
@click.option(
    "--no-docker-interface",
    is_flag=True,
    help="Disable presence of a Docker interface.",
    hidden=True,
)
@click.pass_context
def start(
    ctx,
    agent_option,
    token,
    api,
    name,
    verbose,
    label,
    env,
    namespace,
    no_pull,
    no_cloud_logs,
    base_url,
    import_path,
    show_flow_logs,
    volume,
    network,
    no_docker_interface,
    max_polls,
    agent_address,
):
    """
    Start an agent.

    \b
    Arguments:
        agent-option    TEXT    The name of an agent to start (e.g. `docker`, `kubernetes`,
                                `local`, `fargate`). Defaults to `local`

    \b
    Options:
        --token, -t     TEXT    A Prefect Cloud API token with RUNNER scope
        --api, -a       TEXT    A Prefect API URL
        --name, -n      TEXT    A name to use for the agent
        --verbose, -v           Enable verbose agent DEBUG logs
                                Defaults to INFO level logging
        --label, -l     TEXT    Labels the agent will use to query for flow runs
                                Multiple values supported e.g. `-l label1 -l label2`

        --env, -e       TEXT    Environment variables to set on each submitted flow run.
                                Note that equal signs in environment variable values are not
                                currently supported from the CLI.  Multiple values supported
                                e.g. `-e AUTH=token -e PKG_SETTING=true`
        --max-polls     INT     Maximum number of times the agent should poll the Prefect API
                                for flow runs. Will run forever if not specified.
        --no-cloud-logs         Turn off logging to the Prefect API for all flow runs
                                Defaults to `False`
        --agent-address TEXT    The address to server internal api at. Currently this is
                                just health checks for use by an orchestration layer
                                (e.g. kubernetes). Leave blank for no api server (default).

    \b
    Local Agent Options:
        --import-path, -p   TEXT    Import paths which will be provided to each Flow's runtime
                                    environment.  Used for Flows which might import from
                                    scripts or local packages.  Multiple values supported e.g.
                                    `-p /root/my_scripts -p /utilities`
        --show-flow-logs, -f        Display logging output from flows run by the agent (available
                                    for Local and Docker agents only)

    \b
    Docker Agent Options:
        --base-url, -b      TEXT    A Docker daemon host URL for a DockerAgent
        --no-pull                   Pull images for a DockerAgent
                                    Defaults to pulling if not provided

        --volume            TEXT    Host paths for Docker bind mount volumes attached to each
                                    Flow runtime container.  Multiple values supported e.g.
                                    `--volume /some/path --volume /some/other/path`
        --network           TEXT    Add containers to an existing docker network

        --no-docker-interface       Disable the check of a Docker interface on this machine.
                                    **Note**: This is mostly relevant for some Docker-in-Docker
                                    setups that users may be running their agent with.

    \b
    Kubernetes Agent Options:
        --namespace     TEXT    A Kubernetes namespace to create Prefect jobs in
                                Defaults to env var `NAMESPACE` or `default`

    \b
    Fargate Agent Options:
        Any of the configuration options outlined in the docs can be provided here
        https://docs.prefect.io/orchestration/agents/fargate.html#configuration
    """

    # Split context
    kwargs = dict()
    for item in ctx.args:
        item = item.replace("--", "")
        kwargs.update([item.split("=")])

    tmp_config = {
        "cloud.agent.auth_token": token or config.cloud.agent.auth_token,
    }
    if verbose:
        tmp_config["cloud.agent.level"] = "DEBUG"
    if api:
        tmp_config["cloud.api"] = api

    with set_temporary_config(tmp_config):
        retrieved_agent = _agents.get(agent_option, None)

        if not retrieved_agent:
            click.secho("{} is not a valid agent".format(agent_option), fg="red")
            return

        env_vars = dict()
        for env_var in env:
            k, v = env_var.split("=")
            env_vars[k] = v

        if agent_option == "local":
            from_qualified_name(retrieved_agent)(
                name=name,
                labels=list(label),
                env_vars=env_vars,
                max_polls=max_polls,
                agent_address=agent_address,
                import_paths=list(import_path),
                show_flow_logs=show_flow_logs,
                no_cloud_logs=no_cloud_logs,
            ).start()
        elif agent_option == "docker":
            from_qualified_name(retrieved_agent)(
                name=name,
                labels=list(label),
                env_vars=env_vars,
                max_polls=max_polls,
                agent_address=agent_address,
                base_url=base_url,
                no_pull=no_pull,
                show_flow_logs=show_flow_logs,
                volumes=list(volume),
                network=network,
                docker_interface=not no_docker_interface,
            ).start()
        elif agent_option == "fargate":
            from_qualified_name(retrieved_agent)(
                name=name,
                labels=list(label),
                env_vars=env_vars,
                max_polls=max_polls,
                agent_address=agent_address,
                **kwargs
            ).start()
        elif agent_option == "kubernetes":
            from_qualified_name(retrieved_agent)(
                namespace=namespace,
                name=name,
                labels=list(label),
                env_vars=env_vars,
                max_polls=max_polls,
                agent_address=agent_address,
            ).start()
        else:
            from_qualified_name(retrieved_agent)(
                name=name,
                labels=list(label),
                env_vars=env_vars,
                max_polls=max_polls,
                agent_address=agent_address,
            ).start()


@agent.command(hidden=True)
@click.argument("name")
@click.option(
    "--token", "-t", required=False, help="A Prefect Cloud API token.", hidden=True
)
@click.option("--api", "-a", required=False, help="A Prefect API URL.", hidden=True)
@click.option(
    "--namespace",
    "-n",
    required=False,
    help="Agent namespace to launch workloads.",
    hidden=True,
)
@click.option(
    "--image-pull-secrets",
    "-i",
    required=False,
    help="Name of image pull secrets to use for workloads.",
    hidden=True,
)
@click.option(
    "--resource-manager", is_flag=True, help="Enable resource manager.", hidden=True
)
@click.option("--rbac", is_flag=True, help="Enable default RBAC.", hidden=True)
@click.option(
    "--latest", is_flag=True, help="Use the latest Prefect image.", hidden=True
)
@click.option(
    "--mem-request",
    required=False,
    help="Requested memory for Prefect init job.",
    hidden=True,
)
@click.option(
    "--mem-limit",
    required=False,
    help="Limit memory for Prefect init job.",
    hidden=True,
)
@click.option(
    "--cpu-request",
    required=False,
    help="Requested CPU for Prefect init job.",
    hidden=True,
)
@click.option(
    "--cpu-limit", required=False, help="Limit CPU for Prefect init job.", hidden=True
)
@click.option(
    "--image-pull-policy",
    required=False,
    help="imagePullPolicy for Prefect init job",
    hidden=True,
)
@click.option(
    "--service-account-name",
    required=False,
    help="Name of Service Account for Prefect init job",
    hidden=True,
)
@click.option(
    "--label",
    "-l",
    multiple=True,
    help="Labels the agent will use to query for flow runs.",
    hidden=True,
)
@click.option(
    "--env",
    "-e",
    multiple=True,
    help="Environment variables to set on each submitted flow run.",
    hidden=True,
)
@click.option(
    "--import-path",
    "-p",
    multiple=True,
    help="Import paths the local agent will add to all flow runs.",
    hidden=True,
)
@click.option(
    "--show-flow-logs",
    "-f",
    help="Display logging output from flows run by the agent.",
    hidden=True,
    is_flag=True,
)
@click.option(
    "--backend",
    "-b",
    required=False,
    help="Prefect backend to use for this agent.",
    hidden=True,
)
def install(
    name,
    token,
    api,
    namespace,
    image_pull_secrets,
    resource_manager,
    rbac,
    latest,
    mem_request,
    mem_limit,
    cpu_request,
    cpu_limit,
    image_pull_policy,
    service_account_name,
    label,
    env,
    import_path,
    show_flow_logs,
    backend,
):
    """
    Install an agent. Outputs configuration text which can be used to install on various
    platforms. The Prefect image version will default to your local `prefect.__version__`

    \b
    Arguments:
        name                        TEXT    The name of an agent to install (e.g.
                                            `kubernetes`, `local`)

    \b
    Options:
        --token, -t                 TEXT    A Prefect Cloud API token
        --label, -l                 TEXT    Labels the agent will use to query for flow runs
                                            Multiple values supported e.g. `-l label1 -l label2`
        --env, -e                   TEXT    Environment variables to set on each submitted flow
                                            run. Note that equal signs in environment variable
                                            values are not currently supported from the CLI.
                                            Multiple values supported e.g. `-e AUTH=token -e
                                            PKG_SETTING=true`

    \b
    Kubernetes Agent Options:
        --api, -a                   TEXT    A Prefect API URL
        --namespace, -n             TEXT    Agent namespace to launch workloads
        --image-pull-secrets, -i    TEXT    Name of image pull secrets to use for workloads
        --resource-manager                  Enable resource manager on install
        --rbac                              Enable default RBAC on install
        --latest                            Use the `latest` Prefect image
        --mem-request               TEXT    Requested memory for Prefect init job
        --mem-limit                 TEXT    Limit memory for Prefect init job
        --cpu-request               TEXT    Requested CPU for Prefect init job
        --cpu-limit                 TEXT    Limit CPU for Prefect init job
        --image-pull-policy         TEXT    imagePullPolicy for Prefect init job
        --service-account-name      TEXT    Name of Service Account for Prefect init job
        --backend                   TEST    Prefect backend to use for this agent
                                            Defaults to the backend currently set in config.

    \b
    Local Agent Options:
        --import-path, -p           TEXT    Absolute import paths to provide to the local agent.
                                            Multiple values supported e.g. `-p /root/my_scripts
                                            -p /utilities`
        --show-flow-logs, -f                Display logging output from flows run by the agent
    """

    supported_agents = {
        "kubernetes": "prefect.agent.kubernetes.KubernetesAgent",
        "local": "prefect.agent.local.LocalAgent",
    }

    retrieved_agent = supported_agents.get(name, None)

    if not retrieved_agent:
        click.secho("{} is not a supported agent for `install`".format(name), fg="red")
        return

    env_vars = dict()
    for env_var in env:
        k, v = env_var.split("=")
        env_vars[k] = v

    if name == "kubernetes":
        deployment = from_qualified_name(retrieved_agent).generate_deployment_yaml(
            token=token,
            api=api,
            namespace=namespace,
            image_pull_secrets=image_pull_secrets,
            resource_manager_enabled=resource_manager,
            rbac=rbac,
            latest=latest,
            mem_request=mem_request,
            mem_limit=mem_limit,
            cpu_request=cpu_request,
            cpu_limit=cpu_limit,
            image_pull_policy=image_pull_policy,
            service_account_name=service_account_name,
            labels=list(label),
            env_vars=env_vars,
            backend=backend,
        )
        click.echo(deployment)
    elif name == "local":
        conf = from_qualified_name(retrieved_agent).generate_supervisor_conf(
            token=token,
            labels=list(label),
            import_paths=list(import_path),
            show_flow_logs=show_flow_logs,
        )
        click.echo(conf)
