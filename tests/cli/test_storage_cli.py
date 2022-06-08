import re

import click.testing
from typer.testing import CliRunner

from prefect.cli import app
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock

EXISTING_STORAGE_OPTIONS = {
    "Azure Blob Storage",
    "File Storage",
    "Google Cloud Storage",
    "Temporary Local Storage",
    "Local Storage",
    "S3 Storage",
}

INVALID_OPTION = "99999999"


def get_first_menu_and_fail() -> click.testing.Result:
    """
    Utility function to get output of first step of `prefect storage create` and exit
    """
    command = ["storage", "create"]
    runner = CliRunner()
    result = runner.invoke(app, command, input=INVALID_OPTION, catch_exceptions=False)

    return result


def test_get_first_menu_and_fail():
    """
    Make sure that our utility function is returning as expected
    """
    part_one = f"""
    Found the following storage types:
    0) Azure Blob Storage
        Store data in an Azure blob storage container.
    1) File Storage
        Store data as a file on local or remote file systems.
    2) Google Cloud Storage
        Store data in a GCS bucket.
    3) Local Storage
        Store data in a run's local file system.
    """

    part_two = "Select a storage type to create: 99999999"
    part_three = f"Invalid selection {INVALID_OPTION}"

    command = ["storage", "create"]
    invoke_and_assert(
        command=command,
        user_input=f"{INVALID_OPTION}\n",
        expected_output_contains=(part_one, part_two, part_three),
        expected_code=1,
    )


def test_invalid_number_selection_fails():
    """
    We need to make sure that if we give an invalid number that the CLI
    will exit.
    """
    result = get_first_menu_and_fail()
    lines = result.stdout.splitlines()
    assert f"Invalid selection {INVALID_OPTION}" in lines[-1]
    assert result.exit_code == 1


def test_no_schemas_found(monkeypatch):
    """
    The schemas should always be populated on API startup but in cases where they are
    not we expect a nice error message instead of an exception
    """
    read_block_schemas = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "prefect.client.OrionClient.read_block_schemas", read_block_schemas
    )
    invoke_and_assert(
        command=["storage", "create"],
        expected_output="No storage types are available.",
        expected_code=1,
    )


def test_storage_options_presented_correctly():
    """
    Test uses a regex that can be built on to make a more flexible
    test for the future. Exact string match currently fails due to
    issue with state from other tests.
    """
    # number followed by close-paren, followed by space
    base_pat = r"[0-9]+\) "
    result = get_first_menu_and_fail()

    for option in EXISTING_STORAGE_OPTIONS:
        pat = base_pat + option
        assert re.search(pat, result.stdout)

    # Sanity check because regex is black magic
    assert re.search(pat + "dog", result.stdout) == None


def test_storage_create_hides_kv_ss():
    """
    Make sure that KV Server Storage is not exposed to the user.
    """
    undesired_contents = "KV Server Storage"

    invoke_and_assert(
        command=["storage", "create"],
        user_input=f"{INVALID_OPTION}\n",
        expected_output_does_not_contain=undesired_contents,
        expected_code=1,
    )
