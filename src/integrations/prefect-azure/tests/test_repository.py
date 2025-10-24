import urllib.parse
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from prefect_azure.credentials import AzureDevopsCredentials
from prefect_azure.repository import AzureDevopsRepository
from pydantic import SecretStr

from prefect.testing.utilities import AsyncMock


class TestAzureDevopsRepository:
    def test_https_repo_without_credentials(self):
        repo_url = "https://example.com/org/project/_git/repo"
        repo = AzureDevopsRepository(repository=repo_url)
        assert repo._create_repo_url() == repo_url

    def test_https_repo_with_token_credentials(self):
        repo_url = "https://example.com/org/project/_git/repo"
        token = "test-token"
        credentials = AzureDevopsCredentials(token=SecretStr(token))
        repo = AzureDevopsRepository(repository=repo_url, credentials=credentials)
        full_url = repo._create_repo_url()

        parsed = urllib.parse.urlparse(full_url)
        assert parsed.scheme == "https"
        assert parsed.hostname == "example.com"
        assert parsed.password == token
        assert parsed.username == ""

    def test_https_repo_with_username_and_token(self):
        repo_url = "https://fake@example.com/org/project/_git/repo"
        token = "test-token"
        credentials = AzureDevopsCredentials(token=SecretStr(token))

        repo = AzureDevopsRepository(repository=repo_url, credentials=credentials)
        full_url = repo._create_repo_url()

        parsed = urllib.parse.urlparse(full_url)
        assert parsed.scheme == "https"
        assert parsed.hostname == "example.com"
        assert parsed.username == "fake"
        assert parsed.password == token

    def test_token_url_encoding(self):
        token = "my:we!rd@tok#en"
        encoded_token = urllib.parse.quote(token, safe="")

        repo_url = "https://fake@example.com/org/project/_git/repo"
        credentials = AzureDevopsCredentials(token=SecretStr(token))
        repo = AzureDevopsRepository(repository=repo_url, credentials=credentials)

        full_url = repo._create_repo_url()
        parsed = urllib.parse.urlparse(full_url)

        assert parsed.password == encoded_token
        assert encoded_token in full_url  # Allow this since it's encoded check

    def test_ssh_url_raises_value_error(self):
        ssh_url = "git@example.com:org/project/_git/repo"
        with pytest.raises(ValueError, match="SSH URLs are not supported"):
            AzureDevopsRepository(repository=ssh_url)._create_repo_url()

    async def test_get_directory_executes_clone(self, monkeypatch):
        mock_process = AsyncMock()
        mock_process.return_value.returncode = 0
        monkeypatch.setattr("prefect_azure.repository.run_process", mock_process)

        repo = AzureDevopsRepository(repository="https://example.com/repo.git")
        await repo.get_directory()

        assert mock_process.await_count == 1
        assert "git" in mock_process.await_args[0][0]

    async def test_get_directory_raises_on_failed_clone(self, monkeypatch):
        class FakeProcess:
            returncode = 1

        async def fail_process(*args, **kwargs):
            return FakeProcess()

        monkeypatch.setattr("prefect_azure.repository.run_process", fail_process)

        repo = AzureDevopsRepository(repository="https://example.com/repo.git")

        with pytest.raises(RuntimeError, match="Failed to pull from remote"):
            await repo.get_directory()

    async def test_get_directory_retries_on_failure(self, monkeypatch):
        call_counter = {"count": 0}

        class FakeProcess:
            returncode = 1

        async def fail_process(*args, **kwargs):
            call_counter["count"] += 1
            return FakeProcess()

        monkeypatch.setattr("prefect_azure.repository.run_process", fail_process)

        repo = AzureDevopsRepository(repository="https://example.com/repo.git")

        with pytest.raises(RuntimeError):
            await repo.get_directory()

        assert call_counter["count"] == 3  # MAX_CLONE_ATTEMPTS

    async def test_directory_contents_are_copied(self, monkeypatch):
        class FakeProcess:
            returncode = 0

        monkeypatch.setattr(
            "prefect_azure.repository.run_process",
            AsyncMock(return_value=FakeProcess()),
        )

        repo = AzureDevopsRepository(repository="https://example.com/repo.git")

        with TemporaryDirectory() as tmp_src:
            test_file = Path(tmp_src) / "file.txt"
            test_file.write_text("hello world")

            with TemporaryDirectory() as tmp_dst:

                class MockTmpDir:
                    def __init__(self, *args, **kwargs):
                        pass

                    def __enter__(self):
                        return tmp_src

                    def __exit__(self, *args):
                        pass

                monkeypatch.setattr(
                    "prefect_azure.repository.TemporaryDirectory",
                    lambda *a, **kw: MockTmpDir(),
                )

                await repo.get_directory(local_path=tmp_dst)

                assert (Path(tmp_dst) / "file.txt").exists()

    def test_get_directory_sync(self, monkeypatch):
        """Test that get_directory works in sync context"""
        mock_process = AsyncMock()
        mock_process.return_value.returncode = 0
        monkeypatch.setattr("prefect_azure.repository.run_process", mock_process)

        repo = AzureDevopsRepository(repository="https://example.com/repo.git")

        with TemporaryDirectory() as tmp_src:
            test_file = Path(tmp_src) / "file.txt"
            test_file.write_text("sync test")

            with TemporaryDirectory() as tmp_dst:

                class MockTmpDir:
                    def __init__(self, *args, **kwargs):
                        pass

                    def __enter__(self):
                        return tmp_src

                    def __exit__(self, *args):
                        pass

                monkeypatch.setattr(
                    "prefect_azure.repository.TemporaryDirectory",
                    lambda *a, **kw: MockTmpDir(),
                )

                # Call without await - should use sync implementation via run_coro_as_sync
                repo.get_directory(local_path=tmp_dst)

                assert mock_process.await_count == 1
                assert "git" in mock_process.await_args[0][0]
                assert (Path(tmp_dst) / "file.txt").exists()

    async def test_get_directory_force_sync_from_async(self, monkeypatch):
        """Test that _sync=True forces sync execution from async context"""
        mock_process = AsyncMock()
        mock_process.return_value.returncode = 0
        monkeypatch.setattr("prefect_azure.repository.run_process", mock_process)

        repo = AzureDevopsRepository(repository="https://example.com/repo.git")

        with TemporaryDirectory() as tmp_src:
            test_file = Path(tmp_src) / "file.txt"
            test_file.write_text("force sync")

            with TemporaryDirectory() as tmp_dst:

                class MockTmpDir:
                    def __init__(self, *args, **kwargs):
                        pass

                    def __enter__(self):
                        return tmp_src

                    def __exit__(self, *args):
                        pass

                monkeypatch.setattr(
                    "prefect_azure.repository.TemporaryDirectory",
                    lambda *a, **kw: MockTmpDir(),
                )

                # Force sync execution with _sync=True
                repo.get_directory(local_path=tmp_dst, _sync=True)

                # run_process should be called once (via run_coro_as_sync)
                assert mock_process.await_count == 1
                assert (Path(tmp_dst) / "file.txt").exists()
