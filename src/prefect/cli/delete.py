import click

from prefect.client import Client


@click.group(hidden=True)
def delete():
    """
    Delete commands that refer to mutations of Prefect API metadata.

    \b
    Usage:
        $ prefect delete [OBJECT]

    \b
    Arguments:
        project    Delete projects

    \b
    Examples:
        $ prefect delete project "Goodbye, World!"
        Goodbye, World! deleted

    """


@delete.command(hidden=True)
@click.argument("name", required=True)
def project(name):
    """
    Delete projects with the Prefect API that organize flows.

    \b
    Arguments:
        name                TEXT    The name of a project to delete     [required]

    """
    try:
        Client().delete_project(project_name=name)
    except ValueError as exc:
        click.echo(f"{type(exc).__name__}: {exc}")
        click.secho("Error deleting project", fg="red")
        return

    click.secho("{} deleted".format(name), fg="green")
