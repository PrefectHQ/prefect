import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).parents[2]
RELEASE_WORKFLOWS = (
    ".github/workflows/docker-images.yaml",
    ".github/workflows/prefect-client-publish.yaml",
    ".github/workflows/python-package.yaml",
)


@pytest.fixture(params=RELEASE_WORKFLOWS)
def prerelease_tag_validation_step(
    request: pytest.FixtureRequest,
) -> dict[str, Any]:
    workflow = yaml.safe_load((REPOSITORY_ROOT / request.param).read_text())

    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if step.get("name") == "Validate Prerelease Tag":
                return step

    pytest.fail(f"Validate Prerelease Tag step not found in {request.param}")


def run_validation_step(
    step: dict[str, Any], github_ref: str, working_directory: Path
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["GITHUB_REF"] = github_ref
    for name, value in step.get("env", {}).items():
        environment[name] = str(value).replace("${{ github.ref }}", github_ref)

    script = step["run"].replace("${{ github.ref }}", github_ref)
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
        cwd=working_directory,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )


def test_prerelease_tag_validation_accepts_valid_tag(
    prerelease_tag_validation_step: dict[str, Any], tmp_path: Path
):
    result = run_validation_step(
        prerelease_tag_validation_step, "refs/tags/3.0.0rc1", tmp_path
    )

    assert result.returncode == 0, result.stderr


def test_prerelease_tag_validation_does_not_execute_ref(
    prerelease_tag_validation_step: dict[str, Any], tmp_path: Path
):
    malicious_ref = "refs/tags/3.0.0a;touch${IFS}injected"
    subprocess.run(["git", "check-ref-format", malicious_ref], check=True)

    result = run_validation_step(
        prerelease_tag_validation_step, malicious_ref, tmp_path
    )

    assert result.returncode == 1
    assert not (tmp_path / "injected").exists()
