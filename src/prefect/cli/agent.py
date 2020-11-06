import click

from prefect import config
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.serialization import from_qualified_name

COMMON_START_OPTIONS = [
    click.option(
        "--token",
        "-t",
        required=False,
        help="A Prefect Cloud API token with RUNNER scope.",
    ),
    click.option("--api", "-a", required=False, help="A Prefect API URL."),
    click.option(
        "--agent-config-id",
        help="An agent ID to link this agent instance with",
    ),
    click.option(
        "--name",
        "-n",
        help="A name to use for the agent",
    ),
    click.option(
        "--label",
        "-l",
        multiple=True,
        help="Labels the agent will use to query for flow runs.",
    ),
    click.option(
        "--env",
        "-e",
        multiple=True,
        help="Environment variables to set on each submitted flow run.",
    ),
    click.option(
        "--max-polls",
        help=(
            "Maximum number of times the agent should poll the Prefect API for flow "
            "runs. Default is no limit"
        ),
        type=int,
    ),
    click.option(
        "--agent-address",
        help="Address to serve internal api server at. Defaults to no server.",
        type=str,
    ),
    click.option(
        "--no-cloud-logs",
        is_flag=True,
        help="Turn off logging for all flows run through this agent.",
    ),
    click.option(
        "--log-level",
        type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
        default=None,
        help=(
            "The agent log level to use. Defaults to the value configured in your "
            "environment."
        ),
    ),
]


COMMON_INSTALL_OPTIONS = [
    click.option(
        "--token",
        "-t",
        help="A Prefect Cloud API token with RUNNER scope.",
    ),
    click.option(
        "--label",
        "-l",
        multiple=True,
        help="Labels the agent will use to query for flow runs.",
    ),
    click.option(
        "--env",
        "-e",
        multiple=True,
        help="Environment variables to set on each submitted flow run.",
    ),
]


def add_options(options):
    """A decorator for adding a list of options to a click command"""

    def decorator(func):
        for opt in reversed(options):
            func = opt(func)
        return func

    return decorator


def start_agent(agent_cls, token, api, label, env, log_level, **kwargs):
    labels = sorted(set(label))
    env_vars = dict(e.split("=", 2) for e in env)

    tmp_config = {
        "cloud.agent.auth_token": token or config.cloud.agent.auth_token,
        "cloud.agent.level": log_level or config.cloud.agent.level,
        "cloud.api": api or config.cloud.api,
    }
    with set_temporary_config(tmp_config):
        agent = agent_cls(labels=labels, env_vars=env_vars, **kwargs)
        agent.start()


@click.group()
def agent():
    """Manage Prefect agents."""


###############
# Local Agent #
###############


@agent.group()
def local():
    """Manage Prefect Local agents."""


@local.command()
@add_options(COMMON_START_OPTIONS)
@click.option(
    "--import-path",
    "-p",
    "import_paths",
    multiple=True,
    help="Import paths the local agent will add to all flow runs.",
)
@click.option(
    "--show-flow-logs",
    "-f",
    help="Display logging output from flows run by the agent.",
    is_flag=True,
)
@click.option(
    "--storage-labels/--no-storage-labels",
    default=True,
    help="Add all storage labels to the LocalAgent",
)
@click.option(
    "--hostname-label/--no-hostname-label",
    default=True,
    help="Add hostname to the LocalAgent's labels",
)
def start(import_paths, **kwargs):
    """Start a local agent"""
    from prefect.agent.local import LocalAgent

    start_agent(LocalAgent, import_paths=list(import_paths), **kwargs)


@local.command()
@add_options(COMMON_INSTALL_OPTIONS)
@click.option(
    "--import-path",
    "-p",
    "import_paths",
    multiple=True,
    help="Import paths the local agent will add to all flow runs.",
)
@click.option(
    "--show-flow-logs",
    "-f",
    help="Display logging output from flows run by the agent.",
    is_flag=True,
)
def install(label, env, import_paths, **kwargs):
    """Generate a supervisord.conf file for a Local agent"""
    from prefect.agent.local import LocalAgent

    conf = LocalAgent.generate_supervisor_conf(
        labels=sorted(set(label)),
        env_vars=dict(e.split("=", 2) for e in env),
        import_paths=list(import_paths),
        **kwargs,
    )
    click.echo(conf)


################
# Docker Agent #
################


@agent.group()
def docker():
    """Manage Prefect Docker agents."""


