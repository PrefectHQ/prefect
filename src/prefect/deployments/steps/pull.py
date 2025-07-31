"""
Core set of steps for specifying a Prefect project pull step.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect._internal.retries import retry_async_fn
from prefect.logging.loggers import get_logger
from prefect.runner.storage import BlockStorageAdapter, GitRepository, RemoteStorage
from prefect.utilities.asyncutils import run_coro_as_sync

if TYPE_CHECKING:
    import logging

deployment_logger: "logging.Logger" = get_logger("deployment")

if TYPE_CHECKING:
    from prefect.blocks.core import Block


def set_working_directory(directory: str) -> dict[str, str]:
    """
    Sets the working directory; works with both absolute and relative paths.

    Args:
        directory (str): the directory to set as the working directory

    Returns:
        dict: a dictionary containing a `directory` key of the
            directory that was set
    """
    os.chdir(directory)
    return dict(directory=directory)


@retry_async_fn(
    max_attempts=3,
    base_delay=1,
    max_delay=10,
    retry_on_exceptions=(RuntimeError,),
    operation_name="git_clone",
)
async def _pull_git_repository_with_retries(repo: GitRepository):
    await repo.pull_code()


async def agit_clone(
    repository: str,
    branch: Optional[str] = None,
    commit_sha: Optional[str] = None,
    include_submodules: bool = False,
    access_token: Optional[str] = None,
    credentials: Optional["Block"] = None,
    directories: Optional[list[str]] = None,
) -> dict[str, str]:
    """
    Asynchronously clones a git repository into the current working directory.

    Args:
        repository: the URL of the repository to clone
        branch: the branch to clone; if not provided, the default branch will be used
        commit_sha: the commit SHA to clone; if not provided, the default branch will be used
        include_submodules (bool): whether to include git submodules when cloning the repository
        access_token: an access token to use for cloning the repository; if not provided
            the repository will be cloned using the default git credentials
        credentials: a GitHubCredentials, GitLabCredentials, or BitBucketCredentials block can be used to specify the
            credentials to use for cloning the repository.

    Returns:
        dict: a dictionary containing a `directory` key of the new directory that was created

    Raises:
        subprocess.CalledProcessError: if the git clone command fails for any reason
    """
    if access_token and credentials:
        raise ValueError(
            "Please provide either an access token or credentials but not both."
        )

    _credentials = {"access_token": access_token} if access_token else credentials

    storage = GitRepository(
        url=repository,
        credentials=_credentials,
        branch=branch,
        commit_sha=commit_sha,
        include_submodules=include_submodules,
        directories=directories,
    )

    await _pull_git_repository_with_retries(storage)

    return dict(directory=str(storage.destination.relative_to(Path.cwd())))


@async_dispatch(agit_clone)
def git_clone(
    repository: str,
    branch: Optional[str] = None,
    commit_sha: Optional[str] = None,
    include_submodules: bool = False,
    access_token: Optional[str] = None,
    credentials: Optional["Block"] = None,
    directories: Optional[list[str]] = None,
) -> dict[str, str]:
    """
    Clones a git repository into the current working directory.

    Args:
        repository: the URL of the repository to clone
        branch: the branch to clone; if not provided, the default branch will be used
        commit_sha: the commit SHA to clone; if not provided, the default branch will be used
        include_submodules (bool): whether to include git submodules when cloning the repository
        access_token: an access token to use for cloning the repository; if not provided
            the repository will be cloned using the default git credentials
        credentials: a GitHubCredentials, GitLabCredentials, or BitBucketCredentials block can be used to specify the
            credentials to use for cloning the repository.
        directories: Specify directories you want to be included (uses git sparse-checkout)

    Returns:
        dict: a dictionary containing a `directory` key of the new directory that was created

    Raises:
        subprocess.CalledProcessError: if the git clone command fails for any reason

    Examples:
        Clone a public repository:
        ```yaml
        pull:
            - prefect.deployments.steps.git_clone:
                repository: https://github.com/PrefectHQ/prefect.git
        ```

        Clone a branch of a public repository:
        ```yaml
        pull:
            - prefect.deployments.steps.git_clone:
                repository: https://github.com/PrefectHQ/prefect.git
                branch: my-branch
        ```

        Clone a private repository using a GitHubCredentials block:
        ```yaml
        pull:
            - prefect.deployments.steps.git_clone:
                repository: https://github.com/org/repo.git
                credentials: "{{ prefect.blocks.github-credentials.my-github-credentials-block }}"
        ```

        Clone a private repository using an access token:
        ```yaml
        pull:
            - prefect.deployments.steps.git_clone:
                repository: https://github.com/org/repo.git
                access_token: "{{ prefect.blocks.secret.github-access-token }}" # Requires creation of a Secret block
        ```
        Note that you will need to [create a Secret block](https://docs.prefect.io/v3/concepts/blocks/#pre-registered-blocks) to store the
        value of your git credentials. You can also store a username/password combo or token prefix (e.g. `x-token-auth`)
        in your secret block. Refer to your git providers documentation for the correct authentication schema.

        Clone a repository with submodules:
        ```yaml
        pull:
            - prefect.deployments.steps.git_clone:
                repository: https://github.com/org/repo.git
                include_submodules: true
        ```

        Clone a repository with an SSH key (note that the SSH key must be added to the worker
        before executing flows):
        ```yaml
        pull:
            - prefect.deployments.steps.git_clone:
                repository: git@github.com:org/repo.git
        ```

        Clone a repository using sparse-checkout (allows specific folders of the repository to be checked out)
        ```yaml
        pull:
            - prefect.deployments.steps.git_clone:
                repository: https://github.com/org/repo.git
                directories: ["dir_1", "dir_2", "prefect"]
        ```
    """
    if access_token and credentials:
        raise ValueError(
            "Please provide either an access token or credentials but not both."
        )

    _credentials = {"access_token": access_token} if access_token else credentials

    storage = GitRepository(
        url=repository,
        credentials=_credentials,
        branch=branch,
        commit_sha=commit_sha,
        include_submodules=include_submodules,
        directories=directories,
    )

    run_coro_as_sync(_pull_git_repository_with_retries(storage))

    return dict(directory=str(storage.destination.relative_to(Path.cwd())))


async def pull_from_remote_storage(url: str, **settings: Any) -> dict[str, Any]:
    """
    Pulls code from a remote storage location into the current working directory.

    Works with protocols supported by `fsspec`.

    Args:
        url (str): the URL of the remote storage location. Should be a valid `fsspec` URL.
            Some protocols may require an additional `fsspec` dependency to be installed.
            Refer to the [`fsspec` docs](https://filesystem-spec.readthedocs.io/en/latest/api.html#other-known-implementations)
            for more details.
        **settings (Any): any additional settings to pass the `fsspec` filesystem class.

    Returns:
        dict: a dictionary containing a `directory` key of the new directory that was created

    Examples:
        Pull code from a remote storage location:
        ```yaml
        pull:
            - prefect.deployments.steps.pull_from_remote_storage:
                url: s3://my-bucket/my-folder
        ```

        Pull code from a remote storage location with additional settings:
        ```yaml
        pull:
            - prefect.deployments.steps.pull_from_remote_storage:
                url: s3://my-bucket/my-folder
                key: {{ prefect.blocks.secret.my-aws-access-key }}}
                secret: {{ prefect.blocks.secret.my-aws-secret-key }}}
        ```
    """
    storage = RemoteStorage(url, **settings)

    await storage.pull_code()

    directory = str(storage.destination.relative_to(Path.cwd()))
    deployment_logger.info(f"Pulled code from {url!r} into {directory!r}")
    return {"directory": directory}


async def pull_with_block(
    block_document_name: str, block_type_slug: str
) -> dict[str, Any]:
    """
    Pulls code using a block.

    Args:
        block_document_name: The name of the block document to use
        block_type_slug: The slug of the type of block to use
    """
    from prefect.blocks.core import Block

    full_slug = f"{block_type_slug}/{block_document_name}"
    try:
        block = await Block.aload(full_slug)
    except Exception:
        deployment_logger.exception("Unable to load block '%s'", full_slug)
        raise

    try:
        storage = BlockStorageAdapter(block)
    except Exception:
        deployment_logger.exception(
            "Unable to create storage adapter for block '%s'", full_slug
        )
        raise

    await storage.pull_code()

    directory = str(storage.destination.relative_to(Path.cwd()))
    deployment_logger.info(
        "Pulled code using block '%s' into '%s'", full_slug, directory
    )
    return {"directory": directory}
