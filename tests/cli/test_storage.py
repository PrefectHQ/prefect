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
