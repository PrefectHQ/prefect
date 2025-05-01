from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest
from anyio import run_process

from prefect._versioning import (
    AzureDevopsVersionInfo,
    BitbucketVersionInfo,
    GithubVersionInfo,
    GitlabVersionInfo,
    GitVersionInfo,
    get_inferred_version_info,
)
from prefect.utilities.filesystem import tmpchdir


@pytest.fixture(autouse=True)
def project_dir(tmp_path: Path):
    with tmpchdir(str(tmp_path)):
        yield tmp_path


@pytest.fixture(autouse=True)
def clean_github_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)


@pytest.fixture(autouse=True)
def clean_gitlab_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CI_COMMIT_SHA", raising=False)
    monkeypatch.delenv("CI_COMMIT_REF_NAME", raising=False)
    monkeypatch.delenv("CI_PROJECT_NAME", raising=False)
    monkeypatch.delenv("CI_PROJECT_URL", raising=False)


@pytest.fixture(autouse=True)
def clean_bitbucket_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("BITBUCKET_COMMIT", raising=False)
    monkeypatch.delenv("BITBUCKET_BRANCH", raising=False)
    monkeypatch.delenv("BITBUCKET_REPO_SLUG", raising=False)
    monkeypatch.delenv("BITBUCKET_GIT_HTTP_ORIGIN", raising=False)


@pytest.fixture(autouse=True)
def clean_azure_devops_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("BUILD_SOURCEVERSION", raising=False)
    monkeypatch.delenv("BUILD_SOURCEBRANCHNAME", raising=False)
    monkeypatch.delenv("BUILD_REPOSITORY_NAME", raising=False)
    monkeypatch.delenv("BUILD_REPOSITORY_URI", raising=False)


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
    await run_process(["git", "remote", "remove", "origin"], check=False)
    await git("remote", "add", "origin", "https://example.com/my-repo")

    test_file = project_dir / "test_file.txt"
    test_file.write_text("This is a test file for the git repository")

    await git("add", ".")
    await git("commit", "-m", "Initial commit")

    result = await git("rev-parse", "HEAD")
    commit_sha = result.stdout.decode().strip()

    return GitVersionInfo(
        type="vcs:git",
        version=commit_sha[:8],
        branch="my-default-branch",
        url="https://example.com/my-repo",
        repository="my-repo",
        commit_sha=commit_sha,
        message="Initial commit",
    )


async def test_get_inferred_version_info_with_git_version_info(
    git_repo: GitVersionInfo,
):
    version_info = await get_inferred_version_info()
    assert version_info == git_repo


@pytest.fixture
async def git_repo_many_lines_message(project_dir: Path) -> GitVersionInfo:
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
    await git("commit", "-m", "Initial commit\nWith multiple lines")

    result = await git("rev-parse", "HEAD")
    commit_sha = result.stdout.decode().strip()

    return GitVersionInfo(
        type="vcs:git",
        version=commit_sha[:8],
        branch="my-default-branch",
        url="https://example.com/my-repo",
        repository="my-repo",
        commit_sha=commit_sha,
        message="Initial commit",
    )


async def test_get_inferred_version_info_with_git_version_info_single_line_message(
    git_repo_many_lines_message: GitVersionInfo,
):
    version_info = await get_inferred_version_info()
    assert version_info == git_repo_many_lines_message


@pytest.fixture
async def github_repo(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> GithubVersionInfo:
    async def git(*args: str) -> CompletedProcess[bytes]:
        result = await run_process(["git", *args], check=False)
        assert result.returncode == 0, result.stdout + b"\n" + result.stderr
        return result

    await git("init", "--initial-branch", "my-default-branch")
    await git("config", "user.email", "me@example.com")
    await git("config", "user.name", "Me")
    await run_process(["git", "remote", "remove", "origin"], check=False)
    await git("remote", "add", "origin", "https://github.com/org/test-repo")

    test_file = project_dir / "test_file.txt"
    test_file.write_text("This is a test file for the git repository")

    await git("add", ".")
    await git("commit", "-m", "Initial commit")

    monkeypatch.setenv("GITHUB_SHA", "abcdef1234567890")
    monkeypatch.setenv("GITHUB_REF_NAME", "my-current-branch")
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/test-repo")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    return GithubVersionInfo(
        type="vcs:github",
        version="abcdef12",
        branch="my-current-branch",
        repository="org/test-repo",
        url="https://github.com/org/test-repo/tree/abcdef1234567890",
        commit_sha="abcdef1234567890",
        message="Initial commit",
    )


