import asyncio

from prefect.blocks import system
from prefect.client import OrionClient
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


def test_register_blocks_from_module():
    invoke_and_assert(
        ["block", "register", "-m", "prefect.blocks.system"],
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
    expected_output = (
        "ID",
        "Type",
        "Name",
        "Slug",
    )

    invoke_and_assert(
        ["block", "ls"],
        expected_code=0,
        expected_output_contains=expected_output,
        expected_line_count=6,
    )


def test_listing_blocks_after_saving_a_block():
    system.JSON(value="a casual test block").save("wildblock")

    expected_output = (
        "ID",
        "Type",
        "Name",
        "Slug",
        "wildblock",
    )

    invoke_and_assert(
        ["block", "ls"],
        expected_code=0,
        expected_output_contains=expected_output,
        expected_line_count=7,
    )


def test_listing_system_block_types():
    expected_output = (
        "Block Types",
        "Name",
        "Slug",
        "Description",
        "Slack",
        "Date Time",
        "Docker Container",
        "GCS",
        "JSON",
        "Kubernetes Cluster Config",
        "Kubernetes Job",
        "Local File System",
        "Process",
        "Remote File System",
        "S3",
        "Secret",
        "Slack Webhook",
    )

    invoke_and_assert(
        ["block", "type", "ls"],
        expected_code=0,
        expected_output_contains=expected_output,
    )
