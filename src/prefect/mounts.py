from pathlib import Path
from typing import Optional, Protocol, runtime_checkable
from urllib.parse import urlparse

from anyio import run_process

from prefect.logging.loggers import get_logger


@runtime_checkable
class Mount(Protocol):
    """
    A mount is a location that can be mounted to a flow runner.
    """

    def set_mount_path(self, path: Path):
        """
        Sets the path where the mount is mounted.
        """
        ...

    @property
    def name(self) -> str:
        """
        The name of the mount.
        """
        ...

    @property
    def sync_interval(self) -> int:
        """
        The interval at which the mount is synced.
        """
        ...

    @property
    def destination(self) -> Path:
        """
        The destination path of the mount.
        """
        ...

    async def sync(self):
        """
        Syncs the mount to the local filesystem.
        """
        ...


class GitRepositoryMount:
    """
    Syncs a git repository to the local filesystem.
    """

    def __init__(
        self,
        repository: str,
        name: Optional[str] = None,
        branch: str = "main",
        sync_interval: int = 60,
    ):
        self._repository = repository
        self._branch = branch
        repo_name = urlparse(repository).path.split("/")[-1].replace(".git", "")
        self._name = name or f"{repo_name}-{branch}"
        self._logger = get_logger("git-synchronizer")
        self._mount_path = Path.cwd()
        self._sync_interval = sync_interval

    @property
    def destination(self) -> Path:
        return self._mount_path / self._name

    def set_mount_path(self, path: Path):
        self._mount_path = path

    @property
    def name(self) -> str:
        return self._name

    @property
    def sync_interval(self) -> int:
        return self._sync_interval

    async def sync(self):
        """
        Syncs the repository to the local filesystem.
        """
        self._logger.info(
            f"Syncing repository %s to %s...", self.name, self.destination
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

    def __eq__(self, __value):
        if isinstance(__value, GitRepositoryMount):
            return (
                self._repository == __value._repository
                and self._branch == __value._branch
            )
        return False

    def __repr__(self) -> str:
        return f"GitRepositoryMount(name={self.name!r} repository={self._repository!r}, branch={self._branch!r})"
