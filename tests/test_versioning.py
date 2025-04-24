from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest
from anyio import run_process

from prefect._versioning import (
    GithubVersionInfo,
    GitVersionInfo,
    get_inferred_version_info,
)
from prefect.utilities.filesystem import tmpchdir


@pytest.fixture(autouse=True)
def project_dir(tmp_path: Path):
    with tmpchdir(str(tmp_path)):
        yield tmp_path


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)


async def test_get_inferred_version_info_with_no_other_information():
    version_info = await get_inferred_version_info()
    assert version_info is None


@pytest.fixture
async def git_repo(project_dir: Path) -> GitVersionInfo:
    async def git(*args: str) -> CompletedProcess[bytes]:
        result = await run_process(["git", *args], check=False)
        assert result.returncode == 0, result.stdout + b"\n" + result.stderr
        return result

    await git("init", "--initial-branch", "my-default-branch")
    await git("config", "user.email", "me@example.com")
    await git("config", "user.name", "Me")
    await git("remote", "add", "origin", "https://example.com/my-repo")

    test_file = project_dir / "test_file.txt"
    test_file.write_text("This is a test file for the git repository")

    await git("add", ".")
    await git("commit", "-m", "Initial commit")

    result = await git("rev-parse", "HEAD")
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
    monkeypatch.setenv("GITHUB_REF_NAME", "my-current-branch")
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
