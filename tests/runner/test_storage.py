import re
import shutil
from pathlib import Path
from textwrap import dedent
from typing import Optional

import pytest
from pydantic import SecretStr

from prefect.blocks.core import Block, BlockNotSavedError
from prefect.blocks.system import Secret
from prefect.deployments.steps.core import run_step
from prefect.filesystems import ReadableDeploymentStorage
from prefect.runner.storage import (
    BlockStorageAdapter,
    GitRepository,
    LocalStorage,
    RemoteStorage,
    RunnerStorage,
    create_storage_from_source,
)
from prefect.testing.utilities import AsyncMock, MagicMock, call
from prefect.utilities.filesystem import tmpchdir


@pytest.fixture(autouse=True)
def tmp_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(str(tmp_path))


class TestCreateStorageFromSource:
    @pytest.mark.parametrize(
        "url, expected_type",
        [
            ("git://github.com/user/repo.git", "GitRepository"),
            ("https://github.com/user/repo.git", "GitRepository"),
        ],
    )
    def test_create_git_storage(self, url, expected_type):
        storage = create_storage_from_source(url)
        assert isinstance(storage, eval(expected_type))
        assert storage.pull_interval == 60  # default value

    @pytest.mark.parametrize(
        "url, pull_interval",
        [
            ("git://github.com/user/repo.git", 120),
            ("http://github.com/user/repo.git", 30),
        ],
    )
    def test_create_git_storage_custom_pull_interval(self, url, pull_interval):
        storage = create_storage_from_source(url, pull_interval=pull_interval)
        assert isinstance(
            storage, GitRepository
        )  # We already know it's GitRepository from above tests
        assert storage.pull_interval == pull_interval

    @pytest.mark.parametrize(
        "url",
        [
            "s3://my-bucket/path/to/folder",
            "ftp://example.com/path/to/folder",
        ],
    )
    def test_alternative_storage_url(self, url):
        storage = create_storage_from_source(url)
        assert isinstance(storage, RemoteStorage)
        assert storage._url == url
        assert storage.pull_interval == 60  # default value

    @pytest.mark.parametrize(
        "path",
        [
            "/path/to/local/flows",
            "C:\\path\\to\\local\\flows",
            "file:///path/to/local/flows",
            "flows",  # Relative Path
        ],
    )
    def test_local_storage_path(self, path):
        storage = create_storage_from_source(path)

        path = path.split("://")[-1]  # split from Scheme when present

        assert isinstance(storage, LocalStorage)
        assert storage._path == Path(path).resolve()
        assert storage.pull_interval == 60  # default value


@pytest.fixture
def mock_run_process(monkeypatch):
    mock_run_process = AsyncMock()
    result_mock = MagicMock()
    result_mock.stdout = "https://github.com/org/repo.git".encode()
    mock_run_process.return_value = result_mock
    monkeypatch.setattr("prefect.runner.storage.run_process", mock_run_process)
    return mock_run_process


class MockCredentials(Block):
    token: Optional[SecretStr] = None
    username: Optional[str] = None
    password: Optional[SecretStr] = None


