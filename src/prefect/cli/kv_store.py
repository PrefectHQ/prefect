import sys
import click

from prefect import config
from prefect.backend import kv_store
from prefect.backend.kv_store import NON_CLOUD_BACKEND_ERROR_MESSAGE
from prefect.cli.build_register import (
    handle_terminal_error,
    TerminalError,
    log_exception,
)


@click.group()
def kv():
    """
    Interact with Prefect Cloud KV Store

    \b
    Usage:
        $ prefect kv [COMMAND]
    """
    if config.backend != "cloud":
        click.secho(NON_CLOUD_BACKEND_ERROR_MESSAGE, fg="red")
        sys.exit(1)


@kv.command(name="set")
@click.argument("key")
@click.argument("value")
@handle_terminal_error
def set_command(key, value):
    """
    Set a key value pair, overriding existing values if key exists

    \b
    Arguments:
        key         TEXT    Key to set
        value       TEXT    Value associated with key to set
    """
    try:
        kv_store.set_key_value(key=key, value=value)
        click.secho("Key value pair set successfully", fg="green")
    except Exception as exc:
        log_exception(exc)
        raise TerminalError("An error occurred setting the key value pair")


@kv.command(name="get")
@click.argument("key")
@handle_terminal_error
def get_command(key):
    """
    Get the value of a key

    \b
    Arguments:
        key         TEXT    Key to get
    """
    try:
        result = kv_store.get_key_value(key=key)
        click.secho(f"Key {key!r} has value {result!r}", fg="green")
    except Exception as exc:
        log_exception(exc)
        raise TerminalError(f"Error retrieving value for key {key!r}")


@kv.command(name="delete")
@click.argument("key")
@handle_terminal_error
def delete_command(key):
    """
    Delete a key value pair

    \b
    Arguments:
        key         TEXT    Key to delete
    """
    try:
        kv_store.delete_key(key=key)
        click.secho(f"Key {key!r} has been deleted", fg="green")
    except Exception as exc:
        log_exception(exc)
        raise TerminalError("An error occurred deleting the key")


@kv.command(name="list")
@handle_terminal_error
def list_command():
    """
    List all key value pairs
    """
    try:
        result = kv_store.list_keys()
        if result:
            click.secho("\n".join(result), fg="green")
        else:
            click.secho("No keys found", fg="yellow")
    except Exception as exc:
        log_exception(exc)
        raise TerminalError("An error occurred when listing keys")
