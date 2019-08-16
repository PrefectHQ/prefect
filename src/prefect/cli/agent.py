import click

from prefect import config, context
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.serialization import from_qualified_name

_agents = {
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

    \b
    Examples:
        $ prefect agent start

    \b
        $ prefect agent start kubernetes --token MY_TOKEN
    """
    pass


@agent.command(hidden=True)
@click.argument("name", default="local")
@click.option(
    "--token", "-t", required=False, help="A Prefect Cloud API token.", hidden=True
)
@click.option("--no-pull", is_flag=True, help="Pull images flag.", hidden=True)
def start(name, token, no_pull):
    """
    Start an agent.

    \b
    Arguments:
        name            TEXT    The name of an agent to start (e.g. `local`, `kubernetes`, `nomad`)
                                Defaults to `local`

    \b
    Options:
        --token, -t     TEXT    A Prefect Cloud api token
        --no-pull               Pull images for a LocalAgent
                                Defaults to pulling if not provided
    """
    with set_temporary_config(
        {"cloud.agent.auth_token": token or config.cloud.agent.auth_token}
    ):
        retrieved_agent = _agents.get(name, None)

        if not retrieved_agent:
            click.secho("{} is not a valid agent".format(name), color="red")
            return

        with context(no_pull=no_pull):
            from_qualified_name(retrieved_agent)().start()
