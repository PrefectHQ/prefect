import json
import subprocess
from subprocess import CalledProcessError
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.blocks.core import Block
from prefect.blocks.fields import SecretDict
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import BlockDocumentCreate
from prefect.infrastructure.provisioners.container_instance import (
    ContainerInstancePushProvisioner,
)

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field
else:
    from pydantic import Field


@pytest.fixture
async def existing_credentials_block(prefect_client: PrefectClient):
    # Mock the existing credentials block
    block_type = await prefect_client.read_block_type_by_slug(
        slug="azure-container-instance-credentials"
    )
    block_schema = await prefect_client.get_most_recent_block_schema_for_block_type(
        block_type_id=block_type.id
    )
    assert block_schema is not None

    # Create a mock block document representing the existing credentials
    block_document = await prefect_client.create_block_document(
        block_document=BlockDocumentCreate(
            name="test-work-pool-push-pool-credentials",
            data={
                "client_id": "12345678-1234-1234-1234-123456789012",
                "tenant_id": "9ee4947a-f114-4939-a5ac-7f0ed786de36",
                "client_secret": "<MY_SECRET>",  # noqa
            },
            block_type_id=block_type.id,
            block_schema_id=block_schema.id,
        )
    )

    yield block_document.id  # This will be used in the tests

    # Clean up: delete the mock block document after the test
    await prefect_client.delete_block_document(block_document_id=block_document.id)


