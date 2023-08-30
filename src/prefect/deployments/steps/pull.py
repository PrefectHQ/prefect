"""
Core set of steps for specifying a Prefect project pull step.
"""
import os
import subprocess
import sys
import urllib.parse
from typing import Optional

from prefect._internal.compatibility.deprecated import deprecated_callable
from prefect.blocks.core import Block
from prefect.logging.loggers import get_logger

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


def _format_token(url_components, access_token, username, password, token) -> str:
    """
    Formats the access token for the git provider.

    BitBucket supports the following syntax:
        git clone "https://x-token-auth:{token}@bitbucket.org/yourRepoOwnerHere/RepoNameHere"
        git clone https://username:<token>@bitbucketserver.com/scm/projectname/teamsinspace.git
    """

    if "bitbucketserver" in url_components.netloc:
        # If they pass a header themselves, we can just use that.
        if access_token:
            if ":" in access_token:
                return access_token
            else:
                raise ValueError(
                    "Please prefix your BitBucket Server access_token with a username,"
                    " e.g. 'username:token'."
                )

        # If they pass a BitBucketCredentials block and we don't have both a username and at
        # least one of a password or token and they don't provide a header themselves,
        # we can raise the approriate error to avoid the wrong format for BitBucket Server.
        elif username and (token or password):
            if token:
                return f"{username}:{token}" if username not in token else token
            return f"{username}:{password}"

        for item in [token, password]:
            if ":" in item:
                return item
        raise ValueError(
            "Please provide a `username` and a `password` or `token` in your"
            " BitBucketCredentials block to clone a repo from BitBucket Server."
        )

    elif "bitbucket" in url_components.netloc:
        user_provided_token = access_token or token or password
        contains_header = (
            user_provided_token.startswith("x-token-auth:")
            or ":" in user_provided_token
        )
        return (
            f"x-token-auth:{user_provided_token}"
            if not contains_header
            else user_provided_token
        )

    elif "gitlab" in url_components.netloc:
        user_provided_token = access_token or token
        if user_provided_token:
            return (
                f"oauth2:{user_provided_token}"
                if not user_provided_token.startswith("oauth2:")
                else user_provided_token
            )

    else:
        return access_token or token


def git_clone(
    repository: str,
    branch: Optional[str] = None,
    include_submodules: bool = False,
    access_token: Optional[str] = None,
    credentials: Optional[Block] = None,
) -> dict:
    """
    Clones a git repository into the current working directory.

    Args:
        repository (str): the URL of the repository to clone
        branch (str, optional): the branch to clone; if not provided, the default branch will be used
        include_submodules (bool): whether to include git submodules when cloning the repository
        access_token (str, optional): an access token to use for cloning the repository; if not provided
            the repository will be cloned using the default git credentials
        credentials (optional): a GitHubCredentials, GitLabCredentials, or BitBucketCredentials block can be used to specify the
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

    url_components = urllib.parse.urlparse(repository)

    if access_token or credentials:
        username = credentials.get("username") if credentials else None
        password = credentials.get("password") if credentials else None
        token = credentials.get("token") if credentials else None

        access_token = _format_token(
            url_components, access_token, username, password, token
        )

    if url_components.scheme == "https" and access_token is not None:
        updated_components = url_components._replace(
            netloc=f"{access_token}@{url_components.netloc}"
        )
        repository_url = urllib.parse.urlunparse(updated_components)
    else:
        repository_url = repository

    cmd = ["git", "clone", repository_url]
    if branch:
        cmd += ["-b", branch]
    if include_submodules:
        cmd += ["--recurse-submodules"]

    # Limit git history
    cmd += ["--depth", "1"]

    try:
        subprocess.check_call(
            cmd, shell=sys.platform == "win32", stderr=sys.stderr, stdout=sys.stdout
        )
    except subprocess.CalledProcessError as exc:
        # Hide the command used to avoid leaking the access token
        exc_chain = None if access_token else exc
        raise RuntimeError(
            f"Failed to clone repository {repository!r} with exit code"
            f" {exc.returncode}."
        ) from exc_chain

    directory = "/".join(repository.strip().split("/")[-1:]).replace(".git", "")
    deployment_logger.info(f"Cloned repository {repository!r} into {directory!r}")
    return {"directory": directory}


@deprecated_callable(start_date="Jun 2023", help="Use 'git clone' instead.")
def git_clone_project(
    repository: str,
    branch: Optional[str] = None,
    include_submodules: bool = False,
    access_token: Optional[str] = None,
) -> dict:
    """Deprecated. Use `git_clone` instead."""
    return git_clone(
        repository=repository,
        branch=branch,
        include_submodules=include_submodules,
        access_token=access_token,
    )
