#!/usr/bin/env python

import os

import click

import prefect
from prefect.utilities import backend as backend_util

from .agent import agent as _agent
from .auth import auth as _auth
from .create import create as _create
from .delete import delete as _delete
from .describe import describe as _describe
from .execute import execute as _execute
from .get import get as _get
from .run import run as _run
from .server import server as _server
from .heartbeat import heartbeat as _heartbeat
from .build_register import register as _register, build as _build
from .kv_store import kv as _kv


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
        delete      Delete objects
        execute     Execute a flow run
        run         Run a flow
        register    Register flows with an API
        heartbeat   Send heartbeats for a run

    \b
    Setup Commands:
        auth        Handle Prefect Cloud authorization
        backend     Switch between `server` and `cloud` backends
        server      Interact with the Prefect Server

    \b
    Miscellaneous Commands:
        version     Print the current Prefect version
        config      Output Prefect config
        diagnostics Output Prefect diagnostic information
    """
    pass


cli.add_command(_agent)
cli.add_command(_auth)
cli.add_command(_create)
cli.add_command(_delete)
cli.add_command(_describe)
cli.add_command(_execute)
cli.add_command(_get)
cli.add_command(_run)
cli.add_command(_server)
cli.add_command(_heartbeat)
cli.add_command(_register)
cli.add_command(_build)
cli.add_command(_kv)


# Miscellaneous Commands


@cli.command()
def repl():
    """
    Start an interactive Prefect CLI session
    """
    banner = f"""
Welcome to the Prefect REPL
version : {prefect.__version__}
    """

    try:
        from click_repl import repl as _repl
    except ImportError:
        print(
            """
This command requires the 'click-repl' package. Install it first to use this feature:
python -m pip install click-repl
"""
        )
        exit(1)

    from prompt_toolkit.history import FileHistory

    history_path = os.path.join(prefect.config.home_dir, "repl-history")
    prompt_kwargs = {
        "history": FileHistory(history_path),
    }

    click.echo(banner)
    _repl(click.get_current_context(), prompt_kwargs=prompt_kwargs)


@cli.command(hidden=True)
def version():
    """
    Get the current Prefect version
    """
    click.echo(prefect.__version__)


@cli.command(hidden=True)
def config():
    """
    Output Prefect config
    """
    click.echo(prefect.config.to_json())


@cli.command(hidden=True)
@click.option(
    "--include-secret-names",
    help="Output Prefect diagnostic information",
    hidden=True,
    is_flag=True,
)
def diagnostics(include_secret_names):
    """
    Output Prefect diagnostic information

    \b
    Options:
        --include-secret-names    Enable output of potential Secret names
    """
    click.echo(
        prefect.utilities.diagnostics.diagnostic_info(
            include_secret_names=bool(include_secret_names)
        )
    )


@cli.command(hidden=True)
@click.argument("api")
def backend(api):
    """
    Switch Prefect API backend to either `server` or `cloud`
    """
    if api not in ["server", "cloud"]:
        click.secho("{} is not a valid backend API".format(api), fg="red")
        return

    backend_util.save_backend(api)
    click.secho("Backend switched to {}".format(api), fg="green")


__all__ = ["backend_util"]
