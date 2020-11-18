import click

from prefect.client import Client
from prefect.utilities.exceptions import ClientError


@click.group(hidden=True)
def create():
    """
    Create commands that refer to mutations of Prefect API metadata.

    \b
    Usage:
        $ prefect create [OBJECT]

    \b
    Arguments:
        project    Create projects

    \b
    Examples:
        $ prefect create project "Hello, World!"
        Hello, World! created

    \b
        $ prefect create project "Hello, World!" --description "My description"
        Hello, World! created
    """


@create.command(hidden=True)
@click.argument("name", required=True)
@click.option("--description", "-d", help="Project description to create", hidden=True)
def project(name, description):
    """
    Create projects with the Prefect API that organize flows. Does nothing if
    the project already exists.

    \b
    Arguments:
        name                TEXT    The name of a project to create     [required]

    \b
    Options:
        --description, -d   TEXT    A project description

    """
    try:
        Client().create_project(project_name=name, project_description=description)
    except ClientError as exc:
        click.echo(f"{type(exc).__name__}: {exc}")
        click.secho("Error creating project", fg="red")
        return

    click.secho("{} created".format(name), fg="green")
