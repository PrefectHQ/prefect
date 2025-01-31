from subprocess import CalledProcessError
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from pydantic import Field

from prefect.blocks.core import Block
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import BlockDocumentCreate
from prefect.infrastructure.provisioners.container_instance import (
    ContainerInstancePushProvisioner,
)
from prefect.types import SecretDict


@pytest.fixture
async def existing_credentials_block(prefect_client: PrefectClient):
    block_type = await prefect_client.read_block_type_by_slug(
        slug="azure-container-instance-credentials"
    )
    block_schema = await prefect_client.get_most_recent_block_schema_for_block_type(
        block_type_id=block_type.id
    )
    assert block_schema is not None

    block_document = await prefect_client.create_block_document(
        block_document=BlockDocumentCreate(
            name="test-work-pool-push-pool-credentials",
            data={
                "client_id": "12345678-1234-1234-1234-123456789012",
                "tenant_id": "9ee4947a-f114-4939-a5ac-7f0ed786de36",
                "client_secret": "<MY_SECRET>",
            },
            block_type_id=block_type.id,
            block_schema_id=block_schema.id,
        )
    )

    yield block_document.id

    await prefect_client.delete_block_document(block_document_id=block_document.id)


@pytest.fixture
def default_base_job_template():
    return {
        "job_configuration": {
            "command": "{{ command }}",
            "env": "{{ env }}",
            "labels": "{{ labels }}",
            "name": "{{ name }}",
            "image": "{{ image }}",
            "resource_group_name": "{{ resource_group_name }}",
            "subscription_id": "{{ subscription_id }}",
            "identities": "{{ identities }}",
            "entrypoint": "{{ entrypoint }}",
            "image_registry": "{{ image_registry }}",
            "cpu": "{{ cpu }}",
            "gpu_count": "{{ gpu_count }}",
            "gpu_sku": "{{ gpu_sku }}",
            "memory": "{{ memory }}",
            "subnet_ids": "{{ subnet_ids }}",
            "dns_servers": "{{ dns_servers }}",
            "stream_output": "{{ stream_output }}",
            "aci_credentials": "{{ aci_credentials }}",
            "task_start_timeout_seconds": "{{ task_start_timeout_seconds }}",
            "task_watch_poll_interval": "{{ task_watch_poll_interval }}",
            "arm_template": {
                "$schema": "https://schema.management.azure.com/schemas/2019-08-01/deploymentTemplate.json#",
                "contentVersion": "1.0.0.0",
                "parameters": {
                    "location": {
                        "type": "string",
                        "defaultValue": "[resourceGroup().location]",
                        "metadata": {"description": "Location for all resources."},
                    },
                    "container_group_name": {
                        "type": "string",
                        "defaultValue": "[uniqueString(resourceGroup().id)]",
                        "metadata": {
                            "description": "The name of the container group to create."
                        },
                    },
                    "container_name": {
                        "type": "string",
                        "defaultValue": "[uniqueString(resourceGroup().id)]",
                        "metadata": {
                            "description": "The name of the container to create."
                        },
                    },
                },
                "resources": [
                    {
                        "type": "Microsoft.ContainerInstance/containerGroups",
                        "apiVersion": "2022-09-01",
                        "name": "[parameters('container_group_name')]",
                        "location": "[parameters('location')]",
                        "properties": {
                            "containers": [
                                {
                                    "name": "[parameters('container_name')]",
                                    "properties": {
                                        "image": "{{ image }}",
                                        "command": "{{ command }}",
                                        "resources": {
                                            "requests": {
                                                "cpu": "{{ cpu }}",
                                                "memoryInGB": "{{ memory }}",
                                            }
                                        },
                                        "environmentVariables": [],
                                    },
                                }
                            ],
                            "osType": "Linux",
                            "restartPolicy": "Never",
                        },
                    }
                ],
            },
        },
        "variables": {
            "description": "Variables for an Azure Container Instance flow run.",
            "type": "object",
            "properties": {
                "name": {
                    "title": "Name",
                    "description": "Name given to created infrastructure.",
                    "type": "string",
                },
                "env": {
                    "title": "Environment Variables",
                    "description": (
                        "Environment variables to set when starting a flow run."
                    ),
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
                "labels": {
                    "title": "Labels",
                    "description": "Labels applied to created infrastructure.",
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
                "command": {
                    "title": "Command",
                    "description": (
                        "The command to use when starting a flow run. In most cases,"
                        " this should be left blank and the command will be"
                        " automatically generated."
                    ),
                    "type": "string",
                },
                "image": {
                    "title": "Image",
                    "description": (
                        "The image to use for the Prefect container in the task. This"
                        " value defaults to a Prefect base image matching your local"
                        " versions."
                    ),
                    "type": "string",
                },
                "resource_group_name": {
                    "title": "Azure Resource Group Name",
                    "description": (
                        "The name of the Azure Resource Group in which to run Prefect"
                        " ACI tasks."
                    ),
                    "type": "string",
                },
                "subscription_id": {
                    "title": "Azure Subscription ID",
                    "description": (
                        "The ID of the Azure subscription to create containers under."
                    ),
                    "type": "string",
                    "writeOnly": True,
                    "format": "password",
                },
                "identities": {
                    "title": "Identities",
                    "description": (
                        "A list of user-assigned identities to associate with the"
                        " container group. The identities should be an ARM resource IDs"
                        " in the form:"
                        " '/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/{identityName}'."
                    ),
                    "type": "array",
                    "items": {"type": "string"},
                },
                "entrypoint": {
                    "title": "Entrypoint",
                    "description": (
                        "The entrypoint of the container you wish you run. This value"
                        " defaults to the entrypoint used by Prefect images and should"
                        " only be changed when using a custom image that is not based"
                        " on an official Prefect image. Any commands set on deployments"
                        " will be passed to the entrypoint as parameters."
                    ),
                    "default": "/opt/prefect/entrypoint.sh",
                    "type": "string",
                },
                "image_registry": {
                    "title": "Image Registry (Optional)",
                    "description": (
                        "To use any private container registry with a username and"
                        " password, choose DockerRegistry. To use a private Azure"
                        " Container Registry with a managed identity, choose"
                        " ACRManagedIdentity."
                    ),
                    "anyOf": [
                        {"$ref": "#/definitions/DockerRegistry"},
                        {"$ref": "#/definitions/ACRManagedIdentity"},
                    ],
                },
                "cpu": {
                    "title": "CPU",
                    "description": (
                        "The number of virtual CPUs to assign to the task container. If"
                        " not provided, a default value of 1.0 will be used."
                    ),
                    "default": 1,
                    "type": "number",
                },
                "gpu_count": {
                    "title": "GPU Count",
                    "description": (
                        "The number of GPUs to assign to the task container. If not"
                        " provided, no GPU will be used."
                    ),
                    "type": "integer",
                },
                "gpu_sku": {
                    "title": "GPU SKU",
                    "description": (
                        "The Azure GPU SKU to use. See the ACI documentation for a list"
                        " of GPU SKUs available in each Azure region."
                    ),
                    "type": "string",
                },
                "memory": {
                    "title": "Memory",
                    "description": (
                        "The amount of memory in gigabytes to provide to the ACI task."
                        " Valid amounts are specified in the Azure documentation. If"
                        " not provided, a default value of  1.0 will be used unless"
                        " present on the task definition."
                    ),
                    "default": 1,
                    "type": "number",
                },
                "subnet_ids": {
                    "title": "Subnet IDs",
                    "description": (
                        "A list of Azure subnet IDs to use for the ACI task."
                    ),
                    "type": "array",
                    "items": {"type": "string"},
                },
                "dns_servers": {
                    "title": "DNS Servers",
                    "description": "A list of DNS servers to use for the ACI task.",
                    "type": "array",
                    "items": {"type": "string"},
                },
                "aci_credentials": {
                    "title": "Aci Credentials",
                    "description": "The credentials to use to authenticate with Azure.",
                    "allOf": [
                        {"$ref": "#/definitions/AzureContainerInstanceCredentials"}
                    ],
                },
                "stream_output": {
                    "title": "Stream Output",
                    "description": (
                        "If `True`, logs will be streamed from the Prefect container to"
                        " the local console."
                    ),
                    "default": True,
                    "type": "boolean",
                },
                "task_start_timeout_seconds": {
                    "title": "Task Start Timeout Seconds",
                    "description": (
                        "The amount of time to watch for the start of the ACI"
                        " container. before marking it as failed."
                    ),
                    "default": 240,
                    "type": "integer",
                },
                "task_watch_poll_interval": {
                    "title": "Task Watch Poll Interval",
                    "description": (
                        "The number of seconds to wait between Azure API calls while"
                        " monitoring the state of an Azure Container Instances task."
                    ),
                    "default": 5,
                    "type": "number",
                },
            },
            "required": ["resource_group_name", "subscription_id", "aci_credentials"],
            "definitions": {
                "DockerRegistry": {
                    "title": "DockerRegistry",
                    "description": (
                        "Connects to a Docker registry.\n\nRequires a Docker Engine to"
                        " be connectable."
                    ),
                    "type": "object",
                    "properties": {
                        "username": {
                            "title": "Username",
                            "description": (
                                "The username to log into the registry with."
                            ),
                            "type": "string",
                        },
                        "password": {
                            "title": "Password",
                            "description": (
                                "The password to log into the registry with."
                            ),
                            "type": "string",
                            "writeOnly": True,
                            "format": "password",
                        },
                        "registry_url": {
                            "title": "Registry Url",
                            "description": (
                                'The URL to the registry. Generally, "http" or "https"'
                                " can be omitted."
                            ),
                            "type": "string",
                        },
                        "reauth": {
                            "title": "Reauth",
                            "description": (
                                "Whether or not to reauthenticate on each interaction."
                            ),
                            "default": True,
                            "type": "boolean",
                        },
                    },
                    "required": ["username", "password", "registry_url"],
                    "block_type_slug": "docker-registry",
                    "secret_fields": ["password"],
                    "block_schema_references": {},
                },
                "ACRManagedIdentity": {
                    "title": "ACRManagedIdentity",
                    "description": (
                        "Use a Managed Identity to access Azure Container registry."
                        " Requires the\nuser-assigned managed identity be available to"
                        " the ACI container group."
                    ),
                    "type": "object",
                    "properties": {
                        "registry_url": {
                            "title": "Registry URL",
                            "description": (
                                "The URL to the registry, such as"
                                " myregistry.azurecr.io. Generally, 'http' or 'https'"
                                " can be omitted."
                            ),
                            "type": "string",
                        },
                        "identity": {
                            "title": "Identity",
                            "description": (
                                "The user-assigned Azure managed identity for the"
                                " private registry."
                            ),
                            "type": "string",
                        },
                    },
                    "required": ["registry_url", "identity"],
                },
                "AzureContainerInstanceCredentials": {
                    "title": "AzureContainerInstanceCredentials",
                    "description": (
                        "Block used to manage Azure Container Instances authentication."
                        " Stores Azure Service\nPrincipal authentication data."
                    ),
                    "type": "object",
                    "required": ["client_id", "tenant_id", "client_secret"],
                    "properties": {
                        "client_id": {
                            "title": "Client ID",
                            "description": (
                                "The service principal client ID. If none of client_id,"
                                " tenant_id, and client_secret are provided, will use"
                                " DefaultAzureCredential; else will need to provide all"
                                " three to use ClientSecretCredential."
                            ),
                            "type": "string",
                        },
                        "tenant_id": {
                            "title": "Tenant ID",
                            "description": (
                                "The service principal tenant ID.If none of client_id,"
                                " tenant_id, and client_secret are provided, will use"
                                " DefaultAzureCredential; else will need to provide all"
                                " three to use ClientSecretCredential."
                            ),
                            "type": "string",
                        },
                        "client_secret": {
                            "title": "Client Secret",
                            "description": (
                                "The service principal client secret.If none of"
                                " client_id, tenant_id, and client_secret are provided,"
                                " will use DefaultAzureCredential; else will need to"
                                " provide all three to use ClientSecretCredential."
                            ),
                            "type": "string",
                            "writeOnly": True,
                            "format": "password",
                        },
                        "credential_kwargs": {
                            "title": "Additional Credential Keyword Arguments",
                            "description": (
                                "Additional keyword arguments to pass to"
                                " `ClientSecretCredential` or `DefaultAzureCredential`."
                            ),
                            "type": "object",
                        },
                    },
                    "block_type_slug": "azure-container-instance-credentials",
                    "secret_fields": ["client_secret"],
                    "block_schema_references": {},
                },
            },
        },
    }


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
    provisioner.azure_cli = MagicMock()
    provisioner.azure_cli.run_command = AsyncMock()
    yield provisioner


async def test_aci_az_installed(provisioner):
    provisioner.azure_cli.run_command.side_effect = [
        "2.0.0",  # Azure CLI is installed
        '{"account_a": "b"}',
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
        subscriptions_list,
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
        "westus",
    ]

    await provisioner.set_location()

    expected_calls = [
        call('az account list-locations --query "[?isDefault].name" --output tsv'),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


async def test_aci_resource_group_creation_creates_new_group(provisioner):
    provisioner.azure_cli.run_command.side_effect = [
        False,
        "New resource group created",
    ]

    await provisioner._create_resource_group()

    expected_calls = [
        call(
            "az group exists --name prefect-aci-push-pool-rg --subscription None",
            return_json=True,
        ),
        call(
            (
                "az group create --name 'prefect-aci-push-pool-rg' --location 'eastus'"
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
    provisioner.azure_cli.run_command.return_value = True

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
    provisioner.azure_cli.run_command.side_effect = [None, error]

    with pytest.raises(CalledProcessError):
        await provisioner._create_resource_group()

    expected_calls = [
        call(
            "az group exists --name prefect-aci-push-pool-rg --subscription None",
            return_json=True,
        ),
        call(
            (
                "az group create --name 'prefect-aci-push-pool-rg' --location 'eastus'"
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


async def test_aci_app_registration_creates_new_app(provisioner):
    app_registration = {
        "appId": "12345678-1234-1234-1234-123456789012",
        "displayName": "prefect-aci-push-pool-app",
        "identifierUris": ["https://prefect-aci-push-pool-app"],
    }
    provisioner.azure_cli.run_command.side_effect = [
        None,  # App does not exist
        app_registration,  # Successful creation
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
    provisioner.azure_cli.run_command.return_value = app_registration

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
    provisioner.azure_cli.run_command.side_effect = [None, error]

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
        [],  # Principal does not exist
        service_principal,  # Successful creation
        ["12345678-1234-1234-1234-123456789012"],  # Principal object ID
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
    provisioner.azure_cli.run_command.return_value = service_principal

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
    provisioner.azure_cli.run_command.side_effect = [[], error]

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
        [],  # Principal does not exist
        service_principal,  # Successful creation
        [{"id": "12345678-1234-1234-1234-123456789012"}],  # Principal object ID
        [{"roleDefinitionName": None, "scope": None}],  # Successful creation
        None,
    ]

    await provisioner._assign_contributor_role(
        app_id="bcbeb824-fc3a-41f7-afc0-fc00297c1355",
        subscription_id="12345678-1234-1234-1234-123456789012",
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
        [],  # Principal does not exist
        service_principal,  # Successful creation
        [{"id": "12345678-1234-1234-1234-123456789012"}],  # Principal object ID
        [{"roleDefinitionName": role, "scope": scope}],  # Successful creation
    ]

    await provisioner._assign_contributor_role(
        app_id="bcbeb824-fc3a-41f7-afc0-fc00297c1355",
        subscription_id="12345678-1234-1234-1234-123456789012",
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
                " /subscriptions/None/resourceGroups/prefect-aci-push-pool-rg"
                " --subscription 12345678-1234-1234-1234-123456789012 --output json"
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
        [],  # Principal does not exist
        service_principal,  # Successful creation
        [{"id": "12345678-1234-1234-1234-123456789012"}],  # Principal object ID
        error,
    ]

    with pytest.raises(CalledProcessError):
        await provisioner._assign_contributor_role(
            app_id="bcbeb824-fc3a-41f7-afc0-fc00297c1355",
            subscription_id="12345678-1234-1234-1234-123456789012",
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


async def test_get_or_create_registry_new_registry(provisioner):
    registry_name = "prefect-registry"
    resource_group_name = "prefect-rg"
    location = "westus"
    subscription_id = "12345678-1234-1234-1234-123456789012"

    provisioner.azure_cli.run_command.side_effect = [
        [],  # No existing registry
        {"name": "prefect-registry"},  # Successful creation
    ]

    response = await provisioner._get_or_create_registry(
        registry_name, resource_group_name, location, subscription_id
    )

    expected_calls = [
        call(
            (
                "az acr list --query \"[?starts_with(name, 'prefect')]\" --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az acr create --name prefect-registry --resource-group prefect-rg"
                " --subscription 12345678-1234-1234-1234-123456789012 --location westus"
                " --sku Basic"
            ),
            success_message="Registry created",
            failure_message="Failed to create registry",
            return_json=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)

    assert response == {"name": "prefect-registry"}


async def test_get_or_create_registry_failed_creation(provisioner):
    registry_name = "prefect-registry"
    resource_group_name = "prefect-rg"
    location = "westus"
    subscription_id = "12345678-1234-1234-1234-123456789012"

    provisioner.azure_cli.run_command.side_effect = [
        [],  # No existing registry
        None,  # Failed creation
    ]

    with pytest.raises(Exception):
        await provisioner._get_or_create_registry(
            registry_name, resource_group_name, location, subscription_id
        )

    expected_calls = [
        call(
            (
                "az acr list --query \"[?starts_with(name, 'prefect')]\" --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az acr create --name prefect-registry --resource-group prefect-rg"
                " --subscription 12345678-1234-1234-1234-123456789012 --location westus"
                " --sku Basic"
            ),
            success_message="Registry created",
            failure_message="Failed to create registry",
            return_json=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


async def test_get_or_create_registry_existing_registry(provisioner):
    registry_name = "prefect-registry"
    resource_group_name = "prefect-rg"
    location = "westus"
    subscription_id = "12345678-1234-1234-1234-123456789012"

    provisioner.azure_cli.run_command.side_effect = [
        [{"name": "prefect-registry"}],  # Existing registry
    ]

    response = await provisioner._get_or_create_registry(
        registry_name, resource_group_name, location, subscription_id
    )

    expected_calls = [
        call(
            (
                "az acr list --query \"[?starts_with(name, 'prefect')]\" --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)

    assert response == {"name": "prefect-registry"}


async def test_log_into_registry(provisioner):
    login_server = "my-registry.azurecr.io"
    provisioner.azure_cli.run_command.side_effect = None

    await provisioner._log_into_registry(
        login_server, subscription_id="12345678-1234-1234-1234-123456789012"
    )

    expected_calls = [
        call(
            (
                f"az acr login --name {login_server} --subscription"
                " 12345678-1234-1234-1234-123456789012"
            ),
            success_message=f"Logged into registry {login_server}",
            failure_message=f"Failed to log into registry {login_server}",
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


async def test_assign_acr_pull_role(provisioner):
    identity = {
        "principalId": "12345678-1234-1234-1234-123456789012",
    }
    registry = {
        "id": "12345678-1234-1234-1234-123456789012",
    }

    await provisioner._assign_acr_pull_role(
        identity, registry, subscription_id="12345678-1234-1234-1234-123456789012"
    )

    expected_command = (
        "az role assignment create --assignee-object-id"
        " 12345678-1234-1234-1234-123456789012 --assignee-principal-type"
        " ServicePrincipal --scope 12345678-1234-1234-1234-123456789012 --role AcrPull"
        " --subscription 12345678-1234-1234-1234-123456789012"
    )
    provisioner.azure_cli.run_command.assert_called_once_with(
        expected_command,
        ignore_if_exists=True,
    )


async def test_get_or_create_identity_existing_identity(provisioner):
    identity_name = "test-identity"
    resource_group_name = "test-rg"

    provisioner.azure_cli.run_command.side_effect = [
        [{"name": identity_name}],
    ]

    identity = await provisioner._get_or_create_identity(
        identity_name,
        resource_group_name,
        subscription_id="12345678-1234-1234-1234-123456789012",
    )

    expected_calls = [
        call(
            (
                f"az identity list --query \"[?name=='{identity_name}']\""
                f" --resource-group {resource_group_name} --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)

    assert identity == {"name": identity_name}


async def test_get_or_create_identity_new_identity(provisioner):
    identity_name = "test-identity"
    resource_group_name = "test-rg"

    provisioner.azure_cli.run_command.side_effect = [
        [],  # Identity does not exist
        {"name": identity_name},  # Successful creation
    ]

    identity = await provisioner._get_or_create_identity(
        identity_name,
        resource_group_name,
        subscription_id="12345678-1234-1234-1234-123456789012",
    )

    expected_calls = [
        call(
            (
                f"az identity list --query \"[?name=='{identity_name}']\""
                f" --resource-group {resource_group_name} --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                f"az identity create --name {identity_name} --resource-group"
                f" {resource_group_name} --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            success_message=f"Identity {identity_name!r} created",
            failure_message=f"Failed to create identity {identity_name!r}",
            return_json=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)

    assert identity == {"name": identity_name}


async def test_get_or_create_identity_error(provisioner):
    identity_name = "test-identity"
    resource_group_name = "test-rg"

    error = CalledProcessError(1, "cmd", output="output", stderr="error")
    provisioner.azure_cli.run_command.side_effect = [None, error]

    with pytest.raises(Exception):
        await provisioner._get_or_create_identity(
            identity_name,
            resource_group_name,
            subscription_id="12345678-1234-1234-1234-123456789012",
        )

    expected_calls = [
        call(
            (
                f"az identity list --query \"[?name=='{identity_name}']\""
                f" --resource-group {resource_group_name} --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                f"az identity create --name {identity_name} --resource-group"
                f" {resource_group_name} --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            success_message=f"Identity {identity_name!r} created",
            failure_message=f"Failed to create identity {identity_name!r}",
            return_json=True,
        ),
    ]
    provisioner.azure_cli.run_command.assert_has_calls(expected_calls)


async def test_aci_provision_no_existing_credentials_block(
    default_base_job_template,
    prefect_client: PrefectClient,
    provisioner: ContainerInstancePushProvisioner,
    monkeypatch,
):
    monkeypatch.setattr(
        provisioner,
        "_generate_acr_name",
        lambda *args, **kwargs: "prefectacipushpoolregistry",
    )

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

    client_secret = {
        "appId": "5407b48a-a28d-49ea-a740-54504847153f",
        "password": "<MY_SECRET>",
        "tenant": "9ee4947a-f114-4939-a5ac-7f0ed786de36",
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

    new_registry = {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ContainerRegistry/registries/prefectacipushpoolregistry",
        "loginServer": "prefectacipushpoolregistry.azurecr.io",
    }

    new_identity = {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/prefect-aci-push-pool-identity",
        "principalId": "12345678-1234-1234-1234-123456789012",
    }

    provisioner.azure_cli.run_command.side_effect = [
        "2.0.0",  # Azure CLI is installed
        subscription_list,  #  Azure login check
        subscription_list,  # Select subscription
        "westus",  # Set location
        None,  # Resource group does not exist
        "New resource group created",  # Successful creation
        None,  # App does not exist
        app_registration,  # Successful creation
        client_secret,  # Generate app secret
        [],  # Principal does not exist
        None,  # Successful creation
        new_service_principal,  # Successful retrieval
        [],  # Role does not exist
        role_assignments,  # Successful creation
        [],  # Registry does not exist
        new_registry,  # Successful creation
        None,  # Log in to registry
        [],  # Identity does not exist
        new_identity,  # Successful creation
        None,  # Assign identity to registry
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
                " --subscription 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az role assignment create --role Contributor --assignee-object-id"
                " abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c --scope"
                " /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg"
                " --subscription 12345678-1234-1234-1234-123456789012"
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
        # _get_or_create_registry
        call(
            (
                "az acr list --query \"[?starts_with(name, 'prefect')]\" --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az acr create --name prefectacipushpoolregistry --resource-group"
                " prefect-aci-push-pool-rg --subscription"
                " 12345678-1234-1234-1234-123456789012 --location westus --sku Basic"
            ),
            success_message="Registry created",
            failure_message="Failed to create registry",
            return_json=True,
        ),
        # _log_into_registry
        call(
            (
                "az acr login --name prefectacipushpoolregistry.azurecr.io"
                " --subscription 12345678-1234-1234-1234-123456789012"
            ),
            success_message=(
                "Logged into registry prefectacipushpoolregistry.azurecr.io"
            ),
            failure_message=(
                "Failed to log into registry prefectacipushpoolregistry.azurecr.io"
            ),
        ),
        # _get_or_create_identity
        call(
            (
                "az identity list --query \"[?name=='prefect-acr-identity']\""
                " --resource-group prefect-aci-push-pool-rg --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az identity create --name prefect-acr-identity --resource-group"
                " prefect-aci-push-pool-rg --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            success_message="Identity 'prefect-acr-identity' created",
            failure_message="Failed to create identity 'prefect-acr-identity'",
            return_json=True,
        ),
        # _assign_acr_pull_role
        call(
            (
                "az role assignment create --assignee-object-id"
                " 12345678-1234-1234-1234-123456789012 --assignee-principal-type"
                " ServicePrincipal --scope"
                " /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ContainerRegistry/registries/prefectacipushpoolregistry"
                " --role AcrPull --subscription 12345678-1234-1234-1234-123456789012"
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
        "client_secret": "<MY_SECRET>",
    }

    new_base_job_template["variables"]["properties"]["subscription_id"]["default"] = (
        "12345678-1234-1234-1234-123456789012"
    )

    new_base_job_template["variables"]["properties"]["resource_group_name"][
        "default"
    ] = "prefect-aci-push-pool-rg"

    new_base_job_template["variables"]["properties"]["image_registry"]["default"] = {
        "registry_url": "prefectacipushpoolregistry.azurecr.io",
        "identity": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/prefect-aci-push-pool-identity",
    }

    new_base_job_template["variables"]["properties"]["identities"]["default"] = [
        "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/prefect-aci-push-pool-identity"
    ]


async def test_aci_provision_existing_credentials_block(
    default_base_job_template,
    prefect_client: PrefectClient,
    existing_credentials_block,
    provisioner: ContainerInstancePushProvisioner,
    monkeypatch,
):
    monkeypatch.setattr(
        provisioner,
        "_generate_acr_name",
        lambda *args, **kwargs: "prefectacipushpoolregistry",
    )
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

    new_registry = {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ContainerRegistry/registries/prefectacipushpoolregistry",
        "loginServer": "prefectacipushpoolregistry.azurecr.io",
    }

    new_identity = {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/prefect-aci-push-pool-identity",
        "principalId": "12345678-1234-1234-1234-123456789012",
    }

    provisioner.azure_cli.run_command.side_effect = [
        "2.0.0",  # Azure CLI is installed
        subscription_list,  # Login check
        subscription_list,  # Select subscription
        "westus",  # Set location
        None,  # Resource group does not exist
        "New resource group created",  # Successful creation
        None,  # App does not exist
        app_registration,  # Successful creation
        [],  # Principal does not exist
        None,  # Successful creation
        new_service_principal,  # Successful retrieval
        [],  # Role does not exist
        role_assignments,  # Successful creation
        [],  # Registry does not exist
        new_registry,  # Successful creation
        None,  # Log in to registry
        [],  # Identity does not exist
        new_identity,  # Successful creation
        None,  # Assign identity to registry
    ]

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
                " --subscription 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az role assignment create --role Contributor --assignee-object-id"
                " abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c --scope"
                " /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg"
                " --subscription 12345678-1234-1234-1234-123456789012"
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
        # _get_or_create_registry
        call(
            (
                "az acr list --query \"[?starts_with(name, 'prefect')]\" --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az acr create --name prefectacipushpoolregistry --resource-group"
                " prefect-aci-push-pool-rg --subscription"
                " 12345678-1234-1234-1234-123456789012 --location westus --sku Basic"
            ),
            success_message="Registry created",
            failure_message="Failed to create registry",
            return_json=True,
        ),
        # _log_into_registry
        call(
            (
                "az acr login --name prefectacipushpoolregistry.azurecr.io"
                " --subscription 12345678-1234-1234-1234-123456789012"
            ),
            success_message=(
                "Logged into registry prefectacipushpoolregistry.azurecr.io"
            ),
            failure_message=(
                "Failed to log into registry prefectacipushpoolregistry.azurecr.io"
            ),
        ),
        # _get_or_create_identity
        call(
            (
                "az identity list --query \"[?name=='prefect-acr-identity']\""
                " --resource-group prefect-aci-push-pool-rg --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az identity create --name prefect-acr-identity --resource-group"
                " prefect-aci-push-pool-rg --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            success_message="Identity 'prefect-acr-identity' created",
            failure_message="Failed to create identity 'prefect-acr-identity'",
            return_json=True,
        ),
        # _assign_acr_pull_role
        call(
            (
                "az role assignment create --assignee-object-id"
                " 12345678-1234-1234-1234-123456789012 --assignee-principal-type"
                " ServicePrincipal --scope"
                " /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ContainerRegistry/registries/prefectacipushpoolregistry"
                " --role AcrPull --subscription 12345678-1234-1234-1234-123456789012"
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
    assert unexpected_call not in provisioner.azure_cli.run_command.mock_calls, (
        "Unexpected call made: {call}"
    )

    new_base_job_template["variables"]["properties"]["subscription_id"]["default"] = (
        "12345678-1234-1234-1234-123456789012"
    )

    new_base_job_template["variables"]["properties"]["resource_group_name"][
        "default"
    ] = "prefect-aci-push-pool-rg"

    new_base_job_template["variables"]["properties"]["aci_credentials"]["default"][
        "block_document_id"
    ] = str(existing_credentials_block)

    new_base_job_template["variables"]["properties"]["image_registry"]["default"] = {
        "registry_url": "prefectacipushpoolregistry.azurecr.io",
        "identity": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/prefect-aci-push-pool-identity",
    }

    new_base_job_template["variables"]["properties"]["identities"]["default"] = [
        "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/prefect-aci-push-pool-identity"
    ]


async def test_aci_provision_interactive_default_provisioning(
    prefect_client: PrefectClient,
    monkeypatch,
    default_base_job_template,
    provisioner: ContainerInstancePushProvisioner,
):
    mock_prompt_select_from_table = MagicMock(
        side_effect=[
            {"id": "12345678-1234-1234-1234-123456789012", "name": "subscription_1"},
            {
                "option": (
                    "Yes, proceed with infrastructure provisioning with default"
                    " resource names"
                )
            },
        ]
    )

    monkeypatch.setattr(
        "prefect.infrastructure.provisioners.container_instance.prompt_select_from_table",
        mock_prompt_select_from_table,
    )

    mock_confirm = MagicMock(return_value=True)

    monkeypatch.setattr(
        "prefect.infrastructure.provisioners.container_instance.Confirm.ask",
        mock_confirm,
    )
    monkeypatch.setattr(
        provisioner,
        "_generate_acr_name",
        lambda *args, **kwargs: "prefectacipushpoolregistry",
    )
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

    client_secret = {
        "appId": "5407b48a-a28d-49ea-a740-54504847153f",
        "password": "<MY_SECRET>",
        "tenant": "9ee4947a-f114-4939-a5ac-7f0ed786de36",
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

    new_registry = {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ContainerRegistry/registries/prefectacipushpoolregistry",
        "loginServer": "prefectacipushpoolregistry.azurecr.io",
    }

    new_identity = {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/prefect-aci-push-pool-identity",
        "principalId": "12345678-1234-1234-1234-123456789012",
    }

    provisioner.azure_cli.run_command.side_effect = [
        "2.0.0",  # Azure CLI is installed
        subscription_list,  #  Azure login check
        subscription_list,  # Select subscription
        "westus",  # Set location
        None,  # Resource group does not exist
        "New resource group created",  # Successful creation
        None,  # App does not exist
        app_registration,  # Successful creation
        client_secret,  # Generate app secret
        [],  # Principal does not exist
        None,  # Successful creation
        new_service_principal,  # Successful retrieval
        [],  # Role does not exist
        role_assignments,  # Successful creation
        [],  # Registry does not exist
        new_registry,  # Successful creation
        None,  # Log in to registry
        [],  # Identity does not exist
        new_identity,  # Successful creation
        None,  # Assign identity to registry
    ]

    monkeypatch.setattr(provisioner._console, "is_interactive", True)

    new_base_job_template = await provisioner.provision(
        work_pool_name="test-work-pool",
        base_job_template=default_base_job_template,
        client=prefect_client,
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
                " --subscription 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az role assignment create --role Contributor --assignee-object-id"
                " abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c --scope"
                " /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg"
                " --subscription 12345678-1234-1234-1234-123456789012"
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
        # _get_or_create_registry
        call(
            (
                "az acr list --query \"[?starts_with(name, 'prefect')]\" --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az acr create --name prefectacipushpoolregistry --resource-group"
                " prefect-aci-push-pool-rg --subscription"
                " 12345678-1234-1234-1234-123456789012 --location westus --sku Basic"
            ),
            success_message="Registry created",
            failure_message="Failed to create registry",
            return_json=True,
        ),
        # _log_into_registry
        call(
            (
                "az acr login --name prefectacipushpoolregistry.azurecr.io"
                " --subscription 12345678-1234-1234-1234-123456789012"
            ),
            success_message=(
                "Logged into registry prefectacipushpoolregistry.azurecr.io"
            ),
            failure_message=(
                "Failed to log into registry prefectacipushpoolregistry.azurecr.io"
            ),
        ),
        # _get_or_create_identity
        call(
            (
                "az identity list --query \"[?name=='prefect-acr-identity']\""
                " --resource-group prefect-aci-push-pool-rg --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az identity create --name prefect-acr-identity --resource-group"
                " prefect-aci-push-pool-rg --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            success_message="Identity 'prefect-acr-identity' created",
            failure_message="Failed to create identity 'prefect-acr-identity'",
            return_json=True,
        ),
        # _assign_acr_pull_role
        call(
            (
                "az role assignment create --assignee-object-id"
                " 12345678-1234-1234-1234-123456789012 --assignee-principal-type"
                " ServicePrincipal --scope"
                " /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ContainerRegistry/registries/prefectacipushpoolregistry"
                " --role AcrPull --subscription 12345678-1234-1234-1234-123456789012"
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
        "client_secret": "<MY_SECRET>",
    }

    new_base_job_template["variables"]["properties"]["subscription_id"]["default"] = (
        "12345678-1234-1234-1234-123456789012"
    )

    new_base_job_template["variables"]["properties"]["resource_group_name"][
        "default"
    ] = "prefect-aci-push-pool-rg"

    new_base_job_template["variables"]["properties"]["image_registry"]["default"] = {
        "registry_url": "prefectacipushpoolregistry.azurecr.io",
        "identity": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/prefect-aci-push-pool-identity",
    }

    new_base_job_template["variables"]["properties"]["identities"]["default"] = [
        "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/prefect-aci-push-pool-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/prefect-aci-push-pool-identity"
    ]


async def test_aci_provision_interactive_custom_resource_names(
    prefect_client: PrefectClient,
    monkeypatch,
    default_base_job_template,
    provisioner: ContainerInstancePushProvisioner,
):
    def prompt_mocks(*args, **kwargs):
        if "Please enter a name for the resource group" in args[0]:
            return "custom-rg-name"
        if "Please enter a name for the app registration" in args[0]:
            return "custom-app-name"
        if "Please enter a prefix for the Azure Container Registry" in args[0]:
            return "customregistryname"
        if "Please enter a name for the identity" in args[0]:
            return "custom-identity-name"
        if "Please enter a name for the ACI credentials block" in args[0]:
            return "custom-credentials-name"

    mock_prompt = MagicMock(side_effect=prompt_mocks)

    monkeypatch.setattr(
        "prefect.infrastructure.provisioners.container_instance.prompt", mock_prompt
    )

    mock_prompt_select_from_table = MagicMock(
        side_effect=[
            {"id": "12345678-1234-1234-1234-123456789012", "name": "subscription_1"},
            {"option": "Customize resource names"},
        ]
    )

    monkeypatch.setattr(
        "prefect.infrastructure.provisioners.container_instance.prompt_select_from_table",
        mock_prompt_select_from_table,
    )

    mock_confirm = MagicMock(return_value=True)

    monkeypatch.setattr(
        "prefect.infrastructure.provisioners.container_instance.Confirm.ask",
        mock_confirm,
    )

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

    client_secret = {
        "appId": "5407b48a-a28d-49ea-a740-54504847153f",
        "password": "<MY_SECRET>",
        "tenant": "9ee4947a-f114-4939-a5ac-7f0ed786de36",
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

    new_registry = {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/custom-rg-name/providers/Microsoft.ContainerRegistry/registries/customregistryname",
        "loginServer": "customregistryname.azurecr.io",
    }

    new_identity = {
        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/custom-rg-name/providers/Microsoft.ManagedIdentity/userAssignedIdentities/custom-identity-name",
        "principalId": "12345678-1234-1234-1234-123456789012",
    }

    provisioner.azure_cli.run_command.side_effect = [
        "2.0.0",  # Azure CLI is installed
        subscription_list,  #  Azure login check
        subscription_list,  # Select subscription
        "westus",  # Set location
        None,  # Resource group does not exist
        "New resource group created",  # Successful creation
        None,  # App does not exist
        app_registration,  # Successful creation
        client_secret,  # Generate app secret
        [],  # Principal does not exist
        None,  # Successful creation
        new_service_principal,  # Successful retrieval
        [],  # Role does not exist
        role_assignments,  # Successful creation
        [],  # Registry does not exist
        new_registry,  # Successful creation
        None,  # Log in to registry
        [],  # Identity does not exist
        new_identity,  # Successful creation
        None,  # Assign identity to registry
    ]

    monkeypatch.setattr(
        provisioner,
        "_generate_acr_name",
        lambda *args, **kwargs: "customregistryname",
    )

    monkeypatch.setattr(provisioner._console, "is_interactive", True)

    new_base_job_template = await provisioner.provision(
        work_pool_name="test-work-pool",
        base_job_template=default_base_job_template,
        client=prefect_client,
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
                "az group exists --name custom-rg-name --subscription"
                " 12345678-1234-1234-1234-123456789012"
            ),
            return_json=True,
        ),
        call(
            (
                "az group create --name 'custom-rg-name' --location 'westus'"
                " --subscription '12345678-1234-1234-1234-123456789012'"
            ),
            success_message="Resource group 'custom-rg-name' created successfully",
            failure_message=(
                "Failed to create resource group 'custom-rg-name' in"
                " subscription 'subscription_1'"
            ),
            ignore_if_exists=True,
        ),
        # _create_app_registration
        call("az ad app list --display-name custom-app-name --output json"),
        call(
            "az ad app create --display-name custom-app-name --output json",
            success_message="App registration 'custom-app-name' created successfully",
            failure_message=(
                "Failed to create app registration with name 'custom-app-name'"
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
                " `custom-app-name` resource and try again."
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
                " /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/custom-rg-name"
                " --subscription 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az role assignment create --role Contributor --assignee-object-id"
                " abf1b3a0-1b1b-4c1c-9c9c-1c1c1c1c1c1c --scope"
                " /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/custom-rg-name"
                " --subscription 12345678-1234-1234-1234-123456789012"
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
        # _get_or_create_registry
        call(
            (
                "az acr list --query \"[?starts_with(name, 'customregistryname')]\""
                " --subscription 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az acr create --name customregistryname --resource-group"
                " custom-rg-name --subscription 12345678-1234-1234-1234-123456789012"
                " --location westus --sku Basic"
            ),
            success_message="Registry created",
            failure_message="Failed to create registry",
            return_json=True,
        ),
        # _log_into_registry
        call(
            (
                "az acr login --name customregistryname.azurecr.io --subscription"
                " 12345678-1234-1234-1234-123456789012"
            ),
            success_message="Logged into registry customregistryname.azurecr.io",
            failure_message="Failed to log into registry customregistryname.azurecr.io",
        ),
        # _get_or_create_identity
        call(
            (
                "az identity list --query \"[?name=='custom-identity-name']\""
                " --resource-group custom-rg-name --subscription"
                " 12345678-1234-1234-1234-123456789012 --output json"
            ),
            return_json=True,
        ),
        call(
            (
                "az identity create --name custom-identity-name --resource-group"
                " custom-rg-name --subscription 12345678-1234-1234-1234-123456789012"
                " --output json"
            ),
            success_message="Identity 'custom-identity-name' created",
            failure_message="Failed to create identity 'custom-identity-name'",
            return_json=True,
        ),
        # _assign_acr_pull_role
        call(
            (
                "az role assignment create --assignee-object-id"
                " 12345678-1234-1234-1234-123456789012 --assignee-principal-type"
                " ServicePrincipal --scope"
                " /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/custom-rg-name/providers/Microsoft.ContainerRegistry/registries/customregistryname"
                " --role AcrPull --subscription 12345678-1234-1234-1234-123456789012"
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

    assert block_doc.name == "custom-credentials-name"

    assert block_doc.data == {
        "client_id": "12345678-1234-1234-1234-123456789012",
        "tenant_id": "9ee4947a-f114-4939-a5ac-7f0ed786de36",
        "client_secret": "<MY_SECRET>",
    }

    new_base_job_template["variables"]["properties"]["subscription_id"]["default"] = (
        "12345678-1234-1234-1234-123456789012"
    )

    new_base_job_template["variables"]["properties"]["resource_group_name"][
        "default"
    ] = "custom-rg-name"

    new_base_job_template["variables"]["properties"]["image_registry"]["default"] = {
        "registry_url": "custom-app-name.azurecr.io",
        "identity": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/custom-rg-name/providers/Microsoft.ManagedIdentity/userAssignedIdentities/custom-identity-name",
    }

    new_base_job_template["variables"]["properties"]["identities"]["default"] = [
        "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/custom-rg-name/providers/Microsoft.ManagedIdentity/userAssignedIdentities/custom-identity-name"
    ]


async def test_aci_provision_interactive_reject_provisioning(
    prefect_client: PrefectClient,
    monkeypatch,
    default_base_job_template,
    provisioner: ContainerInstancePushProvisioner,
):
    mock_prompt_select_from_table = MagicMock(
        side_effect=[
            {"id": "12345678-1234-1234-1234-123456789012", "name": "subscription_1"},
            {"option": "Do not proceed with infrastructure provisioning"},
        ]
    )

    mock_confirm = MagicMock(return_value=False)

    monkeypatch.setattr(
        "prefect.infrastructure.provisioners.container_instance.prompt_select_from_table",
        mock_prompt_select_from_table,
    )

    monkeypatch.setattr(
        "prefect.infrastructure.provisioners.container_instance.Confirm.ask",
        mock_confirm,
    )

    provisioner.azure_cli.run_command.side_effect = [
        "2.0.0",  # Azure CLI is installed
        '{"account_a": "b"}',  # Login check
        '{"account_a": "b"}',  # Select subscription
        "westus",  # Set location
    ]

    monkeypatch.setattr(provisioner._console, "is_interactive", True)

    unchanged_base_job_template = await provisioner.provision(
        work_pool_name="test-work-pool",
        base_job_template=default_base_job_template,
        client=prefect_client,
    )

    assert unchanged_base_job_template == default_base_job_template
