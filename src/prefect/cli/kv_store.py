import click

from prefect import config
from prefect.backend import kv_store


@click.group()
def kv():
    """
    Handle Prefect Cloud authorization.

    \b
    Usage:
        $ prefect kv [COMMAND]
    """
    if config.backend == "server":
        raise click.UsageError(
            "Key value commands with server are not currently supported."
        )


@kv.command(name="set")
@click.argument("key")
@click.argument("value")
def set_command(key, value):
    """
    Set a key value pair, overriding existing values if key exists

    \b
    Arguments:
        key         TEXT    Key to set
        value       TEXT    Value associated with key to set
    """
    result = kv_store.set_key_value(key=key, value=value)

    if result is not None:
        click.secho("Key set successfully", fg="green")
    else:
        click.secho("An error occurred setting the key value pair", fg="red")


@kv.command(name="get")
@click.argument("key")
def get_command(key):
    """
    Get the value of a key

    \b
    Arguments:
        key         TEXT    Key to get
    """
    result = kv_store.get_key_value(key=key)
    click.secho(f"Key {key} has value {result}", fg="green")


@kv.command(name="delete")
@click.argument("key")
def delete_command(key):
    """
    Delete a key value pair

    \b
    Arguments:
        key         TEXT    Key to delete
    """
    result = kv_store.delete_key(key=key)
    if result:
        click.secho(f"Key {key} has been deleted", fg="green")
    else:
        click.secho("An error occurred deleting the key", fg="red")


@kv.command(name="list")
def list_command():
    """
    List all key value pairs
    """
    result = kv_store.list_keys()

    if result:
        click.secho("\n".join(result), fg="green")
    else:
        click.secho("No keys found", fg="red")
