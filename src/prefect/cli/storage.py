"""
Command line interface for managing storage settings
"""
import json
from typing import Any, Callable, Coroutine, Dict, Tuple

import pendulum
import typer

from prefect.cli.base import app, console, exit_with_error, exit_with_success
from prefect.client import get_client
from prefect.settings import PREFECT_HOME
from prefect.utilities.asyncio import sync_compatible

storage_config_app = typer.Typer(
    name="storage",
    help="Commands for managing storage settings",
)
app.add_typer(storage_config_app)


async def configure_temp_storage():
    return ("tempstorage-block", dict())


async def configure_local_storage():
    local_data = dict()
    console.print("Follow the prompts to configure local filesystem storage")
    local_data["storage_path"] = typer.prompt(
        "What directory would you like to persist data to?",
        default=PREFECT_HOME.value() / "storage",
        show_default=True,
    )
    return ("localstorage-block", local_data)


async def configure_orion_storage():
    return ("orionstorage-block", dict())


async def configure_s3_storage():
    console.print("Follow the prompts to configure S3 storage")
    s3_data = dict()

    aws_access_key_id = typer.prompt(
        "AWS access_key_id", default="None", show_default=True
    )
    s3_data["aws_access_key_id"] = (
        aws_access_key_id if aws_access_key_id != "None" else None
    )

    aws_secret_access_key = typer.prompt(
        "AWS secret_access_key", default="None", show_default=True
    )
    s3_data["aws_secret_access_key"] = (
        aws_secret_access_key if aws_secret_access_key != "None" else None
    )

    aws_session_token = typer.prompt(
        "AWS session_token", default="None", show_default=True
    )
    s3_data["aws_session_token"] = (
        aws_session_token if aws_session_token != "None" else None
    )

    profile_name = typer.prompt("AWS profile_name", default="None", show_default=True)
    s3_data["profile_name"] = profile_name if profile_name != "None" else None

    region_name = typer.prompt("AWS region_name", default="None", show_default=True)
    s3_data["region_name"] = region_name if region_name != "None" else None

    s3_data["bucket"] = typer.prompt(
        "To which S3 bucket would you like to persist data?"
    )

    return ("s3storage-block", s3_data)


async def configure_google_cloud_storage():
    console.print("Follow the prompts to configure Google Cloud Storage")
    gcs_data = dict()

    gcs_data["project"] = typer.prompt(
        "Which GCP project would like to use for storage?",
        default=None,
        show_default=True,
    )

    gcs_data["bucket"] = typer.prompt(
        "To which GCS bucket would you like to persist data?"
    )

    path_to_service_account_credentials = typer.prompt(
        "What is the path to your service account credentials file?",
        default=None,
        show_default=True,
    )
    try:
        with open(path_to_service_account_credentials, "r") as sa_creds_file:
            gcs_data["service_account_info"] = json.load(sa_creds_file)
    except FileNotFoundError:
        exit_with_error("Unable to find service account credentials file")
    except json.JSONDecodeError:
        exit_with_error(
            "Unable to parse service account credentials file. Is it a valid json file?"
        )

    return ("googlecloudstorage-block", gcs_data)


async def configure_azure_blob_storage():
    console.print("Follow the prompts to configure Azure Blob Storage")
    abs_data = dict()
    abs_data["container"] = typer.prompt(
        "To which Azure Blob container would you like to persist data?"
    )
    abs_data["connection_string"] = typer.prompt(
        "What is your Azure connection string?"
    )

    return ("azureblobstorage-block", abs_data)


storage_configuration_procedures: Dict[
    str, Callable[..., Coroutine[Any, Any, Tuple[str, Dict[str, str]]]]
] = dict(
    temp=configure_temp_storage,
    local=configure_local_storage,
    orion=configure_orion_storage,
    s3=configure_s3_storage,
    gcs=configure_google_cloud_storage,
    azure_blob=configure_azure_blob_storage,
)


@storage_config_app.command()
@sync_compatible
async def configure(storage_type: str):

    valid_storageblocks = storage_configuration_procedures.keys()
    if storage_type not in valid_storageblocks:
        exit_with_error(
            f"Invalid storage type: pick one of {list(valid_storageblocks)}"
        )

    async with get_client() as client:
        await client.update_block_name(
            name="ORION-CONFIG-STORAGE",
            new_name=f"ORION-CONFIG-STORAGE-ARCHIVED-{pendulum.now('UTC')}",
            raise_for_status=False,
        )

        block_ref, data = await storage_configuration_procedures[storage_type]()

        await client.create_block(
            name="ORION-CONFIG-STORAGE",
            blockref=block_ref,
            **data,
        )

        exit_with_success("Successfully configured Orion storage location!")
