import click

from prefect import Client
from prefect.utilities.exceptions import AuthorizationError, ClientError


@click.group(hidden=True)
def auth():
    """
    Handle Prefect Cloud authorization.

    \b
    Usage:
        $ prefect auth [COMMAND]

    \b
    Arguments:
        login       Login to Prefect Cloud

    \b
    Examples:
        $ prefect auth login --token MY_TOKEN

    \b
        $ prefect auth login --token MY_TOKEN
    """
    pass


@auth.command(hidden=True)
@click.option(
    "--token", "-t", required=True, help="A Prefect Cloud API token.", hidden=True
)
def login(token):
    """
    Login to Prefect Cloud with an api token to use for Cloud communication.

    \b
    Options:
        --token, -t         TEXT    A Prefect Cloud api token  [required]
    """

    client = Client()
    client.login(api_token=token)

    # Verify login obtained a valid api token
    try:
        client.graphql(query={"query": "hello"})
    except AuthorizationError:
        click.secho(
            "Error attempting to use Prefect API token {}".format(token), color="RED"
        )
        return
    except ClientError:
        click.secho("Error attempting to communicate with Prefect Cloud", color="RED")
        return

    click.echo("Login successful")
