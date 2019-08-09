import click

from prefect import config
from prefect import agent as prefect_agent
from prefect.utilities.configuration import set_temporary_config

_agents = {
    "local": prefect_agent.local.LocalAgent,
    "kubernetes": prefect_agent.kubernetes.KubernetesAgent,
    "nomad": prefect_agent.nomad.NomadAgent,
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
def start(name, token):
    """
    Start an agent.

    \b
    Arguments:
        name            TEXT    The name of an agent to start (e.g. `local`, `kubernetes`, `nomad`)
                                Defaults to `local`

    \b
    Options:
        --token, -t     TEXT    A Prefect Cloud api token
    """
    with set_temporary_config(
        {"cloud.agent.auth_token": token or config.cloud.agent.auth_token}
    ):
        retrieved_agent = _agents.get(name, None)

        if not retrieved_agent:
            click.secho(f"{name} is not a valid agent", color="red")
            return

        retrieved_agent().start()
