import click

from prefect import config
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
            click.secho("{} is not a valid agent".format(name), color="red")
            return

        from_qualified_name(retrieved_agent)().start()
