import re

from typer.testing import CliRunner

from prefect.cli import app

EXISTING_STORAGE_OPTIONS = {
    "Azure Blob Storage",
    "File Storage",
    "Google Cloud Storage",
    "Temporary Local Storage",
    "Local Storage",
    "S3 Storage",
}


def get_first_menu_and_fail(number_string: str = "99999999"):
    """
    Utility function to get output of first step of `prefect storage create` and exit

    Output as of May 11, 2022 (note - last line is in red)
    ---------
    Found the following storage types:
    0) Azure Blob Storage
        Store data in an Azure blob storage container.
    1) File Storage
        Store data as a file on local or remote file systems.
    2) Google Cloud Storage
        Store data in a GCS bucket.
    3) Temporary Local Storage
        Store data in a temporary directory in a run's local file system.
    4) Local Storage
        Store data in a run's local file system.
    5) S3 Storage
        Store data in an AWS S3 bucket.
    Select a storage type to create: 99999999
    \x1b[31mInvalid selection 99999999\x1b[0m
    """
    command = ["storage", "create"]
    runner = CliRunner()
    result = runner.invoke(app, command, input=number_string, catch_exceptions=False)

    return result


def test_invalid_number_selection_fails():
    """
    We need to make sure that if we give an invalid number that the CLI
    will exit.
    """
    number_string = "99999999"
    result = get_first_menu_and_fail(number_string)
    lines = result.stdout.splitlines()
    # Strange string addition are due to coloring, I believe
    assert lines[-1] == f"\x1b[31mInvalid selection {number_string}\x1b[0m"
    assert result.exit_code == 1


def test_storage_options_presented_correctly():
    # number followed by close-paren, followed by space
    base_pat = r"[0-9]+\) "
    result = get_first_menu_and_fail()

    for option in EXISTING_STORAGE_OPTIONS:
        pat = base_pat + option
        assert re.search(pat, result.stdout)

    # Sanity check because regex is black magic
    assert re.search(pat + "dog", result.stdout) == None


def test_storage_create_hides_kv_ss():
    result = get_first_menu_and_fail()
    assert "KV Server Storage" not in result.stdout
