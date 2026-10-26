import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


@pytest.mark.parametrize("dockerfile", ["Dockerfile", "client/Dockerfile"])
@pytest.mark.parametrize("download_fails", [False, True])
def test_release_rebuild_uses_current_dockerfile_without_changing_sources(
    tmp_path: Path, dockerfile: str, download_fails: bool
):
    root = Path(__file__).parents[2]
    workflow = yaml.safe_load(
        (root / ".github/workflows/docker-images.yaml").read_text()
    )
    steps = workflow["jobs"]["publish-docker-images"]["steps"]
    step = next(step for step in steps if step["name"] == "Load current Dockerfile")
    assert step["env"]["WORKFLOW_SHA"] == "${{ github.workflow_sha }}"
    build = next(
        step["with"] for step in steps if step["name"] == "Build and push image"
    )
    assert build["file"] == "${{ runner.temp }}/Dockerfile"
    assert build["context"] == "."
    assert "workflow_dispatch" in build["no-cache"]

    source = tmp_path / "source"
    source.mkdir()
    (source / "Dockerfile").write_text("old release Dockerfile")
    runner = tmp_path / "runner"
    runner.mkdir()
    gh = tmp_path / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        'test "$1" = api || exit 1\n'
        'test "$3" = "Accept: application/vnd.github.raw+json" || exit 1\n'
        'test "$4" = "repos/PrefectHQ/prefect/contents/$DOCKERFILE?ref=workflow-sha" || exit 1\n'
        'test "$DOWNLOAD_FAILS" = False || exit 7\n'
        "printf 'current Dockerfile'\n"
    )
    gh.chmod(0o755)
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=source,
        env=dict(
            os.environ,
            PATH=f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
            RUNNER_TEMP=str(runner),
            WORKFLOW_SHA="workflow-sha",
            GITHUB_REPOSITORY="PrefectHQ/prefect",
            DOCKERFILE=dockerfile,
            DOWNLOAD_FAILS=str(download_fails),
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode != 0) == download_fails, result.stderr
    assert (source / "Dockerfile").read_text() == "old release Dockerfile"
    if not download_fails:
        assert (runner / "Dockerfile").read_text() == "current Dockerfile"


@pytest.mark.skipif(shutil.which("jq") is None, reason="Requires jq")
def test_verification_pulls_distinct_platform_manifests(tmp_path: Path):
    root = Path(__file__).parents[2]
    workflow = yaml.safe_load(
        (root / ".github/workflows/docker-images.yaml").read_text()
    )
    step = next(
        step
        for step in workflow["jobs"]["publish-docker-images"]["steps"]
        if step["name"] == "Verify published image"
    )
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "if sys.argv[1:4] == ['buildx', 'imagetools', 'inspect']:\n"
        "    print(json.dumps({'manifests': [\n"
        "        {'platform': {'os': 'linux', 'architecture': arch}, 'digest': 'sha256:' + arch}\n"
        "        for arch in ('amd64', 'arm64')]}))\n"
        "else:\n"
        "    assert sys.argv[1] == 'run'\n"
        "    with open(os.environ['DOCKER_CALLS'], 'a') as f:\n"
        "        f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
    )
    docker.chmod(0o755)
    calls = tmp_path / "calls.jsonl"
    subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        env=dict(
            os.environ,
            PATH=f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
            IMAGE="registry.example/prefect@sha256:index",
            DOCKER_CALLS=str(calls),
        ),
        check=True,
    )
    recorded = [json.loads(line) for line in calls.read_text().splitlines()]
    assert len(recorded) == 2
    for call, architecture in zip(recorded, ("amd64", "arm64")):
        assert f"registry.example/prefect@sha256:{architecture}" in call
        assert "registry.example/prefect@sha256:index" not in call
