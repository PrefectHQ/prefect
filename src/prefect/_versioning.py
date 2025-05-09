from __future__ import annotations

import os
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, Literal, Optional
from urllib.parse import urlparse

from anyio import run_process
from pydantic import Field

from prefect.client.schemas.objects import VersionInfo


async def get_commit_message_first_line() -> str:
    result = await run_process(["git", "log", "-1", "--pretty=%B"])
    return result.stdout.decode().strip().splitlines()[0]


class SimpleVersionInfo(VersionInfo):
    type: Literal["prefect:simple"] = "prefect:simple"
    version: str = Field(default="")
    branch: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)


class GithubVersionInfo(VersionInfo):
    type: Literal["vcs:github"] = "vcs:github"
    version: str
    commit_sha: str
    message: str
    branch: str
    repository: str
    url: str


class GitlabVersionInfo(VersionInfo):
    type: Literal["vcs:gitlab"] = "vcs:gitlab"
    version: str
    commit_sha: str
    message: str
    branch: str
    repository: str
    url: str


class BitbucketVersionInfo(VersionInfo):
    type: Literal["vcs:bitbucket"] = "vcs:bitbucket"
    version: str
    commit_sha: str
    message: str
    branch: str
    repository: str
    url: str


class AzureDevopsVersionInfo(VersionInfo):
    type: Literal["vcs:azuredevops"] = "vcs:azuredevops"
    version: str
    commit_sha: str
    message: str
    branch: str
    repository: str
    url: str


class GitVersionInfo(VersionInfo):
    type: Literal["vcs:git"] = "vcs:git"
    version: str
    commit_sha: str
    message: str
    branch: str
    repository: str
    url: str


async def get_github_version_info(
    commit_sha: Optional[str] = None,
    message: Optional[str] = None,
    branch: Optional[str] = None,
    repository: Optional[str] = None,
    url: Optional[str] = None,
) -> GithubVersionInfo:
    """Create a GithubVersionInfo object from provided values or environment variables.

    Args:
        commit_sha: The commit SHA, falls back to GITHUB_SHA env var
        message: The commit message, falls back to git log -1 --pretty=%B
        branch: The git branch, falls back to GITHUB_REF_NAME env var
        repository: The repository name, falls back to GITHUB_REPOSITORY env var
        url: The repository URL, constructed from GITHUB_SERVER_URL/GITHUB_REPOSITORY/tree/GITHUB_SHA if not provided

    Returns:
        A GithubVersionInfo

    Raises:
        ValueError: If any required fields cannot be determined
    """
    try:
        commit_sha = commit_sha or os.getenv("GITHUB_SHA")
        branch = branch or os.getenv("GITHUB_REF_NAME")
        repository = repository or os.getenv("GITHUB_REPOSITORY")
        url = url or f"{os.getenv('GITHUB_SERVER_URL')}/{repository}/tree/{commit_sha}"

        if not message:
            message = await get_commit_message_first_line()

        if not commit_sha:
            raise ValueError(
                "commit_sha is required - must be provided or set in GITHUB_SHA"
            )
        if not branch:
            raise ValueError(
                "branch is required - must be provided or set in GITHUB_REF_NAME"
            )
        if not repository:
            raise ValueError(
                "repository is required - must be provided or set in GITHUB_REPOSITORY"
            )

    except Exception as e:
        raise ValueError(
            f"Error getting git version info: {e}. You may not be in a Github repository."
        )

    return GithubVersionInfo(
        type="vcs:github",
        version=commit_sha[:8],
        commit_sha=commit_sha,
        message=message,
        branch=branch,
        repository=repository,
        url=url,
    )


