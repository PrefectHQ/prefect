import click

from prefect import config
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.serialization import from_qualified_name

_agents = {
    "fargate": "prefect.agent.fargate.FargateAgent",
    "local": "prefect.agent.local.LocalAgent",
    "kubernetes": "prefect.agent.kubernetes.KubernetesAgent",
    "nomad": "prefect.agent.nomad.NomadAgent",
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
        $ prefect agent install --token MY_TOKEN --namespace metrics
        ...k8s yaml output...
    """
    pass


@agent.command(
    hidden=True,
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True,),
)
@click.argument("agent-option", default="local")
@click.option(
    "--token", "-t", required=False, help="A Prefect Cloud API token.", hidden=True
)
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
@click.option("--no-pull", is_flag=True, help="Pull images flag.", hidden=True)
@click.option("--base-url", "-b", help="Docker daemon base URL.", hidden=True)
@click.pass_context
def start(ctx, agent_option, token, name, verbose, label, no_pull, base_url):
    """
    Start an agent.

    \b
    Arguments:
        agent-option    TEXT    The name of an agent to start (e.g. `local`, `kubernetes`, `fargate`, `nomad`)
                                Defaults to `local`

    \b
    Options:
        --token, -t     TEXT    A Prefect Cloud API token with RUNNER scope
        --name, -n      TEXT    A name to use for the agent
        --verbose, -v           Enable verbose agent DEBUG logs
                                Defaults to INFO level logging
        --label, -l     TEXT    Labels the agent will use to query for flow runs
                                Multiple values supported e.g. `-l label1 -l label2`

    \b
    Local Agent Options:
        --base-url, -b  TEXT    A Docker daemon host URL for a LocalAgent
        --no-pull               Pull images for a LocalAgent
                                Defaults to pulling if not provided

    \b
    Fargate Agent Options:
        Any of the configuration options outlined in the docs can be provided here
        https://docs.prefect.io/cloud/agent/fargate.html#configuration
    """

    # Split context
    kwargs = dict()
    for item in ctx.args:
        item = item.replace("--", "")
        kwargs.update([item.split("=")])

    tmp_config = {"cloud.agent.auth_token": token or config.cloud.agent.auth_token}
    if verbose:
        tmp_config["cloud.agent.level"] = "DEBUG"

    with set_temporary_config(tmp_config):
        retrieved_agent = _agents.get(agent_option, None)

        if not retrieved_agent:
            click.secho("{} is not a valid agent".format(agent_option), fg="red")
            return

        _agent = from_qualified_name(retrieved_agent)

        if agent_option == "local":
            from_qualified_name(retrieved_agent)(
                name=name, labels=list(label), base_url=base_url, no_pull=no_pull,
            ).start()
        elif agent_option == "fargate":
            from_qualified_name(retrieved_agent)(
                name=name, labels=list(label), **kwargs
            ).start()
        else:
            from_qualified_name(retrieved_agent)(name=name, labels=list(label)).start()


@agent.command(hidden=True)
@click.argument("name", default="kubernetes")
@click.option(
    "--token", "-t", required=False, help="A Prefect Cloud API token.", hidden=True
)
@click.option(
    "--api", "-a", required=False, help="A Prefect Cloud API URL.", hidden=True
)
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
@click.option(
    "--label",
    "-l",
    multiple=True,
    help="Labels the agent will use to query for flow runs.",
    hidden=True,
)
def install(name, token, api, namespace, image_pull_secrets, resource_manager, label):
    """
    Install an agent. Outputs configuration text which can be used to install on various
    platforms. The Prefect image version will default to your local `prefect.__version__`

    \b
    Arguments:
        name                        TEXT    The name of an agent to start (e.g. `kubernetes`)
                                            Defaults to `kubernetes`

    \b
    Options:
        --token, -t                 TEXT    A Prefect Cloud API token
        --api, -a                   TEXT    A Prefect Cloud API URL
        --namespace, -n             TEXT    Agent namespace to launch workloads
        --image-pull-secrets, -i    TEXT    Name of image pull secrets to use for workloads
        --resource-manager                  Enable resource manager on install
        --label, -l                 TEXT    Labels the agent will use to query for flow runs
                                            Multiple values supported e.g. `-l label1 -l label2`
    """

    supported_agents = {"kubernetes": "prefect.agent.kubernetes.KubernetesAgent"}

    retrieved_agent = supported_agents.get(name, None)

    if not retrieved_agent:
        click.secho("{} is not a supported agent for `install`".format(name), fg="red")
        return

    deployment = from_qualified_name(retrieved_agent).generate_deployment_yaml(
        token=token,
        api=api,
        namespace=namespace,
        image_pull_secrets=image_pull_secrets,
        resource_manager_enabled=resource_manager,
        labels=list(label),
    )
    click.echo(deployment)