class TestGitRepository:
    def test_adheres_to_runner_storage_interface(self):
        assert isinstance(GitRepository, RunnerStorage)

    async def test_init_no_credentials(self, mock_run_process: AsyncMock):
        repo = GitRepository(url="https://github.com/org/repo.git")

        await repo.pull_code()
        # should be no change in url
        mock_run_process.assert_awaited_once_with(
            [
                "git",
                "clone",
                "https://github.com/org/repo.git",
                "--depth",
                "1",
                str(Path.cwd() / "repo"),
            ]
        )

    def test_init_commit_sha_and_branch_raises(self):
        with pytest.raises(
            ValueError,
            match="Cannot provide both a branch and a commit SHA. Please provide only one.",
        ):
            GitRepository(
                url="https://github.com/org/repo.git",
                commit_sha="1234567890",
                branch="main",
            )

    def test_init_with_username_no_token(self):
        with pytest.raises(
            ValueError,
            match=(
                "If a username is provided, an access token or password must also be"
                " provided."
            ),
        ):
            GitRepository(
                url="https://github.com/org/repo.git",
                credentials={"username": "oauth2"},
            )

    def test_init_with_name(self):
        repo = GitRepository(url="https://github.com/org/repo.git", name="custom-name")
        assert repo._name == "custom-name"

    def test_init_with_slashed_branch_name(self):
        """Test that branch names with forward slashes are correctly sanitized in the destination path."""
        repo = GitRepository(
            url="https://github.com/org/repo.git", branch="feature/test-branch"
        )
        assert repo._name == "repo-feature-test-branch"

    def test_destination_property(self, monkeypatch):
        monkeypatch.chdir("/tmp")
        repo = GitRepository(url="https://github.com/org/repo.git", name="custom-name")
        repo.set_base_path(Path("/new/path"))
        assert repo.destination == Path("/new/path/custom-name")

    def test_pull_interval_property(self):
        repo = GitRepository(url="https://github.com/org/repo.git")
        assert repo.pull_interval == 60

    async def test_pull_code_existing_repo_different_url(self, monkeypatch):
        async def mock_run_process(*args, **kwargs):
            class Result:
                stdout = "https://github.com/org/different-repo.git".encode()

            return Result()

        monkeypatch.setattr("prefect.runner.storage.run_process", mock_run_process)
        monkeypatch.setattr("pathlib.Path.exists", lambda x: ".git" in str(x))

        repo = GitRepository(url="https://github.com/org/repo.git")
        with pytest.raises(
            ValueError,
            match=(
                "The existing repository at .* does not match the configured repository"
            ),
        ):
            await repo.pull_code()

    async def test_pull_code_clone_repo(self, mock_run_process: AsyncMock, monkeypatch):
        monkeypatch.setattr("pathlib.Path.exists", lambda x: False)

        repo = GitRepository(
            url="https://github.com/org/repo.git",
            credentials={"username": "oauth2", "access_token": "token"},
        )
        await repo.pull_code()

        mock_run_process.assert_awaited_once_with(
            [
                "git",
                "clone",
                "https://oauth2:token@github.com/org/repo.git",
                "--depth",
                "1",
                str(Path.cwd() / "repo"),
            ]
        )

    async def test_clone_repo_sparse(self, mock_run_process: AsyncMock, monkeypatch):
        """
        Check if cloned repo can achieve sparse checkout with an access token
        """
        monkeypatch.setattr("pathlib.Path.exists", lambda x: False)

        repo = GitRepository(
            url="https://github.com/org/repo.git",
            credentials={"username": "oauth2", "access_token": "token"},
            directories=["dir_1", "dir_2"],
        )
        await repo.pull_code()

        expected_calls = [
            call(
                [
                    "git",
                    "clone",
                    "https://oauth2:token@github.com/org/repo.git",
                    "--sparse",
                    "--depth",
                    "1",
                    str(Path.cwd() / "repo"),
                ]
            ),
            call(
                ["git", "sparse-checkout", "set", "dir_1", "dir_2"],
                cwd=Path.cwd() / "repo",
            ),
        ]

        mock_run_process.assert_has_awaits(expected_calls)
        assert mock_run_process.await_args_list == expected_calls, (
            f"Unexpected calls: {mock_run_process.await_args_list}"
        )

    async def test_clone_existing_repo_sparse(
        self, mock_run_process: AsyncMock, monkeypatch
    ):
        # pretend the repo already exists
        monkeypatch.setattr("pathlib.Path.exists", lambda x: ".git" in str(x))

        repo = GitRepository(
            url="https://github.com/org/repo.git",
            credentials={"username": "oauth2", "access_token": "token"},
            directories=["dir_1", "dir_2"],
        )

        await repo.pull_code()

        expected_calls = [
            call(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=str(Path.cwd() / "repo"),
            ),
            call(
                ["git", "config", "--get", "core.sparseCheckout"],
                cwd=Path.cwd() / "repo",
            ),
            call(
                ["git", "sparse-checkout", "set", "dir_1", "dir_2"],
                cwd=Path.cwd() / "repo",
            ),
            call(["git", "pull", "origin", "--depth", "1"], cwd=Path.cwd() / "repo"),
        ]

        mock_run_process.assert_has_awaits(expected_calls)
        assert mock_run_process.await_args_list == expected_calls, (
            f"Unexpected calls: {mock_run_process.await_args_list}"
        )

    async def test_pull_code_with_username_and_password(
        self,
        monkeypatch,
        mock_run_process: AsyncMock,
    ):
        """
        We need to handle username+password combo for backwards compatibility with
        previous `git_clone` pull step implementation.

        Regression test for https://github.com/PrefectHQ/prefect/issues/11051
        """
        monkeypatch.setattr("pathlib.Path.exists", lambda x: False)

        repo = GitRepository(
            url="https://github.com/org/repo.git",
            credentials={"username": "username", "password": "password"},
        )
        await repo.pull_code()

        mock_run_process.assert_awaited_once_with(
            [
                "git",
                "clone",
                "https://username:password@github.com/org/repo.git",
                "--depth",
                "1",
                str(Path.cwd() / "repo"),
            ]
        )

    def test_eq(self):
        repo1 = GitRepository(url="https://github.com/org/repo.git")
        repo2 = GitRepository(url="https://github.com/org/repo.git")
        repo3 = GitRepository(url="https://github.com/org/different-repo.git")
        assert repo1 == repo2
        assert repo1 != repo3

    def test_repr(self):
        repo = GitRepository(url="https://github.com/org/repo.git")
        assert (
            repr(repo) == "GitRepository(name='repo'"
            " repository='https://github.com/org/repo.git', branch=None)"
        )

    async def test_include_submodules_property(
        self, mock_run_process: AsyncMock, monkeypatch
    ):
        repo = GitRepository(
            url="https://github.com/org/repo.git", include_submodules=True
        )
        await repo.pull_code()
        mock_run_process.assert_awaited_with(
            [
                "git",
                "clone",
                "https://github.com/org/repo.git",
                "--recurse-submodules",
                "--depth",
                "1",
                str(Path.cwd() / "repo"),
            ]
        )

        # pretend the repo already exists
        monkeypatch.setattr("pathlib.Path.exists", lambda x: ".git" in str(x))

        await repo.pull_code()
        mock_run_process.assert_awaited_with(
            [
                "git",
                "pull",
                "origin",
                "--recurse-submodules",
                "--depth",
                "1",
            ],
            cwd=Path.cwd() / "repo",
        )

    async def test_include_submodules_with_credentials(
        self, mock_run_process: AsyncMock, monkeypatch
    ):
        access_token = Secret(value="token")
        await access_token.save("test-token")

        repo = GitRepository(
            url="https://github.com/org/repo.git",
            include_submodules=True,
            credentials={"access_token": access_token},
        )
        await repo.pull_code()
        mock_run_process.assert_awaited_with(
            [
                "git",
                "-c",
                "url.https://token@github.com.insteadOf=https://github.com",
                "clone",
                "https://token@github.com/org/repo.git",
                "--recurse-submodules",
                "--depth",
                "1",
                str(Path.cwd() / "repo"),
            ]
        )

    async def test_pull_code_with_commit_sha(
        self, mock_run_process: AsyncMock, monkeypatch
    ):
        # pretend the repo already exists
        monkeypatch.setattr("pathlib.Path.exists", lambda x: ".git" in str(x))
        # Mock is_current_commit to return False to trigger fetch
        monkeypatch.setattr(
            GitRepository, "is_current_commit", AsyncMock(return_value=False)
        )
        # Mock is_shallow_clone to return True to test unshallow behavior
        monkeypatch.setattr(
            GitRepository, "is_shallow_clone", AsyncMock(return_value=True)
        )

        repo = GitRepository(
            url="https://github.com/org/repo.git", commit_sha="1234567890"
        )

        await repo.pull_code()

        # Verify the expected git commands were called in order
        expected_calls = [
            call(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=str(Path.cwd() / "repo"),
            ),
            call(
                ["git", "fetch", "origin", "--unshallow"],
                cwd=Path.cwd() / "repo",
            ),
            call(
                ["git", "checkout", "1234567890"],
                cwd=Path.cwd() / "repo",
            ),
        ]

        mock_run_process.assert_has_awaits(expected_calls)
        assert mock_run_process.await_args_list == expected_calls

    async def test_is_current_commit_no_sha_raises(self, mock_run_process: AsyncMock):
        repo = GitRepository(url="https://github.com/org/repo.git")
        with pytest.raises(ValueError, match="No commit SHA provided"):
            await repo.is_current_commit()

    async def test_pull_code_with_commit_sha_when_current_commit(
        self, mock_run_process: AsyncMock, monkeypatch
    ):
        # pretend the repo already exists
        monkeypatch.setattr("pathlib.Path.exists", lambda x: ".git" in str(x))
        # Mock is_current_commit to return True to skip fetch/checkout
        monkeypatch.setattr(
            GitRepository, "is_current_commit", AsyncMock(return_value=True)
        )
        # Mock is_shallow_clone to return False (not relevant for this test)
        monkeypatch.setattr(
            GitRepository, "is_shallow_clone", AsyncMock(return_value=False)
        )

        repo = GitRepository(
            url="https://github.com/org/repo.git", commit_sha="1234567890"
        )

        await repo.pull_code()

        # Should only check the remote URL since the commit is already checked out
        expected_calls = [
            call(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=str(Path.cwd() / "repo"),
            ),
        ]

        mock_run_process.assert_has_awaits(expected_calls)
        assert mock_run_process.await_args_list == expected_calls

    async def test_git_clone_errors_obscure_access_token(
        self, monkeypatch, capsys, tmp_path: Path
    ):
        monkeypatch.setattr("pathlib.Path.exists", lambda x: False)

        with tmpchdir(str(tmp_path)):
            with pytest.raises(RuntimeError) as exc:
                # we uppercase the token because this test definition does show up in the exception traceback
                await GitRepository(
                    url="https://github.com/prefecthq/prefect.git",
                    branch="definitely-does-not-exist-123",
                    credentials={"access_token": "super-secret-42".upper()},
                ).pull_code()
            assert "super-secret-42".upper() not in str(exc.getrepr())
            console_output = capsys.readouterr()
            assert "super-secret-42".upper() not in console_output.out
            assert "super-secret-42".upper() not in console_output.err

    async def test_git_clone_errors_obscure_basic_auth(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ):
        monkeypatch.setattr("pathlib.Path.exists", lambda x: False)

        with tmpchdir(str(tmp_path)):
            with pytest.raises(RuntimeError) as exc:
                # we uppercase the auth because this test definition does show up in the exception traceback
                basic_auth_creds = "user:password".upper()
                await GitRepository(
                    url=f"https://{basic_auth_creds}@github.com/prefecthq/prefect.git",
                    branch="definitely-does-not-exist-123",
                ).pull_code()
            assert "user:password".upper() not in str(exc.getrepr()), exc.getrepr()
            console_output = capsys.readouterr()
            assert "user:password".upper() not in console_output.out
            assert "user:password".upper() not in console_output.err

    class TestCredentialFormatting:
        async def test_credential_formatting_maintains_secrets(
            self, mock_run_process: AsyncMock
        ):
            """Regression test for https://github.com/PrefectHQ/prefect/issues/11135"""
            access_token = Secret(value="testtoken")
            await access_token.save("test-token")

            repo = GitRepository(
                url="https://github.com/org/repo.git",
                credentials={"access_token": access_token},
            )

            await repo.pull_code()

            assert repo._credentials == {"access_token": access_token}

        async def test_git_clone_with_credentials_block(
            self, mock_run_process: AsyncMock
        ):
            repo = GitRepository(
                url="https://github.com/org/repo.git",
                credentials=MockCredentials(token="mock-token"),
            )

            await repo.pull_code()

            mock_run_process.assert_awaited_once_with(
                [
                    "git",
                    "clone",
                    "https://mock-token@github.com/org/repo.git",
                    "--depth",
                    "1",
                    str(Path.cwd() / "repo"),
                ]
            )

        @pytest.mark.parametrize(
            "credentials",
            [
                None,
                {"access_token": "example-token"},
                {"access_token": "x-token-auth:example-token"},
                {"username": "x-token-auth", "access_token": "example-token"},
                MockCredentials(token="example-token"),
                MockCredentials(token="x-token-auth:example-token"),
                MockCredentials(username="x-token-auth", token="example-token"),
            ],
        )
        async def test_git_clone_with_bitbucket_access_token(
            self, credentials, mock_run_process
        ):
            repo = GitRepository(
                url="https://bitbucket.org/org/repo.git",
                credentials=credentials,
            )

            await repo.pull_code()

            expected_url = (
                "https://x-token-auth:example-token@bitbucket.org/org/repo.git"
                if credentials
                else "https://bitbucket.org/org/repo.git"
            )

            mock_run_process.assert_awaited_once_with(
                [
                    "git",
                    "clone",
                    expected_url,
                    "--depth",
                    "1",
                    str(Path.cwd() / "repo"),
                ],
            )

        @pytest.mark.parametrize(
            "credentials",
            [
                {"access_token": "x-token-auth:example-token"},
                {"username": "x-token-auth", "access_token": "example-token"},
                MockCredentials(token="x-token-auth:example-token"),
                MockCredentials(username="x-token-auth", token="example-token"),
            ],
        )
        async def test_git_clone_with_bitbucket_server_repo_with_access_token(
            self, credentials, mock_run_process
        ):
            repo = GitRepository(
                url="https://bitbucketserver.com/scm/projectname/teamsinspace.git",
                credentials=credentials,
            )

            await repo.pull_code()

            mock_run_process.assert_awaited_once_with(
                [
                    "git",
                    "clone",
                    "https://x-token-auth:example-token@bitbucketserver.com/scm/projectname/teamsinspace.git",
                    "--depth",
                    "1",
                    str(Path.cwd() / "teamsinspace"),
                ],
            )

        async def test_git_clone_with_bitbucket_server_repo_with_invalid_access_token_raises(
            self,
        ):
            repo = GitRepository(
                url="https://bitbucketserver.com/scm/projectname/teamsinspace.git",
                credentials={"access_token": "example-token"},
            )

            with pytest.raises(
                ValueError,
                match=(
                    "Please provide a `username` and a `password` or `token` in your"
                    " BitBucketCredentials block to clone a repo from BitBucket Server."
                ),
            ):
                await repo.pull_code()

        @pytest.mark.parametrize(
            "credentials",
            [
                None,
                {"access_token": "example-token"},
                {"access_token": "oauth2:example-token"},
                {"username": "oauth2", "access_token": "example-token"},
                MockCredentials(token="example-token"),
                MockCredentials(token="oauth2:example-token"),
                MockCredentials(username="oauth2", token="example-token"),
            ],
        )
        async def test_git_clone_with_gitlab_access_token(
            self, credentials, mock_run_process
        ):
            repo = GitRepository(
                url="https://gitlab.com/org/repo.git",
                credentials=credentials,
            )

            await repo.pull_code()

            expected_url = (
                "https://oauth2:example-token@gitlab.com/org/repo.git"
                if credentials
                else "https://gitlab.com/org/repo.git"
            )

            mock_run_process.assert_awaited_once_with(
                [
                    "git",
                    "clone",
                    expected_url,
                    "--depth",
                    "1",
                    str(Path.cwd() / "repo"),
                ],
            )

    class TestToPullStep:
        async def test_to_pull_step_with_block_credentials(self):
            credentials = MockCredentials(username="testuser", access_token="testtoken")
            await credentials.save("test-credentials")

            repo = GitRepository(
                url="https://github.com/org/repo.git", credentials=credentials
            )
            expected_output = {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://github.com/org/repo.git",
                    "branch": None,
                    "credentials": (
                        "{{ prefect.blocks.mockcredentials.test-credentials }}"
                    ),
                }
            }

            result = repo.to_pull_step()
            assert result == expected_output

        def test_to_pull_step_with_submodules(self):
            repo = GitRepository(
                url="https://github.com/org/repo.git", include_submodules=True
            )
            expected_output = {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://github.com/org/repo.git",
                    "branch": None,
                    "include_submodules": True,
                }
            }

            result = repo.to_pull_step()
            assert result == expected_output

        def test_to_pull_step_with_commit_sha(self):
            repo = GitRepository(
                url="https://github.com/org/repo.git", commit_sha="1234567890"
            )
            expected_output = {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://github.com/org/repo.git",
                    "branch": None,
                    "commit_sha": "1234567890",
                }
            }

            result = repo.to_pull_step()
            assert result == expected_output

        def test_to_pull_step_with_unsaved_block_credentials(self):
            credentials = MockCredentials(username="testuser", access_token="testtoken")

            repo = GitRepository(
                url="https://github.com/org/repo.git", credentials=credentials
            )

            with pytest.raises(
                BlockNotSavedError,
                match="Could not generate block placeholder for unsaved block.",
            ):
                repo.to_pull_step()

        async def test_to_pull_step_with_secret_access_token(self):
            access_token = Secret(value="testtoken")
            await access_token.save("test-access-token")

            repo = GitRepository(
                url="https://github.com/org/repo.git",
                credentials={"username": "testuser", "access_token": access_token},
            )

            expected_output = {
                "prefect.deployments.steps.git_clone": {
                    "repository": "https://github.com/org/repo.git",
                    "branch": None,
                    "credentials": {
                        "username": "testuser",
                        "access_token": "{{ prefect.blocks.secret.test-access-token }}",
                    },
                }
            }

            result = repo.to_pull_step()
            assert result == expected_output

        def test_to_pull_step_with_unsaved_secret_access_token(self):
            access_token = Secret(value="testtoken")

            repo = GitRepository(
                url="https://github.com/org/repo.git",
                credentials={"username": "testuser", "access_token": access_token},
            )

            with pytest.raises(
                BlockNotSavedError,
                match="Could not generate block placeholder for unsaved block.",
            ):
                repo.to_pull_step()

        def test_to_pull_step_with_plaintext(self):
            repo = GitRepository(
                url="https://github.com/org/repo.git",
                credentials={"username": "testuser", "access_token": "testpassword"},
            )

            with pytest.raises(
                ValueError,
                match=(
                    "Please save your access token as a Secret block before converting"
                    " this storage object to a pull step."
                ),
            ):
                repo.to_pull_step()

    async def test_clone_repo_with_commit_sha(
        self, mock_run_process: AsyncMock, monkeypatch
    ):
        # pretend the repo doesn't exist
        monkeypatch.setattr("pathlib.Path.exists", lambda x: False)

        repo = GitRepository(
            url="https://github.com/org/repo.git", commit_sha="1234567890"
        )

        await repo.pull_code()

        # Verify the expected git commands were called in order
        expected_calls = [
            call(
                [
                    "git",
                    "clone",
                    "https://github.com/org/repo.git",
                    "--filter=blob:none",
                    "--no-checkout",
                    str(Path.cwd() / "repo"),
                ]
            ),
            call(
                ["git", "fetch", "origin", "1234567890"],
                cwd=Path.cwd() / "repo",
            ),
            call(
                ["git", "checkout", "1234567890"],
                cwd=Path.cwd() / "repo",
            ),
        ]

        mock_run_process.assert_has_awaits(expected_calls)
        assert mock_run_process.await_args_list == expected_calls


