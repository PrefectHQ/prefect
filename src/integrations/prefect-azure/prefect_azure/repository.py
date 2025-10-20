"""Interact with files stored in Azure DevOps Git repositories.

The `AzureDevopsRepository` class in this module is a storage block that lets Prefect
agents pull Prefect flow code from Azure DevOps repositories.

The `AzureDevopsRepository` block is ideally configured via the Prefect UI, but can
also be used in Python as the following examples demonstrate.

Examples:
    Load a configured Azure DevOps repository block:
    ```python
    from prefect_azure.repository import AzureDevopsRepository

    azuredevops_repository_block = AzureDevopsRepository.load("BLOCK_NAME")
    ```

    Clone a public Azure DevOps repository:
    ```python
    from prefect_azure.repository import AzureDevopsRepository

    public_repo = AzureDevopsRepository(
        repository="https://dev.azure.com/myorg/myproject/_git/myrepo"
    )
    public_repo.save(name="my-azuredevops-block")
    ```

    Clone a specific branch or tag:
    ```python
    from prefect_azure.repository import AzureDevopsRepository

    branch_repo = AzureDevopsRepository(
        repository="https://dev.azure.com/myorg/myproject/_git/myrepo",
        reference="develop"
    )
    branch_repo.save(name="my-azuredevops-branch-block")
    ```

    Clone a private Azure DevOps repository:
    ```python
    from prefect_azure import AzureDevopsCredentials, AzureDevopsRepository

    azuredevops_credentials_block = AzureDevopsCredentials.load("my-azuredevops-credentials")

    private_repo = AzureDevopsRepository(
        repository="https://dev.azure.com/myorg/myproject/_git/myrepo",
        credentials=azuredevops_credentials_block
    )
    private_repo.save(name="my-private-azuredevops-block")
    ```
"""

import io
import shutil
import urllib.parse
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional, Tuple, Union

from pydantic import Field

from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect._internal.retries import retry_async_fn
from prefect.filesystems import ReadableDeploymentStorage
from prefect.utilities.processutils import run_process
from prefect_azure.credentials import AzureDevopsCredentials

MAX_CLONE_ATTEMPTS = 3
CLONE_RETRY_MIN_DELAY_SECONDS = 1
CLONE_RETRY_MIN_DELAY_JITTER_SECONDS = 0
CLONE_RETRY_MAX_DELAY_JITTER_SECONDS = 3


class AzureDevopsRepository(ReadableDeploymentStorage):
    """
    Interact with files stored in Azure DevOps Git repositories.
    """

    _block_type_name = "Azure DevOps Repository"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/54e3fa7e00197a4fbd1d82ed62494cb58d08c96a-250x250.png"
    _description = "Interact with files stored in Azure DevOps repositories."
    _documentation_url = "https://docs.prefect.io/integrations/prefect-azure"

    repository: str = Field(
        default=...,
        description="The full HTTPS URL of the Azure DevOps repository.",
    )
    reference: Optional[str] = Field(
        default=None,
        description="Optional branch or tag name.",
    )
    git_depth: Optional[int] = Field(
        default=1,
        ge=1,
        description="Depth of git history to fetch.",
    )
    credentials: Optional[AzureDevopsCredentials] = Field(
        default=None,
        title="Credentials",
        description="Azure DevOps Credentials block to authenticate with azuredevops private repositories",
    )

    def _create_repo_url(self) -> str:
        if self.repository.startswith("git@"):
            raise ValueError(
                "SSH URLs are not supported. Please provide an HTTPS URL for the repository."
            )
        url_components = urllib.parse.urlparse(self.repository)
        if self.credentials is not None and self.credentials.token is not None:
            token = self.credentials.token.get_secret_value()
            token = urllib.parse.quote(token, safe="")
            if url_components.username:
                user_info = f"{url_components.username}:{token}"
            else:
                user_info = f":{token}"
            netloc = user_info + "@" + url_components.hostname
            if url_components.port:
                netloc += f":{url_components.port}"
            updated_components = url_components._replace(netloc=netloc)
            full_url = urllib.parse.urlunparse(updated_components)
        else:
            full_url = self.repository
        return full_url

    @staticmethod
    def _get_paths(
        dst_dir: Union[str, None], src_dir: str, sub_directory: Optional[str]
    ) -> Tuple[str, str]:
        if dst_dir is None:
            content_destination = Path(".").absolute()
        else:
            content_destination = Path(dst_dir)
        content_source = Path(src_dir)
        if sub_directory:
            content_destination = content_destination.joinpath(sub_directory)
            content_source = content_source.joinpath(sub_directory)
        return str(content_source), str(content_destination)

    @retry_async_fn(
        max_attempts=MAX_CLONE_ATTEMPTS,
        base_delay=CLONE_RETRY_MIN_DELAY_SECONDS,
        max_delay=CLONE_RETRY_MIN_DELAY_SECONDS + CLONE_RETRY_MAX_DELAY_JITTER_SECONDS,
        operation_name="clone_repository",
    )
    async def aget_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> None:
        """Asynchronously clones an Azure DevOps repository.

        This defaults to cloning the repository reference configured on the
        Block to the present working directory.

        Args:
            from_path: If provided, interpreted as a subdirectory of the underlying
                repository that will be copied to the provided local path.
            local_path: A local path to clone to; defaults to present working directory.
        """
        cmd = ["git", "clone", self._create_repo_url()]
        if self.reference:
            cmd += ["-b", self.reference]
        if self.git_depth is not None:
            cmd += ["--depth", f"{self.git_depth}"]

        with TemporaryDirectory(suffix="prefect") as tmp_dir:
            cmd.append(tmp_dir)

            err_stream = io.StringIO()
            out_stream = io.StringIO()
            process = await run_process(cmd, stream_output=(out_stream, err_stream))
            if process.returncode != 0:
                err_stream.seek(0)
                error_output = err_stream.read()
                if self.credentials and self.credentials.token:
                    raw_token = self.credentials.token.get_secret_value()
                    if raw_token:
                        error_output = error_output.replace(raw_token, "[REDACTED]")
                        repo_url_with_token = self._create_repo_url()
                        error_output = error_output.replace(
                            repo_url_with_token, "[REDACTED]"
                        )
                raise RuntimeError(f"Failed to pull from remote:\n {error_output}")

            content_source, content_destination = self._get_paths(
                dst_dir=local_path, src_dir=tmp_dir, sub_directory=from_path
            )
            shutil.copytree(
                src=content_source, dst=content_destination, dirs_exist_ok=True
            )

    @async_dispatch(aget_directory)
    def get_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> None:
        """Clones an Azure DevOps project within `from_path` to the provided `local_path`.

        This defaults to cloning the repository reference configured on the
        Block to the present working directory.

        Args:
            from_path: If provided, interpreted as a subdirectory of the underlying
                repository that will be copied to the provided local path.
            local_path: A local path to clone to; defaults to present working directory.
        """
        from prefect.utilities.asyncutils import run_coro_as_sync

        run_coro_as_sync(
            self.aget_directory(from_path=from_path, local_path=local_path)
        )
