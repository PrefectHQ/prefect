"""
Command line interface for working with Orion on Kubernetes
"""
from string import Template

import yaml

import prefect
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli.root import app
from prefect.flow_runners.base import get_prefect_image_name
from prefect.flow_runners.kubernetes import KubernetesFlowRunner
from prefect.settings import PREFECT_LOGGING_SERVER_LEVEL

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
    image_tag: str = None,
    log_level: str = SettingsOption(PREFECT_LOGGING_SERVER_LEVEL),
):
    """
    Generates a manifest for deploying Orion on Kubernetes.

    Example:
        $ prefect kubernetes manifest orion | kubectl apply -f -
    """

    template = Template(
        (prefect.__module_path__ / "cli" / "templates" / "kubernetes.yaml").read_text()
    )
    manifest = template.substitute(
        {
            "image_name": image_tag or get_prefect_image_name(),
            "log_level": log_level,
        }
    )
    print(manifest)


@manifest_app.command("flow-run-job")
async def manifest_flow_run_job():
    """
    Prints the default KubernetesFlowRunner Job manifest.

    Use this file to fully customize your `KubernetesFlowRunner` deployments.

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

    KubernetesFlowRunner.base_job_manifest()

    output = yaml.dump(KubernetesFlowRunner.base_job_manifest())

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
