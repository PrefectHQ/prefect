import importlib
import shlex
import sys
from copy import deepcopy
from types import ModuleType
from typing import TYPE_CHECKING, Any, Dict, Optional

from anyio import run_process
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from prefect.client.schemas.actions import BlockDocumentCreate
from prefect.client.schemas.objects import BlockDocument
from prefect.client.utilities import inject_client
from prefect.exceptions import ObjectNotFound
from prefect.utilities.importtools import lazy_import

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


coiled: ModuleType = lazy_import("coiled")


class CoiledPushProvisioner:
    """
    A infrastructure provisioner for Coiled push work pools.
    """

    def __init__(self, client: Optional["PrefectClient"] = None):
        self._console = Console()

    @property
    def console(self) -> Console:
        return self._console

    @console.setter
    def console(self, value: Console) -> None:
        self._console = value

    @staticmethod
    def _is_coiled_installed() -> bool:
        """
        Checks if the coiled package is installed.

        Returns:
            True if the coiled package is installed, False otherwise
        """
        try:
            importlib.import_module("coiled")
            return True
        except ModuleNotFoundError:
            return False

    async def _install_coiled(self):
        """
        Installs the coiled package.
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Installing coiled..."),
            transient=True,
            console=self.console,
        ) as progress:
            task = progress.add_task("coiled install")
            progress.start()
            global coiled
            await run_process(
                [shlex.quote(sys.executable), "-m", "pip", "install", "coiled"]
            )
            coiled = importlib.import_module("coiled")
            progress.advance(task)

    async def _get_coiled_token(self) -> str:
        """
        Gets a Coiled API token from the current Coiled configuration.
        """
        import dask.config

        return dask.config.get("coiled.token", "")

    async def _create_new_coiled_token(self):
        """
        Triggers a Coiled login via the browser if no current token. Will create a new token.
        """
        await run_process(["coiled", "login"])

    async def _create_coiled_credentials_block(
        self,
        block_document_name: str,
        coiled_token: str,
        client: "PrefectClient",
    ) -> BlockDocument:
        """
        Creates a CoiledCredentials block containing the provided token.

        Args:
            block_document_name: The name of the block document to create
            coiled_token: The Coiled API token

        Returns:
            The ID of the created block
        """
        assert client is not None, "client injection failed"
        try:
            credentials_block_type = await client.read_block_type_by_slug(
                "coiled-credentials"
            )
        except ObjectNotFound:
            # Shouldn't happen, but just in case
            raise RuntimeError(
                "Unable to find CoiledCredentials block type. Please ensure you are"
                " using Prefect Cloud."
            )
        credentials_block_schema = (
            await client.get_most_recent_block_schema_for_block_type(
                block_type_id=credentials_block_type.id
            )
        )
        assert credentials_block_schema is not None, (
            f"Unable to find schema for block type {credentials_block_type.slug}"
        )

        block_doc = await client.create_block_document(
            block_document=BlockDocumentCreate(
                name=block_document_name,
                data={
                    "api_token": coiled_token,
                },
                block_type_id=credentials_block_type.id,
                block_schema_id=credentials_block_schema.id,
            )
        )
        return block_doc

    @inject_client
    async def provision(
        self,
        work_pool_name: str,
        base_job_template: Dict[str, Any],
        client: Optional["PrefectClient"] = None,
    ) -> Dict[str, Any]:
        """
        Provisions resources necessary for a Coiled push work pool.

        Provisioned resources:
            - A CoiledCredentials block containing a Coiled API token

        Args:
            work_pool_name: The name of the work pool to provision resources for
            base_job_template: The base job template to update

        Returns:
            A copy of the provided base job template with the provisioned resources
        """
        credentials_block_name = f"{work_pool_name}-coiled-credentials"
        base_job_template_copy = deepcopy(base_job_template)
        assert client is not None, "client injection failed"
        try:
            block_doc = await client.read_block_document_by_name(
                credentials_block_name, "coiled-credentials"
            )
            self.console.print(
                f"Work pool [blue]{work_pool_name!r}[/] will reuse the existing Coiled"
                f" credentials block [blue]{credentials_block_name!r}[/blue]"
            )
        except ObjectNotFound:
            if self._console.is_interactive and not Confirm.ask(
                (
                    "\n"
                    "To configure your Coiled push work pool we'll need to store a Coiled"
                    " API token with Prefect Cloud as a block. We'll pull the token from"
                    " your local Coiled configuration or create a new token if we"
                    " can't find one.\n"
                    "\n"
                    "Would you like to continue?"
                ),
                console=self.console,
                default=True,
            ):
                self.console.print(
                    "No problem! You can always configure your Coiled push work pool"
                    " later via the Prefect UI."
                )
                return base_job_template

            if not self._is_coiled_installed():
                if self.console.is_interactive and Confirm.ask(
                    (
                        "The [blue]coiled[/] package is required to configure"
                        " authentication for your work pool.\n"
                        "\n"
                        "Would you like to install it now?"
                    ),
                    console=self.console,
                    default=True,
                ):
                    await self._install_coiled()

            if not self._is_coiled_installed():
                raise RuntimeError(
                    "The coiled package is not installed.\n\nPlease try installing coiled,"
                    " or you can use the Prefect UI to create your Coiled push work pool."
                )

            # Get the current Coiled API token
            coiled_api_token = await self._get_coiled_token()
            if not coiled_api_token:
                # Create a new token one wasn't found
                if self.console.is_interactive and Confirm.ask(
                    "Coiled credentials not found. Would you like to create a new token?",
                    console=self.console,
                    default=True,
                ):
                    await self._create_new_coiled_token()
                    coiled_api_token = await self._get_coiled_token()
                else:
                    raise RuntimeError(
                        "Coiled credentials not found. Please create a new token by"
                        " running [blue]coiled login[/] and try again."
                    )

            # Create the credentials block
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Saving Coiled credentials..."),
                transient=True,
                console=self.console,
            ) as progress:
                task = progress.add_task("create coiled credentials block")
                progress.start()
                block_doc = await self._create_coiled_credentials_block(
                    credentials_block_name,
                    coiled_api_token,
                    client=client,
                )
                progress.advance(task)

        base_job_template_copy["variables"]["properties"]["credentials"]["default"] = {
            "$ref": {"block_document_id": str(block_doc.id)}
        }
        if "image" in base_job_template_copy["variables"]["properties"]:
            base_job_template_copy["variables"]["properties"]["image"]["default"] = ""
        self.console.print(
            f"Successfully configured Coiled push work pool {work_pool_name!r}!",
            style="green",
        )
        return base_job_template_copy
