from unittest.mock import MagicMock

import pytest

import prefect
from prefect.tasks.github import CreateBranch, GetRepoInfo
from prefect.utilities.configuration import set_temporary_config


class TestGetRepoInfoInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = GetRepoInfo()
        assert task.repo is None
        assert task.info_keys == []
        assert task.token_secret == "GITHUB_ACCESS_TOKEN"

    def test_additional_kwargs_passed_upstream(self):
        task = GetRepoInfo(name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize("attr", ["repo", "info_keys", "token_secret"])
    def test_initializes_attr_from_kwargs(self, attr):
        task = GetRepoInfo(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    def test_repo_is_required_eventually(self):
        task = GetRepoInfo()
        with pytest.raises(ValueError) as exc:
            task.run()
        assert "repo" in str(exc.value)


class TestCreateBranchInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = CreateBranch()
        assert task.repo is None
        assert task.base == "master"
        assert task.branch_name is None
        assert task.token_secret == "GITHUB_ACCESS_TOKEN"

    def test_additional_kwargs_passed_upstream(self):
        task = CreateBranch(name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize("attr", ["repo", "base", "branch_name", "token_secret"])
    def test_initializes_attr_from_kwargs(self, attr):
        task = CreateBranch(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    def test_repo_is_required_eventually(self):
        task = CreateBranch(branch_name="bob")
        with pytest.raises(ValueError) as exc:
            task.run()
        assert "repo" in str(exc.value)

    def test_branch_name_is_required_eventually(self):
        task = CreateBranch(repo="org/bob")
        with pytest.raises(ValueError) as exc:
            task.run()
        assert "branch name" in str(exc.value)


class TestCredentials:
    def test_creds_are_pulled_from_secret_at_runtime_repo_info(self, monkeypatch):
        task = GetRepoInfo()

        req = MagicMock()
        monkeypatch.setattr("prefect.tasks.github.repos.requests", req)

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GITHUB_ACCESS_TOKEN={"key": 42})):
                task.run(repo="org/repo")

        assert req.get.call_args[1]["headers"]["AUTHORIZATION"] == "token {'key': 42}"

    def test_creds_are_pulled_from_secret_at_runtime_create_branch(self, monkeypatch):
        task = CreateBranch()

        req = MagicMock()
        monkeypatch.setattr("prefect.tasks.github.repos.requests", req)

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GITHUB_ACCESS_TOKEN={"key": 42})):
                with pytest.raises(ValueError) as exc:
                    task.run(repo="org/repo", branch_name="new")

        assert req.get.call_args[1]["headers"]["AUTHORIZATION"] == "token {'key': 42}"
        assert "not found" in str(exc.value)

    def test_creds_secret_can_be_overwritten_repo_info(self, monkeypatch):
        task = GetRepoInfo(token_secret="MY_SECRET")

        req = MagicMock()
        monkeypatch.setattr("prefect.tasks.github.repos.requests", req)

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(MY_SECRET={"key": 42})):
                task.run(repo="org/repo")

        assert req.get.call_args[1]["headers"]["AUTHORIZATION"] == "token {'key': 42}"

    def test_creds_secret_can_be_overwritten_create_branch(self, monkeypatch):
        task = CreateBranch(token_secret="MY_SECRET")

        req = MagicMock()
        monkeypatch.setattr("prefect.tasks.github.repos.requests", req)

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(MY_SECRET={"key": 42})):
                with pytest.raises(ValueError):
                    task.run(repo="org/repo", branch_name="new")

        assert req.get.call_args[1]["headers"]["AUTHORIZATION"] == "token {'key': 42}"


def test_base_name_is_filtered_for(monkeypatch):
    task = CreateBranch(base="BOB", branch_name="NEWBRANCH")

    payload = [{"ref": "refs/heads/BOB", "object": {"sha": "salty"}}]
    req = MagicMock(
        get=MagicMock(return_value=MagicMock(json=MagicMock(return_value=payload)))
    )
    monkeypatch.setattr("prefect.tasks.github.repos.requests", req)

    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(GITHUB_ACCESS_TOKEN={"key": 42})):
            task.run(repo="org/repo")

    assert req.post.call_args[1]["json"] == {
        "ref": "refs/heads/NEWBRANCH",
        "sha": "salty",
    }
