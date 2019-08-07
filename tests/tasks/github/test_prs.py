from unittest.mock import MagicMock

import pytest

import prefect
from prefect.tasks.github import CreateGitHubPR
from prefect.utilities.configuration import set_temporary_config


class TestCreateGitHubPRInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = CreateGitHubPR()
        assert task.repo is None
        assert task.body is None
        assert task.title is None
        assert task.head is None
        assert task.base is None
        assert task.token_secret == "GITHUB_ACCESS_TOKEN"

    def test_additional_kwargs_passed_upstream(self):
        task = CreateGitHubPR(name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize(
        "attr", ["repo", "body", "title", "head", "base", "token_secret"]
    )
    def test_initializes_attr_from_kwargs(self, attr):
        task = CreateGitHubPR(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    def test_repo_is_required_eventually(self):
        task = CreateGitHubPR()
        with pytest.raises(ValueError, match="repo"):
            task.run()


class TestCredentialsandProjects:
    def test_creds_are_pulled_from_secret_at_runtime(self, monkeypatch):
        task = CreateGitHubPR()

        req = MagicMock()
        monkeypatch.setattr("prefect.tasks.github.prs.requests", req)

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GITHUB_ACCESS_TOKEN={"key": 42})):
                task.run(repo="org/repo")

        assert req.post.call_args[1]["headers"]["AUTHORIZATION"] == "token {'key': 42}"

    def test_creds_secret_can_be_overwritten(self, monkeypatch):
        task = CreateGitHubPR(token_secret="MY_SECRET")

        req = MagicMock()
        monkeypatch.setattr("prefect.tasks.github.prs.requests", req)

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(MY_SECRET={"key": 42})):
                task.run(repo="org/repo")

        assert req.post.call_args[1]["headers"]["AUTHORIZATION"] == "token {'key': 42}"
