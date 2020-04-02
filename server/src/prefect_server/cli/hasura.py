# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import os
import shlex
import subprocess
import sys
from pathlib import Path

import click
import requests
import yaml

import prefect_server
from prefect_server import config

HASURA_DIR = Path(prefect_server.__file__).parents[2] / "services" / "hasura"


@click.group()
def hasura():
    """
    Commands for working with Hasura
    """


def apply_hasura_metadata(
    endpoint=None, admin_secret=None, metadata_path=None, verbose=True
):
    if endpoint is None:
        endpoint = f"http://{config.hasura.host}:{config.hasura.port}"
    if admin_secret is None:
        admin_secret = config.hasura.admin_secret
    if metadata_path is None:
        metadata_path = HASURA_DIR / "migrations" / "metadata.yaml"

    endpoint = os.path.join(endpoint, "v1", "query")

    with open(metadata_path, "r") as f:
        metadata = yaml.load(f, Loader=yaml.SafeLoader)

    response = requests.post(
        endpoint,
        json={"type": "replace_metadata", "args": metadata},
        headers={"x-hasura-admin-secret": admin_secret},
    )
    try:
        response.raise_for_status()
        if verbose:
            click.secho(f"Applied Hasura metadata from {metadata_path}")
    except Exception as exc:
        # echo the error
        click.secho(
            f"\nError applying Hasura metadata from {metadata_path}",
            fg="red",
            bold=True,
        )


@hasura.command()
@click.option(
    "--endpoint",
    "-e",
    help="The GraphQL Engine URL",
    default=f"http://{config.hasura.host}:{config.hasura.port}",
)
@click.option(
    "--admin-secret",
    "-k",
    help="The Hasura access key",
    default=config.hasura.admin_secret,
    show_default=False,
)
@click.option(
    "--metadata-path",
    "-m",
    help="The metadata path",
    default=HASURA_DIR / "migrations" / "metadata.yaml",
    show_default=False,
)
def apply_metadata(endpoint, admin_secret, metadata_path):
    """
    Applies Hasura metadata. Overwrites any existing schema.
    """
    response = None

    try:
        click.secho("\nApplying Hasura metadata...")
        apply_hasura_metadata(
            endpoint=endpoint, admin_secret=admin_secret, metadata_path=metadata_path
        )
        click.secho("\nFinished!", fg="green")
    except Exception:
        click.secho("\nCould not apply metadata!", bg="red", bold=True)
        if response is not None:
            raise click.ClickException(response.content)
        raise Exception from None


@hasura.command()
@click.option(
    "--endpoint",
    "-e",
    help="The GraphQL Engine URL",
    default=f"http://{config.hasura.host}:{config.hasura.port}",
)
@click.option(
    "--admin-secret",
    "-k",
    help="The Hasura access key",
    default=config.hasura.admin_secret,
    show_default=False,
)
@click.option(
    "--metadata-path",
    "-m",
    help="The metadata path",
    default=HASURA_DIR / "migrations" / "metadata.yaml",
    show_default=False,
)
def export_metadata(endpoint, admin_secret, metadata_path):
    """
    Exports Hasura metadata. Overwrites any existing schema.
    """
    response = None

    try:
        click.secho("\nExporting Hasura metadata...")
        endpoint = os.path.join(endpoint, "v1", "query")
        response = requests.post(
            endpoint,
            json={"type": "export_metadata", "args": {}},
            headers={"x-hasura-admin-secret": admin_secret},
        )
        response.raise_for_status()

        with open(metadata_path, "w") as f:
            yaml.dump(response.json(), f)

        click.secho("\nFinished!", fg="green")
    except Exception:
        click.secho("\nCould not export metadata!", bg="red", bold=True)
        if response is not None:
            raise click.ClickException(response.content)
        raise Exception from None


