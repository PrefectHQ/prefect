"""
Integrations with GitLab.

The `GitLab` class in this collection is a storage block that lets Prefect agents
pull Prefect flow code from GitLab repositories.

The `GitLab` block is ideally configured via the Prefect UI, but can also be used
in Python as the following examples demonstrate.

Examples:
```python
    from prefect_gitlab.repositories import GitLabRepository

    # public GitLab repository
    public_gitlab_block = GitLabRepository(
        name="my-gitlab-block",
        repository="https://gitlab.com/testing/my-repository.git"
    )

    public_gitlab_block.save()


    # specific branch or tag of a GitLab repository
    branch_gitlab_block = GitLabRepository(
        name="my-gitlab-block",
        reference="branch-or-tag-name"
        repository="https://gitlab.com/testing/my-repository.git"
    )

    branch_gitlab_block.save()


    # private GitLab repository
    private_gitlab_block = GitLabRepository(
        name="my-private-gitlab-block",
        repository="https://gitlab.com/testing/my-repository.git",
        access_token="YOUR_GITLAB_PERSONAL_ACCESS_TOKEN"
    )

    private_gitlab_block.save()
```
"""
import io
import urllib.parse
from distutils.dir_util import copy_tree
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional, Tuple, Union

from pydantic import VERSION as PYDANTIC_VERSION
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random

from prefect.exceptions import InvalidRepositoryURLError
from prefect.filesystems import ReadableDeploymentStorage
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.processutils import run_process

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field, HttpUrl, validator
else:
    from pydantic import Field, HttpUrl, validator

from prefect_gitlab.credentials import GitLabCredentials

# Create get_directory retry settings

MAX_CLONE_ATTEMPTS = 3
CLONE_RETRY_MIN_DELAY_SECONDS = 1
CLONE_RETRY_MIN_DELAY_JITTER_SECONDS = 0
CLONE_RETRY_MAX_DELAY_JITTER_SECONDS = 3


class GitLabRepository(ReadableDeploymentStorage):
    """
    Interact with files stored in GitLab repositories.

    An accessible installation of git is required for this block to function
    properly.
    """

    _block_type_name = "GitLab Repository"
    _logo_url = HttpUrl(
        url="https://images.ctfassets.net/gm98wzqotmnx/55edIimT4g9gbjhkh5a3Sp/dfdb9391d8f45c2e93e72e3a4d350771/gitlab-logo-500.png?h=250",  # noqa
        scheme="https",
    )
    _description = "Interact with files stored in GitLab repositories."

    repository: str = Field(
        default=...,
        description=(
            "The URL of a GitLab repository to read from, in either HTTP/HTTPS or SSH format."  # noqa
        ),
    )
    reference: Optional[str] = Field(
        default=None,
        description="An optional reference to pin to; can be a branch name or tag.",
    )
    git_depth: Optional[int] = Field(
        default=1,
        gte=1,
        description="The number of commits that Git history is truncated to "
        "during cloning. Set to None to fetch the entire history.",
    )
    credentials: Optional[GitLabCredentials] = Field(
        default=None,
        description="An optional GitLab Credentials block for authenticating with "
        "private GitLab repos.",
    )

    @validator("credentials")
    def _ensure_credentials_go_with_http(cls, v: str, values: dict) -> str:
        """Ensure that credentials are not provided with 'SSH' formatted GitLub URLs.
        Note: validates `access_token` specifically so that it only fires when
        private repositories are used.
        """
        if v is not None:
            if urllib.parse.urlparse(values["repository"]).scheme not in [
                "https",
                "http",
            ]:
                raise InvalidRepositoryURLError(
                    (
                        "Credentials can only be used with GitLab repositories "
                        "using the 'HTTPS'/'HTTP' format. You must either remove the "
                        "credential if you wish to use the 'SSH' format and are not "
                        "using a private repository, or you must change the repository "
                        "URL to the 'HTTPS'/'HTTP' format."
                    )
                )

        return v

    def _create_repo_url(self) -> str:
        """Format the URL provided to the `git clone` command.
        For private repos: https://<oauth-key>@gitlab.com/<username>/<repo>.git
        All other repos should be the same as `self.repository`.
        """
        url_components = urllib.parse.urlparse(self.repository)
        if url_components.scheme in ["https", "http"] and self.credentials is not None:
            token = self.credentials.token.get_secret_value()
            updated_components = url_components._replace(
                netloc=f"oauth2:{token}@{url_components.netloc}"
            )
            full_url = urllib.parse.urlunparse(updated_components)
        else:
            full_url = self.repository

        return full_url

    @staticmethod
    def _get_paths(
        dst_dir: Union[str, None], src_dir: str, sub_directory: Optional[str]
    ) -> Tuple[str, str]:
        """Returns the fully formed paths for GitLabRepository contents in the form
        (content_source, content_destination).
        """
        if dst_dir is None:
            content_destination = Path(".").absolute()
        else:
            content_destination = Path(dst_dir)

        content_source = Path(src_dir)

        if sub_directory:
            content_destination = content_destination.joinpath(sub_directory)
            content_source = content_source.joinpath(sub_directory)

        return str(content_source), str(content_destination)

    @sync_compatible
    @retry(
        stop=stop_after_attempt(MAX_CLONE_ATTEMPTS),
        wait=wait_fixed(CLONE_RETRY_MIN_DELAY_SECONDS)
        + wait_random(
            CLONE_RETRY_MIN_DELAY_JITTER_SECONDS,
            CLONE_RETRY_MAX_DELAY_JITTER_SECONDS,
        ),
        reraise=True,
    )
    async def get_directory(
        self, from_path: Optional[str] = None, local_path: Optional[str] = None
    ) -> None:
        """
        Clones a GitLab project specified in `from_path` to the provided `local_path`;
        defaults to cloning the repository reference configured on the Block to the
        present working directory.
        Args:
            from_path: If provided, interpreted as a subdirectory of the underlying
                repository that will be copied to the provided local path.
            local_path: A local path to clone to; defaults to present working directory.
        """
        # CONSTRUCT COMMAND
        cmd = ["git", "clone", self._create_repo_url()]
        if self.reference:
            cmd += ["-b", self.reference]

        # Limit git history
        if self.git_depth is not None:
            cmd += ["--depth", f"{self.git_depth}"]

        # Clone to a temporary directory and move the subdirectory over
        with TemporaryDirectory(suffix="prefect") as tmp_dir:
            cmd.append(tmp_dir)

            err_stream = io.StringIO()
            out_stream = io.StringIO()
            process = await run_process(cmd, stream_output=(out_stream, err_stream))
            if process.returncode != 0:
                err_stream.seek(0)
                raise OSError(f"Failed to pull from remote:\n {err_stream.read()}")

            content_source, content_destination = self._get_paths(
                dst_dir=local_path, src_dir=tmp_dir, sub_directory=from_path
            )

            copy_tree(src=content_source, dst=content_destination)
