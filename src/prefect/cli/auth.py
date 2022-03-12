import click
import os
import shutil
import pendulum
from click.exceptions import Abort
from tabulate import tabulate
from pathlib import Path

from prefect import Client, config
from prefect.exceptions import AuthorizationError, ClientError
from prefect.cli.build_register import handle_terminal_error, TerminalError
from prefect.backend import TenantView


# For deleting authentication tokens which have been replaced with API keys
AUTH_TOKEN_SETTINGS_PATH = Path(f"{config.home_dir}/client").expanduser()


def check_override_auth_token():
    # Exists for purging old tokens only
    if config.cloud.get("auth_token"):
        if os.environ.get("PREFECT__CLOUD__AUTH_TOKEN"):
            click.secho(
                "Auth token has been set in the environment. The CLI cannot be used to "
                "manage your auth. Unset the key with `unset PREFECT__CLOUD__AUTH_TOKEN`",
                fg="red",
            )
        else:
            click.secho(
                "Auth token has been set in the config. The CLI cannot be used to "
                "manage your auth. Remove the key from your configuration file.",
                fg="red",
            )
        raise Abort


def abort_on_config_api_key(message: str = None):
    if config.cloud.get("api_key"):
        # Add a leading space if not null
        message = (" " + message) if message else ""
        raise TerminalError(
            "Your API key is set in the Prefect config instead of with the CLI."
            + message
        )


@click.group(hidden=True)
def auth():
    """
    Handle Prefect Cloud authorization.

    \b
    Usage:
        $ prefect auth [COMMAND]

    \b
    Commands:
        login           Log in to Prefect Cloud
        logout          Log out of Prefect Cloud
        list-tenants    List your available tenants
        switch-tenants  Switch to a different tenant
        create-key      Create an API key
        list-keys       List details of existing API keys
        revoke-key      Delete an API key from the backend

    \bExamples:

    \b  Log in using an existing key

    \b    $ prefect auth login --key MY_KEY

    \b  Log out, removing your current key or token

    \b    $ prefect auth logout

    \b  Switch to another tenant by slug

    \b    $ prefect auth switch-tenants --slug test-person

    \b  Create a new API key that expires at the start of the next year

    \b    $ prefect auth create-key -n marvin --expire 2022-1-1
    """
    if config.backend == "server":
        raise click.UsageError(
            "Prefect Server does not have authentication. Change your backend to "
            "Prefect Cloud with `prefect backend cloud` to log in."
        )


@auth.command(hidden=True)
@click.option(
    "--key",
    "-k",
    help="A Prefect Cloud API key.",
)
@handle_terminal_error
def login(key):
    """
    Login to Prefect Cloud

    Create an API key in the UI then login with it here:

        $ prefect auth login -k YOUR-KEY

    You will be switched to the default tenant associated with the key. After login,
    your available tenants can be seen with `prefect auth list-tenants` and you can
    change the default tenant on this machine using `prefect auth switch-tenants`.

    The given key will be stored on disk for later access. Prefect will default to using
    this key for all interaction with the API but frequently overrides can be passed to
    individual commands or functions. To remove your key from disk, see
    `prefect auth logout`.
    """
    if not key:
        raise TerminalError("You must supply an API key!")

    abort_on_config_api_key(
        "To log in with the CLI, remove the config key `prefect.cloud.api_key`"
    )

    # Ignore any tenant id that has been previously set via login
    client = Client(api_key=key)
    client._tenant_id = None

    try:
        tenant_id = client._get_auth_tenant()
    except AuthorizationError:
        raise TerminalError("Unauthorized. Invalid Prefect Cloud API key.")
    except ClientError:
        raise TerminalError("Error attempting to communicate with Prefect Cloud.")
    else:
        client.tenant_id = tenant_id
        client.save_auth_to_disk()
        tenant = TenantView.from_tenant_id(tenant_id)
        click.secho(
            f"Logged in to Prefect Cloud tenant {tenant.name!r} ({tenant.slug})",
            fg="green",
        )
        return


