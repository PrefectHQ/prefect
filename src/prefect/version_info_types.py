import os
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, Literal, Optional, Union

from anyio import run_process
from pydantic import Field, RootModel, model_validator

from prefect._internal.schemas.bases import PrefectBaseModel


class SimpleVersionInfo(PrefectBaseModel):
    type: Literal["prefect:simple"]
    version: Optional[str] = Field(default=None)
    branch: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)


class GithubVersionInfo(PrefectBaseModel):
    type: Literal["vcs:github"]
    version: str
    branch: str
    url: str
    repository: str


class GitVersionInfo(PrefectBaseModel):
    type: Literal["vcs:git"]
    version: str
    branch: str
    url: str
    repository: str


class DockerVersionInfo(PrefectBaseModel):
    type: Literal["container:docker"]
    version: str
    branch: str
    url: str
    image_name: str
    registry: str
    image: str


class VersionInfo(
    RootModel[
        Union[SimpleVersionInfo, GithubVersionInfo, GitVersionInfo, DockerVersionInfo]
    ]
):
    root: Union[
        SimpleVersionInfo, GithubVersionInfo, GitVersionInfo, DockerVersionInfo
    ] = Field(..., discriminator="type")

    def __getattr__(self, name: str):
        return getattr(self.__root__, name)

    @model_validator(mode="after")
    def validate_type_requirements(self):
        root = self.__root__

        if isinstance(root, GithubVersionInfo):
            if not root.branch:
                raise ValueError("branch is required when type is 'vcs:github'")
        elif isinstance(root, DockerVersionInfo):
            if not hasattr(root, "image") or not root.image:
                raise ValueError("image is required when type is 'container:docker'")
            if not root.registry:
                raise ValueError("registry is required when type is 'container:docker'")

        return self


async def get_github_version_info(
    version: Optional[str] = None,
    branch: Optional[str] = None,
    repository: Optional[str] = None,
    url: Optional[str] = None,
) -> GithubVersionInfo:
    """Create a GithubVersionInfo object from provided values or environment variables.

    Args:
        version: The commit SHA, falls back to GITHUB_SHA env var
        branch: The git branch, falls back to GITHUB_REF env var
        repository: The repository name, falls back to GITHUB_REPOSITORY env var
        url: The repository URL, constructed from GITHUB_SERVER_URL/GITHUB_REPOSITORY if not provided

    Returns:
        A GithubVersionInfo

    Raises:
        ValueError: If any required fields cannot be determined
    """
    version = version or os.getenv("GITHUB_SHA")
    branch = branch or os.getenv("GITHUB_REF")
    repository = repository or os.getenv("GITHUB_REPOSITORY")
    url = url or f"{os.getenv('GITHUB_SERVER_URL')}/{repository}"

    if not version:
        raise ValueError("version is required - must be provided or set in GITHUB_SHA")
    if not branch:
        raise ValueError("branch is required - must be provided or set in GITHUB_REF")
    if not repository:
        raise ValueError(
            "repository is required - must be provided or set in GITHUB_REPOSITORY"
        )

    return GithubVersionInfo(
        type="vcs:github",
        version=version,
        branch=branch,
        repository=repository,
        url=url,
    )


async def get_git_version_info(
    version: Optional[str] = None,
    branch: Optional[str] = None,
    url: Optional[str] = None,
    repository: Optional[str] = None,
) -> GitVersionInfo:
    try:
        if not version:
            # Run git command and get stdout
            result = await run_process(["git", "rev-parse", "HEAD"])
            # Decode bytes to string and strip whitespace
            version = result.stdout.decode().strip()

        if not branch:
            result = await run_process(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            branch = result.stdout.decode().strip()

        if not repository:
            result = await run_process(["git", "config", "--get", "remote.origin.url"])
            remote_url = result.stdout.decode().strip()

            # Extract just the repository name (last part of the path)
            repo_name = os.path.basename(remote_url.split(":")[1].rstrip(".git"))
            repository = repo_name

        if not url and repository:
            # Use the full remote URL as the URL
            result = await run_process(["git", "config", "--get", "remote.origin.url"])
            url = result.stdout.decode().strip()
    except Exception as e:
        raise ValueError(
            f"Error getting git version info: {e}. You may not be in a git repository."
        )

    return GitVersionInfo(
        type="vcs:git", version=version, branch=branch, url=url, repository=repository
    )


async def get_docker_version_info(
    version: Optional[str] = None,
    branch: Optional[str] = None,
    url: Optional[str] = None,
    registry: Optional[str] = None,
    image: Optional[str] = None,
) -> DockerVersionInfo:
    return DockerVersionInfo(
        type="container:docker",
        version=version,
        branch=branch,
        url=url,
        registry=registry,
        image=image,
    )


# Add this enum to map version types to their string values
class VersionType(str, Enum):
    SIMPLE = "prefect:simple"
    GITHUB = "vcs:github"
    GIT = "vcs:git"
    DOCKER = "container:docker"


async def get_inferred_version_info(version_type: Optional[str] = None):
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
        VersionType.DOCKER: get_docker_version_info,
        VersionType.GITHUB: get_github_version_info,
        VersionType.GIT: get_git_version_info,
    }

    # Default order of getters to try
    default_getters = [
        get_docker_version_info,
        get_github_version_info,
        get_git_version_info,
    ]

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
            if len(getters) == 1:
                raise
            continue

    # If we get here, all attempted inferred getters failed
    SimpleVersionInfo(
        type="prefect:simple",
    )
