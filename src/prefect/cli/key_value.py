import click

from prefect import Client, config


@click.group(hidden=True)
def kv():
    """
    Handle Prefect Cloud authorization.

    \b
    Usage:
        $ prefect kv [COMMAND]

    \b
    Arguments:
        set             Set a key value pair
        get             Get the value associated with a key
        delete          Delete a key value pair
        list            List keys

    \b
    Examples:
        $ prefect kv set foo bar

    \b
        $ prefect kv get my_key
        bar

    \b
        $ prefect kv list
        foo

    \b
        $ prefect kv delete foo
        Key foo has been deleted
    """
    if config.backend == "server":
        raise click.UsageError(
            "Key value commands with server are not currently supported."
        )


@kv.command(name="set", hidden=True)
@click.argument("key")
@click.argument("value")
def _set(key, value):
    """
    Set a key value pair, overriding existing values if key exists

    \b
    Arguments:
        key         TEXT    Key to set
        value       TEXT    Value associated with key to set
    """
    client = Client()
    result = client.set_key_value(key=key, value=value)

    if result is not None:
        click.secho("Key set successfully", fg="green")
    else:
        click.echo("An error occurred setting the key value pair", fg="red")


@kv.command(hidden=True)
@click.argument("key")
def get(key):
    """
    Get the value of a key

    \b
    Arguments:
        key         TEXT    Key to get
    """
    client = Client()
    result = client.get_key_value(key=key)
    click.secho(f"Key {key} has value {result}", fg="green")


@kv.command(hidden=True)
@click.argument("key")
def delete(key):
    """
    Delete a key value pair

    \b
    Arguments:
        key         TEXT    Key to delete
    """
    client = Client()
    result = client.delete_key_value(key=key)
    if result:
        click.secho(f"Key {key} has been deleted", fg="green")
    else:
        click.secho("An error occurred deleting the key", fg="red")


@kv.command(name="list", hidden=True)
def _list():
    """
    List all key value pairs
    """
    client = Client()
    result = client.list_keys()

    if result:
        click.secho("\n".join(result), fg="green")
    else:
        click.secho("No keys found", fg="red")
