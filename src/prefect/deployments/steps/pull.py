"""
Core set of steps for specifying a Prefect project pull step.
"""
import os
from pathlib import Path
from typing import Optional

from prefect._internal.compatibility.deprecated import deprecated_callable
from prefect.blocks.core import Block
from prefect.logging.loggers import get_logger
from prefect.runner.storage import GitRepository
from prefect.utilities.asyncutils import sync_compatible

deployment_logger = get_logger("deployment")


def set_working_directory(directory: str) -> dict:
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


@sync_compatible
async def git_clone(
    repository: str,
    branch: Optional[str] = None,
    include_submodules: bool = False,
    access_token: Optional[str] = None,
    credentials: Optional[Block] = None,
) -> dict:
    """
    Clones a git repository into the current working directory.

    Args:
        repository: the URL of the repository to clone
        branch: the branch to clone; if not provided, the default branch will be used
        include_submodules (bool): whether to include git submodules when cloning the repository
        access_token: an access token to use for cloning the repository; if not provided
            the repository will be cloned using the default git credentials
        credentials: a GitHubCredentials, GitLabCredentials, or BitBucketCredentials block can be used to specify the
            credentials to use for cloning the repository.

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
        Note that you will need to [create a Secret block](/concepts/blocks/#using-existing-block-types) to store the
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
    """
    if access_token and credentials:
        raise ValueError(
            "Please provide either an access token or credentials but not both."
        )

    credentials = {"access_token": access_token} if access_token else credentials

    storage = GitRepository(
        url=repository,
        credentials=credentials,
        branch=branch,
        include_submodules=include_submodules,
    )

    await storage.pull_code()

    directory = str(storage.destination.relative_to(Path.cwd()))
    deployment_logger.info(f"Cloned repository {repository!r} into {directory!r}")
    return {"directory": directory}


@deprecated_callable(start_date="Jun 2023", help="Use 'git clone' instead.")
@sync_compatible
async def git_clone_project(
    repository: str,
    branch: Optional[str] = None,
    include_submodules: bool = False,
    access_token: Optional[str] = None,
) -> dict:
    """Deprecated. Use `git_clone` instead."""
    return await git_clone(
        repository=repository,
        branch=branch,
        include_submodules=include_submodules,
        access_token=access_token,
    )
