import subprocess
from pathlib import Path
from typing import Optional, Protocol, TypedDict, runtime_checkable
from urllib.parse import urlparse, urlunparse

from anyio import run_process

from prefect.logging.loggers import get_logger


@runtime_checkable
class RunnerStorage(Protocol):
    """
    A storage interface for a runner to use to retrieve
    remotely stored flow code.
    """

    def set_base_path(self, path: Path):
        """
        Sets the base path to use when pulling contents from remote storage to
        local storage.
        """
        ...

    @property
    def pull_interval(self) -> Optional[int]:
        """
        The interval at which contents from remote storage should be pulled to
        local storage. If None, remote storage will perform a one-time sync.
        """
        ...

    @property
    def destination(self) -> Path:
        """
        The local file path to pull contents from remote storage to.
        """
        ...

    async def pull_code(self):
        """
        Pulls contents from remote storage to the local filesystem.
        """
        ...

    def __eq__(self, __value) -> bool:
        """
        Equality check for runner storage objects.
        """
        ...


class GitCredentials(TypedDict, total=False):
    username: str
    access_token: str


class GitRepository:
    """
    Pulls the contents of a git repository to the local filesystem.

    Parameters:
        url: The URL of the git repository to pull from
        credentials: A dictionary of credentials to use when pulling from the
            repository. If a username is provided, an access token must also be
            provided.
        name: The name of the repository. If not provided, the name will be
            inferred from the repository URL.
        branch: The branch to pull from. Defaults to "main".
        pull_interval: The interval in seconds at which to pull contents from
            remote storage to local storage. If None, remote storage will perform
            a one-time sync.

    Examples:
        Pull the contents of a private git repository to the local filesystem:

        ```python
        from prefect.runner.storage import GitRepository

        storage = GitRepository(
            url="https://github.com/org/repo.git",
            credentials={"username": "oauth2", "access_token": "my-access-token"},
        )

        await storage.pull_code()
        ```
    """

    def __init__(
        self,
        url: str,
        credentials: Optional[GitCredentials] = None,
        name: Optional[str] = None,
        branch: str = "main",
        pull_interval: Optional[int] = 60,
    ):
        if credentials is None:
            credentials = {}

        if credentials.get("username") and not credentials.get("access_token"):
            raise ValueError(
                "If a username is provided, an access token must also be provided."
            )
        self._url = url
        self._branch = branch
        self._username = credentials.get("username")
        self._access_token = credentials.get("access_token")
        repo_name = urlparse(url).path.split("/")[-1].replace(".git", "")
        self._name = name or f"{repo_name}-{branch}"
        self._logger = get_logger(f"runner.storage.git-repository.{self._name}")
        self._storage_base_path = Path.cwd()
        self._pull_interval = pull_interval

    @property
    def destination(self) -> Path:
        return self._storage_base_path / self._name

    def set_base_path(self, path: Path):
        self._storage_base_path = path

    @property
    def pull_interval(self) -> Optional[int]:
        return self._pull_interval

    async def pull_code(self):
        """
        Pulls the contents of the configured repository to the local filesystem.
        """
        self._logger.debug(
            "Pull contents from repository '%s' to '%s'...",
            self._name,
            self.destination,
        )

        git_dir = self.destination / ".git"

        if git_dir.exists():
            # Check if the existing repository matches the configured repository
            result = await run_process(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=str(self.destination),
            )
            existing_repo_url = None
            if result.stdout is not None:
                existing_repo_url = result.stdout.decode().strip()
                existing_repo_url_parts = urlparse(existing_repo_url)
                if self._access_token and not self._username:
                    existing_repo_url_parts = existing_repo_url_parts._replace(
                        netloc=existing_repo_url_parts.netloc.replace(
                            f"{self._access_token}@", ""
                        )
                    )
                if self._username and self._access_token:
                    existing_repo_url_parts = existing_repo_url_parts._replace(
                        netloc=existing_repo_url_parts.netloc.replace(
                            f"{self._username}:{self._access_token}@", ""
                        )
                    )
                existing_repo_url = urlunparse(existing_repo_url_parts)

            if existing_repo_url != self._url:
                raise ValueError(
                    f"The existing repository at {str(self.destination)} "
                    f"does not match the configured repository {self._url}"
                )

            self._logger.debug("Pulling latest changes from origin/%s", self._branch)
            # Update the existing repository
            await run_process(
                ["git", "pull", "origin", self._branch],
                cwd=self.destination,
            )
        else:
            self._logger.debug("Cloning repository %s", self._url)
            # Clone the repository if it doesn't exist at the destination

            repo_url_parts = urlparse(self._url)
            if self._access_token and not self._username:
                updated_components = repo_url_parts._replace(
                    netloc=f"{self._access_token}@{repo_url_parts.netloc}"
                )
                repository_url = urlunparse(updated_components)
            elif self._username and self._access_token:
                updated_components = repo_url_parts._replace(
                    netloc=(
                        f"{self._username}:{self._access_token}@{repo_url_parts.netloc}"
                    )
                )
                repository_url = urlunparse(updated_components)
            else:
                repository_url = self._url

            try:
                await run_process(
                    [
                        "git",
                        "clone",
                        "--branch",
                        self._branch,
                        repository_url,
                        str(self.destination),
                    ]
                )
            except subprocess.CalledProcessError as exc:
                # Hide the command used to avoid leaking the access token
                exc_chain = None if self._access_token else exc
                raise RuntimeError(
                    f"Failed to clone repository {self._url!r} with exit code"
                    f" {exc.returncode}."
                ) from exc_chain

    def __eq__(self, __value) -> bool:
        if isinstance(__value, GitRepository):
            return (
                self._url == __value._url
                and self._branch == __value._branch
                and self._name == __value._name
            )
        return False

    def __repr__(self) -> str:
        return (
            f"GitRepository(name={self._name!r} repository={self._url!r},"
            f" branch={self._branch!r})"
        )


def create_storage_from_url(
    url: str, pull_interval: Optional[int] = 60
) -> RunnerStorage:
    """
    Creates a storage object from a URL.

    Args:
        url: The URL to create a storage object from
        pull_interval: The interval at which to pull contents from remote storage to
            local storage

    Returns:
        RunnerStorage: A runner storage compatible object
    """
    parsed_url = urlparse(url)
    if parsed_url.scheme == "git" or parsed_url.path.endswith(".git"):
        return GitRepository(url=url, pull_interval=pull_interval)
    raise ValueError(f"Unsupported storage URL: {url}. Only git URLs are supported.")
