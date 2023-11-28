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
from rich.pretty import Pretty
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from prefect.cli._prompts import prompt_select_from_table
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import BlockDocumentCreate
from prefect.client.utilities import inject_client
from prefect.exceptions import ObjectAlreadyExists
from prefect.settings import PREFECT_DEBUG_MODE


class ContainerInstancePushProvisioner:
    def __init__(self):
        self._console = Console()
        self._subscription_id = None
        self._subscription_name = None
        self._resource_group = None
        self._aci = None
        self._location = None

    @property
    def console(self) -> Console:
        return self._console

    @console.setter
    def console(self, value: Console) -> None:
        self._console = value

    async def _run_command(self, command: str, *args, **kwargs):
        result = await run_process(shlex.split(command), check=False, *args, **kwargs)

        if result.returncode != 0:
            if PREFECT_DEBUG_MODE:
                self._console.print(
                    "Error running command:",
                    Pretty(
                        {
                            "command": command,
                            "stdout": result.stdout.decode("utf-8"),
                            "stderr": result.stderr.decode("utf-8"),
                        }
                    ),
                    style="red",
                )
            raise subprocess.CalledProcessError(
                result.returncode, command, output=result.stdout, stderr=result.stderr
            )

        return result.stdout.decode("utf-8").strip()

    async def _verify_az_ready(self) -> None:
        try:
            await self._run_command("az --version")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Azure CLI is not installed. Please see"
                " https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
            ) from e
        accounts = json.loads(await self._run_command("az account list --output json"))
        if not accounts:
            raise RuntimeError(
                "No Azure accounts found. Please run `az login` to log in to Azure."
            )

    async def _select_subscription(self) -> str:
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
                subscriptions_raw = await self._run_command(
                    "az account list --output json"
                )
                progress.update(list_projects_task, completed=1)
            subscriptions = json.loads(subscriptions_raw)
            selected_subscription = prompt_select_from_table(
                self.console,
                "Please select which Azure subscription to use:",
                [
                    {"header": "Name", "key": "name"},
                    {"header": "Subscription ID", "key": "id"},
                ],
                subscriptions,
            )
            return selected_subscription["id"]
        else:
            return await self._run_command("az account show --output json --query id")

    async def _create_resource_group(self) -> str:
        self._resource_group = f"prefect-{UUID().hex[:8]}"
        await self._run_command(
            f"az group create --name {self._resource_group} --location {self._location}"
        )
        return self._resource_group

    async def _create_app_registration(self) -> tuple:
        app_name = f"prefect-{UUID().hex[:8]}"
        description = (
            "App registration created by Prefect for Azure Container Instance push work"
            " pool"
        )

        try:
            app_registration_command = (
                f"az ad app create --display-name {app_name} "
                f"--description '{description}' --output json"
            )
            app_registration = json.loads(
                await self._run_command(app_registration_command)
            )
            client_id = app_registration["appId"]

            service_principal_command = (
                f"az ad sp create --id {client_id} --output json"
            )
            await self._run_command(service_principal_command)

            secret_command = (
                f"az ad app credential reset --id {client_id} --append --output json"
            )
            app_secret = json.loads(await self._run_command(secret_command))
            client_secret = app_secret["password"]

            tenant_id = app_secret["tenant"]
            return client_id, tenant_id, client_secret

        except subprocess.CalledProcessError as e:
            self._console.log(
                f"Failed to create app registration: {e.stderr}", style="red"
            )
            raise

    async def _assign_contributor_role(self, app_id: str) -> None:
        role = "Contributor"
        scope = f"/subscriptions/{self._subscription_id}/resourceGroups/{self._resource_group}"

        try:
            assign_command = (
                f"az role assignment create --role {role} --assignee {app_id} --scope"
                f" {scope}"
            )
            await self._run_command(assign_command)

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to assign role to service principal: {e.stderr}"
            raise RuntimeError(error_msg) from e

    async def _create_container_instance(self) -> None:
        container_group_name = f"prefect-{UUID().hex[:8]}"
        try:
            create_command = (
                f"az container create --name {container_group_name} "
                f"--resource-group {self._resource_group} "
                f"--image {container_group_name} "
                "--restart-policy OnFailure --output json"
            )
            await self._run_command(create_command)

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to create Azure Container Instance: {e.stderr}"
            raise RuntimeError(error_msg) from e

    async def _create_aci_credentials_block(
        self,
        work_pool_name: str,
        client_id: str,
        tenant_id: str,
        client_secret: str,
        client: PrefectClient,
    ) -> UUID:
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
                    name=f"{work_pool_name}-push-pool-credentials",
                    data={
                        "client_id": client_id,
                        "tenant_id": tenant_id,
                        "client_secret": client_secret,
                    },
                    block_type_id=credentials_block_type.id,
                    block_schema_id=credentials_block_schema.id,
                )
            )

            return block_doc.id

        except ObjectAlreadyExists:
            block_doc = await client.read_block_document_by_name(
                name=f"{work_pool_name}-push-pool-credentials",
                block_type_slug="azure-container-instance-credentials",
            )
            return block_doc.id

    @inject_client
    async def provision(
        self,
        work_pool_name: str,
        base_job_template: Dict[str, Any],
        client: Optional[PrefectClient] = None,
    ) -> Dict[str, Any]:
        assert client, "Client injection failed"
        await self._verify_az_ready()
        self._subscription_id, self._subscription_name = (
            await self._select_subscription()
        )

        table = Panel(
            dedent(
                f"""\
                    Provisioning infrastructure for your work pool [blue]{work_pool_name}[/] will require:

                        Updates in Azure subscription [blue]{self._subscription_name}[/] in region [blue]{self._location}[/]

                            - Create a resource group: [blue]{self._resource_group}[/]
                            - Create an Azure Container Instance: [blue]{self._aci}[/]

                        Updates in Prefect workspace

                            - Create Azure Container Instance credentials block [blue]{work_pool_name}-push-pool-credentials[/]
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
            progress.console.print("Creating resource group...")
            await self._create_resource_group()
            progress.advance(task)

            progress.console.print("Creating app registration...")
            client_id, tenant_id, client_secret = await self._create_app_registration()
            progress.advance(task)

            progress.console.print(
                "Adding app registration contributor role to resource group..."
            )
            await self._assign_contributor_role(app_id=client_id)
            progress.advance(task)

            progress.console.print("Creating container instance...")
            await self._create_container_instance()
            progress.advance(task)

            progress.console.print(
                "Creating Azure Container Instance credentials block..."
            )
            block_doc_id = await self._create_aci_credentials_block(
                work_pool_name, client_id, tenant_id, client_secret, client
            )

            base_job_template_copy = deepcopy(base_job_template)
            base_job_template_copy["variables"]["properties"]["credentials"][
                "default"
            ] = {"$ref": {"block_document_id": str(block_doc_id)}}
            progress.advance(task)

        self._console.print("Infrastructure successfully provisioned!", style="green")

        return base_job_template
