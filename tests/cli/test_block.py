import pytest

from prefect.blocks import system
from prefect.client.orchestration import PrefectClient
from prefect.exceptions import ObjectNotFound
from prefect.server import models
from prefect.settings import (
    PREFECT_UI_URL,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread

TEST_BLOCK_CODE = """\
from prefect.blocks.core import Block

class TestForFileRegister(Block):
    message: str
"""
TEST_BLOCK_CODE_BAD_SYNTAX = """\
from prefect.blocks.core import Bloc

class TestForFileRegister(Block):
    message: str
"""


@pytest.fixture
async def install_system_block_types(session):
    return await models.block_registration._install_protected_system_blocks(
        session=session
    )


def test_register_blocks_from_module_with_ui_url():
    with temporary_settings(set_defaults={PREFECT_UI_URL: "https://app.prefect.cloud"}):
        invoke_and_assert(
            ["block", "register", "-m", "prefect.blocks.system"],
            expected_code=0,
            expected_output_contains=[
                "Successfully registered",
                "blocks",
            ],
        )


def test_register_blocks_from_module_without_ui_url(
    disable_hosted_api_server, enable_ephemeral_server
):
    with temporary_settings(set_defaults={PREFECT_UI_URL: None}):
        invoke_and_assert(
            ["block", "register", "-m", "prefect.blocks.system"],
            expected_code=0,
            expected_output_contains=[
                "Successfully registered",
                "blocks",
                "Prefect UI",
            ],
            expected_output_does_not_contain=["Prefect UI: https://"],
        )


def test_register_blocks_no_blocks_found_to_register():
    invoke_and_assert(
        ["block", "register", "-m", "prefect.blocks.core"],
        expected_code=1,
        expected_output_contains=[
            "No blocks were registered from module 'prefect.blocks.core'",
            "Please make sure the module 'prefect.blocks.core' contains valid blocks",
        ],
    )


def test_register_blocks_from_nonexistent_module():
    invoke_and_assert(
        ["block", "register", "-m", "prefect.blocks.blorp"],
        expected_code=1,
        expected_output_contains=(
            "Unable to load prefect.blocks.blorp. Please make sure "
            "the module is installed in your current environment."
        ),
    )


def test_register_blocks_from_invalid_module():
    invoke_and_assert(
        ["block", "register", "-m", "prefect-aws.credentials"],
        expected_code=1,
        expected_output_contains=(
            "Unable to load prefect-aws.credentials. Please make sure "
            "the module is installed in your current environment."
        ),
    )


async def test_register_blocks_from_file(tmp_path, prefect_client: PrefectClient):
    test_file_path = tmp_path / "test.py"

    with open(test_file_path, "w") as f:
        f.write(TEST_BLOCK_CODE)

    with temporary_settings(set_defaults={PREFECT_UI_URL: "https://app.prefect.cloud"}):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            ["block", "register", "-f", str(test_file_path)],
            expected_code=0,
            expected_output_contains=[
                "Successfully registered 1 block",
                "blocks/catalog",
            ],
        )

    block_type = prefect_client.read_block_type_by_slug(slug="testforfileregister")
    assert block_type is not None


def test_register_blocks_from_nonexistent_file():
    invoke_and_assert(
        ["block", "register", "-f", "fake_file.py"],
        expected_code=1,
        expected_output_contains=(
            "Unable to load file at fake_file.py. "
            "Please make sure the file path is correct and the file contains "
            "valid Python."
        ),
    )


def test_register_blocks_from_txt_file(tmp_path):
    test_file_path = tmp_path / "test.txt"

    with open(test_file_path, "w") as f:
        f.write("Trust me, there's a block in here.")

    invoke_and_assert(
        ["block", "register", "-f", "test.txt"],
        expected_code=1,
        expected_output_contains=(
            "test.txt is not a .py file. Please specify a "
            ".py that contains blocks to be registered."
        ),
    )


def test_register_blocks_from_file_bad_syntax(tmp_path):
    test_file_path = tmp_path / "test.py"

    with open(test_file_path, "w") as f:
        f.write(TEST_BLOCK_CODE_BAD_SYNTAX)

    invoke_and_assert(
        ["block", "register", "-f", str(test_file_path)],
        expected_code=1,
        expected_output_contains=(
            f"Unable to load file at {test_file_path}. "
            "Please make sure the file path is correct and the file contains "
            "valid Python."
        ),
    )


def test_register_fails_on_no_options():
    invoke_and_assert(
        ["block", "register"],
        expected_code=1,
        expected_output_contains=(
            "Please specify either a module or a file containing blocks to be"
            " registered, but not both."
        ),
    )


