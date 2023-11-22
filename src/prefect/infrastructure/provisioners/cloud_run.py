import json
import shlex
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
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
from prefect.client.orchestration import PrefectClient, ServerType
from prefect.client.schemas.actions import BlockDocumentCreate
from prefect.client.utilities import inject_client
from prefect.exceptions import ObjectAlreadyExists
from prefect.settings import PREFECT_DEBUG_MODE


class CloudRunPushProvisioner:
    def __init__(self):
        self._console = Console()
        self._project = None
        self._region = None

    @property
    def console(self):
        return self._console

    @console.setter
    def console(self, value):
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

    async def _verify_gcloud_ready(self):
        try:
            await self._run_command("gcloud --version")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "gcloud not found. Please install gcloud and ensure it is in your PATH."
            ) from e

        accounts = json.loads(await self._run_command("gcloud auth list --format=json"))
        if not [account for account in accounts if account["status"] == "ACTIVE"]:
            raise RuntimeError(
                "No active gcloud account found. Please run `gcloud auth login`."
            )

    async def _get_project(self):
        if self._console.is_interactive:
            with Progress(
                SpinnerColumn(),
                TextColumn("Fetching your GCP projects..."),
                transient=True,
                console=self.console,
            ) as progress:
                list_projects_task = progress.add_task("list_projects", total=1)
                projects_raw = await self._run_command(
                    "gcloud projects list --format=json"
                )

                progress.update(list_projects_task, completed=1)
            projects = json.loads(projects_raw)
            selected_project = prompt_select_from_table(
                self.console,
                "Please select which GCP project to use",
                [
                    {"header": "Name", "key": "name"},
                    {"header": "Project ID", "key": "projectId"},
                ],
                projects,
            )
            return selected_project["projectId"]
        else:
            return await self._run_command("gcloud config get-value project")

    async def _get_default_region(self):
        default_region = await self._run_command("gcloud config get-value run/region")
        return default_region or "us-central1"

    async def _enable_cloud_run_api(self):
        try:
            await self._run_command("gcloud services enable run.googleapis.com")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Error enabling Cloud Run API. Please ensure you have the necessary"
                " permissions."
            ) from e

    async def _create_service_account(self):
        try:
            await self._run_command(
                "gcloud iam service-accounts create prefect-cloud-run"
                ' --display-name "Prefect Cloud Run Service Account"'
            )
        except subprocess.CalledProcessError as e:
            if "already exists" not in e.output.decode("utf-8"):
                return
            raise RuntimeError(
                "Error creating service account. Please ensure you have the necessary"
                " permissions."
            ) from e

    async def _create_service_account_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                await self._run_command(
                    "gcloud iam service-accounts keys create"
                    f" {tmpdir}/prefect-cloud-run-key.json"
                    f" --iam-account=prefect-cloud-run@{self._project}.iam.gserviceaccount.com"
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError(
                    "Error creating service account key. Please ensure you have the"
                    " necessary permissions."
                ) from e
            key = json.loads((Path(tmpdir) / "prefect-cloud-run-key.json").read_text())
        return key

    async def _assign_roles(self):
        try:
            await self._run_command(
                "gcloud projects add-iam-policy-binding"
                f' {self._project} --member="serviceAccount:prefect-cloud-run@{self._project}.iam.gserviceaccount.com"'
                ' --role="roles/iam.serviceAccountUser"'
            )
            await self._run_command(
                "gcloud projects add-iam-policy-binding"
                f' {self._project} --member="serviceAccount:prefect-cloud-run@{self._project}.iam.gserviceaccount.com"'
                ' --role="roles/run.developer"'
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Error assigning roles to service account. Please ensure you have the"
                " necessary permissions."
            ) from e

    async def _create_gcp_credentials_block(
        self, work_pool_name: str, key: dict, client: PrefectClient
    ) -> UUID:
        credentials_block_type = await client.read_block_type_by_slug("gcp-credentials")

        credentials_block_schema = (
            await client.get_most_recent_block_schema_for_block_type(
                block_type_id=credentials_block_type.id
            )
        )

        try:
            block_doc = await client.create_block_document(
                block_document=BlockDocumentCreate(
                    name=f"{work_pool_name}-push-pool-credentials",
                    data={"service_account_info": key},
                    block_type_id=credentials_block_type.id,
                    block_schema_id=credentials_block_schema.id,
                )
            )
            return block_doc.id
        except ObjectAlreadyExists:
            block_doc = await client.read_block_document_by_name(
                name=f"{work_pool_name}-push-pool-credentials",
                block_type_slug="gcp-credentials",
            )
            return block_doc.id

    @inject_client
    async def provision(
        self,
        work_pool_name: str,
        base_job_template: dict,
        client: Optional[PrefectClient] = None,
    ) -> Dict[str, Any]:
        assert client, "Client injection failed"
        await self._verify_gcloud_ready()
        self._project = await self._get_project()
        self._region = await self._get_default_region()

        table = Panel(
            dedent(
                f"""\
                    Provisioning infrastructure for your work pool [blue]{work_pool_name}[/] will require:

                        Updates in GCP project [blue]{self._project}[/] in region [blue]{self._region}[/]

                            - Activate the Cloud Run API for your project
                            - Create a service account for managing Cloud Run jobs: [blue]prefect-cloud-run[/]
                                - Service account will be granted the following roles:
                                    - Service Account User
                                    - Cloud Run Developer
                            - Create a key for service account [blue]prefect-cloud-run[/]

                        Updates in Prefect {"workspace" if client.server_type == ServerType.CLOUD else "server"}

                            - Create GCP credentials block [blue]{work_pool_name}-push-pool-credentials[/] to store the service account key
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
            task = progress.add_task("Provisioning Infrastructure", total=5)
            progress.console.print("Activating Cloud Run API")
            await self._enable_cloud_run_api()
            progress.advance(task)

            progress.console.print("Creating service account")
            await self._create_service_account()
            progress.advance(task)

            progress.console.print("Assigning roles to service account")
            await self._assign_roles()
            progress.advance(task)

            progress.console.print("Creating service account key")
            key = await self._create_service_account_key()
            progress.advance(task)

            progress.console.print("Creating GCP credentials block")
            block_doc_id = await self._create_gcp_credentials_block(
                work_pool_name, key, client
            )
            base_job_template_copy = deepcopy(base_job_template)
            base_job_template_copy["variables"]["properties"]["credentials"][
                "default"
            ] = {"$ref": {"block_document_id": str(block_doc_id)}}
            progress.advance(task)

        self._console.print("Infrastructure successfully provisioned!", style="green")

        return base_job_template_copy
