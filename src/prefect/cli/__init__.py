#!/usr/bin/env python


import click

import prefect

from .agent import agent as _agent
from .auth import auth as _auth
from .create import create as _create
from .describe import describe as _describe
from .execute import execute as _execute
from .get import get as _get
from .run import run as _run


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """
    The Prefect CLI for creating, managing, and inspecting your flows.

    \b
    Note: a Prefect Cloud API token is required for all Cloud related commands. If a token
    is not set then run `prefect auth login` to set it.

    \b
    Query Commands:
        get         List high-level object information
        describe    Retrieve detailed object descriptions

    \b
    Action Commands:
        agent       Manage agents
        create      Create objects
        execute     Execute a flow's environment
        run         Run a flow

    \b
    Setup Commands:
        auth        Handle Prefect Cloud authorization

    \b
    Miscellaneous Commands:
        version     Get your current Prefect version
        config      Output your Prefect config
    """
    pass


cli.add_command(_agent)
cli.add_command(_auth)
cli.add_command(_create)
cli.add_command(_describe)
cli.add_command(_execute)
cli.add_command(_get)
cli.add_command(_run)


# Miscellaneous Commands


@cli.command(hidden=True)
def version():
    """
    Get your current Prefect version
    """
    click.echo(prefect.__version__)


@cli.command(hidden=True)
def config():
    """
    Output your Prefect config
    """
    click.echo(prefect.config.to_dict())
