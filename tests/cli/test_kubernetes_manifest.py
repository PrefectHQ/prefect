import yaml

from prefect.docker import get_prefect_image_name
from prefect.infrastructure.kubernetes import KubernetesJob
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_LOGGING_SERVER_LEVEL,
)
from prefect.testing.cli import invoke_and_assert


def test_printing_the_orion_manifest_with_no_args():
    """`prefect kubernetes manifest orion` should print a valid YAML file
    representing a basic Orion deployment to a cluster"""
    result = invoke_and_assert(
        ["kubernetes", "manifest", "orion"],
        expected_output_contains="kind: Deployment",
    )
    manifests = yaml.load_all(result.stdout, yaml.SafeLoader)

    # Spot-check a few things. This test is mostly just confirming that the output
    # looks roughly like a set of Kubernetes manifests in YAML, not that this is a
    # valid and working Orion deployment.
    assert manifests

    for manifest in manifests:
        assert manifest["metadata"]["namespace"] == "default"

        if manifest["kind"] == "Deployment":
            assert manifest["metadata"]["name"] == "prefect-orion"
            assert len(manifest["spec"]["template"]["spec"]["containers"]) == 1

            orion_container = manifest["spec"]["template"]["spec"]["containers"][0]
            assert orion_container["image"] == get_prefect_image_name()
            assert orion_container["command"][0:3] == ["prefect", "orion", "start"]
            assert orion_container["command"][0:3] == ["prefect", "orion", "start"]
            assert orion_container["command"][5:] == [
                "--log-level",
                str(PREFECT_LOGGING_SERVER_LEVEL.value()),
            ]


def test_printing_the_orion_manifest_with_image_tag_and_log_level():
    result = invoke_and_assert(
        [
            "kubernetes",
            "manifest",
            "orion",
            "-i",
            "test_image_tag",
            "--log-level",
            "test_log_level",
        ],
        expected_output_contains="kind: Deployment",
    )
    manifests = yaml.load_all(result.stdout, yaml.SafeLoader)
    assert manifests

    manifests = yaml.load_all(result.stdout, yaml.SafeLoader)
    assert manifests

    deployment = next(m for m in manifests if m["kind"] == "Deployment")
    assert deployment["metadata"]["name"] == "prefect-orion"
    assert len(deployment["spec"]["template"]["spec"]["containers"]) == 1

    orion_container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert orion_container["image"] == "test_image_tag"
    assert orion_container["command"][5:] == ["--log-level", "test_log_level"]


def test_printing_the_orion_manifest_with_namespace():
    result = invoke_and_assert(
        ["kubernetes", "manifest", "orion", "-n", "test_namespace"],
        expected_output_contains="kind: Deployment",
    )
    manifests = yaml.load_all(result.stdout, yaml.SafeLoader)
    assert manifests

    for manifest in manifests:
        assert manifest["metadata"]["namespace"] == "test_namespace"


def test_printing_the_agent_manifest_with_no_args():
    """`prefect kubernetes manifest agent` should print a valid YAML file
    representing a basic agent deployment to a cluster"""
    result = invoke_and_assert(
        ["kubernetes", "manifest", "agent"],
        expected_output_contains="kind: Deployment",
    )
    manifests = yaml.load_all(result.stdout, yaml.SafeLoader)

    # Spot-check a few things. This test is mostly just confirming that the output
    # looks roughly like a set of Kubernetes manifests in YAML.
    assert manifests

    for manifest in manifests:
        assert manifest["metadata"]["namespace"] == "default"

        if manifest["kind"] == "Deployment":
            assert manifest["metadata"]["name"] == "prefect-agent"
            assert len(manifest["spec"]["template"]["spec"]["containers"]) == 1

            agent_container = manifest["spec"]["template"]["spec"]["containers"][0]
            assert agent_container["image"] == get_prefect_image_name()
            assert agent_container["command"] == [
                "prefect",
                "agent",
                "start",
                "-q",
                "kubernetes",
            ]
            assert len(agent_container["env"]) == 2
            assert agent_container["env"][0]["name"] == "PREFECT_API_URL"
            assert agent_container["env"][1]["name"] == "PREFECT_API_KEY"
            assert agent_container["env"][0]["value"] == str(PREFECT_API_URL.value())
            assert agent_container["env"][1]["value"] == str(PREFECT_API_KEY.value())


def test_printing_the_agent_manifest_with_api_url_image_tag_and_work_queue():
    result = invoke_and_assert(
        [
            "kubernetes",
            "manifest",
            "agent",
            "--api-url",
            "test_api_url",
            "--api-key",
            "test_api_key",
            "-i",
            "test_image_tag",
            "-q",
            "test_work_queue",
        ],
        expected_output_contains="kind: Deployment",
    )
    manifests = yaml.load_all(result.stdout, yaml.SafeLoader)
    assert manifests

    deployment = next(m for m in manifests if m["kind"] == "Deployment")
    assert deployment["metadata"]["name"] == "prefect-agent"
    assert len(deployment["spec"]["template"]["spec"]["containers"]) == 1

    agent_container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert agent_container["image"] == "test_image_tag"
    assert agent_container["command"][3:5] == ["-q", "test_work_queue"]
    assert len(agent_container["env"]) == 2
    assert agent_container["env"][0]["name"] == "PREFECT_API_URL"
    assert agent_container["env"][1]["name"] == "PREFECT_API_KEY"
    assert agent_container["env"][0]["value"] == "test_api_url"
    assert agent_container["env"][1]["value"] == "test_api_key"


def test_printing_the_agent_manifest_with_namespace():
    result = invoke_and_assert(
        ["kubernetes", "manifest", "agent", "-n", "test_namespace"],
        expected_output_contains="kind: Deployment",
    )
    manifests = yaml.load_all(result.stdout, yaml.SafeLoader)
    assert manifests

    for manifest in manifests:
        assert manifest["metadata"]["namespace"] == "test_namespace"


def test_printing_the_job_base_manifest():
    """`prefect kubernetes manifest flow-run-job` should print a valid YAML file
    representing the minimum starting point for a Kubernetes Job"""
    result = invoke_and_assert(
        ["kubernetes", "manifest", "flow-run-job"],
        expected_output_contains="kind: Job",
    )

    # check for the presence of helpful comments
    assert "# the first container is required" in result.stdout

    parsed = yaml.load(result.stdout, yaml.SafeLoader)

    assert parsed == KubernetesJob.base_job_manifest()
