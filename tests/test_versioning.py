from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from anyio import run_process

import prefect
from prefect.deployments.base import initialize_project
from prefect.utilities.filesystem import tmpchdir
from prefect.versioning import (
    GithubVersionInfo,
    GitVersionInfo,
    get_inferred_version_info,
)

TEST_PROJECTS_DIR = prefect.__development_base_path__ / "tests" / "test-projects"


@pytest.fixture(autouse=True)
def project_dir(tmp_path: Path):
    with tmpchdir(str(tmp_path)):
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path, dirs_exist_ok=True)
        prefect_home = tmp_path / ".prefect"
        prefect_home.mkdir(exist_ok=True, mode=0o0700)
        initialize_project()
        yield tmp_path


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.delenv("GITHUB_REF", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)


async def test_get_inferred_version_info_with_no_other_information():
    version_info = await get_inferred_version_info()
    assert version_info is None


@pytest.fixture
async def git_repo(project_dir: Path) -> GitVersionInfo:
    result = await run_process(["git", "init", "--initial-branch", "my-default-branch"])
    assert result.returncode == 0

    result = await run_process(
        ["git", "remote", "add", "origin", "https://example.com/my-repo"]
    )
    assert result.returncode == 0

    test_file = project_dir / "test_file.txt"
    test_file.write_text("This is a test file for the git repository")

    result = await run_process(["git", "add", "."])
    assert result.returncode == 0

    result = await run_process(["git", "commit", "-m", "Initial commit"])
    assert result.returncode == 0

    result = await run_process(["git", "rev-parse", "HEAD"])
    assert result.returncode == 0
    commit_sha = result.stdout.decode().strip()

    return GitVersionInfo(
        type="vcs:git",
        version=commit_sha,
        branch="my-default-branch",
        url="https://example.com/my-repo",
        repository="my-repo",
    )


async def test_get_inferred_version_info_with_git_version_info(
    git_repo: GitVersionInfo,
):
    version_info = await get_inferred_version_info()
    assert version_info == git_repo


@pytest.fixture
async def github_repo(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> GithubVersionInfo:
    monkeypatch.setenv("GITHUB_SHA", "abcdef1234567890")
    monkeypatch.setenv("GITHUB_REF", "my-current-branch")
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/test-repo")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    return GithubVersionInfo(
        type="vcs:github",
        version="abcdef1234567890",
        branch="my-current-branch",
        repository="org/test-repo",
        url="https://github.com/org/test-repo",
    )


async def test_get_inferred_version_info_with_github_version_info(
    github_repo: GithubVersionInfo,
):
    version_info = await get_inferred_version_info()
    assert version_info == github_repo


async def test_github_takes_precedence_over_git(
    git_repo: GitVersionInfo, github_repo: GithubVersionInfo
):
    version_info = await get_inferred_version_info()
    assert version_info == github_repo
