import click


@click.group(hidden=True)
def auth():
    """
    Handle Prefect Cloud authorization.
    """
    pass


@auth.command()
@click.option("--token", "-t", required=True, help="A Prefect Cloud auth token.")
def add(token):
    """
    Add a new Prefect Cloud auth token to use.
    """
    pass