def test_register_fails_on_multiple_options():
    invoke_and_assert(
        ["block", "register", "-m", "prefect.blocks.blorp", "-f", "fake_file.py"],
        expected_code=1,
        expected_output_contains=(
            "Please specify either a module or a file containing blocks to be"
            " registered, but not both."
        ),
    )


def test_listing_blocks_when_none_are_registered():
    invoke_and_assert(
        ["block", "ls"],
        expected_output_contains="""
           ┏━━━━┳━━━━━━┳━━━━━━┳━━━━━━┓
           ┃ ID ┃ Type ┃ Name ┃ Slug ┃
           ┡━━━━╇━━━━━━╇━━━━━━╇━━━━━━┩
           └────┴──────┴──────┴──────┘
            """,
    )


async def test_listing_blocks_after_saving_a_block():
    block_id = await system.Secret(value="a casual test block").save("wildblock")

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=["block", "ls"],
        expected_output_contains=[
            "ID",
            "Type",
            "Name",
            "Slug",
            str(block_id),
            "Secret",
            "wildblock",
            "secret/wildblock",
        ],
    )


def test_listing_system_block_types(register_block_types):
    expected_output = (
        "Block Types",
        "Slug",
        "Description",
        "slack",
        "date-time",
        "json",
        "local-file-system",
        "remote-file-system",
        "secret",
        "slack-webhook",
    )

    invoke_and_assert(
        ["block", "type", "ls"],
        expected_code=0,
        expected_output_contains=expected_output,
    )


async def test_inspecting_a_block(ignore_prefect_deprecation_warnings):
    await system.JSON(value="a simple json blob").save("jsonblob")

    expected_output = ("Block Type", "Block id", "value", "a simple json blob")

    await run_sync_in_worker_thread(
        invoke_and_assert,
        ["block", "inspect", "json/jsonblob"],
        expected_code=0,
        expected_output_contains=expected_output,
    )


def test_inspecting_a_block_malformed_slug():
    invoke_and_assert(
        ["block", "inspect", "chonk-block"],
        expected_code=1,
        expected_output_contains="'chonk-block' is not valid. Slug must contain a '/'",
    )


async def test_deleting_a_block():
    await system.Secret(value="don't delete me please").save("pleasedonterase")

    await run_sync_in_worker_thread(
        invoke_and_assert,
        ["block", "delete", "secret/pleasedonterase"],
        user_input="y",
        expected_code=0,
    )

    await run_sync_in_worker_thread(
        invoke_and_assert,
        ["block", "inspect", "secret/pleasedonterase"],
        expected_code=1,
    )


def test_deleting_a_block_malformed_slug():
    invoke_and_assert(
        ["block", "delete", "chonk-block"],
        expected_code=1,
        expected_output_contains="'chonk-block' is not valid. Slug must contain a '/'",
    )


def test_inspecting_a_block_type(tmp_path):
    test_file_path = tmp_path / "test.py"

    with open(test_file_path, "w") as f:
        f.write(TEST_BLOCK_CODE)

    invoke_and_assert(
        ["block", "register", "-f", str(test_file_path)],
        expected_code=0,
        expected_output_contains="Successfully registered 1 block",
    )

    expected_output = [
        "Slug",
        "Block Type id",
        "Description",
        "TestForFileRegister",
        "testforfileregister",
        "Schema Properties",
        "message",
        "Message",
    ]

    invoke_and_assert(
        ["block", "type", "inspect", "testforfileregister"],
        expected_code=0,
        expected_output_contains=expected_output,
    )


async def test_deleting_a_block_type(tmp_path, prefect_client):
    test_file_path = tmp_path / "test.py"

    with open(test_file_path, "w") as f:
        f.write(TEST_BLOCK_CODE)

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=["block", "register", "-f", str(test_file_path)],
        expected_code=0,
        expected_output_contains="Successfully registered 1 block",
    )

    expected_output = [
        "Deleted Block Type",
        "testforfileregister",
    ]

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=["block", "type", "delete", "testforfileregister"],
        expected_code=0,
        user_input="y",
        expected_output_contains=expected_output,
    )

    with pytest.raises(ObjectNotFound):
        await prefect_client.read_block_type_by_slug(slug="testforfileregister")


def test_deleting_a_protected_block_type(
    tmp_path, prefect_client, install_system_block_types
):
    expected_output = "is a protected block"

    invoke_and_assert(
        ["block", "type", "delete", "json"],
        expected_code=1,
        user_input="y",
        expected_output_contains=expected_output,
    )
