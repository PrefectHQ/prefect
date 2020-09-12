from unittest.mock import MagicMock

import pytest
import requests

import prefect
from prefect.tasks.github import CreateIssueComment
from prefect.utilities.configuration import set_temporary_config


class TestOpenGithubIssueInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = CreateIssueComment()
        assert task.repo is None
        assert task.issue_number is None
        assert task.body is None

    def test_additional_kwargs_passed_upstream(self):
        task = CreateIssueComment(name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize("attr", ["repo", "issue_number", "body"])
    def test_initializes_attr_from_kwargs(self, attr):
        task = CreateIssueComment(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    def test_repo_is_required_eventually(self):
        task = CreateIssueComment()
        with pytest.raises(ValueError, match="repo"):
            task.run()

    def test_issue_number_is_required_eventually(self):
        task = CreateIssueComment(repo="my-value")
        with pytest.raises(ValueError, match="issue number"):
            task.run()