class TestRemoteStorage:
    def test_init(self):
        rs = RemoteStorage("s3://bucket/path")
        assert rs._url == "s3://bucket/path"
        assert rs.pull_interval == 60

    def test_get_required_package_for_scheme(self):
        assert RemoteStorage._get_required_package_for_scheme("s3") == "s3fs"
        assert RemoteStorage._get_required_package_for_scheme("gs") == "gcsfs"
        assert RemoteStorage._get_required_package_for_scheme("unknown") is None

    def test_filesystem(self, monkeypatch):
        mock_filesystem = MagicMock()
        monkeypatch.setattr("fsspec.filesystem", mock_filesystem)

        key = Secret(value="fake")
        secret = Secret(value="fake")
        token = Secret(value="fake")

        rs = RemoteStorage("s3://bucket/path", key=key, secret=secret, token=token)
        rs._filesystem
        mock_filesystem.assert_called_once_with(
            "s3", key="fake", secret="fake", token="fake"
        )

    def test_set_base_path(self):
        rs = RemoteStorage("s3://bucket/path")
        path = Path.cwd() / "new_base_path"
        rs.set_base_path(path)
        assert rs._storage_base_path == path

    def test_destination(self):
        rs = RemoteStorage("s3://bucket/path")
        assert rs.destination == Path.cwd() / Path("bucket") / Path("path")

    async def test_pull_code(self, monkeypatch):
        rs = RemoteStorage("memory://path/to/directory/")

        mock_mkdir = MagicMock()
        monkeypatch.setattr("pathlib.Path.mkdir", mock_mkdir)

        mock_get = MagicMock()
        monkeypatch.setattr(rs._filesystem, "get", mock_get)

        await rs.pull_code()
        mock_mkdir.assert_called_once()
        mock_get.assert_called_once_with(
            "path/to/directory/", str(rs.destination), recursive=True
        )

    async def test_pull_code_fails(self, monkeypatch):
        rs = RemoteStorage("memory://path/to/directory/")

        mock_mkdir = MagicMock()
        monkeypatch.setattr("pathlib.Path.mkdir", mock_mkdir)

        mock_get = MagicMock()
        mock_get.side_effect = Exception("oops")
        monkeypatch.setattr(rs._filesystem, "get", mock_get)

        with pytest.raises(
            RuntimeError,
            match=(
                "Failed to pull contents from remote storage"
                " 'memory://path/to/directory/'"
            ),
        ):
            await rs.pull_code()
        mock_mkdir.assert_called_once()
        mock_get.assert_called_once_with(
            "path/to/directory/", str(rs.destination), recursive=True
        )

    async def test_to_pull_step(self, monkeypatch):
        # saving blocks for this test
        key = Secret(value="fake")
        await key.save(name="aws-access-key-id")
        secret = Secret(value="fake")
        await secret.save(name="aws-secret-access-key")
        token = Secret(value="fake")
        await token.save(name="aws-session-token")

        rs = RemoteStorage(url="s3://bucket/path", key=key, secret=secret, token=token)

        pull_step = rs.to_pull_step()
        assert pull_step == {
            "prefect.deployments.steps.pull_from_remote_storage": {
                "requires": "s3fs",
                "url": "s3://bucket/path",
                "key": "{{ prefect.blocks.secret.aws-access-key-id }}",
                "secret": "{{ prefect.blocks.secret.aws-secret-access-key }}",
                "token": "{{ prefect.blocks.secret.aws-session-token }}",
            }
        }

    def test_to_pull_step_with_unsaved_block_secret(self):
        key = Secret(value="fake")
        secret = Secret(value="fake")

        rs = RemoteStorage(url="s3://bucket/path", key=key, secret=secret)

        with pytest.raises(
            BlockNotSavedError,
            match="Could not generate block placeholder for unsaved block.",
        ):
            rs.to_pull_step()

    def test_eq(self):
        rs1 = RemoteStorage("s3://bucket/path")
        rs2 = RemoteStorage("s3://bucket/path")
        rs3 = RemoteStorage("gs://bucket/path")

        assert rs1 == rs2
        assert rs1 != rs3

    def test_repr(self):
        rs = RemoteStorage("s3://bucket/path")
        assert repr(rs) == "RemoteStorage(url='s3://bucket/path')"