@docker.command()
@add_options(COMMON_START_OPTIONS)
@click.option("--base-url", "-b", help="Docker daemon base URL.")
@click.option("--no-pull", is_flag=True, help="Disable pulling images in the agent")
@click.option(
    "--show-flow-logs",
    "-f",
    help="Display logging output from flows run by the agent.",
    is_flag=True,
)
@click.option(
    "--volume",
    "volumes",
    multiple=True,
    help=(
        "Host paths for Docker bind mount volumes attached to each Flow "
        "container. Can be provided multiple times to pass multiple volumes "
        "(e.g. `--volume /volume1 --volume /volume2`)"
    ),
)
@click.option(
    "--network",
    help="Add containers to an existing docker network",
)
@click.option(
    "--no-docker-interface",
    is_flag=True,
    help=(
        "Disable the check of a Docker interface on this machine. "
        "Note: This is mostly relevant for some Docker-in-Docker "
        "setups that users may be running their agent with."
    ),
)
def start(volumes, no_docker_interface, **kwargs):
    """Start a docker agent"""
    from prefect.agent.docker import DockerAgent

    start_agent(
        DockerAgent,
        volumes=list(volumes),
        docker_interface=not no_docker_interface,
        **kwargs,
    )


####################
# Kubernetes Agent #
####################


@agent.group()
def kubernetes():
    """Manage Prefect Kubernetes agents."""


@kubernetes.command()
@add_options(COMMON_START_OPTIONS)
@click.option(
    "--namespace",
    help="Kubernetes namespace to deploy in. Defaults to `default`.",
)
@click.option(
    "--job-template",
    "job_template_path",
    help="Path to a kubernetes job template to use instead of the default.",
)
def start(**kwargs):
    """Start a Kubernetes agent"""
    from prefect.agent.kubernetes import KubernetesAgent

    start_agent(KubernetesAgent, **kwargs)


@kubernetes.command()
@add_options(COMMON_INSTALL_OPTIONS)
@click.option("--api", "-a", required=False, help="A Prefect API URL.")
@click.option("--namespace", "-n", help="Agent namespace to launch workloads.")
@click.option(
    "--image-pull-secrets",
    "-i",
    help="Name of image pull secrets to use for workloads.",
)
@click.option(
    "--resource-manager",
    "resource_manager_enabled",
    is_flag=True,
    help="Enable resource manager.",
)
@click.option("--rbac", is_flag=True, help="Enable default RBAC.")
@click.option("--latest", is_flag=True, help="Use the latest Prefect image.")
@click.option("--mem-request", help="Requested memory for Prefect init job.")
@click.option("--mem-limit", help="Limit memory for Prefect init job.")
@click.option("--cpu-request", help="Requested CPU for Prefect init job.")
@click.option("--cpu-limit", help="Limit CPU for Prefect init job.")
@click.option("--image-pull-policy", help="imagePullPolicy for Prefect init job")
@click.option(
    "--service-account-name", help="Name of Service Account for Prefect init job"
)
@click.option("--backend", "-b", help="Prefect backend to use for this agent.")
def install(label, env, **kwargs):
    """Generate a supervisord.conf file for a Local agent"""
    from prefect.agent.kubernetes import KubernetesAgent

    deployment = KubernetesAgent.generate_deployment_yaml(
        labels=sorted(set(label)), env_vars=dict(e.split("=", 2) for e in env), **kwargs
    )
    click.echo(deployment)


#################
# Fargate Agent #
#################


@agent.group()
def fargate():
    """Manage Prefect Fargate agents."""


@fargate.command(
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True)
)
@add_options(COMMON_START_OPTIONS)
@click.pass_context
def start(ctx, **kwargs):
    """Start a Fargate agent"""
    from prefect.agent.fargate import FargateAgent

    for item in ctx.args:
        k, v = item.replace("--", "").split("=", 2)
        kwargs[k] = v

    start_agent(FargateAgent, **kwargs)


#############
# ECS Agent #
#############


@agent.group()
def ecs():
    """Manage Prefect ECS agents."""