@hasura.command()
@click.option(
    "--endpoint",
    "-e",
    help="The GraphQL Engine URL",
    default=f"http://{config.hasura.host}:{config.hasura.port}",
)
@click.option(
    "--admin-secret",
    "-k",
    help="The Hasura access key",
    default=config.hasura.admin_secret,
    show_default=False,
)
def drop_inconsistent_metadata(endpoint, admin_secret):
    """
    Drops inconsistent metadata from Hasura, including any tables or columns that are referenced but not found in the database.
    """
    response = None
    try:
        click.secho("\nDropping inconsistent Hasura metadata...")
        endpoint = os.path.join(endpoint, "v1", "query")
        response = requests.post(
            endpoint,
            json={"type": "drop_inconsistent_metadata", "args": {}},
            headers={"x-hasura-admin-secret": admin_secret},
        )
        response.raise_for_status()

        click.secho("\nFinished!", fg="green")
    except Exception:
        click.secho("\nCould not drop inconsistent metadata!", bg="red", bold=True)
        if response is not None:
            raise click.ClickException(response.content)
        raise Exception from None


@hasura.command()
@click.option(
    "--endpoint",
    "-e",
    help="The GraphQL Engine URL",
    default=f"http://{config.hasura.host}:{config.hasura.port}",
)
@click.option(
    "--admin-secret",
    "-k",
    help="The Hasura access key",
    default=config.hasura.admin_secret,
    show_default=False,
)
def clear_metadata(endpoint, admin_secret):
    """
    Clear Hasura metadata. Overwrites any existing schema.
    """

    response = None

    try:
        click.secho("\nClearing Hasura metadata...")
        endpoint = os.path.join(endpoint, "v1", "query")
        response = requests.post(
            endpoint,
            json={"type": "clear_metadata", "args": {}},
            headers={"x-hasura-admin-secret": admin_secret},
        )
        response.raise_for_status()
        click.secho("\nFinished!", fg="green")
    except Exception:
        click.secho("\nCould not clear metadata!", bg="red", bold=True)
        if response is not None:
            raise click.ClickException(response.content)
        raise Exception from None


@hasura.command()
@click.option(
    "--endpoint",
    "-e",
    help="The GraphQL Engine URL",
    default=f"http://{config.hasura.host}:{config.hasura.port}",
)
@click.option(
    "--admin-secret",
    "-k",
    help="The Hasura access key",
    default=config.hasura.admin_secret,
    show_default=False,
)
def reload_metadata(endpoint, admin_secret):
    """
    Reloads Hasura metadata. Helpful if the Postgres schema has changed.
    """

    response = None

    try:
        click.secho("\nReloading Hasura metadata...")
        endpoint = os.path.join(endpoint, "v1", "query")
        response = requests.post(
            endpoint,
            json={"type": "reload_metadata", "args": {}},
            headers={"x-hasura-admin-secret": admin_secret},
        )
        response.raise_for_status()
        click.secho("\nFinished!", fg="green")
    except Exception:
        click.secho("\nCould not reload metadata!", bg="red", bold=True)
        if response is not None:
            raise click.ClickException(response.content)
        raise Exception from None


@hasura.command()
@click.option(
    "--endpoint",
    "-e",
    help="The GraphQL Engine URL",
    default=f"http://{config.hasura.host}:{config.hasura.port}",
)
@click.option(
    "--admin-secret",
    "-k",
    help="The Hasura access key",
    default=config.hasura.admin_secret,
    show_default=False,
)
def console(endpoint, admin_secret):
    """
    Opens the Hasura console

    Note: requires installing the Hasura CLI. See https://docs.hasura.io/graphql/manual/hasura-cli/install-hasura-cli.html
    """

    try:
        cmd = shlex.split(
            f"hasura console --endpoint {endpoint} --admin-secret {admin_secret} --skip-update-check"
        )
        subprocess.check_output(cmd, cwd=HASURA_DIR)
    except Exception:
        click.secho("\nCould not open console!", bg="red", bold=True)
        raise Exception from None


@hasura.command()
@click.option(
    "--metadata-path",
    "-m",
    help="The metadata path",
    default=HASURA_DIR / "migrations" / "metadata.yaml",
    show_default=False,
)
def format_metadata(metadata_path):
    """
    Sorts and reformats the Hasura metadata
    """
    with open(metadata_path, "r") as f:
        data = yaml.safe_load(f)

    with open(metadata_path, "w") as g:
        yaml.dump(
            prefect_server.utilities.tests.yaml_sorter(data),
            g,
            default_flow_style=False,
        )

    click.secho("Metadata file sorted.", fg="green")
