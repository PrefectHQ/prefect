from subprocess import CalledProcessError
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from prefect.infrastructure.provisioners.container_instance import (
    ContainerInstancePushProvisioner,
)


@pytest.mark.asyncio
async def test_aci_resource_group_creation_creates_new_group():
    provisioner = ContainerInstancePushProvisioner()

    provisioner.azure_cli = MagicMock()
    provisioner.azure_cli.run_command = AsyncMock()

    # First call simulates that the group doesn't exist
    # Second call simulates successful creation of the group
    provisioner.azure_cli.run_command.side_effect = [
        ("not_exists", False),
        ("created", "New resource group created"),
    ]

    await provisioner._create_resource_group()

    expected_calls = [
        call(
            "az group exists --name prefect-aci-push-pool-rg --subscription None",
            return_json=True,
        ),
        call(
            (
                "az group create --name 'prefect-aci-push-pool-rg' --location 'None'"
                " --subscription 'None'"
            ),
            success_message=(
                "Resource group 'prefect-aci-push-pool-rg' created successfully"
            ),
            failure_message=(
                "Failed to create resource group 'prefect-aci-push-pool-rg' in"
                " subscription 'None'"
            ),
            ignore_if_exists=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


@pytest.mark.asyncio
async def test_aci_resource_group_creation_handles_existing_group():
    provisioner = ContainerInstancePushProvisioner()

    provisioner.azure_cli = MagicMock()
    provisioner.azure_cli.run_command = AsyncMock()

    # Simulate that the group already exists
    provisioner.azure_cli.run_command.return_value = ("exists", True)

    await provisioner._create_resource_group()

    expected_calls = [
        call(
            "az group exists --name prefect-aci-push-pool-rg --subscription None",
            return_json=True,
        )
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)
    assert provisioner.azure_cli.run_command.call_count == 1
    assert (
        provisioner.azure_cli.run_command.call_args[0][0].startswith("az group create")
        is False
    )


@pytest.mark.asyncio
async def test_aci_resource_group_creation_handles_errors():
    provisioner = ContainerInstancePushProvisioner()

    # Mock Azure CLI command execution
    provisioner.azure_cli = MagicMock()
    provisioner.azure_cli.run_command = AsyncMock()

    error = CalledProcessError(1, "cmd", output="output", stderr="error")
    provisioner.azure_cli.run_command.side_effect = [("not_exists", None), error]

    with pytest.raises(CalledProcessError):
        await provisioner._create_resource_group()

    expected_calls = [
        call(
            "az group exists --name prefect-aci-push-pool-rg --subscription None",
            return_json=True,
        ),
        call(
            (
                "az group create --name 'prefect-aci-push-pool-rg' --location 'None'"
                " --subscription 'None'"
            ),
            success_message=(
                "Resource group 'prefect-aci-push-pool-rg' created successfully"
            ),
            failure_message=(
                "Failed to create resource group 'prefect-aci-push-pool-rg' in"
                " subscription 'None'"
            ),
            ignore_if_exists=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


@pytest.mark.asyncio
async def test_aci_container_instance_creation_creates_new_instance():
    provisioner = ContainerInstancePushProvisioner()

    provisioner.azure_cli = MagicMock()
    provisioner.azure_cli.run_command = AsyncMock()

    # First call simulates that the container instance doesn't exist
    # Second call simulates successful creation of the container instance
    provisioner.azure_cli.run_command.side_effect = [
        (False, None),  # Container instance does not exist
        ("created", "New container instance created"),  # Successful creation
    ]

    await provisioner._create_container_instance()

    expected_calls = [
        call(
            (
                "az container list --resource-group prefect-aci-push-pool-rg"
                " --subscription None --query"
                " \"[?name=='prefect-aci-push-pool-container']\" --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az container create --name prefect-aci-push-pool-container"
                " --resource-group prefect-aci-push-pool-rg --image"
                " docker.io/prefecthq/prefect:2-latest --location None --subscription"
                " None --restart-policy OnFailure --output json"
            ),
            success_message=(
                "Container instance 'prefect-aci-push-pool-container' created"
                " successfully in resource group 'prefect-aci-push-pool-rg' in location"
                " 'None' in subscription 'None'"
            ),
            failure_message=(
                "Failed to create container instance 'prefect-aci-push-pool-container'"
                " in resource group 'prefect-aci-push-pool-rg' in location 'None' in"
                " subscription 'None'"
            ),
            ignore_if_exists=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


@pytest.mark.asyncio
async def test_aci_container_instance_creation_handles_existing_instance():
    provisioner = ContainerInstancePushProvisioner()

    # Mock Azure CLI command execution
    provisioner.azure_cli = MagicMock()
    provisioner.azure_cli.run_command = AsyncMock()

    # Simulate that the container instance already exists
    provisioner.azure_cli.run_command.return_value = (None, "exists")

    # Perform the container instance creation
    await provisioner._create_container_instance()

    # Assert the Azure CLI command was called correctly for checking existence
    expected_calls = [
        call(
            (
                "az container list --resource-group prefect-aci-push-pool-rg"
                " --subscription None --query"
                " \"[?name=='prefect-aci-push-pool-container']\" --output json"
            ),
            return_json=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)

    # Assert the Azure CLI command was called only once and creation command wasn't executed
    assert provisioner.azure_cli.run_command.call_count == 1
    assert (
        provisioner.azure_cli.run_command.call_args[0][0].startswith(
            "az container create"
        )
        is False
    )


@pytest.mark.asyncio
async def test_aci_container_instance_creation_handles_errors():
    provisioner = ContainerInstancePushProvisioner()

    # Mock Azure CLI command execution
    provisioner.azure_cli = MagicMock()
    provisioner.azure_cli.run_command = AsyncMock()

    error = CalledProcessError(1, "cmd", output="output", stderr="error")
    provisioner.azure_cli.run_command.side_effect = [(False, None), error]

    with pytest.raises(CalledProcessError):
        await provisioner._create_container_instance()

    expected_calls = [
        call(
            (
                "az container list --resource-group prefect-aci-push-pool-rg"
                " --subscription None --query"
                " \"[?name=='prefect-aci-push-pool-container']\" --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az container create --name prefect-aci-push-pool-container"
                " --resource-group prefect-aci-push-pool-rg --image"
                " docker.io/prefecthq/prefect:2-latest --location None --subscription"
                " None --restart-policy OnFailure --output json"
            ),
            success_message=(
                "Container instance 'prefect-aci-push-pool-container' created"
                " successfully in resource group 'prefect-aci-push-pool-rg' in location"
                " 'None' in subscription 'None'"
            ),
            failure_message=(
                "Failed to create container instance 'prefect-aci-push-pool-container'"
                " in resource group 'prefect-aci-push-pool-rg' in location 'None' in"
                " subscription 'None'"
            ),
            ignore_if_exists=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


@pytest.mark.asyncio
async def test_aci_app_registration_creates_new_app():
    provisioner = ContainerInstancePushProvisioner()

    provisioner.azure_cli = MagicMock()
    provisioner.azure_cli.run_command = AsyncMock()

    # First call simulates that the app doesn't exist
    # Second call simulates successful creation of the app
    app_registration = {
        "appId": "12345678-1234-1234-1234-123456789012",
        "displayName": "prefect-aci-push-pool-app",
        "identifierUris": ["https://prefect-aci-push-pool-app"],
    }
    provisioner.azure_cli.run_command.side_effect = [
        (None, None),  # App does not exist
        ("created", app_registration),  # Successful creation
    ]

    await provisioner._create_app_registration()

    expected_calls = [
        call(
            "az ad app list --display-name prefect-aci-push-pool-app --output json",
        ),
        call(
            "az ad app create --display-name prefect-aci-push-pool-app --output json",
            success_message=(
                "App registration 'prefect-aci-push-pool-app' created successfully"
            ),
            failure_message=(
                "Failed to create app registration with name"
                " 'prefect-aci-push-pool-app'"
            ),
            ignore_if_exists=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)
