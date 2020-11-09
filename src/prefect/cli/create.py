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
@click.option(
    "--skip-if-exists",
    is_flag=True,
    help="Skip creating the project if it already exists",
    hidden=True,
)
def project(name, description, skip_if_exists):
    """
    Create projects with the Prefect API that organize flows.

    \b
    Arguments:
        name                TEXT    The name of a project to create     [required]

    \b
    Options:
        --description, -d   TEXT    A project description
        --skip-if-exists            Skip creating the project if it already exists

    """
    try:
        project_id = Client().create_project(
            project_name=name,
            project_description=description,
            skip_if_exists=skip_if_exists,
        )
    except ClientError as exc:
        click.echo(f"{type(exc).__name__}: {exc}")
        click.secho("Error creating project", fg="red")
        return

    if project_id:
        message = "{} created".format(name)
    else:
        message = "skipped creating {} as it already exists".format(name)
    click.secho(message, fg="green")