async def test_get_inferred_version_info_with_github_version_info(
    github_repo: GithubVersionInfo,
):
    version_info = await get_inferred_version_info()
    assert version_info == github_repo


@pytest.fixture
async def gitlab_repo(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> GitlabVersionInfo:
    async def git(*args: str) -> CompletedProcess[bytes]:
        result = await run_process(["git", *args], check=False)
        assert result.returncode == 0, result.stdout + b"\n" + result.stderr
        return result

    await git("init", "--initial-branch", "my-default-branch")
    await git("config", "user.email", "me@example.com")
    await git("config", "user.name", "Me")
    await git("remote", "add", "origin", "https://gitlab.com/org/test-repo")

    test_file = project_dir / "test_file.txt"
    test_file.write_text("This is a test file for the git repository")

    await git("add", ".")
    await git("commit", "-m", "Initial commit")

    monkeypatch.setenv("CI_COMMIT_SHA", "abcdef1234567890")
    monkeypatch.setenv("CI_COMMIT_REF_NAME", "my-current-branch")
    monkeypatch.setenv("CI_PROJECT_NAME", "org/test-repo")
    monkeypatch.setenv("CI_PROJECT_URL", "https://gitlab.com/org/test-repo")
    return GitlabVersionInfo(
        type="vcs:gitlab",
        version="abcdef12",
        branch="my-current-branch",
        repository="org/test-repo",
        url="https://gitlab.com/org/test-repo/-/tree/abcdef1234567890",
        commit_sha="abcdef1234567890",
        message="Initial commit",
    )


async def test_get_inferred_version_info_with_gitlab_version_info(
    gitlab_repo: GitlabVersionInfo,
):
    version_info = await get_inferred_version_info()
    assert version_info == gitlab_repo


@pytest.fixture
async def bitbucket_repo(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> BitbucketVersionInfo:
    async def git(*args: str) -> CompletedProcess[bytes]:
        result = await run_process(["git", *args], check=False)
        assert result.returncode == 0, result.stdout + b"\n" + result.stderr
        return result

    await git("init", "--initial-branch", "my-default-branch")
    await git("config", "user.email", "me@example.com")
    await git("config", "user.name", "Me")
    await git("remote", "add", "origin", "https://bitbucket.org/org/test-repo")

    test_file = project_dir / "test_file.txt"
    test_file.write_text("This is a test file for the git repository")

    await git("add", ".")
    await git("commit", "-m", "Initial commit")

    monkeypatch.setenv("BITBUCKET_COMMIT", "abcdef1234567890")
    monkeypatch.setenv("BITBUCKET_BRANCH", "my-current-branch")
    monkeypatch.setenv("BITBUCKET_REPO_SLUG", "org/test-repo")
    monkeypatch.setenv(
        "BITBUCKET_GIT_HTTP_ORIGIN", "https://bitbucket.org/org/test-repo"
    )
    return BitbucketVersionInfo(
        type="vcs:bitbucket",
        version="abcdef12",
        branch="my-current-branch",
        repository="org/test-repo",
        url="https://bitbucket.org/org/test-repo/src/abcdef1234567890",
        commit_sha="abcdef1234567890",
        message="Initial commit",
    )


async def test_get_inferred_version_info_with_bitbucket_version_info(
    bitbucket_repo: BitbucketVersionInfo,
):
    version_info = await get_inferred_version_info()
    assert version_info == bitbucket_repo


@pytest.fixture
async def azure_devops_repo(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> AzureDevopsVersionInfo:
    async def git(*args: str) -> CompletedProcess[bytes]:
        result = await run_process(["git", *args], check=False)
        assert result.returncode == 0, result.stdout + b"\n" + result.stderr
        return result

    await git("init", "--initial-branch", "my-default-branch")
    await git("config", "user.email", "me@example.com")
    await git("config", "user.name", "Me")
    await git("remote", "add", "origin", "https://dev.azure.com/org/test-repo")

    test_file = project_dir / "test_file.txt"
    test_file.write_text("This is a test file for the git repository")

    await git("add", ".")
    await git("commit", "-m", "Initial commit")

    monkeypatch.setenv("BUILD_SOURCEVERSION", "abcdef1234567890")
    monkeypatch.setenv("BUILD_SOURCEBRANCHNAME", "my-current-branch")
    monkeypatch.setenv("BUILD_REPOSITORY_NAME", "org/test-repo")
    monkeypatch.setenv("BUILD_REPOSITORY_URI", "https://dev.azure.com/org/test-repo")
    return AzureDevopsVersionInfo(
        type="vcs:azuredevops",
        version="abcdef12",
        branch="my-current-branch",
        repository="org/test-repo",
        url="https://dev.azure.com/org/test-repo?version=GCabcdef1234567890",
        commit_sha="abcdef1234567890",
        message="Initial commit",
    )


async def test_get_inferred_version_info_with_azure_devops_version_info(
    azure_devops_repo: AzureDevopsVersionInfo,
):
    version_info = await get_inferred_version_info()
    assert version_info == azure_devops_repo


async def test_github_takes_precedence_over_git(
    git_repo: GitVersionInfo, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("GITHUB_SHA", "abcdef1234567890")
    monkeypatch.setenv("GITHUB_REF_NAME", "my-current-branch")
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/test-repo")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")

    version_info = await get_inferred_version_info()
    assert version_info == GithubVersionInfo(
        type="vcs:github",
        version="abcdef12",
        branch="my-current-branch",
        repository="org/test-repo",
        url="https://github.com/org/test-repo/tree/abcdef1234567890",
        commit_sha="abcdef1234567890",
        message="Initial commit",
    )


async def test_gitlab_takes_precedence_over_git(
    git_repo: GitVersionInfo, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CI_COMMIT_SHA", "abcdef1234567890")
    monkeypatch.setenv("CI_COMMIT_REF_NAME", "my-current-branch")
    monkeypatch.setenv("CI_PROJECT_NAME", "org/test-repo")
    monkeypatch.setenv("CI_PROJECT_URL", "https://gitlab.com/org/test-repo")

    version_info = await get_inferred_version_info()
    assert version_info == GitlabVersionInfo(
        type="vcs:gitlab",
        version="abcdef12",
        branch="my-current-branch",
        repository="org/test-repo",
        url="https://gitlab.com/org/test-repo/-/tree/abcdef1234567890",
        commit_sha="abcdef1234567890",
        message="Initial commit",
    )


async def test_bitbucket_takes_precedence_over_git(
    git_repo: GitVersionInfo, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("BITBUCKET_COMMIT", "abcdef1234567890")
    monkeypatch.setenv("BITBUCKET_BRANCH", "my-current-branch")
    monkeypatch.setenv("BITBUCKET_REPO_SLUG", "org/test-repo")
    monkeypatch.setenv(
        "BITBUCKET_GIT_HTTP_ORIGIN", "https://bitbucket.org/org/test-repo"
    )

    version_info = await get_inferred_version_info()
    assert version_info == BitbucketVersionInfo(
        type="vcs:bitbucket",
        version="abcdef12",
        branch="my-current-branch",
        repository="org/test-repo",
        url="https://bitbucket.org/org/test-repo/src/abcdef1234567890",
        commit_sha="abcdef1234567890",
        message="Initial commit",
    )


async def test_azure_devops_takes_precedence_over_git(
    git_repo: GitVersionInfo, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("BUILD_SOURCEVERSION", "abcdef1234567890")
    monkeypatch.setenv("BUILD_SOURCEBRANCHNAME", "my-current-branch")
    monkeypatch.setenv("BUILD_REPOSITORY_NAME", "org/test-repo")
    monkeypatch.setenv("BUILD_REPOSITORY_URI", "https://dev.azure.com/org/test-repo")

    version_info = await get_inferred_version_info()
    assert version_info == AzureDevopsVersionInfo(
        type="vcs:azuredevops",
        version="abcdef12",
        branch="my-current-branch",
        repository="org/test-repo",
        url="https://dev.azure.com/org/test-repo?version=GCabcdef1234567890",
        commit_sha="abcdef1234567890",
        message="Initial commit",
    )
