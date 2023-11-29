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
import shlex
import subprocess
from copy import deepcopy
from textwrap import dedent
from typing import Any, Dict, Optional
from uuid import UUID

from anyio import run_process
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from prefect.cli._prompts import prompt_select_from_table
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import BlockDocumentCreate
from prefect.client.utilities import inject_client
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound


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
                    return ("created", json.loads(output))
                except json.JSONDecodeError as e:
                    self._console.print(f"Failed to decode JSON: {e}", style="red")
                    raise e

            return ("created", output)

        except subprocess.CalledProcessError as e:
            self._console.print(f"Command execution failed: {e}", style="red")
            return ("error", None)


class ContainerInstancePushProvisioner:
    """
    A class responsible for provisioning Azure resources and setting up a push work pool.

    Attributes:
        _console (Console): A Rich console object for displaying messages and progress.
        _subscription_id (str): Azure subscription ID.
        _subscription_name (str): Azure subscription name.
        _resource_group (str): Azure resource group name.
        _location (str): Azure resource location.
        _container_image (str): Docker image for the container instance.
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
        _create_container_instance: Creates an Azure Container Instance.
        _create_aci_credentials_block: Creates an Azure Container Instance credentials block.
        provision: Orchestrates the provisioning of Azure resources and setup for the push work pool.
    """

    DEFAULT_LOCATION = "eastus"
    RESOURCE_GROUP_NAME = "prefect-aci-push-pool-rg"
    CONTAINER_IMAGE = "docker.io/prefecthq/prefect:2-latest"
    APP_REGISTRATION_NAME = "prefect-aci-push-pool-app"

    def __init__(self):
        self._console = Console()
        self._subscription_id = None
        self._subscription_name = None
        self._location = None
        self.azure_cli = AzureCLI(self.console)
        self.created_resources = []

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
            _, output = await self.azure_cli.run_command(command)
            self._location = output if output else self.DEFAULT_LOCATION
        except subprocess.CalledProcessError as e:
            self._location = self.DEFAULT_LOCATION
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

        _, accounts_unformatted = await self.azure_cli.run_command(
            command="az account list --output json",
        )
        if accounts_unformatted:
            accounts = json.loads(accounts_unformatted)
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
            _, subscriptions_list = await self.azure_cli.run_command(
                command="az account list --output json",
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
                return selected_subscription["id"], selected_subscription["name"]
        else:
            await self.azure_cli.run_command(
                command="az account show --output json --query id",
                success_message="Azure subscription found",
                failure_message="No Azure subscription found",
            )

    async def _create_resource_group(self):
        """
        Creates a resource group in Azure using predefined names and locations.

        Raises:
            subprocess.CalledProcessError: If the Azure CLI command execution fails.
        """
        resource_group_command = (
            f"az group create --name {self.RESOURCE_GROUP_NAME} --location"
            f" {self._location}"
        )
        result, _ = await self.azure_cli.run_command(
            resource_group_command,
            # I'd prefer the message says "it already exists if it does"
            success_message=(
                f"Resource group '{self.RESOURCE_GROUP_NAME}' created in location"
                f" '{self._location}'"
            ),
            failure_message=(
                f"Failed to create resource group '{self.RESOURCE_GROUP_NAME}' in"
                f" location '{self._location}'"
            ),
            ignore_if_exists=True,
        )
        if result == "created":
            self.created_resources.append(
                {"type": "resource_group", "name": self.RESOURCE_GROUP_NAME}
            )
        elif result == "exists":
            self._console.print(
                f"Resource group '{self.RESOURCE_GROUP_NAME}' already exists",
                style="yellow",
            )

    async def _create_app_registration(self) -> str:
        """
        Creates an app registration in Azure Active Directory.

        Returns:
            str: The client ID of the newly created app registration.

        Raises:
            subprocess.CalledProcessError: If the Azure CLI command execution fails.
        """
        app_registration_command = (
            f"az ad app create --display-name {self.APP_REGISTRATION_NAME} "
            "--output json"
        )
        result, output = await self.azure_cli.run_command(
            app_registration_command,
            success_message=(
                f"App registration '{self.APP_REGISTRATION_NAME}' created successfully"
            ),
            failure_message=(
                "Failed to create app registration with name"
                f" '{self.APP_REGISTRATION_NAME}'"
            ),
            ignore_if_exists=True,
        )
        if result == "created":
            self.created_resources.append(
                {"type": "app_registration", "name": self.APP_REGISTRATION_NAME}
            )
            app_registration = json.loads(output)
            return app_registration["appId"]

        elif result == "exists":
            self._console.print(
                f"App registration '{self.APP_REGISTRATION_NAME}' already exists",
                style="yellow",
            )
        elif result == "error":
            raise Exception("Error creating the app registration")

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
        result, output = await self.azure_cli.run_command(
            secret_command,
            success_message=(
                f"Secret generated for app registration with client ID '{app_id}'"
            ),
            failure_message=(
                "Failed to generate secret for app registration with client ID"
                f" '{app_id}'. If you have already generated 2 secrets for this app"
                " registration, please delete one from the `prefect-aci-push-pool-app`"
                " resource and try again."
            ),
            ignore_if_exists=True,
        )
        if result == "created":
            app_secret = json.loads(output)
            return app_secret["tenant"], app_secret["password"]

    async def _get_or_create_service_principal_object_id(self, app_id: str):
        """
        Retrieves or creates a service principal for the given app registration client ID.

        Args:
            app_id (str): The client ID of the app registration.

        Returns:
            str: The object ID of the service principal.
        """
        # Try to retrieve the existing service principal
        command_get_sp = f"az ad sp show --id {app_id}"
        _, service_principal = await self.azure_cli.run_command(
            command_get_sp,
            failure_message=(
                f"Failed to retrieve existing service principal for app ID {app_id}"
            ),
            return_json=True,
        )
        if service_principal:
            return service_principal

        # Service principal does not exist, create it
        command_create_sp = f"az ad sp create --id {app_id}"
        await self.azure_cli.run_command(
            command_create_sp,
            success_message=f"Service principal created for app ID '{app_id}'",
            failure_message=f"Failed to create service principal for app ID '{app_id}'",
        )

        # Retrieve the object ID of the newly created service principal
        _, new_service_principal = await self.azure_cli.run_command(
            command_get_sp,
            failure_message=(
                f"Failed to retrieve new service principal for app ID {app_id}"
            ),
            return_json=True,
        )

        if new_service_principal:
            return new_service_principal
        else:
            raise Exception(
                f"Failed to retrieve new service principal for app ID {app_id}"
            )

    async def _assign_contributor_role(self, app_id: str) -> None:
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
            scope = f"/subscriptions/{self._subscription_id}/resourceGroups/{self.RESOURCE_GROUP_NAME}"

            assign_command = (
                f"az role assignment create --role {role} --assignee-object-id"
                f" {service_principal_id} --scope {scope}"
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
        else:
            self._console.print(
                f"Failed to retrieve or create service principal for app ID '{app_id}'",
                style="red",
            )

    async def _create_container_instance(self) -> None:
        """
        Creates an Azure Container Instance using predefined settings.

        Raises:
            subprocess.CalledProcessError: If the Azure CLI command execution fails.
        """
        container_name = "prefect-acipool-container"

        create_command = (
            f"az container create --name {container_name} "
            f"--resource-group {self.RESOURCE_GROUP_NAME} "
            "--image docker.io/prefecthq/prefect:2-latest "
            "--restart-policy OnFailure --output json"
        )
        result, _ = await self.azure_cli.run_command(
            create_command,
            success_message=(
                f"Container instance '{container_name}' created successfully"
            ),
            failure_message=f"Failed to create container instance '{container_name}'",
            ignore_if_exists=True,
        )

        if result == "created":
            self.created_resources.append(
                {"type": "container_instance", "name": container_name}
            )
        elif result == "exists":
            self._console.print(
                f"Container instance '{container_name}' already exists", style="yellow"
            )
        elif result == "error":
            raise Exception(f"Error creating container instance '{container_name}'")

    async def _create_aci_credentials_block(
        self,
        work_pool_name: str,
        client_id: str,
        tenant_id: str,
        client_secret: str,
        client: PrefectClient,
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
        credentials_block_name = f"{work_pool_name}-push-pool-credentials"
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
                f"ACI credentials block '{credentials_block_name}' created",
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

    async def _aci_credentials_block_exists(
        self, block_name: str, client: PrefectClient
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

    @inject_client
    async def provision(
        self,
        work_pool_name: str,
        base_job_template: Dict[str, Any],
        client: Optional[PrefectClient] = None,
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
        self._subscription_id, self._subscription_name = (
            await self._select_subscription()
        )

        await self.set_location()

        table = Panel(
            dedent(
                f"""\
                    Provisioning infrastructure for your work pool [blue]{work_pool_name}[/] will require:

                        Updates in subscription [blue]{self._subscription_name}[/]

                            - Create a resource group in location [blue]{self._location}[/]
                            - Create an app registration in Azure AD
                            - Create a service principal for app registration
                            - Generate a secret for app registration
                            - Assign Contributor role to service account
                            - Create Azure Container Instance

                        Updates in Prefect workspace

                            - Create Azure Container Instance credentials block [blue]aci-push-pool-credentials[/]
                    """
            ),
            expand=False,
        )
        self._console.print(table)
        if self._console.is_interactive:
            if not Confirm.ask(
                "Proceed with infrastructure provisioning?", console=self._console
            ):
                return base_job_template

        with Progress(console=self._console) as progress:
            task = progress.add_task("Provisioning infrastructure...", total=5)
            progress.console.print("Creating resource group")
            await self._create_resource_group()
            progress.advance(task)

            progress.console.print("Creating app registration")
            client_id = await self._create_app_registration()
            progress.advance(task)

            progress.console.print("Generating secret for app registration")
            tenant_id, client_secret = await self._generate_secret_for_app(
                app_id=client_id,
            )
            block_doc_id = await self._create_aci_credentials_block(
                work_pool_name, client_id, tenant_id, client_secret, client
            )

            progress.advance(task)

            progress.console.print("Assigning Contributor role to service account...")
            await self._assign_contributor_role(app_id=client_id)
            progress.advance(task)

            progress.console.print("Creating Azure Container Instance")
            await self._create_container_instance()
            progress.advance(task)

            progress.console.print(
                "Creating Azure Container Instance credentials block"
            )

            base_job_template_copy = deepcopy(base_job_template)
            base_job_template_copy["variables"]["properties"]["aci_credentials"][
                "default"
            ] = {"$ref": {"block_document_id": str(block_doc_id)}}

            self._console.print(
                "Infrastructure successfully provisioned!", style="green"
            )
            return base_job_template