@pytest.fixture
def default_base_job_template():
    command = [
        "prefect",
        "work-pool",
        "get-default-base-job-template",
        "--type",
        "azure-container-instance",
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0:
        return json.loads(result.stdout)
    else:
        pytest.fail(f"Command failed: {result.stderr}")


@pytest.fixture(autouse=True)
async def aci_credentials_block_type_and_schema():
    class MockACICredentials(Block):
        _block_type_name = "Azure Container Instance Credentials"
        service_account_info: Optional[SecretDict] = Field(
            default=None, description="The contents of the keyfile as a dict."
        )

    await MockACICredentials.register_type_and_schema()


@pytest.fixture(autouse=True)
async def provisioner():
    provisioner = ContainerInstancePushProvisioner()
    yield provisioner


@pytest.fixture(autouse=True)
async def azure_cli(provisioner):
    provisioner.azure_cli = MagicMock()
    provisioner.azure_cli.run_command = AsyncMock()


async def test_aci_az_installed(provisioner):
    provisioner.azure_cli.run_command.side_effect = [
        ("2.0.0", "2.0.0"),  # Azure CLI is installed
        (None, '{"account_a": "b"}'),
    ]

    await provisioner._verify_az_ready()

    expected_calls = [
        call("az --version", ignore_if_exists=True),
        call("az account list --output json", return_json=True),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


async def test_select_subscription(provisioner):
    subscriptions_list = [
        {
            "cloudName": "AzureCloud",
            "id": "12345678-1234-1234-1234-123456789012",
            "isDefault": True,
            "name": "None",
            "state": "Enabled",
            "tenantId": "12345678-1234-1234-1234-123456789012",
        }
    ]

    provisioner.azure_cli.run_command.side_effect = [
        (None, subscriptions_list),
    ]

    await provisioner._select_subscription()

    expected_calls = [
        call(
            "az account list --output json",
            failure_message=(
                "No Azure subscriptions found. Please create an Azure subscription and"
                " try again."
            ),
            ignore_if_exists=True,
            return_json=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


async def test_set_location(provisioner):
    provisioner.azure_cli.run_command.side_effect = [
        (None, "westus"),
    ]

    await provisioner.set_location()

    expected_calls = [
        call('az account list-locations --query "[?isDefault].name" --output tsv'),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


async def test_aci_resource_group_creation_creates_new_group(provisioner):
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


async def test_aci_resource_group_creation_handles_existing_group(provisioner):
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


async def test_aci_resource_group_creation_handles_errors(provisioner):
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


async def test_aci_container_instance_creation_creates_new_instance(provisioner):
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


async def test_aci_container_instance_creation_handles_existing_instance(provisioner):
    provisioner.azure_cli.run_command.return_value = (None, "exists")

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
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)

    assert provisioner.azure_cli.run_command.call_count == 1
    assert (
        provisioner.azure_cli.run_command.call_args[0][0].startswith(
            "az container create"
        )
        is False
    )


async def test_aci_container_instance_creation_handles_errors(provisioner):
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


async def test_aci_app_registration_creates_new_app(provisioner):
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


async def test_aci_app_registration_handles_existing_app(provisioner):
    app_registration = [
        {
            "appId": "12345678-1234-1234-1234-123456789012",
            "displayName": "prefect-aci-push-pool-app",
            "identifierUris": ["https://prefect-aci-push-pool-app"],
        }
    ]
    provisioner.azure_cli.run_command.return_value = (None, app_registration)

    await provisioner._create_app_registration()

    expected_calls = [
        call(
            "az ad app list --display-name prefect-aci-push-pool-app --output json",
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)

    assert provisioner.azure_cli.run_command.call_count == 1
    assert (
        provisioner.azure_cli.run_command.call_args[0][0].startswith("az ad app create")
        is False
    )


async def test_aci_app_registration_handles_errors(provisioner):
    error = CalledProcessError(1, "cmd", output="output", stderr="error")
    provisioner.azure_cli.run_command.side_effect = [(None, None), error]

    with pytest.raises(CalledProcessError):
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


async def test_aci_service_principal_creation_creates_new_principal(provisioner):
    # First call simulates that the principal doesn't exist
    # Second call simulates successful creation of the principal
    service_principal = [
        {
            "accountEnabled": True,
            "addIns": [],
            "alternativeNames": [],
            "appDescription": None,
            "appDisplayName": "prefect-aci-push-pool-app",
            "appId": "bcbeb824-fc3a-41f7-afc0-fc00297c1355",
        }
    ]

    provisioner.azure_cli.run_command.side_effect = [
        (None, []),  # Principal does not exist
        ("created", service_principal),  # Successful creation
        (None, ["12345678-1234-1234-1234-123456789012"]),  # Principal object ID
    ]

    await provisioner._get_or_create_service_principal_object_id(
        app_id="bcbeb824-fc3a-41f7-afc0-fc00297c1355"
    )
    expected_calls = [
        call(
            (
                "az ad sp list --all --query"
                " \"[?appId=='bcbeb824-fc3a-41f7-afc0-fc00297c1355']\" --output json"
            ),
            return_json=True,
        ),
        call(
            "az ad sp create --id bcbeb824-fc3a-41f7-afc0-fc00297c1355",
            success_message=(
                "Service principal created for app ID"
                " 'bcbeb824-fc3a-41f7-afc0-fc00297c1355'"
            ),
            failure_message=(
                "Failed to create service principal for app ID"
                " 'bcbeb824-fc3a-41f7-afc0-fc00297c1355'"
            ),
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


async def test_aci_service_principal_creation_handles_existing_principal(provisioner):
    service_principal = [
        {
            "accountEnabled": True,
            "addIns": [],
            "alternativeNames": [],
            "appDescription": None,
            "appDisplayName": "prefect-aci-push-pool-app",
            "appId": "bcbeb824-fc3a-41f7-afc0-fc00297c1355",
        }
    ]
    provisioner.azure_cli.run_command.return_value = (None, service_principal)

    await provisioner._get_or_create_service_principal_object_id(
        app_id="bcbeb824-fc3a-41f7-afc0-fc00297c1355"
    )

    expected_calls = [
        call(
            (
                "az ad sp list --all --query"
                " \"[?appId=='bcbeb824-fc3a-41f7-afc0-fc00297c1355']\" --output json"
            ),
            return_json=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)

    assert provisioner.azure_cli.run_command.call_count == 1
    assert (
        provisioner.azure_cli.run_command.call_args[0][0].startswith("az ad sp create")
        is False
    )


async def test_aci_service_principal_creation_handles_errors(provisioner):
    error = CalledProcessError(1, "cmd", output="output", stderr="error")
    provisioner.azure_cli.run_command.side_effect = [(None, []), error]

    with pytest.raises(CalledProcessError):
        await provisioner._get_or_create_service_principal_object_id(
            app_id="bcbeb824-fc3a-41f7-afc0-fc00297c1355"
        )

    expected_calls = [
        call(
            (
                "az ad sp list --all --query"
                " \"[?appId=='bcbeb824-fc3a-41f7-afc0-fc00297c1355']\" --output json"
            ),
            return_json=True,
        ),
        call(
            "az ad sp create --id bcbeb824-fc3a-41f7-afc0-fc00297c1355",
            success_message=(
                "Service principal created for app ID"
                " 'bcbeb824-fc3a-41f7-afc0-fc00297c1355'"
            ),
            failure_message=(
                "Failed to create service principal for app ID"
                " 'bcbeb824-fc3a-41f7-afc0-fc00297c1355'"
            ),
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


async def test_aci_assign_contributor_role(provisioner):
    service_principal = [
        {
            "accountEnabled": True,
            "addIns": [],
            "alternativeNames": [],
            "appDescription": None,
            "appDisplayName": "prefect-aci-push-pool-app",
            "appId": "bcbeb824-fc3a-41f7-afc0-fc00297c1355",
        }
    ]

    provisioner.azure_cli.run_command.side_effect = [
        (None, []),  # Principal does not exist
        ("created", service_principal),  # Successful creation
        (None, [{"id": "12345678-1234-1234-1234-123456789012"}]),  # Principal object ID
        (
            "created",
            [{"roleDefinitionName": None, "scope": None}],
        ),  # Successful creation
        (None, None),
    ]

    await provisioner._assign_contributor_role(
        app_id="bcbeb824-fc3a-41f7-afc0-fc00297c1355"
    )

    expected_calls = [
        call(
            (
                "az ad sp list --all --query"
                " \"[?appId=='bcbeb824-fc3a-41f7-afc0-fc00297c1355']\" --output json"
            ),
            return_json=True,
        ),
        call(
            "az ad sp create --id bcbeb824-fc3a-41f7-afc0-fc00297c1355",
            success_message=(
                "Service principal created for app ID"
                " 'bcbeb824-fc3a-41f7-afc0-fc00297c1355'"
            ),
            failure_message=(
                "Failed to create service principal for app ID"
                " 'bcbeb824-fc3a-41f7-afc0-fc00297c1355'"
            ),
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


async def test_aci_assign_contributor_role_handles_existing_role(provisioner):
    service_principal = [
        {
            "accountEnabled": True,
            "addIns": [],
            "alternativeNames": [],
            "appDescription": None,
            "appDisplayName": "prefect-aci-push-pool-app",
            "appId": "bcbeb824-fc3a-41f7-afc0-fc00297c1355",
        }
    ]

    role = "Contributor"
    scope = "/subscriptions/None/resourceGroups/prefect-aci-push-pool-rg"

    provisioner.azure_cli.run_command.side_effect = [
        (None, []),  # Principal does not exist
        ("created", service_principal),  # Successful creation
        (None, [{"id": "12345678-1234-1234-1234-123456789012"}]),  # Principal object ID
        (
            "created",
            [{"roleDefinitionName": role, "scope": scope}],
        ),  # Successful creation
    ]

    await provisioner._assign_contributor_role(
        app_id="bcbeb824-fc3a-41f7-afc0-fc00297c1355"
    )

    expected_calls = [
        call(
            (
                "az ad sp list --all --query"
                " \"[?appId=='bcbeb824-fc3a-41f7-afc0-fc00297c1355']\" --output json"
            ),
            return_json=True,
        ),
        call(
            "az ad sp create --id bcbeb824-fc3a-41f7-afc0-fc00297c1355",
            success_message=(
                "Service principal created for app ID"
                " 'bcbeb824-fc3a-41f7-afc0-fc00297c1355'"
            ),
            failure_message=(
                "Failed to create service principal for app ID"
                " 'bcbeb824-fc3a-41f7-afc0-fc00297c1355'"
            ),
        ),
        call(
            (
                "az ad sp list --all --query"
                " \"[?appId=='bcbeb824-fc3a-41f7-afc0-fc00297c1355']\" --output json"
            ),
            failure_message=(
                "Failed to retrieve new service principal for app ID"
                " bcbeb824-fc3a-41f7-afc0-fc00297c1355"
            ),
            return_json=True,
        ),
        call(
            (
                "az role assignment list --assignee"
                " 12345678-1234-1234-1234-123456789012 --role Contributor --scope"
                " /subscriptions/None/resourceGroups/prefect-aci-push-pool-rg --output"
                " json"
            ),
            return_json=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


async def test_aci_assign_contributor_role_handles_error(provisioner):
    service_principal = [
        {
            "accountEnabled": True,
            "addIns": [],
            "alternativeNames": [],
            "appDescription": None,
            "appDisplayName": "prefect-aci-push-pool-app",
            "appId": "bcbeb824-fc3a-41f7-afc0-fc00297c1355",
        }
    ]

    error = CalledProcessError(1, "cmd", output="output", stderr="error")
    provisioner.azure_cli.run_command.side_effect = [
        (None, []),  # Principal does not exist
        ("created", service_principal),  # Successful creation
        (None, [{"id": "12345678-1234-1234-1234-123456789012"}]),  # Principal object ID
        error,
    ]

    with pytest.raises(CalledProcessError):
        await provisioner._assign_contributor_role(
            app_id="bcbeb824-fc3a-41f7-afc0-fc00297c1355"
        )

    expected_calls = [
        call(
            (
                "az ad sp list --all --query"
                " \"[?appId=='bcbeb824-fc3a-41f7-afc0-fc00297c1355']\" --output json"
            ),
            return_json=True,
        ),
        call(
            "az ad sp create --id bcbeb824-fc3a-41f7-afc0-fc00297c1355",
            success_message=(
                "Service principal created for app ID"
                " 'bcbeb824-fc3a-41f7-afc0-fc00297c1355'"
            ),
            failure_message=(
                "Failed to create service principal for app ID"
                " 'bcbeb824-fc3a-41f7-afc0-fc00297c1355'"
            ),
        ),
        call(
            (
                "az ad sp list --all --query"
                " \"[?appId=='bcbeb824-fc3a-41f7-afc0-fc00297c1355']\" --output json"
            ),
            failure_message=(
                "Failed to retrieve new service principal for app ID"
                " bcbeb824-fc3a-41f7-afc0-fc00297c1355"
            ),
            return_json=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


async def test_aci_provision_az_not_installed(provisioner):
    provisioner.azure_cli.run_command.side_effect = CalledProcessError(
        1, "cmd", output="output", stderr="error"
    )

    with pytest.raises(RuntimeError, match="Azure CLI is not installed"):
        await provisioner.provision(
            work_pool_name="test-work-pool",
            base_job_template={},
        )

    expected_calls = [
        call("az --version", ignore_if_exists=True),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


async def test_aci_provision_no_existing_credentials_block(
    default_base_job_template,
    prefect_client: PrefectClient,
    provisioner: ContainerInstancePushProvisioner,
):
    subscription_list = [
        {
            "cloudName": "AzureCloud",
            "id": "12345678-1234-1234-1234-123456789012",
            "isDefault": True,
            "name": "subscription_1",
            "state": "Enabled",
            "tenantId": "12345678-1234-1234-1234-123456789012",
        }
    ]

    app_registration = {
        "appId": "12345678-1234-1234-1234-123456789012",
        "displayName": "prefect-aci-push-pool-app",
        "identifierUris": ["https://prefect-aci-push-pool-app"],
    }

    client_secret = (
        '{"appId": "5407b48a-a28d-49ea-a740-54504847153f", "password":'
        ' "<MY_SECRET>", "tenant":'  # noqa
        ' "9ee4947a-f114-4939-a5ac-7f0ed786de36"}'
    )

    new_service_principal = [
        {
            "id": "abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c",
            "accountEnabled": True,
            "addIns": [],
            "alternativeNames": [],
            "appDescription": None,
            "appDisplayName": "prefect-aci-push-pool-app",
            "appId": "bcbeb824-fc3a-41f7-afc0-fc00297c1355",
        }
    ]

    role_assignments = {
        "roleDefinitionName": "Contributor",
        # "scope": "/subscriptions/None/resourceGroups/prefect-aci-push-pool-rg",
    }

    provisioner.azure_cli.run_command.side_effect = [
        ("2.0.0", "2.0.0"),  # Azure CLI is installed
        (None, subscription_list),  # I don't know what call this is from
        (None, subscription_list),  # Select subscription
        (None, "westus"),  # Set location
        (None, None),  # Resource group does not exist
        ("created", "New resource group created"),  # Successful creation
        (None, None),  # App does not exist
        ("created", app_registration),  # Successful creation
        (None, client_secret),  # Generate app secret
        (None, []),  # Principal does not exist
        ("created", None),  # Successful creation
        ("created", new_service_principal),  # Successful retrieval
        (None, []),  # Role does not exist
        ("created", role_assignments),  # Successful creation
        (None, []),  # Container instance does not exist
        (None, None),  # Successful creation
    ]

    new_base_job_template = await provisioner.provision(
        work_pool_name="test-work-pool",
        base_job_template=default_base_job_template,
    )

    assert new_base_job_template

    expected_calls = [
        # _verify_az_ready
        call("az --version", ignore_if_exists=True),
        call("az account list --output json", return_json=True),
        # _select_subscription
        call(
            "az account list --output json",
            failure_message=(
                "No Azure subscriptions found. Please create an Azure subscription and"
                " try again."
            ),
            ignore_if_exists=True,
            return_json=True,
        ),
        # _set_location
        call('az account list-locations --query "[?isDefault].name" --output tsv'),
        # _create_resource_group
        call(
            (
                "az group exists --name prefect-aci-push-pool-rg --subscription"
                " 12345678-1234-1234-1234-123456789012"
            ),
            return_json=True,
        ),
        call(
            (
                "az group create --name 'prefect-aci-push-pool-rg' --location 'westus'"
                " --subscription '12345678-1234-1234-1234-123456789012'"
            ),
            success_message=(
                "Resource group 'prefect-aci-push-pool-rg' created successfully"
            ),
            failure_message=(
                "Failed to create resource group 'prefect-aci-push-pool-rg' in"
                " subscription 'subscription_1'"
            ),
            ignore_if_exists=True,
        ),
        # _create_app_registration
        call("az ad app list --display-name prefect-aci-push-pool-app --output json"),
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
        # _create secret
        call(
            (
                "az ad app credential reset --id 12345678-1234-1234-1234-123456789012"
                " --append --output json"
            ),
            success_message=(
                "Secret generated for app registration with client ID"
                " '12345678-1234-1234-1234-123456789012'"
            ),
            failure_message=(
                "Failed to generate secret for app registration with client ID"
                " '12345678-1234-1234-1234-123456789012'. If you have already generated"
                " 2 secrets for this app registration, please delete one from the"
                " `prefect-aci-push-pool-app` resource and try again."
            ),
            ignore_if_exists=True,
            return_json=True,
        ),
        # _create_service_principal
        call(
            (
                "az ad sp list --all --query"
                " \"[?appId=='12345678-1234-1234-1234-123456789012']\" --output json"
            ),
            return_json=True,
        ),
        call(
            "az ad sp create --id 12345678-1234-1234-1234-123456789012",
            success_message=(
                "Service principal created for app ID"
                " '12345678-1234-1234-1234-123456789012'"
            ),
            failure_message=(
                "Failed to create service principal for app ID"
                " '12345678-1234-1234-1234-123456789012'"
            ),
        ),
        call(
            (
                "az ad sp list --all --query"
                " \"[?appId=='12345678-1234-1234-1234-123456789012']\" --output json"
            ),
            failure_message=(
                "Failed to retrieve new service principal for app ID"
                " 12345678-1234-1234-1234-123456789012"
            ),
            return_json=True,
        ),
        # _assign_contributor_role
        call(
            (
                "az role assignment list --assignee"
                " abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c --role Contributor --scope"
                " /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg"
                " --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az role assignment create --role Contributor --assignee-object-id"
                " abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c --scope"
                " /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg"
            ),
            success_message=(
                "Contributor role assigned to service principal with object ID"
                " 'abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c'"
            ),
            failure_message=(
                "Failed to assign Contributor role to service principal with object ID"
                " 'abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c'"
            ),
            ignore_if_exists=True,
        ),
        # _create_container_instance
        call(
            (
                "az container list --resource-group prefect-aci-push-pool-rg"
                " --subscription 12345678-1234-1234-1234-123456789012 --query"
                " \"[?name=='prefect-aci-push-pool-container']\" --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az container create --name prefect-aci-push-pool-container"
                " --resource-group prefect-aci-push-pool-rg --image"
                " docker.io/prefecthq/prefect:2-latest --location westus --subscription"
                " 12345678-1234-1234-1234-123456789012 --restart-policy OnFailure"
                " --output json"
            ),
            success_message=(
                "Container instance 'prefect-aci-push-pool-container' created"
                " successfully in resource group 'prefect-aci-push-pool-rg' in location"
                " 'westus' in subscription 'subscription_1'"
            ),
            failure_message=(
                "Failed to create container instance 'prefect-aci-push-pool-container'"
                " in resource group 'prefect-aci-push-pool-rg' in location 'westus' in"
                " subscription 'subscription_1'"
            ),
            ignore_if_exists=True,
        ),
    ]

    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)

    new_block_doc_id = new_base_job_template["variables"]["properties"][
        "aci_credentials"
    ]["default"]["$ref"]["block_document_id"]
    assert new_block_doc_id

    block_doc = await prefect_client.read_block_document(new_block_doc_id)

    assert block_doc.name == "test-work-pool-push-pool-credentials"
    assert block_doc.data == {
        "client_id": "12345678-1234-1234-1234-123456789012",
        "tenant_id": "9ee4947a-f114-4939-a5ac-7f0ed786de36",
        "client_secret": "<MY_SECRET>",  # noqa
    }


async def test_aci_provision_existing_credentials_block(
    default_base_job_template,
    prefect_client: PrefectClient,
    existing_credentials_block,
    provisioner: ContainerInstancePushProvisioner,
):
    subscription_list = [
        {
            "cloudName": "AzureCloud",
            "id": "12345678-1234-1234-1234-123456789012",
            "isDefault": True,
            "name": "subscription_1",
            "state": "Enabled",
            "tenantId": "12345678-1234-1234-1234-123456789012",
        }
    ]

    app_registration = {
        "appId": "12345678-1234-1234-1234-123456789012",
        "displayName": "prefect-aci-push-pool-app",
        "identifierUris": ["https://prefect-aci-push-pool-app"],
    }

    new_service_principal = [
        {
            "id": "abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c",
            "accountEnabled": True,
            "addIns": [],
            "alternativeNames": [],
            "appDescription": None,
            "appDisplayName": "prefect-aci-push-pool-app",
            "appId": "bcbeb824-fc3a-41f7-afc0-fc00297c1355",
        }
    ]

    role_assignments = {
        "roleDefinitionName": "Contributor",
    }

    provisioner.azure_cli.run_command.side_effect = [
        ("2.0.0", "2.0.0"),  # Azure CLI is installed
        (None, subscription_list),  # I don't know what call this is from
        (None, subscription_list),  # Select subscription
        (None, "westus"),  # Set location
        (None, None),  # Resource group does not exist
        ("created", "New resource group created"),  # Successful creation
        (None, None),  # App does not exist
        ("created", app_registration),  # Successful creation
        (None, []),  # Principal does not exist
        ("created", None),  # Successful creation
        ("created", new_service_principal),  # Successful retrieval
        (None, []),  # Role does not exist
        ("created", role_assignments),  # Successful creation
        (None, []),  # Container instance does not exist
        (None, None),  # Successful creation
    ]

    # Run the provision method
    new_base_job_template = await provisioner.provision(
        work_pool_name="test-work-pool",
        base_job_template=default_base_job_template,
        client=prefect_client,
    )

    assert new_base_job_template

    # Verify that the existing credentials block was reused
    new_block_doc_id = new_base_job_template["variables"]["properties"][
        "aci_credentials"
    ]["default"]["$ref"]["block_document_id"]
    assert new_block_doc_id == str(existing_credentials_block)

    # Verify Azure CLI interactions as in the previous test if applicable
    expected_calls = [
        # _verify_az_ready
        call("az --version", ignore_if_exists=True),
        call("az account list --output json", return_json=True),
        # _select_subscription
        call(
            "az account list --output json",
            failure_message=(
                "No Azure subscriptions found. Please create an Azure subscription and"
                " try again."
            ),
            ignore_if_exists=True,
            return_json=True,
        ),
        # _set_location
        call('az account list-locations --query "[?isDefault].name" --output tsv'),
        # _create_resource_group
        call(
            (
                "az group exists --name prefect-aci-push-pool-rg --subscription"
                " 12345678-1234-1234-1234-123456789012"
            ),
            return_json=True,
        ),
        call(
            (
                "az group create --name 'prefect-aci-push-pool-rg' --location 'westus'"
                " --subscription '12345678-1234-1234-1234-123456789012'"
            ),
            success_message=(
                "Resource group 'prefect-aci-push-pool-rg' created successfully"
            ),
            failure_message=(
                "Failed to create resource group 'prefect-aci-push-pool-rg' in"
                " subscription 'subscription_1'"
            ),
            ignore_if_exists=True,
        ),
        # _create_app_registration
        call("az ad app list --display-name prefect-aci-push-pool-app --output json"),
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
        # _create_service_principal
        call(
            (
                "az ad sp list --all --query"
                " \"[?appId=='12345678-1234-1234-1234-123456789012']\" --output json"
            ),
            return_json=True,
        ),
        call(
            "az ad sp create --id 12345678-1234-1234-1234-123456789012",
            success_message=(
                "Service principal created for app ID"
                " '12345678-1234-1234-1234-123456789012'"
            ),
            failure_message=(
                "Failed to create service principal for app ID"
                " '12345678-1234-1234-1234-123456789012'"
            ),
        ),
        call(
            (
                "az ad sp list --all --query"
                " \"[?appId=='12345678-1234-1234-1234-123456789012']\" --output json"
            ),
            failure_message=(
                "Failed to retrieve new service principal for app ID"
                " 12345678-1234-1234-1234-123456789012"
            ),
            return_json=True,
        ),
        # _assign_contributor_role
        call(
            (
                "az role assignment list --assignee"
                " abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c --role Contributor --scope"
                " /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg"
                " --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az role assignment create --role Contributor --assignee-object-id"
                " abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c --scope"
                " /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg"
            ),
            success_message=(
                "Contributor role assigned to service principal with object ID"
                " 'abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c'"
            ),
            failure_message=(
                "Failed to assign Contributor role to service principal with object ID"
                " 'abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c'"
            ),
            ignore_if_exists=True,
        ),
        # _create_container_instance
        call(
            (
                "az container list --resource-group prefect-aci-push-pool-rg"
                " --subscription 12345678-1234-1234-1234-123456789012 --query"
                " \"[?name=='prefect-aci-push-pool-container']\" --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az container create --name prefect-aci-push-pool-container"
                " --resource-group prefect-aci-push-pool-rg --image"
                " docker.io/prefecthq/prefect:2-latest --location westus --subscription"
                " 12345678-1234-1234-1234-123456789012 --restart-policy OnFailure"
                " --output json"
            ),
            success_message=(
                "Container instance 'prefect-aci-push-pool-container' created"
                " successfully in resource group 'prefect-aci-push-pool-rg' in location"
                " 'westus' in subscription 'subscription_1'"
            ),
            failure_message=(
                "Failed to create container instance 'prefect-aci-push-pool-container'"
                " in resource group 'prefect-aci-push-pool-rg' in location 'westus' in"
                " subscription 'subscription_1'"
            ),
            ignore_if_exists=True,
        ),
    ]

    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)

    # assert not called
    unexpected_call = call(
        (
            "az ad app credential reset --id 12345678-1234-1234-1234-123456789012"
            " --append --output json"
        ),
        success_message=(
            "Secret generated for app registration with client ID"
            " '12345678-1234-1234-1234-123456789012'"
        ),
        failure_message=(
            "Failed to generate secret for app registration with client ID"
            " '12345678-1234-1234-1234-123456789012'. If you have already generated 2"
            " secrets for this app registration, please delete one from the"
            " `prefect-aci-push-pool-app` resource and try again."
        ),
        ignore_if_exists=True,
        return_json=True,
    )
    assert (
        unexpected_call not in provisioner.azure_cli.run_command.mock_calls
    ), "Unexpected call made: {call}"