@auth.command(hidden=True)
@click.option(
    "--token",
    "-t",
    help="Log out from the API token based authentication, ignoring API keys",
    is_flag=True,
)
@handle_terminal_error
def logout(token):
    """
    Log out of Prefect Cloud

    This will remove your cached authentication from disk.
    """

    client = Client()

    # Log out of API keys unless given the token flag
    if client.api_key and not token:

        # Check the source of the API key
        abort_on_config_api_key(
            "To log out, remove the config key `prefect.cloud.api_key`"
        )

        click.confirm(
            "Are you sure you want to log out of Prefect Cloud? "
            "This will remove your API key from this machine.",
            default=False,
            abort=True,
        )

        # Clear the key and tenant id then write to the cache
        client.api_key = ""
        client._tenant_id = ""
        client.save_auth_to_disk()

        click.secho("Logged out of Prefect Cloud", fg="green")

    else:
        raise TerminalError(
            "You are not logged in to Prefect Cloud. "
            "Use `prefect auth login` to log in first."
        )


@auth.command()
def purge_tokens():
    check_override_auth_token()

    if not AUTH_TOKEN_SETTINGS_PATH.exists():
        click.secho(
            "The deprecated authentication tokens settings path "
            f"'{AUTH_TOKEN_SETTINGS_PATH}' has already been removed."
        )

    else:
        confirm = click.confirm(
            "Are you sure you want to delete the deprecated authentication token "
            f"settings folder '{AUTH_TOKEN_SETTINGS_PATH}'?"
        )
        if not confirm:
            print("Aborted!")
            return

        shutil.rmtree(AUTH_TOKEN_SETTINGS_PATH)
        print("Removed!")


@auth.command(hidden=True)
@handle_terminal_error
def list_tenants():
    """
    List available tenants
    """
    client = Client()

    try:
        tenants = client.get_available_tenants()
    except AuthorizationError:
        raise TerminalError(
            "You are not authenticated. Use `prefect auth login` first."
        )

    output = []
    for item in tenants:
        active = None
        if item.id == client.tenant_id:
            active = "*"
        output.append([item.name, item.slug, item.id, active])

    click.echo(
        tabulate(
            output,
            headers=["NAME", "SLUG", "ID", ""],
            tablefmt="plain",
            numalign="left",
            stralign="left",
        )
    )


@auth.command(hidden=True)
@click.option(
    "--id", "-i", required=False, help="A Prefect Cloud tenant id.", hidden=True
)
@click.option(
    "--slug", "-s", required=False, help="A Prefect Cloud tenant slug.", hidden=True
)
@click.option(
    "--default",
    "-d",
    is_flag=True,
    help="Switch to the default tenant for your API key",
)
@handle_terminal_error
def switch_tenants(id, slug, default):
    """
    Switch active tenant

    \b
    Options:
        --id, -i    TEXT    A Prefect Cloud tenant id
        --slug, -s  TEXT    A Prefect Cloud tenant slug
    """

    # If the config specifies a tenant explicitly, it is used before this mechanism
    if config.cloud.get("tenant_id"):
        raise TerminalError(
            "Your tenant id has been set in the Prefect config instead of with the "
            "CLI. To switch tenants with the CLI, remove the config key "
            " `prefect.cloud.tenant_id`"
        )

    client = Client()

    if not client.api_key:
        raise TerminalError("You are not logged in!")

    if default:
        # Clear the set tenant on disk
        client.tenant_id = None
        client.save_auth_to_disk()
        click.secho(
            "Tenant restored to the default tenant for your API key: "
            f"{client._get_auth_tenant()}",
            fg="green",
        )
        return

    try:
        tenant_id = client.switch_tenant(tenant_slug=slug, tenant_id=id)
    except AuthorizationError:
        raise TerminalError("Unauthorized. Your API key is not valid for that tenant.")

    client.save_auth_to_disk()
    click.secho(f"Tenant switched to {tenant_id}", fg="green")


