"""
Command line interface for working with Orion on Kubernetes
"""
from string import Template

import typer
import yaml

import prefect
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli.root import app
from prefect.docker import get_prefect_image_name
from prefect.infrastructure import KubernetesJob
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_LOGGING_SERVER_LEVEL,
)

kubernetes_app = PrefectTyper(
    name="kubernetes",
    help="Commands for working with Orion on Kubernetes.",
)
app.add_typer(kubernetes_app)

manifest_app = PrefectTyper(
    name="manifest",
    help="Commands for generating Kubernetes manifests.",
)
kubernetes_app.add_typer(manifest_app)


@manifest_app.command("orion")
def manifest_orion(
    image_tag: str = typer.Option(
        get_prefect_image_name(),
        "-i",
        "--image-tag",
        help="The tag of a Docker image to use for the Orion.",
    ),
    namespace: str = typer.Option(
        "default",
        "-n",
        "--namespace",
        help="A Kubernetes namespace to create Orion in.",
    ),
    log_level: str = SettingsOption(PREFECT_LOGGING_SERVER_LEVEL),
):
    """
    Generates a manifest for deploying Orion on Kubernetes.

    Example:
        $ prefect kubernetes manifest orion | kubectl apply -f -
    """

    template = Template(
        (
            prefect.__module_path__ / "cli" / "templates" / "kubernetes-orion.yaml"
        ).read_text()
    )
    manifest = template.substitute(
        {
            "image_name": image_tag,
            "namespace": namespace,
            "log_level": log_level,
        }
    )
    print(manifest)


@manifest_app.command("agent")
def manifest_agent(
    api_url: str = SettingsOption(PREFECT_API_URL),
    api_key: str = SettingsOption(PREFECT_API_KEY),
    image_tag: str = typer.Option(
        get_prefect_image_name(),
        "-i",
        "--image-tag",
        help="The tag of a Docker image to use for the Agent.",
    ),
    namespace: str = typer.Option(
        "default",
        "-n",
        "--namespace",
        help="A Kubernetes namespace to create agent in.",
    ),
    work_queue: str = typer.Option(
        "kubernetes",
        "-q",
        "--work-queue",
        help="A work queue name for the agent to pull from.",
    ),
):
    """
    Generates a manifest for deploying Agent on Kubernetes.

    Example:
        $ prefect kubernetes manifest agent | kubectl apply -f -
    """

    template = Template(
        (
            prefect.__module_path__ / "cli" / "templates" / "kubernetes-agent.yaml"
        ).read_text()
    )
    manifest = template.substitute(
        {
            "api_url": api_url,
            "api_key": api_key,
            "image_name": image_tag,
            "namespace": namespace,
            "work_queue": work_queue,
        }
    )
    print(manifest)


@manifest_app.command("flow-run-job")
async def manifest_flow_run_job():
    """
    Prints the default KubernetesJob Job manifest.

    Use this file to fully customize your `KubernetesJob` deployments.

    \b
    Example:
        \b
        $ prefect kubernetes manifest flow-run-job

    \b
    Output, a YAML file:
        \b
        apiVersion: batch/v1
        kind: Job
        ...
    """

    KubernetesJob.base_job_manifest()

    output = yaml.dump(KubernetesJob.base_job_manifest())

    # add some commentary where appropriate
    output = output.replace(
        "metadata:\n  labels:",
        "metadata:\n  # labels are required, even if empty\n  labels:",
    )
    output = output.replace(
        "containers:\n",
        "containers:  # the first container is required\n",
    )
    output = output.replace(
        "env: []\n",
        "env: []  # env is required, even if empty\n",
    )

    print(output)
