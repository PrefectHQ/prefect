import click


@click.group(hidden=True)
def summarize():
    """
    Summarize Prefect Cloud metadata. *Not yet implemented*

    \b
    Usage:
        $ prefect summarize [OBJECT]

    \b
    Arguments:
        flow-runs   Summarize flow runs over a set timeframe
        projects    Retrieve summary stats about projects

    \b
    Examples:
        $ prefect summarize flow-runs --hours 24 --project My-Project

    \b
        $ prefect summarize flow-runs --start-date MM-DD-YYYY --end-date MM-DD-YYYY

    \b
        $ prefect summarize projects --name My-Project
    """
    pass


@summarize.command(hidden=True)
def flow_runs():
    """
    Summarize flow runs over a set timeframe
    """
    pass


@summarize.command(hidden=True)
def projects():
    """
    Retrieve summary statatistics about projects
    """
    pass
