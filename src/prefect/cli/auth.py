import click
import os
import pendulum
from click.exceptions import Abort
from tabulate import tabulate

from prefect import Client, config
from prefect.exceptions import AuthorizationError, ClientError
from prefect.cli.build_register import handle_terminal_error, TerminalError
from prefect.backend import TenantView


def check_override_auth_token():
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
        create-token    Create an API token (DEPRECATED)
        list-tokens     List the names and ids of existing API tokens (DEPRECATED)
        revoke-token    Delete an API token from the backend (DEPRECATED)

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
@click.option(
    "--token",
    "-t",
    help="A Prefect Cloud API token. DEPRECATED.",
)
@handle_terminal_error
def login(key, token):
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

    This command has backwards compatibility support for API tokens, which are a
    deprecated form of authentication with Prefect Cloud
    """
    if not key and not token:
        raise TerminalError("You must supply an API key or token!")

    if key and token:
        raise TerminalError("You cannot supply both an API key and token")

    abort_on_config_api_key(
        "To log in with the CLI, remove the config key `prefect.cloud.api_key`"
    )

    # Attempt to treat the input like an API key even if it is passed as a token
    # Ignore any tenant id that has been previously set via login
    client = Client(api_key=key or token, tenant_id=None)

    try:
        tenant_id = client._get_auth_tenant()
    except AuthorizationError:
        if key:  # We'll catch an error again later if using a token
            raise TerminalError("Unauthorized. Invalid Prefect Cloud API key.")
    except ClientError:
        raise TerminalError("Error attempting to communicate with Prefect Cloud.")
    else:
        if token:
            click.secho(
                "WARNING: You logged in with an API key using the `--token` flag "
                "which is deprecated. Please use `--key` instead.",
                fg="yellow",
            )
        client.tenant_id = tenant_id
        client.save_auth_to_disk()
        tenant = TenantView.from_tenant_id(tenant_id)
        click.secho(
            f"Logged in to Prefect Cloud tenant {tenant.name!r} ({tenant.slug})",
            fg="green",
        )
        return

        # If there's not a tenant id, we've been given an actual token, fallthrough to
        # the backwards compatibility token auth

    # Backwards compatibility for tokens
    if token:
        check_override_auth_token()
        client = Client(api_token=token)

        # Verify they're not also using an API key
        if client.api_key:
            raise TerminalError(
                "You have already logged in with an API key and cannot use a token."
            )

        click.secho(
            "WARNING: API tokens are deprecated. Please create an API key and use "
            "`prefect auth login --key <KEY>` to login instead.",
            fg="yellow",
        )

        # Verify login obtained a valid api token
        try:
            output = client.graphql(
                query={"query": {"user": {"default_membership": "tenant_id"}}}
            )

            # Log into default membership
            success_login = client.login_to_tenant(
                tenant_id=output.data.user[0].default_membership.tenant_id
            )

            if not success_login:
                raise AuthorizationError

        except AuthorizationError:
            click.secho(
                "Error attempting to use the given API token. "
                "Please check that you are providing a USER scoped Personal Access Token "
                "and consider switching API key.",
                fg="red",
            )
            return
        except ClientError:
            click.secho(
                "Error attempting to communicate with Prefect Cloud. "
                "Please check that you are providing a USER scoped Personal Access Token "
                "and consider switching API key.",
                fg="red",
            )
            return

        # save token
        client.save_api_token()

        click.secho("Login successful!", fg="green")


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

    elif client._api_token:

        check_override_auth_token()
        tenant_id = client.active_tenant_id

        if not tenant_id:
            click.confirm(
                "Are you sure you want to log out of Prefect Cloud? "
                "This will remove your API token from this machine.",
                default=False,
                abort=True,
            )

            # Remove the token from local storage by writing blank settings
            client._save_local_settings({})
            click.secho("Logged out of Prefect Cloud", fg="green")

        else:
            # Log out of the current tenant (dropping the access token) while retaining
            # the API token. This is backwards compatible behavior. Running the logout
            # command twice will remove the token from storage entirely
            click.confirm(
                "Are you sure you want to log out of your current Prefect Cloud tenant?",
                default=False,
                abort=True,
            )

            client.logout_from_tenant()

            click.secho(
                f"Logged out from tenant {tenant_id}. Run `prefect auth logout` again "
                "to delete your API token.",
                fg="green",
            )
    else:
        raise TerminalError(
            "You are not logged in to Prefect Cloud. "
            "Use `prefect auth login` to log in first."
        )


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

    # Deprecated API token check
    if not client.api_key:
        check_override_auth_token()

        if default:
            raise TerminalError(
                "The default tenant flag can only be used with API keys."
            )

    else:  # Using an API key
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

    login_success = client.login_to_tenant(tenant_slug=slug, tenant_id=id)
    if not login_success:
        raise TerminalError("Unable to switch tenant!")

    # `login_to_tenant` will write to disk if using an API token, if using an API key
    # we will write to disk manually here
    if client.api_key:
        client.save_auth_to_disk()

    click.secho(f"Tenant switched to {client.tenant_id}", fg="green")


@auth.command(hidden=True)
@click.option("--name", "-n", required=True, help="A token name.", hidden=True)
@click.option("--scope", "-s", required=True, help="A token scopre.", hidden=True)
def create_token(name, scope):
    """
    DEPRECATED. Please use API keys instead.

    Create a Prefect Cloud API token.

    For more info on API tokens visit https://docs.prefect.io/orchestration/concepts/api.html

    \b
    Options:
        --name, -n      TEXT    A name to give the generated token
        --scope, -s     TEXT    A scope for the token
    """
    click.secho(
        "WARNING: API tokens are deprecated. Please use `prefect auth create-key` to "
        "create an API key instead.",
        fg="yellow",
        err=True,  # Write to stderr in case the user is piping
    )

    client = Client()

    output = client.graphql(
        query={
            "mutation($input: create_api_token_input!)": {
                "create_api_token(input: $input)": {"token"}
            }
        },
        variables=dict(input=dict(name=name, scope=scope)),
    )

    if not output.get("data", None):
        click.secho("Issue creating API token", fg="red")
        return

    click.echo(output.data.create_api_token.token)


@auth.command(hidden=True)
def list_tokens():
    """
    DEPRECATED. Please use API keys instead.

    List your available Prefect Cloud API tokens.
    """
    click.secho(
        "WARNING: API tokens are deprecated. Please consider removing your remaining "
        "tokens and using API keys instead.",
        fg="yellow",
        err=True,  # Write to stderr in case the user is piping
    )

    client = Client()
    output = client.graphql(query={"query": {"api_token": {"id", "name"}}})

    if not output.get("data", None):
        click.secho("Unable to list API tokens", fg="red")
        return

    tokens = []
    for item in output.data.api_token:
        tokens.append([item.name, item.id])

    click.echo(
        tabulate(
            tokens,
            headers=["NAME", "ID"],
            tablefmt="plain",
            numalign="left",
            stralign="left",
        )
    )


@auth.command(hidden=True)
@click.option("--id", "-i", required=True, help="A token ID.", hidden=True)
def revoke_token(id):
    """
    DEPRECATED. Please use API keys instead.

    Revote a Prefect Cloud API token

    \b
    Options:
        --id, -i    TEXT    The id of a token to revoke
    """
    check_override_auth_token()

    client = Client()

    output = client.graphql(
        query={
            "mutation($input: delete_api_token_input!)": {
                "delete_api_token(input: $input)": {"success"}
            }
        },
        variables=dict(input=dict(token_id=id)),
    )

    if not output.get("data", None) or not output.data.delete_api_token.success:
        click.secho("Unable to revoke token with ID {}".format(id), fg="red")
        return

    click.secho("Token successfully revoked", fg="green")


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

    if client._api_token:
        click.secho(
            "You are logged in with an API token. These have been deprecated in favor "
            "of API keys."
            + (
                " Since you have set an API key as well, this will be ignored."
                if client.api_key
                else ""
            ),
            fg="yellow",
        )

    if not client._api_token and not client.api_key:
        click.secho("You are not logged in!", fg="yellow")
