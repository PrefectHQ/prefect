import json
import shlex
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID

from anyio import run_process
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.syntax import Syntax

from prefect.cli._prompts import prompt, prompt_select_from_table
from prefect.client.orchestration import ServerType
from prefect.client.schemas.actions import BlockDocumentCreate
from prefect.client.utilities import inject_client
from prefect.exceptions import ObjectAlreadyExists
from prefect.settings import (
    PREFECT_DEBUG_MODE,
    PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE,
    update_current_profile,
)

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


class CloudRunPushProvisioner:
    def __init__(self):
        self._console: Console = Console()
        self._project = None
        self._region = None
        self._service_account_name = "prefect-cloud-run"
        self._credentials_block_name = None
        self._image_repository_name = "prefect-images"

    @property
    def console(self) -> Console:
        return self._console

    @console.setter
    def console(self, value: Console) -> None:
        self._console = value

    async def _run_command(self, command: str, *args: Any, **kwargs: Any) -> str:
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
            await self._run_command(
                f"gcloud services enable run.googleapis.com --project={self._project}"
            )

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Error enabling Cloud Run API. Please ensure you have the necessary"
                " permissions."
            ) from e

    async def _create_service_account(self):
        try:
            await self._run_command(
                f"gcloud iam service-accounts create {self._service_account_name}"
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
                    f" {tmpdir}/{self._service_account_name}-key.json"
                    f" --iam-account={self._service_account_name}@{self._project}.iam.gserviceaccount.com"
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError(
                    "Error creating service account key. Please ensure you have the"
                    " necessary permissions."
                ) from e
            key = json.loads(
                (Path(tmpdir) / f"{self._service_account_name}-key.json").read_text()
            )
        return key

    async def _assign_roles(self):
        try:
            await self._run_command(
                "gcloud projects add-iam-policy-binding"
                f' {self._project} --member="serviceAccount:{self._service_account_name}@{self._project}.iam.gserviceaccount.com"'
                ' --role="roles/iam.serviceAccountUser"'
            )
            await self._run_command(
                "gcloud projects add-iam-policy-binding"
                f' {self._project} --member="serviceAccount:{self._service_account_name}@{self._project}.iam.gserviceaccount.com"'
                ' --role="roles/run.developer"'
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Error assigning roles to service account. Please ensure you have the"
                " necessary permissions."
            ) from e

    async def _enable_artifact_registry_api(self):
        try:
            await self._run_command(
                "gcloud services enable artifactregistry.googleapis.com"
                f" --project={self._project}"
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Error enabling Artifact Registry API. Please ensure you have the"
                " necessary permissions."
            ) from e

    async def _create_artifact_registry_repository(self, repository_name: str):
        try:
            await self._run_command(
                "gcloud artifacts repositories create"
                f" {repository_name} --repository-format=docker"
                f" --location={self._region} --project={self._project}"
            )
        except subprocess.CalledProcessError as e:
            if "already exists" not in e.output.decode("utf-8"):
                return
            raise RuntimeError(
                "Error creating Artifact Registry repository. Please ensure you have"
                " the necessary permissions."
            ) from e

    async def _login_to_artifact_registry(self):
        try:
            await self._run_command(
                f"gcloud auth configure-docker {self._region}-docker.pkg.dev"
                f" --project={self._project}"
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Error logging into Artifact Registry. Please ensure you have the"
                " necessary permissions."
            ) from e

    async def _create_gcp_credentials_block(
        self, block_document_name: str, key: dict, client: "PrefectClient"
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
                    name=block_document_name,
                    data={"service_account_info": key},
                    block_type_id=credentials_block_type.id,
                    block_schema_id=credentials_block_schema.id,
                )
            )
            return block_doc.id
        except ObjectAlreadyExists:
            block_doc = await client.read_block_document_by_name(
                name=block_document_name,
                block_type_slug="gcp-credentials",
            )
            return block_doc.id

    async def _create_provision_table(
        self, work_pool_name: str, client: "PrefectClient"
    ):
        return Panel(
            dedent(
                f"""\
                    Provisioning infrastructure for your work pool [blue]{work_pool_name}[/] will require:

                        Updates in GCP project [blue]{self._project}[/] in region [blue]{self._region}[/]

                            - Activate the Cloud Run API for your project
                            - Activate the Artifact Registry API for your project
                            - Create an Artifact Registry repository named [blue]{self._image_repository_name}[/]
                            - Create a service account for managing Cloud Run jobs: [blue]{self._service_account_name}[/]
                                - Service account will be granted the following roles:
                                    - Service Account User
                                    - Cloud Run Developer
                            - Create a key for service account: [blue]{self._service_account_name}[/]

                        Updates in Prefect {"workspace" if client.server_type == ServerType.CLOUD else "server"}

                            - Create GCP credentials block to store the service account key: [blue]{self._credentials_block_name}[/]
                """
            ),
            expand=False,
        )

    async def _customize_resource_names(
        self, work_pool_name: str, client: "PrefectClient"
    ) -> bool:
        self._service_account_name = prompt(
            "Please enter a name for the service account",
            default=self._service_account_name,
        )
        self._credentials_block_name = prompt(
            "Please enter a name for the GCP credentials block",
            default=self._credentials_block_name,
        )
        self._image_repository_name = prompt(
            "Please enter a name for the Artifact Registry repository",
            default=self._image_repository_name,
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
        base_job_template: dict,
        client: Optional["PrefectClient"] = None,
    ) -> Dict[str, Any]:
        assert client, "Client injection failed"
        await self._verify_gcloud_ready()
        self._project = await self._get_project()
        self._region = await self._get_default_region()
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

        with Progress(console=self._console) as progress:
            task = progress.add_task("Provisioning Infrastructure", total=9)
            progress.console.print("Activating Cloud Run API")
            await self._enable_cloud_run_api()
            progress.advance(task)

            progress.console.print("Activating Artifact Registry API")
            await self._enable_artifact_registry_api()
            progress.advance(task)

            progress.console.print("Creating Artifact Registry repository")
            await self._create_artifact_registry_repository(self._image_repository_name)
            progress.advance(task)

            progress.console.print("Configuring authentication to Artifact Registry")
            await self._login_to_artifact_registry()
            progress.advance(task)

            progress.console.print("Setting default Docker build namespace")
            default_docker_build_namespace = f"{self._region}-docker.pkg.dev/{self._project}/{self._image_repository_name}"
            update_current_profile(
                {PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE: default_docker_build_namespace}
            )
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
                self._credentials_block_name, key, client
            )
            base_job_template_copy = deepcopy(base_job_template)
            base_job_template_copy["variables"]["properties"]["credentials"][
                "default"
            ] = {"$ref": {"block_document_id": str(block_doc_id)}}
            progress.advance(task)

            self._console.print(
                dedent(
                    f"""\
                    Your default Docker build namespace has been set to [blue]{default_docker_build_namespace!r}[/].
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
                            print(f"Hello {{name}}! I'm a flow running in Cloud Run!")


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