@auth.command(hidden=True)
@click.option("--name", "-n", required=True, help="A name to associate with the key")
@click.option(
    "--expire",
    "-e",
    help=(
        "A optional dateutil parsable time to at. "
        "If not given, the key will never expire."
    ),
    default=None,
)
@click.option(
    "--quiet",
    "-q",
    help="If set, only display the created key.",
    is_flag=True,
)
@handle_terminal_error
def create_key(name, expire, quiet):
    """
    Create a Prefect Cloud API key for authentication with your current user
    """
    # TODO: Add service account associated key creation eventually

    # Parse the input expiration
    if expire is not None:
        try:
            expires_at = pendulum.parse(expire, strict=False)
        except pendulum.parsing.exceptions.ParserError as exc:
            raise TerminalError(
                f"Failed to parse expiration time. {exc}\n"
                "Please pass a date in a dateutil parsable format."
            )

        if expires_at.diff(abs=False).in_seconds() > 0:
            raise TerminalError(
                f"Given expiration time {expire!r} is a time in the past: {expires_at}"
            )
        expire_msg = f" that will expire {expires_at.diff_for_humans()}"
    else:
        expires_at = None
        expire_msg = ""

    client = Client()

    # We must retrieve our own user id first since you could be creating a key for a SA
    if not quiet:
        click.echo("Retrieving user information...")

    response = client.graphql({"query": {"auth_info": {"user_id"}}})
    user_id = response.get("data", {}).get("auth_info", {}).get("user_id")
    if not user_id:
        raise TerminalError("Failed to retrieve the current user id from Prefect Cloud")

    # Actually create the key
    if not quiet:
        click.echo(f"Creating key{expire_msg}...")
    response = client.graphql(
        query={
            "mutation($input: create_api_key_input!)": {
                "create_api_key(input: $input)": {"key"}
            }
        },
        variables=dict(
            input=dict(
                name=name,
                user_id=user_id,
                expires_at=expires_at.in_tz("utc").isoformat() if expires_at else None,
            )
        ),
    )

    key = response.get("data", {}).get("create_api_key", {}).get("key")
    if key is None:
        raise TerminalError(f"Unexpected response from Prefect Cloud: {response}")

    if quiet:
        click.echo(key)
    else:
        click.echo(
            "This is the only time this key will be displayed! Store it somewhere safe."
        )
        click.secho(f"Successfully created key: {key}", fg="green")


@auth.command(hidden=True)
@handle_terminal_error
def list_keys():
    """
    List Prefect Cloud API keys

    If you are a tenant admin, this should list all service account keys as well as keys
    you have created.
    """
    client = Client()

    response = client.graphql(
        query={
            "query": {
                "auth_api_key": {
                    "id": True,
                    "name": True,
                    "expires_at": True,
                }
            }
        }
    )
    keys = response.get("data", {}).get("auth_api_key")
    if keys is None:
        raise TerminalError(f"Unexpected response from Prefect Cloud: {response}")

    if not keys:
        click.secho("You have not created any API keys", fg="yellow")

    else:
        click.echo(
            tabulate(
                [(key.name, key.id, key.expires_at or "NEVER") for key in keys],
                headers=["NAME", "ID", "EXPIRES AT"],
                tablefmt="plain",
                numalign="left",
                stralign="left",
            )
        )


@auth.command(hidden=True)
@click.option(
    "--id",
    "-i",
    required=True,
    help="The UUID for the API key to delete.",
)
@handle_terminal_error
def revoke_key(id):
    """
    Revoke a Prefect Cloud API key.
    """
    client = Client()

    output = client.graphql(
        query={
            "mutation($input: delete_api_key_input!)": {
                "delete_api_key(input: $input)": {"success"}
            }
        },
        variables=dict(input=dict(key_id=id)),
    )

    if not output.get("data", None) or not output.data.delete_api_key.success:
        raise TerminalError(f"Unable to revoke key {id!r}")

    click.secho("Key successfully revoked!", fg="green")


@auth.command(hidden=True)
@handle_terminal_error
def status():
    """
    Get the current Prefect authentication status
    """
    client = Client()
    click.echo(f"You are connecting to {client.api_server}")

    if client.api_key:
        click.echo("You are authenticating with an API key")

        try:
            click.echo(f"You are logged in to tenant {client.tenant_id}")
        except Exception as exc:
            click.echo(f"Your authentication is not working: {exc}")

    if AUTH_TOKEN_SETTINGS_PATH.exists():
        click.secho(
            "The authentication tokens settings path still exists. These have been "
            "removed in favor of API keys. We recommend purging old tokens with "
            "`prefect auth purge-tokens`",
            fg="yellow",
        )

    if config.cloud.get("auth_token"):
        if os.environ.get("PREFECT__CLOUD__AUTH_TOKEN"):
            click.secho(
                "An authentication token is set via environment variable. "
                "These have been removed in favor of API keys and the variable will be "
                "ignored. We recommend unsetting the 'PREFECT__CLOUD__AUTH_TOKEN' key",
                fg="yellow",
            )
        else:
            click.secho(
                "An authentication token is set via the prefect config file. "
                "These have been removed in favor of API keys and the setting will be "
                "ignored. We recommend removing the 'prefect.cloud.auth_token' key",
                fg="yellow",
            )

    if not client.api_key:
        click.secho(
            "You are not logged in! Use `prefect auth login` to login with an API key.",
            fg="yellow",
        )
