import shlex
import subprocess

from anyio import run_process
from rich.panel import Panel


class CloudRunPushProvisioner:
    def __init__(self):
        self._printer = print
        self._project = None
        self._region = None

    @property
    def printer(self):
        return self._printer

    @printer.setter
    def printer(self, value):
        self._printer = value

    @property
    def run_book(self):
        if not self._project:
            raise RuntimeError("Project must be set before generating run book")
        return {
            "resources": [
                {
                    "name": "prefect-cloud-run",
                    "type": "iam-service-account",
                    "description": "Service account for managing Cloud Run jobs",
                    "commands": [
                        # create the service account
                        shlex.split(
                            "gcloud iam service-accounts create prefect-cloud-run"
                            ' --display-name "Prefect Cloud Run Service Account"'
                        ),
                        # grant the service account the service account user role
                        shlex.split(
                            "gcloud projects add-iam-policy-binding {self._project}"
                            ' --member="serviceAccount:prefect-cloud-run@{self._project}.iam.gserviceaccount.com"'
                            ' --role="roles/iam.serviceAccountUser"'
                        ),
                        # grant the service account the cloud run developer role
                        shlex.split(
                            "gcloud projects add-iam-policy-binding {self._project}"
                            ' --member="serviceAccount:prefect-cloud-run@{self._project}.iam.gserviceaccount.com"'
                            ' --role="roles/run.admin"'
                        ),
                    ],
                },
                {
                    "name": "prefect-cloud-run-key",
                    "type": "iam-service-account-key",
                    "description": "Service account key for managing Cloud Run jobs",
                    "commands": [
                        # create the service account key
                        shlex.split(
                            "gcloud iam service-accounts keys create"
                            " /tmp/prefect-cloud-run-key.json"
                            " --iam-account=prefect-cloud-run@{self._project}.iam.gserviceaccount.com"
                        ),
                        # set the service account key as an environment variable
                        shlex.split(
                            "export PREFECT__CLOUD__AUTH_TOKEN=$(cat"
                            " /tmp/prefect-cloud-run-key.json)"
                        ),
                    ],
                },
            ]
        }

    @staticmethod
    async def _run_command(command, *args, **kwargs):
        result = await run_process(command, *args, **kwargs)

        if result.returncode != 0:
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
        return await self._run_command(["gcloud", "config", "get-value", "project"])

    async def _get_default_region(self):
        default_region = await self._run_command(
            ["gcloud", "config", "get-value", "run/region"]
        )
        return default_region or "us-central1"

    async def provision(self):
        await self._check_for_gcloud()
        self._project = await self._get_current_project()
        self._region = await self._get_default_region()

        panel = Panel(
            "foo",
            title=(
                f"Resources to be provisioned in project [blue]{self._project}[/] in"
                f" region [blue]{self._region}[/]"
            ),
        )
        self._printer(panel)