async def get_gitlab_version_info(
    commit_sha: Optional[str] = None,
    message: Optional[str] = None,
    branch: Optional[str] = None,
    repository: Optional[str] = None,
    url: Optional[str] = None,
) -> GitlabVersionInfo:
    """Create a GitlabVersionInfo object from provided values or environment variables.

    Args:
        commit_sha: The commit SHA, falls back to CI_COMMIT_SHA env var
        message: The commit message, falls back to git log -1 --pretty=%B
        branch: The git branch, falls back to CI_COMMIT_REF_NAME env var
        repository: The repository name, falls back to CI_PROJECT_NAME env var
        url: The repository URL, constructed from CI_PROJECT_URL/-/tree/CI_COMMIT_SHA if not provided

    Returns:
        A GitlabVersionInfo

    Raises:
        ValueError: If any required fields cannot be determined
    """
    try:
        commit_sha = commit_sha or os.getenv("CI_COMMIT_SHA")
        branch = branch or os.getenv("CI_COMMIT_REF_NAME")
        repository = repository or os.getenv("CI_PROJECT_NAME")
        url = url or f"{os.getenv('CI_PROJECT_URL')}/-/tree/{commit_sha}"

        if not message:
            message = await get_commit_message_first_line()

        if not commit_sha:
            raise ValueError(
                "commit_sha is required - must be provided or set in CI_COMMIT_SHA"
            )
        if not branch:
            raise ValueError(
                "branch is required - must be provided or set in CI_COMMIT_REF_NAME"
            )
        if not repository:
            raise ValueError(
                "repository is required - must be provided or set in CI_PROJECT_NAME"
            )
        if not url:
            raise ValueError(
                "url is required - must be provided or set in CI_PROJECT_URL"
            )

    except Exception as e:
        raise ValueError(
            f"Error getting git version info: {e}. You may not be in a Gitlab repository."
        )

    return GitlabVersionInfo(
        type="vcs:gitlab",
        version=commit_sha[:8],
        commit_sha=commit_sha,
        message=message,
        branch=branch,
        repository=repository,
        url=url,
    )


async def get_bitbucket_version_info(
    commit_sha: Optional[str] = None,
    message: Optional[str] = None,
    branch: Optional[str] = None,
    repository: Optional[str] = None,
    url: Optional[str] = None,
) -> BitbucketVersionInfo:
    """Create a BitbucketVersionInfo object from provided values or environment variables.

    Args:
        commit_sha: The commit SHA, falls back to BITBUCKET_COMMIT env var
        message: The commit message, falls back to git log -1 --pretty=%B
        branch: The git branch, falls back to BITBUCKET_BRANCH env var
        repository: The repository name, falls back to BITBUCKET_REPO_SLUG env var
        url: The repository URL, constructed from BITBUCKET_GIT_HTTP_ORIGIN/BITBUCKET_REPO_SLUG/src/BITBUCKET_COMMIT if not provided

    Returns:
        A BitbucketVersionInfo

    Raises:
        ValueError: If any required fields cannot be determined
    """
    try:
        commit_sha = commit_sha or os.getenv("BITBUCKET_COMMIT")
        branch = branch or os.getenv("BITBUCKET_BRANCH")
        repository = repository or os.getenv("BITBUCKET_REPO_SLUG")
        url = url or f"{os.getenv('BITBUCKET_GIT_HTTP_ORIGIN')}/src/{commit_sha}"

        if not message:
            message = await get_commit_message_first_line()

        if not commit_sha:
            raise ValueError(
                "commit_sha is required - must be provided or set in BITBUCKET_COMMIT"
            )
        if not branch:
            raise ValueError(
                "branch is required - must be provided or set in BITBUCKET_BRANCH"
            )
        if not repository:
            raise ValueError(
                "repository is required - must be provided or set in BITBUCKET_REPO_SLUG"
            )
        if not url:
            raise ValueError(
                "url is required - must be provided or set in BITBUCKET_GIT_HTTP_ORIGIN"
            )

    except Exception as e:
        raise ValueError(
            f"Error getting git version info: {e}. You may not be in a Bitbucket repository."
        )

    return BitbucketVersionInfo(
        type="vcs:bitbucket",
        version=commit_sha[:8],
        commit_sha=commit_sha,
        message=message,
        branch=branch,
        repository=repository,
        url=url,
    )


