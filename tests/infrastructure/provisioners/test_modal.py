import shlex
import sys
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID

import pytest

from prefect.blocks.core import Block
from prefect.client.orchestration import PrefectClient
from prefect.infrastructure.provisioners.modal import ModalPushProvisioner


@pytest.fixture(autouse=True)
async def modal_credentials_block_cls():
    class MockModalCredentials(Block):
        _block_type_name = "Modal Credentials"
        token_id: str
        token_secret: str

    await MockModalCredentials.register_type_and_schema()

    return MockModalCredentials


@pytest.fixture
async def modal_credentials_block_id(modal_credentials_block_cls: Block):
    block_doc_id = await modal_credentials_block_cls(
        token_id="existing_id", token_secret="existing_secret"
    ).save("work-pool-name-modal-credentials", overwrite=True)

    return block_doc_id


@pytest.fixture
def mock_run_process():
    with patch("prefect.infrastructure.provisioners.modal.run_process") as mock:
        yield mock


@pytest.fixture
def mock_ainstall_packages():
    with patch("prefect.infrastructure.provisioners.modal.ainstall_packages") as mock:
        yield mock


@pytest.fixture
def mock_modal(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("prefect.infrastructure.provisioners.modal.modal", mock)
    yield mock


@pytest.fixture
def mock_importlib():
    with patch("prefect.infrastructure.provisioners.modal.importlib") as mock:
        yield mock


@pytest.fixture
def mock_confirm():
    with patch("prefect.infrastructure.provisioners.modal.Confirm") as mock:
        yield mock


async def test_provision(
    prefect_client: PrefectClient,
    mock_run_process: AsyncMock,
    mock_modal: MagicMock,
    mock_confirm: MagicMock,
    mock_importlib: MagicMock,
    mock_ainstall_packages: AsyncMock,
):
    """
    Test provision from a clean slate:
        - Modal is not installed
        - Modal token does not exist
        - ModalCredentials block does not exist
    """
    provisioner = ModalPushProvisioner()
    provisioner.console.is_interactive = True

    mock_confirm.ask.side_effect = [
        True,
        True,
        True,
    ]  # confirm provision, install modal, create new token
    mock_importlib.import_module.side_effect = [ModuleNotFoundError, mock_modal]
    # simulate modal token creation
    mock_modal.config.Config.return_value.get.side_effect = [
        None,
        None,
        "mock_id",
        "mock_secret",
    ]

    work_pool_name = "work-pool-name"
    base_job_template = {"variables": {"properties": {"modal_credentials": {}}}}

    result = await provisioner.provision(
        work_pool_name, base_job_template, client=prefect_client
    )

    # Check if the block document exists and has expected values
    block_document = await prefect_client.read_block_document_by_name(
        "work-pool-name-modal-credentials", "modal-credentials"
    )

    assert block_document.data["token_id"] == "mock_id"
    assert block_document.data["token_secret"] == "mock_secret"

    # Check if the base job template was updated
    assert result["variables"]["properties"]["modal_credentials"] == {
        "default": {"$ref": {"block_document_id": str(block_document.id)}},
    }

    mock_ainstall_packages.assert_has_calls(
        [
            call(["modal"]),
        ]
    )

    # Check expected CLI calls
    mock_run_process.assert_has_calls(
        [
            # create new token
            call([shlex.quote(sys.executable), "-m", "modal", "token", "new"]),
        ]
    )


async def test_provision_existing_modal_credentials_block(
    prefect_client: PrefectClient,
    modal_credentials_block_id: UUID,
    mock_run_process: AsyncMock,
):
    """
    Test provision with an existing ModalCredentials block.
    """
    provisioner = ModalPushProvisioner()

    work_pool_name = "work-pool-name"
    base_job_template = {"variables": {"properties": {"modal_credentials": {}}}}

    result = await provisioner.provision(
        work_pool_name, base_job_template, client=prefect_client
    )

    # Check if the base job template was updated
    assert result["variables"]["properties"]["modal_credentials"] == {
        "default": {"$ref": {"block_document_id": str(modal_credentials_block_id)}},
    }

    mock_run_process.assert_not_called()


async def test_provision_existing_modal_credentials(
    prefect_client: PrefectClient,
    mock_run_process: AsyncMock,
    mock_modal: MagicMock,
    mock_confirm: MagicMock,
    mock_importlib: MagicMock,
):
    """
    Test provision where the user has modal installed and an existing Modal configuration.
    """
    provisioner = ModalPushProvisioner()
    mock_confirm.ask.side_effect = [
        True,
    ]  # confirm provision
    mock_importlib.import_module.side_effect = [
        mock_modal
    ]  # modal is already installed
    mock_modal.config.Config.return_value.get.side_effect = [
        "mock_id",
        "mock_secret",
    ]  # modal config exists

    work_pool_name = "work-pool-name"
    base_job_template = {"variables": {"properties": {"modal_credentials": {}}}}

    result = await provisioner.provision(
        work_pool_name, base_job_template, client=prefect_client
    )

    # Check if the block document exists and has expected values
    block_document = await prefect_client.read_block_document_by_name(
        "work-pool-name-modal-credentials", "modal-credentials"
    )

    assert block_document.data["token_id"] == "mock_id"
    assert block_document.data["token_secret"] == "mock_secret"

    # Check if the base job template was updated
    assert result["variables"]["properties"]["modal_credentials"] == {
        "default": {"$ref": {"block_document_id": str(block_document.id)}},
    }

    mock_run_process.assert_not_called()
