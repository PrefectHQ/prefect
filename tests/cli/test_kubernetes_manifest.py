import yaml

from prefect.flow_runners.kubernetes import KubernetesFlowRunner
from prefect.testing.cli import invoke_and_assert


def test_printing_the_orion_manifest():
    """`prefect kubernetes manifest orion` should print a valid YAML file
    representing a basic Orion deployment to a cluster"""
    result = invoke_and_assert(
        ["kubernetes", "manifest", "orion"],
        expected_output_contains="kind: Deployment",
    )
    manifests = yaml.load_all(result.stdout, yaml.SafeLoader)

    # Spot-check a few things.  This test is mostly just confirming that the output
    # looks roughly like a set of Kubernetes manifests in YAML, not that this is a
    # valid and working Orion deployment
    assert manifests

    deployment = next(m for m in manifests if m["kind"] == "Deployment")
    assert deployment["metadata"]["name"] == "orion"

    orion_container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert orion_container["command"][0:3] == ["prefect", "orion", "start"]


def test_printing_the_job_base_manifest():
    """`prefect kubernetes manifest flow-run-job` should print a valid YAML file
    representing the minimum starting point for a KubernetesFlowRunner Job"""
    result = invoke_and_assert(
        ["kubernetes", "manifest", "flow-run-job"],
        expected_output_contains="kind: Job",
    )

    # check for the presence of helpful comments
    assert "# the first container is required" in result.stdout

    parsed = yaml.load(result.stdout, yaml.SafeLoader)

    assert parsed == KubernetesFlowRunner.base_job_manifest()