async def get_azuredevops_version_info(
    commit_sha: Optional[str] = None,
    message: Optional[str] = None,
    branch: Optional[str] = None,
    repository: Optional[str] = None,
    url: Optional[str] = None,
) -> AzureDevopsVersionInfo:
    """Create an AzureDevopsVersionInfo object from provided values or environment variables.

    Args:
        commit_sha: The commit SHA, falls back to BUILD_SOURCEVERSION env var
        message: The commit message, falls back to git log -1 --pretty=%B
        branch: The git branch, falls back to BUILD_SOURCEBRANCHNAME env var
        repository: The repository name, falls back to BUILD_REPOSITORY_NAME env var
        url: The repository URL, constructed from BUILD_REPOSITORY_URI?version=GCBUILD_SOURCEVERSION if not provided

    Returns:
        An AzureDevopsVersionInfo

    Raises:
        ValueError: If any required fields cannot be determined
    """
    try:
        commit_sha = commit_sha or os.getenv("BUILD_SOURCEVERSION")
        branch = branch or os.getenv("BUILD_SOURCEBRANCHNAME")
        repository = repository or os.getenv("BUILD_REPOSITORY_NAME")
        url = url or f"{os.getenv('BUILD_REPOSITORY_URI')}?version=GC{commit_sha}"

        if not message:
            message = await get_commit_message_first_line()

        if not commit_sha:
            raise ValueError(
                "commit_sha is required - must be provided or set in BUILD_SOURCEVERSION"
            )
        if not branch:
            raise ValueError(
                "branch is required - must be provided or set in BUILD_SOURCEBRANCHNAME"
            )
        if not repository:
            raise ValueError(
                "repository is required - must be provided or set in BUILD_REPOSITORY_NAME"
            )
        if not url:
            raise ValueError(
                "url is required - must be provided or set in BUILD_REPOSITORY_URI"
            )

    except Exception as e:
        raise ValueError(
            f"Error getting git version info: {e}. You may not be in an Azure DevOps repository."
        )

    return AzureDevopsVersionInfo(
        type="vcs:azuredevops",
        version=commit_sha[:8],
        commit_sha=commit_sha,
        message=message,
        branch=branch,
        repository=repository,
        url=url,
    )


async def get_git_version_info(
    commit_sha: Optional[str] = None,
    message: Optional[str] = None,
    branch: Optional[str] = None,
    url: Optional[str] = None,
    repository: Optional[str] = None,
) -> GitVersionInfo:
    try:
        if not commit_sha:
            # Run git command and get stdout
            result = await run_process(["git", "rev-parse", "HEAD"])
            # Decode bytes to string and strip whitespace
            commit_sha = result.stdout.decode().strip()

        if not branch:
            result = await run_process(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            branch = result.stdout.decode().strip()

        if not repository:
            result = await run_process(["git", "config", "--get", "remote.origin.url"])
            remote_url = result.stdout.decode().strip()

            # Extract just the repository name (last part of the path)
            repo_url = urlparse(remote_url)
            repository = repo_url.path.strip("/")
            if repository.endswith(".git"):
                repository = repository[:-4]

        if not message:
            message = await get_commit_message_first_line()

        if not url and repository:
            # Use the full remote URL as the URL
            result = await run_process(["git", "config", "--get", "remote.origin.url"])
            url = result.stdout.decode().strip()
    except Exception as e:
        raise ValueError(
            f"Error getting git version info: {e}. You may not be in a git repository."
        )

    if not url:
        raise ValueError("Could not determine git repository URL")

    return GitVersionInfo(
        type="vcs:git",
        version=commit_sha[:8],
        branch=branch,
        url=url,
        repository=repository,
        commit_sha=commit_sha,
        message=message,
    )


class VersionType(str, Enum):
    SIMPLE = "prefect:simple"
    GITHUB = "vcs:github"
    GITLAB = "vcs:gitlab"
    BITBUCKET = "vcs:bitbucket"
    AZUREDEVOPS = "vcs:azuredevops"
    GIT = "vcs:git"


async def get_inferred_version_info(
    version_type: Optional[str] = None,
) -> VersionInfo | None:
    """
    Attempts to infer version information from the environment.

    Args:
        version_type: Optional type of version info to get. If provided, only that
                     type will be attempted.

    Returns:
        VersionInfo: The inferred version information

    Raises:
        ValueError: If unable to infer version info from any source
    """
    # Map version types to their getter functions
    type_to_getter: Dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {
        VersionType.GITHUB: get_github_version_info,
        VersionType.GITLAB: get_gitlab_version_info,
        VersionType.BITBUCKET: get_bitbucket_version_info,
        VersionType.AZUREDEVOPS: get_azuredevops_version_info,
        VersionType.GIT: get_git_version_info,
    }

    # Default order of getters to try
    default_getters = [
        get_github_version_info,
        get_gitlab_version_info,
        get_bitbucket_version_info,
        get_azuredevops_version_info,
        get_git_version_info,
    ]

    if version_type is VersionType.SIMPLE:
        return None
    if version_type:
        if version_type not in type_to_getter:
            raise ValueError(f"Unknown version type: {version_type}")
        getters = [type_to_getter[version_type]]
    else:
        getters = default_getters

    for getter in getters:
        try:
            return await getter()
        except ValueError:
            continue

    return None
