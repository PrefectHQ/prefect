import json
import shlex
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from textwrap import dedent
from uuid import UUID

from anyio import run_process
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty
from rich.progress import Progress
from rich.prompt import Confirm

from prefect.client.orchestration import PrefectClient, ServerType, get_client
from prefect.client.schemas.actions import BlockDocumentCreate
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

    async def _run_command(self, command, *args, **kwargs):
        result = await run_process(command, check=False, *args, **kwargs)

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

    async def _check_for_gcloud(self):
        try:
            await self._run_command(["gcloud", "--version"])
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "gcloud not found. Please install gcloud and ensure it is in your PATH."
            ) from e

    async def _get_current_project(self):
        return await self._run_command(shlex.split("gcloud config get-value project"))

    async def _get_default_region(self):
        default_region = await self._run_command(
            shlex.split("gcloud config get-value run/region")
        )
        return default_region or "us-central1"

    async def _enable_cloud_run_api(self):
        try:
            await self._run_command(
                shlex.split("gcloud services enable run.googleapis.com")
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Error enabling Cloud Run API. Please ensure you have the necessary"
                " permissions."
            ) from e

    async def _create_service_account(self):
        try:
            await self._run_command(
                shlex.split(
                    "gcloud iam service-accounts create prefect-cloud-run"
                    ' --display-name "Prefect Cloud Run Service Account"'
                )
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
                    shlex.split(
                        "gcloud iam service-accounts keys create"
                        f" {tmpdir}/prefect-cloud-run-key.json"
                        f" --iam-account=prefect-cloud-run@{self._project}.iam.gserviceaccount.com"
                    )
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
                shlex.split(
                    "gcloud projects add-iam-policy-binding"
                    f' {self._project} --member="serviceAccount:prefect-cloud-run@{self._project}.iam.gserviceaccount.com"'
                    ' --role="roles/iam.serviceAccountUser"'
                )
            )
            await self._run_command(
                shlex.split(
                    "gcloud projects add-iam-policy-binding"
                    f' {self._project} --member="serviceAccount:prefect-cloud-run@{self._project}.iam.gserviceaccount.com"'
                    ' --role="roles/run.developer"'
                )
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

    async def provision(self, work_pool_name: str, base_job_template: dict):
        async with get_client() as client:
            await self._check_for_gcloud()
            self._project = await self._get_current_project()
            self._region = await self._get_default_region()

            table = Panel(
                dedent(
                    f"""\
                    Here's what we'll do to provision infrastructure for this work pool:

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
            choice = Confirm.ask(
                "Proceed with infrastructure provisioning?", console=self._console
            )
            if not choice:
                return

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

            self._console.print(
                "Infrastructure successfully provisioned!", style="green"
            )

            return base_job_template_copy
