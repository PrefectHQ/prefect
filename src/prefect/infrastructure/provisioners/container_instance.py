"""
This module defines the ContainerInstancePushProvisioner class, which is responsible for provisioning
infrastructure using Azure Container Instances for Prefect work pools.

The ContainerInstancePushProvisioner class provides methods for provisioning infrastructure and
interacting with Azure Container Instances.

Classes:
    AzureCLI: A class to handle Azure CLI commands.
    ContainerInstancePushProvisioner: A class for provisioning infrastructure using Azure Container Instances.

"""

import json
import random
import shlex
import string
import subprocess
import time
from copy import deepcopy
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID

from anyio import run_process
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.syntax import Syntax

from prefect.cli._prompts import prompt, prompt_select_from_table
from prefect.client.schemas.actions import BlockDocumentCreate
from prefect.client.utilities import inject_client
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound
from prefect.settings import (
    PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE,
    update_current_profile,
)

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


class AzureCLI:
    """
    A class for executing Azure CLI commands and handling their output.

    Args:
        console (Console): A Rich console object for displaying messages.

    Methods:
        run_command(command, success_message=None, failure_message=None, ignore_if_exists=False, return_json=False)
            Execute an Azure CLI command.
    """

    def __init__(self, console: Console):
        self._console = console

    async def run_command(
        self,
        command: str,
        success_message: Optional[str] = None,
        failure_message: Optional[str] = None,
        ignore_if_exists: bool = False,
        return_json: bool = False,
    ):
        """
        Runs an Azure CLI command and processes the output.

        Args:
            command (str): The Azure CLI command to execute.
            success_message (str, optional): Message to print on success.
            failure_message (str, optional): Message to print on failure.
            ignore_if_exists (bool): Whether to ignore errors if a resource already exists.
            return_json (bool): Whether to return the output as JSON.

        Returns:
            tuple: A tuple with two elements:
                - str: Status, either 'created', 'exists', or 'error'.
                - str or dict or None: The command output or None if an error occurs (depends on return_json).

        Raises:
            subprocess.CalledProcessError: If the command execution fails.
            json.JSONDecodeError: If output cannot be decoded as JSON when return_json is True.
        """
        try:
            result = await run_process(shlex.split(command), check=False)
            output = result.stdout.decode("utf-8").strip()

            if result.returncode != 0:
                error_message = result.stderr.decode("utf-8")
                if ignore_if_exists and "already exists" in error_message:
                    if success_message:
                        self._console.print(
                            f"{success_message} (already exists)", style="yellow"
                        )
                    return ("exists", None)
                else:
                    if failure_message:
                        self._console.print(
                            f"{failure_message}: {result.stderr.decode('utf-8')}",
                            style="red",
                        )
                    raise subprocess.CalledProcessError(
                        result.returncode,
                        command,
                        output=result.stdout,
                        stderr=result.stderr,
                    )
            if success_message:
                self._console.print(success_message, style="green")

            if return_json:
                try:
                    return json.loads(output)
                except json.JSONDecodeError as e:
                    self._console.print(f"Failed to decode JSON: {e}", style="red")
                    raise e

            return output

        except subprocess.CalledProcessError as e:
            self._console.print(f"Command execution failed: {e}", style="red")
            return