@ecs.command()
@add_options(COMMON_START_OPTIONS)
@click.option(
    "--cluster",
    help="The cluster to use. If not provided, your default cluster will be used",
)
@click.option(
    "--launch-type",
    type=click.Choice(["FARGATE", "EC2"], case_sensitive=False),
    help="The launch type to use, defaults to FARGATE",
)
@click.option(
    "--task-role-arn",
    help="The default task role ARN to use for ECS tasks started by this agent.",
)
@click.option(
    "--task-definition",
    "task_definition_path",
    help=(
        "Path to a task definition template to use when defining new tasks "
        "instead of the default."
    ),
)
@click.option(
    "--run-task-kwargs",
    "run_task_kwargs_path",
    help="Path to a yaml file containing extra kwargs to pass to `run_task`",
)
def start(**kwargs):
    """Start an ECS agent"""
    from prefect.agent.ecs import ECSAgent

    start_agent(ECSAgent, **kwargs)


#############################
# Deprecated Agent Commands #
#############################

_agents = {
    "fargate": "prefect.agent.fargate.FargateAgent",
    "docker": "prefect.agent.docker.DockerAgent",
    "kubernetes": "prefect.agent.kubernetes.KubernetesAgent",
    "local": "prefect.agent.local.LocalAgent",
}


