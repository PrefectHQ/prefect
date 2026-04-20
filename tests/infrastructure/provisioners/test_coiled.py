import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prefect.blocks.core import Block
from prefect.client.orchestration import PrefectClient
from prefect.infrastructure.provisioners.coiled import CoiledPushProvisioner


@pytest.fixture(autouse=True)
async def coiled_credentials_block_cls():
    class MockCoiledCredentials(Block):
        _block_type_name = "Coiled Credentials"
        api_token: str

    await MockCoiledCredentials.register_type_and_schema()

    return MockCoiledCredentials


@pytest.fixture
async def existing_coiled_credentials_block(coiled_credentials_block_cls: Block):
    work_pool_name = f"work-pool-name-{uuid.uuid4()}"
    block_name = f"{work_pool_name}-coiled-credentials"
    block_doc_id = await coiled_credentials_block_cls(api_token="existing_token").save(
        block_name, overwrite=True
    )
    return {"block_id": block_doc_id, "work_pool_name": work_pool_name}


@pytest.fixture
def mock_run_process():
    with patch("prefect.infrastructure.provisioners.coiled.run_process") as mock:
        yield mock


@pytest.fixture
def mock_coiled(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("prefect.infrastructure.provisioners.coiled.coiled", mock)
    yield mock


@pytest.fixture
def mock_importlib():
    with patch("prefect.infrastructure.provisioners.coiled.importlib") as mock:
        yield mock


@pytest.fixture
def mock_confirm():
    with patch("prefect.infrastructure.provisioners.coiled.Confirm") as mock:
        yield mock


@pytest.fixture
def mock_dask_config():
    with patch(
        "prefect.infrastructure.provisioners.coiled.CoiledPushProvisioner._get_coiled_token"
    ) as mock:
        mock.return_value = "local-api-token-from-dask-config"
        yield mock


async def test_provision(
    prefect_client: PrefectClient,
    mock_run_process: AsyncMock,
    mock_coiled: MagicMock,
    mock_dask_config: MagicMock,
    mock_confirm: MagicMock,
    mock_importlib: MagicMock,
):
    """
    Test provision from a clean slate:
        - Coiled is not installed
        - Coiled token does not exist
        - CoiledCredentials block does not exist
    """
    provisioner = CoiledPushProvisioner()
    provisioner.console.is_interactive = True

    mock_confirm.ask.side_effect = [
        True,
        True,
        True,
    ]  # confirm provision, install coiled, create new token
    mock_importlib.import_module.side_effect = [
        ModuleNotFoundError,
        mock_coiled,
        mock_coiled,
    ]

    work_pool_name = "work-pool-name"
    base_job_template = {"variables": {"properties": {"credentials": {}}}}

    result = await provisioner.provision(
        work_pool_name, base_job_template, client=prefect_client
    )

    # Check if the block document exists and has expected values
    block_document = await prefect_client.read_block_document_by_name(
        "work-pool-name-coiled-credentials", "coiled-credentials"
    )

    assert block_document.data["api_token"] == "local-api-token-from-dask-config"

    # Check if the base job template was updated
    assert result["variables"]["properties"]["credentials"] == {
        "default": {"$ref": {"block_document_id": str(block_document.id)}},
    }


async def test_provision_existing_coiled_credentials_block(
    prefect_client: PrefectClient,
    existing_coiled_credentials_block: dict,
    mock_run_process: AsyncMock,
):
    """
    Test provision with an existing CoiledCredentials block.
    """
    provisioner = CoiledPushProvisioner()

    work_pool_name = existing_coiled_credentials_block["work_pool_name"]
    base_job_template = {"variables": {"properties": {"credentials": {}}}}

    result = await provisioner.provision(
        work_pool_name, base_job_template, client=prefect_client
    )

    # Check if the base job template was updated
    assert result["variables"]["properties"]["credentials"] == {
        "default": {
            "$ref": {
                "block_document_id": str(existing_coiled_credentials_block["block_id"])
            }
        },
    }

    mock_run_process.assert_not_called()


async def test_provision_existing_coiled_credentials(
    prefect_client: PrefectClient,
    mock_run_process: AsyncMock,
    mock_coiled: MagicMock,
    mock_dask_config: MagicMock,
    mock_confirm: MagicMock,
    mock_importlib: MagicMock,
):
    """
    Test provision where the user has coiled installed and an existing Coiled configuration.
    """
    provisioner = CoiledPushProvisioner()
    mock_confirm.ask.side_effect = [
        True,
    ]  # confirm provision
    mock_importlib.import_module.side_effect = [
        mock_coiled,
        mock_coiled,
    ]  # coiled is already installed

    work_pool_name = "work-pool-name"
    base_job_template = {"variables": {"properties": {"credentials": {}}}}

    result = await provisioner.provision(
        work_pool_name, base_job_template, client=prefect_client
    )

    # Check if the block document exists and has expected values
    block_document = await prefect_client.read_block_document_by_name(
        "work-pool-name-coiled-credentials", "coiled-credentials"
    )

    assert block_document.data["api_token"] == "local-api-token-from-dask-config"

    # Check if the base job template was updated
    assert result["variables"]["properties"]["credentials"] == {
        "default": {"$ref": {"block_document_id": str(block_document.id)}},
    }

    mock_run_process.assert_not_called()
