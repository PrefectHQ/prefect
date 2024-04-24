import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Set, Tuple

import pytest
from pydantic import VERSION as PYDANTIC_VERSION

from prefect.exceptions import InvalidRepositoryURLError
from prefect.testing.utilities import AsyncMock

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import SecretStr
else:
    from pydantic import SecretStr

import prefect_gitlab
from prefect_gitlab.credentials import GitLabCredentials
from prefect_gitlab.repositories import GitLabRepository  # noqa: E402


class TestGitLab:
    def setup_test_directory(
        self, tmp_src: str, sub_dir: str = "puppy"
    ) -> Tuple[Set[str], Set[str]]:
        """Add files and directories to a temporary directory. Returns a tuple with the
        expected parent-level contents and the expected child-level contents.
        """
        # add file to tmp_src
        f1_name = "dog.text"
        f1_path = Path(tmp_src) / f1_name
        f1 = open(f1_path, "w")
        f1.close()

        # add sub-directory to tmp_src
        sub_dir_path = Path(tmp_src) / sub_dir
        os.mkdir(sub_dir_path)

        # add file to sub-directory
        f2_name = "cat.txt"
        f2_path = sub_dir_path / f2_name
        f2 = open(f2_path, "w")
        f2.close()

        parent_contents = {f1_name, sub_dir}
        child_contents = {f2_name}

        assert set(os.listdir(tmp_src)) == parent_contents
        assert set(os.listdir(sub_dir_path)) == child_contents

        return parent_contents, child_contents

    class MockTmpDir:
        """Utility for having `TemporaryDirectory` return a known location."""

        dir = None

        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self.dir

        def __exit__(self, *args, **kwargs):
            pass

    async def test_subprocess_errors_are_surfaced(self):
        g = GitLabRepository(repository="incorrect-url-scheme")
        with pytest.raises(
            OSError, match="fatal: repository 'incorrect-url-scheme' does not exist"
        ):
            await g.get_directory()

    async def test_repository_default(self, monkeypatch):
        class p:
            returncode = 0

        mock = AsyncMock(return_value=p())
        monkeypatch.setattr(prefect_gitlab.repositories, "run_process", mock)
        g = GitLabRepository(repository="prefect")
        await g.get_directory()

        assert mock.await_count == 1
        expected_cmd = ["git", "clone", "prefect"]
        assert mock.await_args[0][0][: len(expected_cmd)] == expected_cmd

    async def test_reference_default(self, monkeypatch):
        class p:
            returncode = 0

        mock = AsyncMock(return_value=p())
        monkeypatch.setattr(prefect_gitlab.repositories, "run_process", mock)
        g = GitLabRepository(repository="prefect", reference="2.0.0")
        await g.get_directory()

        assert mock.await_count == 1
        expected_cmd = ["git", "clone", "prefect", "-b", "2.0.0", "--depth", "1"]
        assert mock.await_args[0][0][: len(expected_cmd)] == expected_cmd

    async def test_https_connection_with_token_added_correctly(self, monkeypatch):
        """Ensure that the repo url is in the format `https://<oauth-key>@gitlab.com/<username>/<repo>.git`."""  # noqa: E501

        class p:
            returncode = 0

        mock = AsyncMock(return_value=p())
        monkeypatch.setattr(prefect_gitlab.repositories, "run_process", mock)
        credential = "XYZ"
        repo = "https://gitlab.com/PrefectHQ/prefect.git"
        g = GitLabRepository(
            repository=repo,
            credentials=GitLabCredentials(token=SecretStr(credential)),
        )
        await g.get_directory()
        assert mock.await_count == 1
        expected_cmd = [
            "git",
            "clone",
            f"https://oauth2:{credential}@gitlab.com/PrefectHQ/prefect.git",
            "--depth",
            "1",
        ]
        assert mock.await_args[0][0][: len(expected_cmd)] == expected_cmd

    async def test_http_connection_with_token_added_correctly(self, monkeypatch):
        """Ensure that the repo url is in the format `http://<oauth-key>@gitlab.com/<username>/<repo>.git`."""  # noqa: E501

        class p:
            returncode = 0

        mock = AsyncMock(return_value=p())
        monkeypatch.setattr(prefect_gitlab.repositories, "run_process", mock)
        credential = "XYZ"
        repo = "http://gitlab.xxx.com/PrefectHQ/prefect.git"
        g = GitLabRepository(
            repository=repo,
            credentials=GitLabCredentials(token=SecretStr(credential)),
        )
        await g.get_directory()
        assert mock.await_count == 1
        expected_cmd = [
            "git",
            "clone",
            f"http://oauth2:{credential}@gitlab.xxx.com/PrefectHQ/prefect.git",
            "--depth",
            "1",
        ]
        assert mock.await_args[0][0][: len(expected_cmd)] == expected_cmd

    async def test_cloning_with_custom_depth(self, monkeypatch):
        """Ensure that we can retrieve the whole history, i.e. support true git clone"""  # noqa: E501

        class p:
            returncode = 0

        mock = AsyncMock(return_value=p())
        monkeypatch.setattr(prefect_gitlab.repositories, "run_process", mock)
        repo = "git@gitlab.com:PrefectHQ/prefect.git"
        depth = None
        g = GitLabRepository(
            repository=repo,
            git_depth=depth,
        )
        await g.get_directory()
        assert mock.await_count == 1
        expected_cmd = [
            "git",
            "clone",
            repo,
        ]
        assert mock.await_args[0][0][: len(expected_cmd)] == expected_cmd

    async def test_ssh_fails_with_credential(self, monkeypatch):
        """Ensure that credentials cannot be passed in if the URL is not in the HTTPS/HTTP
        format.
        """

        class p:
            returncode = 0

        mock = AsyncMock(return_value=p())
        monkeypatch.setattr(prefect_gitlab.repositories, "run_process", mock)
        credential = "XYZ"
        error_msg = (
            "Credentials can only be used with GitLab repositories "
            "using the 'HTTPS'/'HTTP' format. You must either remove the "
            "credential if you wish to use the 'SSH' format and are not "
            "using a private repository, or you must change the repository "
            "URL to the 'HTTPS'/'HTTP' format."
        )
        with pytest.raises(InvalidRepositoryURLError, match=error_msg):
            GitLabRepository(
                repository="git@gitlab.com:PrefectHQ/prefect.git",
                credentials=GitLabCredentials(token=SecretStr(credential)),
            )

    async def test_dir_contents_copied_correctly_with_get_directory(self, monkeypatch):  # noqa
        """Check that `get_directory` is able to correctly copy contents from src->dst"""  # noqa

        class p:
            returncode = 0

        mock = AsyncMock(return_value=p())
        monkeypatch.setattr(prefect_gitlab.repositories, "run_process", mock)

        sub_dir_name = "puppy"

        with TemporaryDirectory() as tmp_src:
            parent_contents, child_contents = self.setup_test_directory(
                tmp_src, sub_dir_name
            )
            self.MockTmpDir.dir = tmp_src

            # move file contents to tmp_dst
            with TemporaryDirectory() as tmp_dst:
                monkeypatch.setattr(
                    prefect_gitlab.repositories,
                    "TemporaryDirectory",
                    self.MockTmpDir,
                )

                g = GitLabRepository(
                    repository="https://gitlab.com/PrefectHQ/prefect.git",
                )
                await g.get_directory(local_path=tmp_dst)

                assert set(os.listdir(tmp_dst)) == parent_contents
                assert set(os.listdir(Path(tmp_dst) / sub_dir_name)) == child_contents

    async def test_dir_contents_copied_correctly_with_get_directory_and_from_path(
        self, monkeypatch
    ):  # noqa
        """Check that `get_directory` is able to correctly copy contents from src->dst
        when `from_path` is included.
        It is expected that the directory specified by `from_path` will be moved to the
        specified destination, along with all of its contents.
        """

        class p:
            returncode = 0

        mock = AsyncMock(return_value=p())
        monkeypatch.setattr(prefect_gitlab.repositories, "run_process", mock)

        sub_dir_name = "puppy"

        with TemporaryDirectory() as tmp_src:
            parent_contents, child_contents = self.setup_test_directory(
                tmp_src, sub_dir_name
            )
            self.MockTmpDir.dir = tmp_src

            # move file contents to tmp_dst
            with TemporaryDirectory() as tmp_dst:
                monkeypatch.setattr(
                    prefect_gitlab.repositories,
                    "TemporaryDirectory",
                    self.MockTmpDir,
                )

                g = GitLabRepository(
                    repository="https://gitlab.com/PrefectHQ/prefect.git",
                )
                await g.get_directory(local_path=tmp_dst, from_path=sub_dir_name)

                assert set(os.listdir(tmp_dst)) == set([sub_dir_name])
                assert set(os.listdir(Path(tmp_dst) / sub_dir_name)) == child_contents

    async def test_get_directory_retries(self, monkeypatch):
        # Constants for the retry decorator
        MAX_CLONE_ATTEMPTS = 3

        # Create an instance of GitLabRepository
        g = GitLabRepository(repository="https://gitlab.com/prefectHQ/prefect.git")

        # Prepare a MagicMock to simulate the process call within get_directory
        mock = AsyncMock()
        mock.return_value = AsyncMock(returncode=1)  # Simulate failure
        monkeypatch.setattr(prefect_gitlab.repositories, "run_process", mock)

        # Call get_directory and expect it to raise a RetryError after maximum attempts
        with pytest.raises(OSError):
            await g.get_directory()
        print(mock.call_count)
        # Verify that the function retried the expected number of times
        assert mock.call_count == MAX_CLONE_ATTEMPTS
