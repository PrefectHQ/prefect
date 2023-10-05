from pathlib import Path

import pytest

from prefect.runner.storage import GitRepository, RunnerStorage, create_storage_from_url


class TestCreateStorageFromUrl:
    @pytest.mark.parametrize(
        "url, expected_type",
        [
            ("git://github.com/user/repo.git", "GitRepository"),
            ("https://github.com/user/repo.git", "GitRepository"),
        ],
    )
    def test_create_git_storage(self, url, expected_type):
        storage = create_storage_from_url(url)
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
        storage = create_storage_from_url(url, pull_interval=pull_interval)
        assert isinstance(
            storage, GitRepository
        )  # We already know it's GitRepository from above tests
        assert storage.pull_interval == pull_interval

    @pytest.mark.parametrize(
        "url",
        [
            "http://example.com",
            "ftp://example.com/file.txt",
            "https://github.com/user/repo.png",
        ],
    )
    def test_invalid_storage_url(self, url):
        with pytest.raises(
            ValueError,
            match=f"Unsupported storage URL: {url}. Only git URLs are supported.",
        ):
            create_storage_from_url(url)


class TestGitRepository:
    def test_adheres_to_runner_storage_interface(self):
        assert isinstance(GitRepository, RunnerStorage)

    def test_init_no_credentials(self):
        repo = GitRepository(url="https://github.com/org/repo.git")
        assert repo._username is None
        assert repo._access_token is None

    def test_init_with_username_no_token(self):
        with pytest.raises(
            ValueError,
            match="If a username is provided, an access token must also be provided.",
        ):
            GitRepository(
                url="https://github.com/org/repo.git",
                credentials={"username": "oauth2"},
            )

    def test_init_with_name(self):
        repo = GitRepository(url="https://github.com/org/repo.git", name="custom-name")
        assert repo._name == "custom-name"

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

    async def test_pull_code_clone_repo(self, monkeypatch):
        calls = []

        async def mock_run_process(*args, **kwargs):
            calls.append(args[0])
            return None

        monkeypatch.setattr("prefect.runner.storage.run_process", mock_run_process)
        monkeypatch.setattr("pathlib.Path.exists", lambda x: False)

        repo = GitRepository(
            url="https://github.com/org/repo.git",
            credentials={"username": "oauth2", "access_token": "token"},
        )
        await repo.pull_code()

        assert [
            "git",
            "clone",
            "--branch",
            "main",
            "https://oauth2:token@github.com/org/repo.git",
            str(Path.cwd() / "repo-main"),
        ] in calls

    def test_eq(self):
        repo1 = GitRepository(url="https://github.com/org/repo.git")
        repo2 = GitRepository(url="https://github.com/org/repo.git")
        repo3 = GitRepository(url="https://github.com/org/different-repo.git")
        assert repo1 == repo2
        assert repo1 != repo3

    def test_repr(self):
        repo = GitRepository(url="https://github.com/org/repo.git")
        assert (
            repr(repo)
            == "GitRepository(name='repo-main'"
            " repository='https://github.com/org/repo.git', branch='main')"
        )