@agent.command(
    hidden=True,
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True),
)
@click.argument("agent-option", default="local")
@click.option(
    "--token", "-t", required=False, help="A Prefect Cloud API token.", hidden=True
)
@click.option("--api", "-a", required=False, help="A Prefect API URL.", hidden=True)
@click.option("--agent-config-id", required=False, help="An agent ID", hidden=True)
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
    "--storage-labels/--no-storage-labels",
    default=True,
    help="Add all storage labels to the LocalAgent",
    hidden=True,
)
@click.option(
    "--hostname-label/--no-hostname-label",
    default=True,
    help="Add hostname to the LocalAgent's labels",
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
    "--job-template",
    required=False,
    help="Path to a kubernetes job template to use instead of the default.",
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
    "--network",
    help="Add containers to an existing docker network",
    hidden=True,
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
    agent_config_id,
    name,
    verbose,
    label,
    env,
    namespace,
    job_template,
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
    storage_labels,
    hostname_label,
):
    """
    Start an agent.

    DEPRECATED: use `prefect agent <agent-type> start` instead.

    \b
    Arguments:
        agent-option    TEXT    The name of an agent to start (e.g. `docker`, `kubernetes`,
                                `local`, `fargate`). Defaults to `local`

    \b
    Options:
        --token, -t             TEXT    A Prefect Cloud API token with RUNNER scope
        --api, -a               TEXT    A Prefect API URL
        --agent-config--id      TEXT    An agent ID to link this agent instance with
        --name, -n              TEXT    A name to use for the agent
        --verbose, -v                   Enable verbose agent DEBUG logs
                                        Defaults to INFO level logging
        --label, -l             TEXT    Labels the agent will use to query for flow runs
                                        Multiple values supported e.g. `-l label1 -l label2`
        --env, -e               TEXT    Environment variables to set on each submitted flow
                                        run.
                                        Note that equal signs in environment variable values
                                        are not currently supported from the CLI.  Multiple
                                        values supported.
                                            e.g. `-e AUTH=token -e PKG_SETTING=true`
        --max-polls             INT     Maximum number of times the agent should poll the
                                        Prefect API for flow runs. Will run forever if not
                                        specified.
        --no-cloud-logs                 Turn off logging to the Prefect API for all flow runs
                                        Defaults to `False`
        --agent-address         TEXT    The address to server internal api at. Currently this
                                        is just health checks for use by an orchestration layer
                                        (e.g. kubernetes). Leave blank for no api server (default).

    \b
    Local Agent:
        --import-path, -p   TEXT    Import paths which will be provided to each Flow's
                                    runtime environment.  Used for Flows which might
                                    import from scripts or local packages.  Multiple values
                                    supported.
                                        e.g. `-p /root/my_scripts -p /utilities`
        --show-flow-logs, -f        Display logging output from flows run by the agent
                                    (available for Local and Docker agents only)
        --hostname-label            Add hostname to the Agent's labels
                                        (Default to True. Disable with --no-hostname-label option)
        --storage-labels            Add all storage labels to the Agent
                                        (Default to True. Disable with --no-storage-labels option)

    \b
    Docker Agent:
        --base-url, -b      TEXT    A Docker daemon host URL for a DockerAgent
        --no-pull                   Pull images for a DockerAgent
                                    Defaults to pulling if not provided
        --volume            TEXT    Host paths for Docker bind mount volumes attached to
                                    each Flow runtime container. Multiple values supported.
                                        e.g. `--volume /some/path`
        --network           TEXT    Add containers to an existing docker network
        --no-docker-interface       Disable the check of a Docker interface on this machine.
                                    Note: This is mostly relevant for some Docker-in-Docker
                                    setups that users may be running their agent with.

    \b
    Kubernetes Agent:
        --namespace     TEXT    A Kubernetes namespace to create Prefect jobs in
                                Defaults to env var `NAMESPACE` or `default`
        --job-template  TEXT    Path to a job template to use instead of the default.

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

        click.secho(
            f"Warning: `prefect agent start {agent_option}` is deprecated, use "
            f"`prefect agent {agent_option} start` instead",
            fg="yellow",
        )

        env_vars = dict()
        for env_var in env:
            k, v = env_var.split("=")
            env_vars[k] = v

        labels = sorted(set(label))

        if agent_option == "local":
            from_qualified_name(retrieved_agent)(
                agent_config_id=agent_config_id,
                name=name,
                labels=labels,
                env_vars=env_vars,
                max_polls=max_polls,
                agent_address=agent_address,
                import_paths=list(import_path),
                show_flow_logs=show_flow_logs,
                no_cloud_logs=no_cloud_logs,
                hostname_label=hostname_label,
                storage_labels=storage_labels,
            ).start()
        elif agent_option == "docker":
            from_qualified_name(retrieved_agent)(
                agent_config_id=agent_config_id,
                name=name,
                labels=labels,
                env_vars=env_vars,
                max_polls=max_polls,
                no_cloud_logs=no_cloud_logs,
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
                agent_config_id=agent_config_id,
                name=name,
                labels=labels,
                env_vars=env_vars,
                max_polls=max_polls,
                no_cloud_logs=no_cloud_logs,
                agent_address=agent_address,
                **kwargs,
            ).start()
        elif agent_option == "kubernetes":
            from_qualified_name(retrieved_agent)(
                agent_config_id=agent_config_id,
                namespace=namespace,
                job_template_path=job_template,
                name=name,
                labels=labels,
                env_vars=env_vars,
                max_polls=max_polls,
                no_cloud_logs=no_cloud_logs,
                agent_address=agent_address,
            ).start()
        else:
            from_qualified_name(retrieved_agent)(
                agent_config_id=agent_config_id,
                name=name,
                labels=labels,
                env_vars=env_vars,
                max_polls=max_polls,
                no_cloud_logs=no_cloud_logs,
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

    DEPRECATED: use `prefect agent <agent-type> install` instead.

    \b
    Arguments:
        name                        TEXT    The name of an agent to install (e.g.
                                            `kubernetes`, `local`)

    \b
    Options:
        --token, -t                 TEXT    A Prefect Cloud API token
        --label, -l                 TEXT    Labels the agent will use to query for flow runs
                                            Multiple values supported.
                                                e.g. `-l label1 -l label2`
        --env, -e                   TEXT    Environment variables to set on each submitted
                                            flow run. Note that equal signs in environment
                                            variable values are not currently supported from
                                            the CLI. Multiple values supported.
                                                e.g. `-e AUTH=token -e PKG_SETTING=true`

    \b
    Kubernetes Agent:
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
    Local Agent:
        --import-path, -p           TEXT    Absolute import paths to provide to the local
                                            agent. Multiple values supported.
                                                e.g. `-p /root/my_scripts -p /utilities`
        --show-flow-logs, -f                Display logging output from flows run by the
                                            agent
    """

    supported_agents = {
        "kubernetes": "prefect.agent.kubernetes.KubernetesAgent",
        "local": "prefect.agent.local.LocalAgent",
    }

    retrieved_agent = supported_agents.get(name, None)

    if not retrieved_agent:
        click.secho("{} is not a supported agent for `install`".format(name), fg="red")
        return

    click.secho(
        f"Warning: `prefect agent install {name}` is deprecated, use "
        f"`prefect agent {name} install` instead",
        fg="yellow",
    )

    env_vars = dict()
    for env_var in env:
        k, v = env_var.split("=")
        env_vars[k] = v

    labels = sorted(set(label))
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
            labels=labels,
            env_vars=env_vars,
            backend=backend,
        )
        click.echo(deployment)
    elif name == "local":
        conf = from_qualified_name(retrieved_agent).generate_supervisor_conf(
            token=token,
            labels=labels,
            env_vars=env_vars,
            import_paths=list(import_path),
            show_flow_logs=show_flow_logs,
        )
        click.echo(conf)
