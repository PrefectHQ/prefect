import asyncio

import pytest

from prefect.blocks import system
from prefect.client import OrionClient
from prefect.exceptions import ObjectNotFound
from prefect.orion import models
from prefect.settings import PREFECT_ORION_BLOCKS_REGISTER_ON_START, temporary_settings
from prefect.testing.cli import invoke_and_assert

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


def test_register_blocks_from_module():
    invoke_and_assert(
        ["block", "register", "-m", "prefect.blocks.core"],
        expected_code=0,
        expected_output_contains=["Successfully registered", "blocks"],
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


def test_register_blocks_from_file(tmp_path, orion_client: OrionClient):
    test_file_path = tmp_path / "test.py"

    with open(test_file_path, "w") as f:
        f.write(TEST_BLOCK_CODE)

    invoke_and_assert(
        ["block", "register", "-f", str(test_file_path)],
        expected_code=0,
        expected_output_contains="Successfully registered 1 block",
    )

    block_type = asyncio.run(
        orion_client.read_block_type_by_slug(slug="testforfileregister")
    )
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
            f"test.txt is not a .py file. Please specify a "
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
        expected_output_contains="Please specify either a module or a file containing blocks to be registered, but not both.",
    )


def test_register_fails_on_multiple_options():
    invoke_and_assert(
        ["block", "register", "-m", "prefect.blocks.blorp", "-f", "fake_file.py"],
        expected_code=1,
        expected_output_contains="Please specify either a module or a file containing blocks to be registered, but not both.",
    )


def test_listing_blocks_when_none_are_registered():
    invoke_and_assert(
        ["block", "ls"],
        expected_output_contains=(
            f"""                           
           ┏━━━━┳━━━━━━┳━━━━━━┳━━━━━━┓
           ┃ ID ┃ Type ┃ Name ┃ Slug ┃
           ┡━━━━╇━━━━━━╇━━━━━━╇━━━━━━┩
           └────┴──────┴──────┴──────┘
            """
        ),
    )


def test_listing_blocks_after_saving_a_block():
    block_id = system.JSON(value="a casual test block").save("wildblock")

    invoke_and_assert(
        ["block", "ls"],
        expected_output_contains=(
            f"""                           
            ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
            ┃ ID                                   ┃ Type ┃ Name      ┃ Slug           ┃
            ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
            │ {block_id} │ JSON │ wildblock │ json/wildblock │
            └──────────────────────────────────────┴──────┴───────────┴────────────────┘  
            """
        ),
    )


def test_listing_system_block_types():
    with temporary_settings({PREFECT_ORION_BLOCKS_REGISTER_ON_START: True}):
        expected_output = (
            "Block Types",
            "Slug",
            "Description",
            "slack",
            "date-time",
            "docker-container",
            "gcs",
            "json",
            "kubernetes-cluster-config",
            "kubernetes-job",
            "local-file-system",
            "process",
            "remote-file-system",
            "s3",
            "secret",
            "slack-webhook",
        )

        invoke_and_assert(
            ["block", "type", "ls"],
            expected_code=0,
            expected_output_contains=expected_output,
        )


def test_inspecting_a_block():
    system.JSON(value="a simple json blob").save("jsonblob")

    expected_output = ("Block Type", "Block id", "value", "a simple json blob")

    invoke_and_assert(
        ["block", "inspect", "json/jsonblob"],
        expected_code=0,
        expected_output_contains=expected_output,
    )


def test_deleting_a_block():
    system.JSON(value="don't delete me please").save("pleasedonterase")

    invoke_and_assert(
        ["block", "delete", "json/pleasedonterase"],
        expected_code=0,
    )

    invoke_and_assert(
        ["block", "inspect", "json/pleasedonterase"],
        expected_code=1,
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
    ]

    invoke_and_assert(
        ["block", "type", "inspect", "testforfileregister"],
        expected_code=0,
        expected_output_contains=expected_output,
    )


def test_deleting_a_block_type(tmp_path, orion_client):
    test_file_path = tmp_path / "test.py"

    with open(test_file_path, "w") as f:
        f.write(TEST_BLOCK_CODE)

    invoke_and_assert(
        ["block", "register", "-f", str(test_file_path)],
        expected_code=0,
        expected_output_contains="Successfully registered 1 block",
    )

    expected_output = [
        "Deleted Block Type",
        "testforfileregister",
    ]

    invoke_and_assert(
        ["block", "type", "delete", "testforfileregister"],
        expected_code=0,
        expected_output_contains=expected_output,
    )

    with pytest.raises(ObjectNotFound):
        block_type = asyncio.run(
            orion_client.read_block_type_by_slug(slug="testforfileregister")
        )


def test_deleting_a_protected_block_type(
    tmp_path, orion_client, install_system_block_types
):
    expected_output = "is a protected block"

    invoke_and_assert(
        ["block", "type", "delete", "json"],
        expected_code=1,
        expected_output_contains=expected_output,
    )
