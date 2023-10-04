from pathlib import Path
from typing import Optional, Protocol, runtime_checkable
from urllib.parse import urlparse

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
        Sets the base path to use when syncing remote storage to local storage.
        """
        ...

    @property
    def sync_interval(self) -> Optional[int]:
        """
        The interval at which remote storage should be synced to local storage.
        If None, remote storage will perform a one-time sync.
        """
        ...

    @property
    def destination(self) -> Path:
        """
        The local file path to sync remote storage to.
        """
        ...

    async def sync(self):
        """
        Syncs remote storage to the local filesystem.
        """
        ...

    def __eq__(self, __value) -> bool:
        """
        Equality check for runner storage objects.
        """
        ...


class GitRepository:
    """
    Syncs a git repository to the local filesystem.
    """

    def __init__(
        self,
        repository: str,
        name: Optional[str] = None,
        branch: str = "main",
        sync_interval: Optional[int] = 60,
    ):
        self._repository = repository
        self._branch = branch
        repo_name = urlparse(repository).path.split("/")[-1].replace(".git", "")
        self._name = name or f"{repo_name}-{branch}"
        self._logger = get_logger(f"runner.storage.git-repository.{self._name}")
        self._mount_path = Path.cwd()
        self._sync_interval = sync_interval

    @property
    def destination(self) -> Path:
        return self._mount_path / self._name

    def set_base_path(self, path: Path):
        self._mount_path = path

    @property
    def sync_interval(self) -> Optional[int]:
        return self._sync_interval

    async def sync(self):
        """
        Syncs the repository to the local filesystem.
        """
        self._logger.debug(
            "Syncing repository %s to %s...", self._name, self.destination
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

            if existing_repo_url != self._repository:
                raise ValueError(
                    f"The existing repository at {str(self.destination)} "
                    f"does not match the configured repository {self._repository}"
                )

            self._logger.debug("Pulling latest changes from origin/%s", self._branch)
            # Update the existing repository
            await run_process(
                ["git", "pull", "origin", self._branch],
                cwd=self.destination,
            )
        else:
            self._logger.debug("Cloning repository %s", self._repository)
            # Clone the repository if it doesn't exist at the destination
            await run_process(
                [
                    "git",
                    "clone",
                    "--branch",
                    self._branch,
                    self._repository,
                    str(self.destination),
                ]
            )

    def __eq__(self, __value) -> bool:
        if isinstance(__value, GitRepository):
            return (
                self._repository == __value._repository
                and self._branch == __value._branch
                and self._name == __value._name
            )
        return False

    def __repr__(self) -> str:
        return (
            f"GitRepositoryMount(name={self._name!r} repository={self._repository!r},"
            f" branch={self._branch!r})"
        )


def create_storage_from_url(
    url: str, sync_interval: Optional[int] = 60
) -> RunnerStorage:
    """
    Creates a storage object from a URL.

    Args:
        url: The URL to create a storage object from
        sync_interval: The interval at which to sync remote storage to local storage

    Returns:
        RunnerStorage: A runner storage compatible object
    """
    parsed_url = urlparse(url)
    if parsed_url.scheme == "git" or parsed_url.path.endswith(".git"):
        return GitRepository(repository=url, sync_interval=sync_interval)
    raise ValueError(f"Unsupported storage URL: {url}. Only git URLs are supported.")