class TestLocalStorage:
    def test_init(self):
        ls = LocalStorage("/path/to/directory", pull_interval=60)
        assert ls._path == Path("/path/to/directory")
        assert ls.pull_interval == 60

    def test_set_base_path(self):
        locals = LocalStorage("/path/to/directory")
        path = Path.cwd() / "new_base_path"
        locals.set_base_path(path)
        assert locals._storage_base_path == path

    def test_destination(self):
        locals = LocalStorage("/path/to/directory")
        assert locals.destination == Path("/path/to/directory")

    def test_to_pull_step(self):
        locals = LocalStorage("/path/to/directory")
        pull_step = locals.to_pull_step()
        assert pull_step == {
            "prefect.deployments.steps.set_working_directory": {
                "directory": "/path/to/directory"
            }
        }

    def test_eq(self):
        local1 = LocalStorage(path="/path/to/local/flows")
        local2 = LocalStorage(path="/path/to/local/flows")
        local3 = LocalStorage(path="C:\\path\\to\\local\\flows")
        assert local1 == local2
        assert local1 != local3

    def test_repr(self):
        local = LocalStorage(path="/path/to/local/flows")
        assert repr(local) == "LocalStorage(path=PosixPath('/path/to/local/flows'))"


class TestBlockStorageAdapter:
    @pytest.fixture
    async def test_block(self):
        class FakeStorageBlock(Block):
            _block_type_slug = "fake-storage-block"

            code: str = dedent(
                """\
                from prefect import flow

                @flow
                def test_flow():
                    return 1
                """
            )

            async def get_directory(self, local_path: str):
                (Path(local_path) / "flows.py").write_text(self.code)

        return FakeStorageBlock()

    async def test_init_with_not_a_block(self):
        class NotABlock:
            looks_around = "nervously"

        with pytest.raises(
            TypeError, match="Expected a block object. Received a 'NotABlock' object."
        ):
            BlockStorageAdapter(block=NotABlock())

    async def test_init_with_wrong_type_of_block(self):
        class NotAStorageBlock(Block):
            _block_type_slug = "not-a-storage-block"

        with pytest.raises(
            ValueError,
            match="Provided block must have a `get_directory` method.",
        ):
            BlockStorageAdapter(block=NotAStorageBlock())

    async def test_pull_code(self, test_block: Block):
        storage = BlockStorageAdapter(block=test_block)
        try:
            await storage.pull_code()
            assert (storage.destination / "flows.py").read_text() == test_block.code
        finally:
            if storage.destination.exists():
                shutil.rmtree(storage.destination)

    async def test_to_pull_step(self, test_block: Block):
        await test_block.save("test-block")
        storage = BlockStorageAdapter(block=test_block)
        pull_step = storage.to_pull_step()
        assert pull_step == {
            "prefect.deployments.steps.pull_with_block": {
                "block_document_name": "test-block",
                "block_type_slug": "fake-storage-block",
            }
        }
        try:
            # test pull step runs
            output = await run_step(pull_step)

            assert (
                Path(output["directory"]) / "flows.py"
            ).read_text() == test_block.code
        finally:
            if "output" in locals() and "directory" in output:
                shutil.rmtree(f"{output['directory']}")

    async def test_to_pull_step_with_unsaved_block(self, test_block: Block):
        storage = BlockStorageAdapter(block=test_block)
        with pytest.raises(
            BlockNotSavedError,
            match=re.escape(
                "Block must be saved with `.save()` before it can be converted to a"
                " pull step."
            ),
        ):
            storage.to_pull_step()

    async def test_set_base_path(self, test_block: Block):
        storage = BlockStorageAdapter(block=test_block)
        new_path = Path("/new/path")
        storage.set_base_path(new_path)
        assert storage._storage_base_path == new_path

    def test_pull_interval_property(self, test_block: Block):
        storage = BlockStorageAdapter(block=test_block, pull_interval=120)
        assert storage.pull_interval == 120

    async def test_destination_property(self, test_block: Block):
        storage = BlockStorageAdapter(block=test_block)
        assert storage.destination == Path.cwd() / storage._name

    async def test_pull_code_existing_destination(self, test_block: Block):
        try:
            storage = BlockStorageAdapter(block=test_block)
            storage.destination.mkdir(
                parents=True, exist_ok=True
            )  # Ensure the destination exists
            await storage.pull_code()
            assert (storage.destination / "flows.py").read_text() == test_block.code
        finally:
            if storage.destination.exists():
                shutil.rmtree(storage.destination)

    async def test_eq_method_same_block(self, test_block: Block):
        storage1 = BlockStorageAdapter(block=test_block)
        storage2 = BlockStorageAdapter(block=test_block)
        assert storage1 == storage2

    async def test_eq_method_different_block(self, test_block: Block):
        class FakeDeploymentStorage(ReadableDeploymentStorage):
            def get_directory(self, *args, **kwargs):
                pass

        storage1 = BlockStorageAdapter(block=test_block)
        storage2 = BlockStorageAdapter(block=FakeDeploymentStorage())
        assert storage1 != storage2

    async def test_eq_method_different_type(self, test_block: Block):
        storage = BlockStorageAdapter(block=test_block)
        assert storage != "NotABlockStorageAdapter"
