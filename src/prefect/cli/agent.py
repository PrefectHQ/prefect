import click

from prefect import config
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.cli import add_options

COMMON_START_OPTIONS = [
    click.option(
        "--key",
        "-k",
        help=(
            "A Prefect Cloud API key. If not set, the value will be inferred from the "
            "local machine."
        ),
    ),
    click.option(
        "--tenant-id",
        help=(
            "The ID of the tenant to connect the agent to. If not set, the value will "
            "be inferred from the local machine and fallback to the default associated "
            "with the API key."
        ),
    ),
    click.option(
        "--api",
        "-a",
        required=False,
        help="A Prefect API URL. If not set, the value in the config is used.",
    ),
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
        help=(
            "Turn off logging for all flows run through this agent. If not set, the "
            "Prefect config value will be used."
        ),
        default=None,
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
        "--key",
        "-k",
        help="A Prefect Cloud API key",
    ),
    click.option(
        "--tenant-id",
        help=(
            "The ID of the tenant to connect the agent to. If not set, the default "
            "tenant associated with the API key."
        ),
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
        "--agent-config-id",
        help="An agent ID to link this agent instance with",
    ),
]


def start_agent(agent_cls, api, label, env, log_level, key, tenant_id, **kwargs):
    labels = sorted(set(label))
    env_vars = dict(e.split("=", 1) for e in env)
    tmp_config = {
        "cloud.api_key": key or config.cloud.api_key,
        "cloud.tenant_id": tenant_id or config.cloud.tenant_id,
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
        env_vars=dict(e.split("=", 1) for e in env),
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
    "networks",
    multiple=True,
    help=(
        "Add containers to existing Docker networks. "
        "Can be provided multiple times to pass multiple networks "
        "(e.g. `--network network1 --network network2`)"
    ),
)
@click.option(
    "--docker-client-timeout",
    default=None,
    type=int,
    help="The timeout to use for docker API calls, defaults to 60 seconds.",
)
def start(volumes, **kwargs):
    """Start a docker agent"""
    from prefect.agent.docker import DockerAgent

    start_agent(
        DockerAgent,
        volumes=list(volumes),
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
@click.option(
    "--service-account-name",
    "service_account_name",
    help="A default service account name to configure on started jobs.",
)
@click.option(
    "--image-pull-secrets",
    "image_pull_secrets",
    help="Default image pull secrets to configure on started jobs. Multiple "
    "values can be provided as a comma-separated list "
    "(e.g. `--image-pull-secrets VAL1,VAL2`)",
)
@click.option(
    "--disable-job-deletion",
    "delete_finished_jobs",
    help="Turn off automatic deletion of finished jobs in the namespace.",
    is_flag=True,
    default=True,  # Defaults to `True` because setting this flag sets `delete_finished_jobs` to `False`
)
def start(image_pull_secrets=None, **kwargs):
    """Start a Kubernetes agent"""
    from prefect.agent.kubernetes import KubernetesAgent

    if image_pull_secrets is not None:
        image_pull_secrets = [s.strip() for s in image_pull_secrets.split(",")]

    start_agent(KubernetesAgent, image_pull_secrets=image_pull_secrets, **kwargs)


@kubernetes.command()
@add_options(COMMON_INSTALL_OPTIONS)
@click.option("--api", "-a", required=False, help="A Prefect API URL.")
@click.option("--namespace", "-n", help="Agent namespace to launch workloads.")
@click.option(
    "--image-pull-secrets",
    "-i",
    help="Name of image pull secrets to use for workloads.",
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
    """Generate a deployment.yml file for a Kubernetes agent"""
    from prefect.agent.kubernetes import KubernetesAgent

    deployment = KubernetesAgent.generate_deployment_yaml(
        labels=sorted(set(label)), env_vars=dict(e.split("=", 1) for e in env), **kwargs
    )
    click.echo(deployment)


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
    "--execution-role-arn",
    help="The default execution role ARN to use for ECS tasks started by this agent.",
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


#############
# Vertex Agent #
#############


@agent.group()
def vertex():
    """Manage Prefect Vertex agents."""


@vertex.command()
@add_options(COMMON_START_OPTIONS)
@click.option(
    "--project",
    help="The Google cloud project where flow runs will be launched in vertex.",
)
@click.option(
    "--region-name",
    help="The region where flow runs will be launched in vertex.",
)
@click.option(
    "--service-account",
    help="The service account that flow runs will act as in vertex.",
)
def start(**kwargs):
    """Start a Vertex agent"""
    from prefect.agent.vertex.agent import VertexAgent

    start_agent(VertexAgent, **kwargs)
