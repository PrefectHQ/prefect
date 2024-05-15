import importlib
import shlex
import sys
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

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


modal = lazy_import("modal")


class ModalPushProvisioner:
    """
    A infrastructure provisioner for Modal push work pools.
    """

    def __init__(self, client: Optional["PrefectClient"] = None):
        self._console = Console()

    @property
    def console(self):
        return self._console

    @console.setter
    def console(self, value):
        self._console = value

    @staticmethod
    def _is_modal_installed() -> bool:
        """
        Checks if the modal package is installed.

        Returns:
            True if the modal package is installed, False otherwise
        """
        try:
            importlib.import_module("modal")
            return True
        except ModuleNotFoundError:
            return False

    async def _install_modal(self):
        """
        Installs the modal package.
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Installing modal..."),
            transient=True,
            console=self.console,
        ) as progress:
            task = progress.add_task("modal install")
            progress.start()
            global modal
            await run_process(
                [shlex.quote(sys.executable), "-m", "pip", "install", "modal"]
            )
            modal = importlib.import_module("modal")
            progress.advance(task)

    async def _get_modal_token_id_and_secret(self) -> Tuple[str, str]:
        """
        Gets a Model API token ID and secret from the current Modal configuration.
        """
        modal_config = modal.config.Config()
        modal_token_id = modal_config.get("token_id")
        modal_token_secret = modal_config.get("token_secret")

        return modal_token_id, modal_token_secret

    async def _create_new_modal_token(self):
        """
        Triggers a Modal login via the browser. Will create a new token in the default Modal profile.
        """
        await run_process([shlex.quote(sys.executable), "-m", "modal", "token", "new"])
        # Reload the modal.config module to pick up the new token
        importlib.reload(modal.config)

    async def _create_modal_credentials_block(
        self,
        block_document_name: str,
        modal_token_id: str,
        modal_token_secret: str,
        client: "PrefectClient",
    ) -> BlockDocument:
        """
        Creates a ModalCredentials block containing the provided token ID and secret.

        Args:
            block_document_name: The name of the block document to create
            modal_token_id: The Modal token ID
            modal_token_secret: The Modal token secret

        Returns:
            The ID of the created block
        """
        assert client is not None, "client injection failed"
        try:
            credentials_block_type = await client.read_block_type_by_slug(
                "modal-credentials"
            )
        except ObjectNotFound:
            # Shouldn't happen, but just in case
            raise RuntimeError(
                "Unable to find ModalCredentials block type. Please ensure you are"
                " using Prefect Cloud."
            )
        credentials_block_schema = (
            await client.get_most_recent_block_schema_for_block_type(
                block_type_id=credentials_block_type.id
            )
        )
        assert (
            credentials_block_schema is not None
        ), f"Unable to find schema for block type {credentials_block_type.slug}"

        block_doc = await client.create_block_document(
            block_document=BlockDocumentCreate(
                name=block_document_name,
                data={
                    "token_id": modal_token_id,
                    "token_secret": modal_token_secret,
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
        Provisions resources necessary for a Modal push work pool.

        Provisioned resources:
            - A ModalCredentials block containing a Modal API token

        Args:
            work_pool_name: The name of the work pool to provision resources for
            base_job_template: The base job template to update

        Returns:
            A copy of the provided base job template with the provisioned resources
        """
        credentials_block_name = f"{work_pool_name}-modal-credentials"
        base_job_template_copy = deepcopy(base_job_template)
        assert client is not None, "client injection failed"
        try:
            block_doc = await client.read_block_document_by_name(
                credentials_block_name, "modal-credentials"
            )
            self.console.print(
                f"Work pool [blue]{work_pool_name!r}[/] will reuse the existing Modal"
                f" credentials block [blue]{credentials_block_name!r}[/blue]"
            )
        except ObjectNotFound:
            if self._console.is_interactive and not Confirm.ask(
                (
                    "To configure your Modal push work pool we'll need to store a Modal"
                    " token with Prefect Cloud as a block. We'll pull the token from"
                    " your local Modal configuration or create a new token if we"
                    " can't find one. Would you like to continue?"
                ),
                console=self.console,
            ):
                self.console.print(
                    "No problem! You can always configure your Modal push work pool"
                    " later via the Prefect UI."
                )
                return base_job_template

            if not self._is_modal_installed():
                if self.console.is_interactive and Confirm.ask(
                    (
                        "The [blue]modal[/] package is required to configure"
                        " authentication for your work pool. Would you like to install"
                        " it now?"
                    ),
                    console=self.console,
                ):
                    await self._install_modal()

            # Get the current Modal token ID and secret
            (
                modal_token_id,
                modal_token_secret,
            ) = await self._get_modal_token_id_and_secret()
            if not modal_token_id or not modal_token_secret:
                # Create a new token one wasn't found
                if self.console.is_interactive and Confirm.ask(
                    (
                        "Modal credentials not found. Would you like to create a new"
                        " token?"
                    ),
                    console=self.console,
                ):
                    await self._create_new_modal_token()
                    (
                        modal_token_id,
                        modal_token_secret,
                    ) = await self._get_modal_token_id_and_secret()
                else:
                    raise RuntimeError(
                        "Modal credentials not found. Please create a new token by"
                        " running [blue]modal token new[/] and try again."
                    )

            # Create the credentials block
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]Saving Modal credentials..."),
                transient=True,
                console=self.console,
            ) as progress:
                task = progress.add_task("create modal credentials block")
                progress.start()
                block_doc = await self._create_modal_credentials_block(
                    credentials_block_name,
                    modal_token_id,
                    modal_token_secret,
                    client=client,
                )
                progress.advance(task)

        base_job_template_copy["variables"]["properties"]["modal_credentials"][
            "default"
        ] = {"$ref": {"block_document_id": str(block_doc.id)}}
        self.console.print(
            f"Successfully configured Modal push work pool {work_pool_name!r}!",
            style="green",
        )
        return base_job_template_copy
