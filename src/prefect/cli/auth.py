import os

import click
import toml

from prefect import Client


@click.group(hidden=True)
def auth():
    """
    Handle Prefect Cloud authorization.

    \b
    Usage:
        $ prefect auth [COMMAND]

    \b
    Arguments:
        add     Add a Cloud auth token to your Prefect config

    \b
    Examples:
        $ prefect auth add --token MY_TOKEN

    \b
        $ prefect auth add --token MY_TOKEN --config-path ~/.prefect/new-config.toml
    """
    pass


@auth.command(hidden=True)
@click.option(
    "--token", "-t", required=True, help="A Prefect Cloud auth token.", hidden=True
)
@click.option(
    "--config-path",
    "-c",
    default="~/.prefect/config.toml",
    help="Path to your Prefect config.toml",
    hidden=True,
)
def add(token, config_path):
    """
    Add a new Prefect Cloud auth token to use for Cloud communication.

    \b
    Options:
        --token, -t         TEXT    A Prefect Cloud auth token                                          [required]
        --config-path, -c   TEXT    Path to a Prefect config.toml, defaults to `~/.prefect/config.toml`
    """
    abs_directory = os.path.abspath(os.path.expanduser(config_path))
    if not os.path.exists(abs_directory):
        click.secho("{} does not exist".format(config_path), fg="red")
        return

    config = toml.load(abs_directory)
    if not config.get("cloud"):
        config["cloud"] = {}
    config["cloud"]["auth_token"] = token

    with open(abs_directory, "w") as file:
        toml.dump(config, file)
        click.echo("Auth token added to Prefect config")

        client = Client()
        client.token = token
        result = client.graphql(query={"query": "hello"})
        if not result.data.hello:
            click.secho("Error attempting to use Prefect auth token {}".format(result))
