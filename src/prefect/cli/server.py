import click


@click.group(hidden=True)
def server():
    """
    Commands for interacting with the Prefect Server

    \b
    Usage:
        $ prefect server ...

    \b
    Arguments:
        up   ...

    \b
    Examples:
        $ prefect server up
        ...

    \b
        $ prefect server services
        ...
    """


@server.command(hidden=True)
def up():
    """
    Server up
    """
    pass
