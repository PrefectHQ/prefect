import click

from prefect.client import Client
from prefect.utilities.exceptions import ClientError


@click.group(hidden=True)
def create():
    """
    Create commands that refer to mutations of Prefect Cloud metadata.

    \b
    Usage:
        $ prefect create [OBJECT]

    \b
    Arguments:
        project    Create projects

    \b
    Examples:
        $ prefect create project -n My-Project
        My-Project created

    \b
        $ prefect create project -n My-Project --description "My description"
        My-Project created
    """
    pass


@create.command(hidden=True)
@click.option(
    "--name", "-n", help="Project name to create.", required=True, hidden=True
)
@click.option("--description", "-d", help="Project description to create", hidden=True)
def project(name, description):
    """
    Create projects in Prefect Cloud that organize flows.

    \b
    Options:
        --name, -n          TEXT    A project name to create    [required]
        --description, -d   TEXT    A project description

    """
    try:
        Client().create_project(project_name=name, project_description=description)
    except ClientError:
        click.secho("Error creating project", fg="red")
        return

    click.secho("{} created".format(name), fg="green")