class ContainerInstancePushProvisioner:
    """
    A class responsible for provisioning Azure resources and setting up a push work pool.

    Attributes:
        _console (Console): A Rich console object for displaying messages and progress.
        _subscription_id (str): Azure subscription ID.
        _subscription_name (str): Azure subscription name.
        _resource_group (str): Azure resource group name.
        _location (str): Azure resource location.
        azure_cli (AzureCLI): An instance of AzureCLI for running Azure commands.

    Methods:
        set_location: Sets the location for Azure resource deployment.
        _verify_az_ready: Verifies if Azure CLI is ready and available.
        _select_subscription: Selects an Azure subscription interactively or automatically.
        _create_resource_group: Creates a resource group in Azure.
        _create_app_registration: Creates an app registration in Azure AD.
        _generate_secret_for_app: Generates a secret for the app registration.
        _get_service_principal_object_id: Retrieves the object ID of the service principal associated with the app registration.
        _assign_contributor_role: Assigns the Contributor role to the service account.
        _create_aci_credentials_block: Creates an Azure Container Instance credentials block.
        provision: Orchestrates the provisioning of Azure resources and setup for the push work pool.
    """

    def __init__(self):
        self._console = Console()
        self._subscription_id = None
        self._subscription_name = None
        self._location = "eastus"
        self._identity_name = "prefect-acr-identity"
        self.azure_cli = AzureCLI(self.console)
        self._credentials_block_name = None
        self._resource_group_name = "prefect-aci-push-pool-rg"
        self._app_registration_name = "prefect-aci-push-pool-app"
        self._registry_name_prefix = "prefect"

    @property
    def console(self) -> Console:
        return self._console

    @console.setter
    def console(self, value: Console) -> None:
        self._console = value

    async def set_location(self):
        """
        Set the Azure resource deployment location to the default or 'eastus' on failure.

        Raises:
            RuntimeError: If unable to execute the Azure CLI command.
        """
        try:
            command = (
                'az account list-locations --query "[?isDefault].name" --output tsv'
            )
            output = await self.azure_cli.run_command(command)
            if output:
                self._location = output
        except subprocess.CalledProcessError as e:
            raise RuntimeError("Failed to get default location.") from e

    async def _verify_az_ready(self) -> None:
        """
        Verifies if Azure CLI is installed and ready to use.

        Raises:
            RuntimeError: If Azure CLI is not installed.
            subprocess.CalledProcessError: If the Azure CLI command execution fails.
        """
        try:
            await self.azure_cli.run_command("az --version", ignore_if_exists=True)

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Azure CLI is not installed. Please see"
                " https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
            ) from e

        accounts = await self.azure_cli.run_command(
            "az account list --output json",
            return_json=True,
        )
        if not accounts:
            raise RuntimeError(
                "No Azure accounts found. Please run `az login` to log in to Azure."
            )

    async def _select_subscription(self) -> str:
        """
        Selects an Azure subscription for use. If running in interactive mode,
        the user will be prompted to select a subscription. Otherwise, the current subscription is used.

        Returns:
            str: The ID of the selected Azure subscription.

        Raises:
            RuntimeError: If no Azure subscriptions are found or the Azure CLI command execution fails.
        """
        if self._console.is_interactive:
            with Progress(
                SpinnerColumn(),
                TextColumn("Fetching Azure subscriptions..."),
                transient=True,
                console=self._console,
            ) as progress:
                list_projects_task = progress.add_task(
                    "Fetching subscriptions...", total=1
                )
            subscriptions_list = await self.azure_cli.run_command(
                "az account list --output json",
                failure_message=(
                    "No Azure subscriptions found. Please create an Azure subscription"
                    " and try again."
                ),
                ignore_if_exists=True,
                return_json=True,
            )
            progress.update(list_projects_task, completed=1)
            if subscriptions_list:
                selected_subscription = prompt_select_from_table(
                    self._console,
                    "Please select which Azure subscription to use:",
                    [
                        {"header": "Name", "key": "name"},
                        {"header": "Subscription ID", "key": "id"},
                    ],
                    subscriptions_list,
                )
                self._subscription_id = selected_subscription["id"]
                self._subscription_name = selected_subscription["name"]

        else:
            subscriptions_list = await self.azure_cli.run_command(
                "az account list --output json",
                failure_message=(
                    "No Azure subscriptions found. Please create an Azure subscription"
                    " and try again."
                ),
                ignore_if_exists=True,
                return_json=True,
            )
            if subscriptions_list:
                self._subscription_id = subscriptions_list[0]["id"]
                self._subscription_name = subscriptions_list[0]["name"]
            else:
                raise RuntimeError(
                    "No Azure subscriptions found. Please create an Azure subscription"
                    " and try again."
                )

    async def _create_resource_group(self):
        """
        Creates a resource group in Azure using predefined names and locations.

        Raises:
            subprocess.CalledProcessError: If the Azure CLI command execution fails.
        """
        check_exists_command = (
            f"az group exists --name {self._resource_group_name} --subscription"
            f" {self._subscription_id}"
        )
        exists_result = await self.azure_cli.run_command(
            check_exists_command, return_json=True
        )
        if exists_result is True:
            self._console.print(
                (
                    f"Resource group '{self._resource_group_name}' already exists in"
                    f" subscription {self._subscription_name}."
                ),
                style="yellow",
            )
            return

        resource_group_command = (
            f"az group create --name '{self._resource_group_name}' --location"
            f" '{self._location}' --subscription '{self._subscription_id}'"
        )
        await self.azure_cli.run_command(
            resource_group_command,
            success_message=(
                f"Resource group '{self._resource_group_name}' created successfully"
            ),
            failure_message=(
                f"Failed to create resource group '{self._resource_group_name}' in"
                f" subscription '{self._subscription_name}'"
            ),
            ignore_if_exists=True,
        )

    async def _create_app_registration(self) -> str:
        """
        Creates an app registration in Azure Active Directory.

        Returns:
            str: The client ID of the newly created app registration.

        Raises:
            subprocess.CalledProcessError: If the Azure CLI command execution fails.
        """
        # Check if the app registration already exists
        check_exists_command = (
            f"az ad app list --display-name {self._app_registration_name} --output json"
        )
        app_registrations = await self.azure_cli.run_command(
            check_exists_command,
        )
        if app_registrations:
            if isinstance(app_registrations, str):
                app_registrations = json.loads(app_registrations)

            existing_app_registration = next(
                (
                    app
                    for app in app_registrations
                    if app["displayName"] == self._app_registration_name
                ),
                None,
            )
            if existing_app_registration:
                self._console.print(
                    f"App registration '{self._app_registration_name}' already exists.",
                    style="yellow",
                )
                return existing_app_registration["appId"]

        app_registration_command = (
            f"az ad app create --display-name {self._app_registration_name} "
            "--output json"
        )
        app_registration = await self.azure_cli.run_command(
            app_registration_command,
            success_message=(
                f"App registration '{self._app_registration_name}' created successfully"
            ),
            failure_message=(
                "Failed to create app registration with name"
                f" '{self._app_registration_name}'"
            ),
            ignore_if_exists=True,
        )
        if app_registration:
            if isinstance(app_registration, str):
                app_registration = json.loads(app_registration)
            return app_registration["appId"]

        else:
            raise RuntimeError("Failed to create app registration.")

    async def _generate_secret_for_app(self, app_id: str) -> tuple:
        """
        Generates a secret for the app registration.

        Args:
            app_id (str): The client ID of the app registration for which to generate the secret.

        Returns:
            tuple: A tuple containing the tenant ID and the generated secret.

        Raises:
            subprocess.CalledProcessError: If the Azure CLI command execution fails.
        """
        secret_command = (
            f"az ad app credential reset --id {app_id} --append --output json"
        )
        app_secret = await self.azure_cli.run_command(
            secret_command,
            success_message=(
                f"Secret generated for app registration with client ID '{app_id}'"
            ),
            failure_message=(
                "Failed to generate secret for app registration with client ID"
                f" '{app_id}'. If you have already generated 2 secrets for this app"
                " registration, please delete one from the"
                f" `{self._app_registration_name}` resource and try again."
            ),
            ignore_if_exists=True,
            return_json=True,
        )

        try:
            return app_secret["tenant"], app_secret["password"]
        except Exception as e:
            raise RuntimeError(
                "Failed to generate a new secret for the app registration."
            ) from e

    async def _get_or_create_service_principal_object_id(self, app_id: str):
        """
        Retrieves or creates a service principal for the given app registration client ID.

        Args:
            app_id (str): The client ID of the app registration.

        Returns:
            str: The object ID of the service principal.
        """
        # Try to retrieve the existing service principal
        command_get_sp = (
            f"az ad sp list --all --query \"[?appId=='{app_id}']\" --output json"
        )
        service_principal = await self.azure_cli.run_command(
            command_get_sp,
            return_json=True,
        )

        if service_principal:
            return service_principal[0]

        # Service principal does not exist, create it
        command_create_sp = f"az ad sp create --id {app_id}"
        await self.azure_cli.run_command(
            command_create_sp,
            success_message=f"Service principal created for app ID '{app_id}'",
            failure_message=f"Failed to create service principal for app ID '{app_id}'",
        )

        # Retrieve the object ID of the newly created service principal
        new_service_principal = await self.azure_cli.run_command(
            command_get_sp,
            failure_message=(
                f"Failed to retrieve new service principal for app ID {app_id}"
            ),
            return_json=True,
        )

        if new_service_principal:
            return new_service_principal[0]
        else:
            raise Exception(
                f"Failed to retrieve new service principal for app ID {app_id}"
            )

    async def _get_or_create_identity(
        self, identity_name: str, resource_group_name: str, subscription_id: str
    ):
        """
        Retrieves or creates a managed identity for the given resource group.

        Returns:
            dict: Object representing the identity.
        """
        # Try to retrieve the existing identity
        command_get_identity = (
            f"az identity list --query \"[?name=='{identity_name}']\" --resource-group"
            f" {resource_group_name} --subscription {subscription_id} --output json"
        )
        identity = await self.azure_cli.run_command(
            command_get_identity,
            return_json=True,
        )

        if identity:
            self._console.print(
                (
                    f"Identity '{self._identity_name}' already exists in"
                    f" subscription '{self._subscription_name}'."
                ),
                style="yellow",
            )
            return identity[0]

        # Identity does not exist, create it
        command_create_identity = (
            f"az identity create --name {identity_name} --resource-group"
            f" {resource_group_name} --subscription {subscription_id} --output json"
        )
        response = await self.azure_cli.run_command(
            command_create_identity,
            success_message=f"Identity {identity_name!r} created",
            failure_message=f"Failed to create identity {identity_name!r}",
            return_json=True,
        )

        if response:
            return response
        else:
            raise Exception(
                f"Failed to retrieve new identity for identity {self._identity_name}"
            )

    @staticmethod
    def _generate_acr_name(base_name: str):
        # Ensure the base name adheres to ACR naming conventions
        if not base_name.isalnum() or len(base_name) > 50:
            raise ValueError(
                "ACR registry name prefix should be alphanumeric and up to 50"
                " characters"
            )

        # Generate a unique string
        timestamp = int(time.time())
        random_str = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=4)
        )

        # Combine to form the ACR name
        acr_name = f"{base_name}{timestamp}{random_str}"
        return acr_name

    async def _get_or_create_registry(
        self,
        registry_name: str,
        resource_group_name: str,
        location: str,
        subscription_id: str,
    ):
        """
        Retrieves or creates an Azure Container Registry.

        Args:
            registry_name: The name of the registry.
            resource_group_name: The name of the resource group to use for the registry.
            location: Where to create the registry.
            subscription_id: The ID of the subscription to use for the registry.

        Returns:
            dict: Object representing the registry.
        """
        # check to see if there are any registries starting with 'prefect'
        command_get_registries = (
            'az acr list --query "[?starts_with(name,'
            f" '{self._registry_name_prefix}')]\" --subscription"
            f" {subscription_id} --output json"
        )
        response = await self.azure_cli.run_command(
            command_get_registries,
            return_json=True,
        )

        # acr names must be globally unique, so if there are any matches, use the first one
        if response:
            self._console.print(
                (
                    f"Registry with prefix {self._registry_name_prefix!r} already"
                    f" exists in subscription '{subscription_id}'."
                ),
                style="yellow",
            )
            return response[0]

        command_create_repository = (
            f"az acr create --name {registry_name} --resource-group"
            f" {resource_group_name} --subscription {subscription_id} --location"
            f" {location} --sku Basic"
        )
        response = await self.azure_cli.run_command(
            command_create_repository,
            success_message="Registry created",
            failure_message="Failed to create registry",
            return_json=True,
        )

        if response:
            return response
        else:
            raise Exception(f"Failed to create registry {registry_name}")

    async def _log_into_registry(self, login_server: str, subscription_id: str):
        """
        Logs into the given Azure Container Registry.

        Args:
            registry_name: The name of the registry to log into.

        Raises:
            subprocess.CalledProcessError: If the Azure CLI command execution fails.
        """
        command_login = (
            f"az acr login --name {login_server} --subscription {subscription_id}"
        )
        await self.azure_cli.run_command(
            command_login,
            success_message=f"Logged into registry {login_server}",
            failure_message=f"Failed to log into registry {login_server}",
        )

    async def _assign_contributor_role(self, app_id: str, subscription_id: str) -> None:
        """
        Assigns the 'Contributor' role to the service principal associated with a given app ID.

        Args:
            app_id (str): The client ID of the app registration.
        """
        service_principal = await self._get_or_create_service_principal_object_id(
            app_id
        )

        service_principal_id = service_principal["id"]

        if service_principal_id:
            role = "Contributor"
            scope = f"/subscriptions/{self._subscription_id}/resourceGroups/{self._resource_group_name}"

            # Check if the role is already assigned
            check_role_command = (
                f"az role assignment list --assignee {service_principal_id} --role"
                f" {role} --scope {scope} --subscription {subscription_id} --output"
                " json"
            )
            role_assignments = await self.azure_cli.run_command(
                check_role_command, return_json=True
            )
            if role_assignments and any(
                ra
                for ra in role_assignments
                if ra["roleDefinitionName"] == role and ra["scope"] == scope
            ):
                self._console.print(
                    (
                        f"Service principal with object ID '{service_principal_id}'"
                        f" already has the '{role}' role assigned in '{scope}'."
                    ),
                    style="yellow",
                )
                return

            assign_command = (
                f"az role assignment create --role {role} --assignee-object-id"
                f" {service_principal_id} --scope {scope} --subscription"
                f" {subscription_id}"
            )
            await self.azure_cli.run_command(
                assign_command,
                success_message=(
                    "Contributor role assigned to service principal with object ID"
                    f" '{service_principal_id}'"
                ),
                failure_message=(
                    "Failed to assign Contributor role to service principal with"
                    f" object ID '{service_principal_id}'"
                ),
                ignore_if_exists=True,
            )

    async def _assign_acr_pull_role(
        self, identity: Dict[str, Any], registry: Dict[str, Any], subscription_id: str
    ) -> None:
        """
        Assigns the AcrPull role to the specified identity for the given registry.

        Args:
            identity: The identity to assign the role to.
            registry: The registry to grant access to.
        """
        command = (
            "az role assignment create --assignee-object-id"
            f" {identity['principalId']} --assignee-principal-type ServicePrincipal"
            f" --scope {registry['id']} --role AcrPull --subscription {subscription_id}"
        )
        await self.azure_cli.run_command(
            command,
            ignore_if_exists=True,
        )

    async def _create_aci_credentials_block(
        self,
        work_pool_name: str,
        client_id: str,
        tenant_id: str,
        client_secret: str,
        client: "PrefectClient",
    ) -> UUID:
        """
        Creates a credentials block for Azure Container Instance.

        Args:
            work_pool_name (str): The name of the work pool.
            client_id (str): The client ID obtained from app registration.
            tenant_id (str): The tenant ID obtained from the secret generation.
            client_secret (str): The client secret obtained from the secret generation.
            client (PrefectClient): An instance of PrefectClient.

        Returns:
            UUID: The ID of the created credentials block.

        Raises:
            ObjectAlreadyExists: If a credentials block with the same name already exists.
        """
        credentials_block_name = self._credentials_block_name
        credentials_block_type = await client.read_block_type_by_slug(
            "azure-container-instance-credentials"
        )

        credentials_block_schema = (
            await client.get_most_recent_block_schema_for_block_type(
                block_type_id=credentials_block_type.id
            )
        )

        try:
            block_doc = await client.create_block_document(
                block_document=BlockDocumentCreate(
                    name=credentials_block_name,
                    data={
                        "client_id": client_id,
                        "tenant_id": tenant_id,
                        "client_secret": client_secret,
                    },
                    block_type_id=credentials_block_type.id,
                    block_schema_id=credentials_block_schema.id,
                )
            )

            self._console.print(
                (
                    f"ACI credentials block '{credentials_block_name}' created in"
                    " Prefect Cloud"
                ),
                style="green",
            )
            return block_doc.id

        except ObjectAlreadyExists:
            self._console.print(
                f"ACI credentials block '{credentials_block_name}' already exists",
                style="yellow",
            )
            block_doc = await client.read_block_document_by_name(
                name=credentials_block_name,
                block_type_slug="azure-container-instance-credentials",
            )
            return block_doc.id

        except Exception as e:
            self._console.print(
                f"Failed to create ACI credentials block: {e}",
                style="red",
            )
            raise e

    async def _aci_credentials_block_exists(
        self, block_name: str, client: "PrefectClient"
    ) -> bool:
        """
        Checks if an ACI credentials block with the given name already exists.

        Args:
            block_name (str): The name of the ACI credentials block.
            client (PrefectClient): An instance of PrefectClient.

        Returns:
            bool: True if the credentials block exists, False otherwise.
        """
        try:
            await client.read_block_document_by_name(
                name=block_name,
                block_type_slug="azure-container-instance-credentials",
            )
            return True
        except ObjectNotFound:
            return False

    def _validate_user_input(self, name):
        if 2 < len(name) < 40 and name.isalnum():
            return True
        else:
            return False

    async def _create_provision_table(
        self, work_pool_name: str, client: "PrefectClient"
    ):
        return Panel(
            dedent(
                f"""\
                    Provisioning infrastructure for your work pool [blue]{work_pool_name}[/] will require:

                        Updates in subscription: [blue]{self._subscription_name}[/]

                            - Create a resource group in location: [blue]{self._location}[/]
                            - Create an app registration in Azure AD: [blue]{self._app_registration_name}[/]
                            - Create/use a service principal for app registration
                            - Generate a secret for app registration
                            - Create an Azure Container Registry with prefix [blue]{self._registry_name_prefix}[/]
                            - Create an identity [blue]{self._identity_name}[/] to allow access to the created registry
                            - Assign Contributor role to service account
                            - Create an ACR registry for image hosting
                            - Create an identity for Azure Container Instance to allow access to the registry

                        Updates in Prefect workspace

                            - Create Azure Container Instance credentials block: [blue]{self._credentials_block_name}[/]
                    """
            ),
            expand=False,
        )

    async def _customize_resource_names(
        self, work_pool_name: str, client: "PrefectClient"
    ) -> bool:
        self._resource_group_name = prompt(
            "Please enter a name for the resource group",
            default=self._resource_group_name,
        )
        self._app_registration_name = prompt(
            "Please enter a name for the app registration",
            default=self._app_registration_name,
        )
        while True:
            self._registry_name_prefix = prompt(
                "Please enter a prefix for the Azure Container Registry",
                default=self._registry_name_prefix,
            )
            if self._validate_user_input(self._registry_name_prefix):
                break
            else:
                self._console.print(
                    "The prefix must be alphanumeric and between 3-50 characters.",
                    style="red",
                )
        self._identity_name = prompt(
            "Please enter a name for the identity (used for ACR access)",
            default=self._identity_name,
        )
        self._credentials_block_name = prompt(
            "Please enter a name for the ACI credentials block",
            default=self._credentials_block_name,
        )
        table = await self._create_provision_table(work_pool_name, client)
        self._console.print(table)

        return Confirm.ask(
            "Proceed with infrastructure provisioning?", console=self._console
        )

    @inject_client
    async def provision(
        self,
        work_pool_name: str,
        base_job_template: Dict[str, Any],
        client: Optional["PrefectClient"] = None,
    ) -> Dict[str, Any]:
        """
        Orchestrates the provisioning of Azure resources and setup for the push work pool.

        Args:
            work_pool_name (str): The name of the work pool.
            base_job_template (Dict[str, Any]): The base template for job creation.
            client (Optional[PrefectClient]): An instance of PrefectClient. If None, it will be injected.

        Returns:
            Dict[str, Any]: The updated job template with necessary references and configurations.

        Raises:
            RuntimeError: If client injection fails or the Azure CLI command execution fails.
        """
        if not client:
            self._console.print(
                "Client injection failed, cannot proceed with provisioning.",
                style="red",
            )
            return base_job_template

        await self._verify_az_ready()
        await self._select_subscription()
        await self.set_location()
        self._credentials_block_name = f"{work_pool_name}-push-pool-credentials"

        table = await self._create_provision_table(work_pool_name, client)
        self._console.print(table)
        if self._console.is_interactive:
            chosen_option = prompt_select_from_table(
                self._console,
                "Proceed with infrastructure provisioning with default resource names?",
                [
                    {"header": "Options:", "key": "option"},
                ],
                [
                    {
                        "option": (
                            "Yes, proceed with infrastructure provisioning with default"
                            " resource names"
                        )
                    },
                    {"option": "Customize resource names"},
                    {"option": "Do not proceed with infrastructure provisioning"},
                ],
            )
            if chosen_option["option"] == "Customize resource names":
                if not await self._customize_resource_names(work_pool_name, client):
                    return base_job_template

            elif (
                chosen_option["option"]
                == "Do not proceed with infrastructure provisioning"
            ):
                return base_job_template
            elif (
                chosen_option["option"]
                != "Yes, proceed with infrastructure provisioning with default"
                " resource names"
            ):
                # basically, we should never hit this. i'm concerned that we might change
                # the options in the future and forget to update this check
                raise ValueError(f"Invalid option selected: {chosen_option['option']}")

        credentials_block_exists = await self._aci_credentials_block_exists(
            block_name=self._credentials_block_name, client=client
        )

        if not credentials_block_exists:
            total_tasks = 7
        else:
            total_tasks = 6

        with Progress(console=self._console) as progress:
            self.azure_cli._console = progress.console
            task = progress.add_task("Provisioning infrastructure.", total=total_tasks)
            progress.console.print("Creating resource group")
            await self._create_resource_group()
            progress.advance(task)

            progress.console.print("Creating app registration")
            client_id = await self._create_app_registration()
            progress.advance(task)

            credentials_block_exists = await self._aci_credentials_block_exists(
                block_name=self._credentials_block_name, client=client
            )

            if not credentials_block_exists:
                progress.console.print("Generating secret for app registration")
                tenant_id, client_secret = await self._generate_secret_for_app(
                    app_id=client_id,
                )
                progress.advance(task)

                progress.console.print("Creating ACI credentials block")
                block_doc_id = await self._create_aci_credentials_block(
                    work_pool_name, client_id, tenant_id, client_secret, client
                )
                progress.advance(task)
            else:
                progress.console.print(
                    "ACI credentials block already exists.", style="yellow"
                )
                block_doc = await client.read_block_document_by_name(
                    name=self._credentials_block_name,
                    block_type_slug="azure-container-instance-credentials",
                )
                block_doc_id = block_doc.id
                progress.advance(task)

            progress.console.print("Assigning Contributor role to service account")
            await self._assign_contributor_role(
                app_id=client_id, subscription_id=self._subscription_id
            )
            progress.advance(task)

            progress.console.print(
                "Creating Azure Container Registry (this make take a few minutes)"
            )

            registry_name = self._generate_acr_name(self._registry_name_prefix)
            registry = await self._get_or_create_registry(
                registry_name=registry_name,
                resource_group_name=self._resource_group_name,
                location=self._location,
                subscription_id=self._subscription_id,
            )
            await self._log_into_registry(
                login_server=registry["loginServer"],
                subscription_id=self._subscription_id,
            )
            update_current_profile(
                {PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE: registry["loginServer"]}
            )
            progress.advance(task)

            progress.console.print("Creating identity")
            identity = await self._get_or_create_identity(
                identity_name=self._identity_name,
                resource_group_name=self._resource_group_name,
                subscription_id=self._subscription_id,
            )
            await self._assign_acr_pull_role(
                identity=identity,
                registry=registry,
                subscription_id=self._subscription_id,
            )
            progress.advance(task)

        base_job_template_copy = deepcopy(base_job_template)
        base_job_template_copy["variables"]["properties"]["aci_credentials"][
            "default"
        ] = {"$ref": {"block_document_id": str(block_doc_id)}}

        base_job_template_copy["variables"]["properties"]["resource_group_name"][
            "default"
        ] = self._resource_group_name

        base_job_template_copy["variables"]["properties"]["subscription_id"][
            "default"
        ] = self._subscription_id
        base_job_template_copy["variables"]["properties"]["image_registry"][
            "default"
        ] = {
            "registry_url": registry["loginServer"],
            "identity": identity["id"],
        }
        base_job_template_copy["variables"]["properties"]["identities"]["default"] = [
            identity["id"]
        ]

        self._console.print(
            dedent(
                f"""\
                    Your default Docker build namespace has been set to [blue]{registry["loginServer"]!r}[/].
                    Use any image name to build and push to this registry by default:
                    """
            ),
            Panel(
                Syntax(
                    dedent(
                        f"""\
                        from prefect import flow
                        from prefect.docker import DockerImage


                        @flow(log_prints=True)
                        def my_flow(name: str = "world"):
                            print(f"Hello {{name}}! I'm a flow running on an Azure Container Instance!")


                        if __name__ == "__main__":
                            my_flow.deploy(
                                name="my-deployment",
                                work_pool_name="{work_pool_name}",
                                image=DockerImage(
                                    name="my-image:latest",
                                    platform="linux/amd64",
                                )
                            )"""
                    ),
                    "python",
                    background_color="default",
                ),
                title="example_deploy_script.py",
                expand=False,
            ),
        )

        self._console.print(
            (
                f"Infrastructure successfully provisioned for '{work_pool_name}' work"
                " pool!"
            ),
            style="green",
        )
        return base_job_template_copy
